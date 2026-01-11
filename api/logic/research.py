import asyncio
import logging
import os, re
from typing import List, Dict, Any
from bson import ObjectId
from models.db import db
from services import llm, search, extract, live
from services.academic import deep_academic_search, score_source_quality
from services.pdf_processor import process_academic_pdf
from services.vision import analyze_source_visuals
from services.agents import generate_diagram, extract_chart_data, should_generate_visuals
from services.messages import emit_msg
from services.text_processing import clean_report_text, correct_query
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def _domain(u: str) -> str:
    try:
        return urlparse(u).hostname or ""
    except Exception:
        return ""

def _short(s: str, n: int = 64) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"

def _parse_quality_score(quality):
    """Parse quality score from various formats (string or numeric) to float."""
    if isinstance(quality, (int, float)):
        return float(quality)
    
    if isinstance(quality, str):
        quality_lower = quality.lower()
        if quality_lower in ['high', 'excellent', 'great']:
            return 0.9
        elif quality_lower in ['medium', 'good', 'average']:
            return 0.7
        elif quality_lower in ['low', 'poor', 'bad']:
            return 0.3
        else:
            try:
                return float(quality)
            except ValueError:
                logger.warning(f"Could not parse quality score: {quality}, using default 0.5")
                return 0.5
    
    logger.warning(f"Unknown quality score type: {type(quality)}, using default 0.5")
    return 0.5

def _filter_results_by_topic(results: List[dict], topic_terms: dict, topic: str) -> List[dict]:
    """FIXED: More flexible filtering that handles word variants"""
    if not topic_terms or not results:
        return results
    
    core_terms = topic_terms.get("core_terms", [])
    alternative_terms = topic_terms.get("alternative_terms", [])
    exclusion_hints = topic_terms.get("exclusion_hints", [])
    
    # CRITICAL FIX: Break multi-word terms into individual words
    all_relevant_words = set()
    for term in (core_terms + alternative_terms):
        # Split phrases and add individual significant words (length > 3)
        words = [w.lower() for w in term.split() if len(w) > 3]
        all_relevant_words.update(words)
    
    # Also add the topic words themselves
    topic_words = [w.lower() for w in topic.split() if len(w) > 3]
    all_relevant_words.update(topic_words)
    
    if not all_relevant_words:
        return results
    
    filtered_results = []
    
    for result in results:
        title = result.get("title", "").lower()
        abstract = result.get("abstract", "").lower()
        combined_text = title + " " + abstract
        
        # Check for word stems (artery/arterial/arteries all match "arteri")
        matches = 0
        for word in all_relevant_words:
            # Use first 5-6 chars as stem to catch variants
            stem = word[:6] if len(word) > 6 else word[:5]
            if stem in combined_text:
                matches += 1
        
        # Require at least ONE word match (very lenient)
        has_relevant_term = matches >= 1
        
        # Check exclusion terms
        has_exclusion = any(hint.lower() in combined_text for hint in exclusion_hints)
        
        if has_relevant_term and not has_exclusion:
            filtered_results.append(result)
        else:
            if has_exclusion:
                logger.warning(f"Filtered (exclusion): {result.get('title', '')[:60]}")
            else:
                logger.warning(f"Filtered (no topic words): {result.get('title', '')[:60]}")
    
    logger.info(f"Filtering: {len(results)} → {len(filtered_results)} ({len(results)-len(filtered_results)} filtered)")
    return filtered_results

def _validate_content_relevance(doc: dict, topic: str, topic_terms: dict) -> bool:
    """
    POST-EXTRACTION VALIDATION: Check if the full text actually mentions the topic.
    
    This is a final safety check after content extraction to ensure the document
    is actually about the research topic.
    """
    if not doc or not doc.get("text"):
        return False
    
    text_lower = doc.get("text", "").lower()
    topic_lower = topic.lower()
    
    # Strategy 1: Check for topic words (at least one significant word)
    topic_words = [word for word in topic_lower.split() if len(word) > 3]
    has_topic_word = any(word in text_lower for word in topic_words)
    
    if not has_topic_word and topic_terms:
        # Strategy 2: Check for core terms from terminology extraction
        core_terms = topic_terms.get("core_terms", [])
        has_core_term = any(term.lower() in text_lower for term in core_terms)
        
        if not has_core_term:
            logger.warning(f"Content validation failed (no topic/core terms): {doc.get('title', '')[:60]}")
            return False
    elif not has_topic_word:
        logger.warning(f"Content validation failed (no topic words): {doc.get('title', '')[:60]}")
        return False
    
    return True

async def validate_outline_coherence(topic: str, outline: List[dict]) -> dict:
    """Validate that outline items stay aligned with the original topic"""
    try:
        validation = await llm.validate_outline(topic, outline)
        return validation
    except Exception as e:
        logger.warning(f"Outline validation failed: {e}, proceeding anyway")
        return {"is_coherent": True, "drift_score": 0.0, "suggestions": []}

async def start_run_task(run_id: str):
    logger.info(f"Starting research run task for ID: {run_id}")
    runs = db().runs
    run = await runs.find_one({"_id": ObjectId(run_id)})
    if not run:
        logger.error(f"Run not found: {run_id}")
        return
    
    # Get project info for user message
    project = await db().projects.find_one({"_id": run["projectId"]})
    topic = project.get("title", "") if project else ""

    logger.info(f"Extracting domain-specific terminology for: {topic}")
    topic_terms = await llm.extract_topic_terminology(topic)
    logger.info(f"Core terms: {topic_terms.get('core_terms', [])}")
    logger.info(f"Alternative terms: {topic_terms.get('alternative_terms', [])}")
    logger.info(f"Exclusion hints: {topic_terms.get('exclusion_hints', [])}")
    
    # Add user message
    await emit_msg(run_id, role="user", kind="info", text=f"Research '{topic}'")
    
    logger.info(f"Found run, updating status to 'planning'...")
    await runs.update_one({"_id": run["_id"]}, {"$set":{"status":"planning"}})
    await live.set_live(run_id, "planning", "Planning outline…")
    
    # Add system message
    await emit_msg(run_id, role="system", kind="status", text="planning outline")

    n = project.get("maxParagraphs", 6)
    
    logger.info(f"Research topic: '{topic}' with {n} max paragraphs")
    logger.info("Planning research outline with LLM...")
    
    try:
        logger.info("Calling LLM plan_outline...")
        outline = await llm.plan_outline(topic, n)
        logger.info(f"Generated outline with {len(outline)} items")
        
        # ENHANCEMENT: Validate outline coherence
        validation = await validate_outline_coherence(topic, outline)
        
        if not validation.get("is_coherent", True) or validation.get("drift_score", 0) > 0.3:
            logger.warning(f"Outline coherence issue detected (drift={validation.get('drift_score', 0):.2f}), regenerating...")
            await emit_msg(run_id, role="system", kind="status", text="refining outline for better focus")
            
            # Regenerate with stricter instructions
            outline = await llm.plan_outline_strict(topic, n, validation.get("suggestions", []))
            logger.info(f"Regenerated stricter outline with {len(outline)} items")
        
        # Add outline message
        outline_text = f"outline ready ({len(outline)} sections)"
        await emit_msg(run_id, role="system", kind="status", text=outline_text)
        
    except Exception as e:
        logger.error(f"LLM API Error during outline planning: {e}")
        await emit_msg(run_id, role="system", kind="error", text=f"failed to plan outline: {str(e)}")
        await runs.update_one({"_id": run["_id"]}, {"$set":{"status":"failed", "error": str(e)}})
        return
    
    oi_ids: List[ObjectId] = []
    for i, item in enumerate(outline[:n]):
        doc = {
            "runId": run["_id"],
            "idx": item.get("idx", len(oi_ids)+1),
            "heading": item.get("heading", f"Section {len(oi_ids)+1}"),
            "brief": item.get("brief", ""),
            "status": "queued"
        }
        res = await db().outlineItems.insert_one(doc)
        oi_ids.append(res.inserted_id)
        logger.info(f"Created outline item {i+1}: '{doc['heading']}'")

    logger.info("Updating run status to 'running'...")
    await runs.update_one({"_id": run["_id"]}, {"$set":{"status":"running"}})
    await live.set_live(run_id, "outline", f"Outline ready ({len(oi_ids)} sections)")

    # Add research phase message
    await emit_msg(run_id, role="system", kind="status", text="starting research phase")

    cfg = run.get("config", {})
    cfg["topic_terms"] = topic_terms
    logger.info(f"Processing {len(oi_ids)} outline items with config: {cfg}")
    R = int(cfg.get("rounds", 3))
    TOP = int(cfg.get("resultsPerRound", 12))
    KEEP = int(cfg.get("keepPerParagraph", 10))

    # Process each outline item (paragraph) independently
    for oi_id in oi_ids:
        await _work_outline_item(oi_id, R, TOP, KEEP, run_id, cfg, topic, len(oi_ids))

    # ENHANCEMENT: Synthesize final report with coherence
    await live.set_live(run_id, "aggregate", "Assembling final report…")
    await emit_msg(run_id, role="system", kind="status", text="synthesizing final report")
    
    paras = [p async for p in db().paragraphs.find({"runId": run["_id"]}).sort("idx", 1)]

    try:
        logger.info(f"Starting report synthesis with {len(paras)} paragraphs...")
        md = await llm.synthesize_report(topic, paras, outline)
        logger.info(f"Synthesized report: {len(md)} characters")
        
        # Validate synthesis
        if not md or len(md) < 500:
            logger.error(f"Synthesis produced insufficient content ({len(md)} chars)")
            raise ValueError("Synthesis output too short")
            
    except Exception as e:
        logger.error(f"Report synthesis failed: {e}, using aggregate fallback")
        try:
            md = await llm.aggregate_report(topic, paras)
            logger.info(f"Aggregate fallback produced {len(md)} characters")
        except Exception as e2:
            logger.error(f"Aggregate also failed: {e2}, using emergency fallback")
            # Emergency fallback: stitch drafts
            parts = [p.get("draftMd","") for p in paras]
            md = f"# {topic}\n\n" + "\n\n---\n\n".join(parts)

    # Build references from all paragraphs
    refs = {}
    for p in paras:
        for k, v in (p.get("citations") or {}).items():
            if v and v.get("url"):
                refs[k] = v
    
    logger.info(f"Collected {len(refs)} total citations")

    if refs:
        lines = []
        # Sort by section and citation number (S1-1, S1-2, S2-1, etc.)
        def citation_sort_key(k):
            try:
                if '-' in k:
                    parts = k.split('-')
                    section = int(parts[0][1:])  # Remove 'S' prefix
                    num = int(parts[1])
                    return (section, num)
                return (0, int(k))
            except (ValueError, IndexError):
                return (999, 0)
        
        for k in sorted(refs.keys(), key=citation_sort_key):
            v = refs[k]
            title = v.get("title","").strip() or v.get("url","")
            url = v.get("url","").strip()
            # Escape brackets to prevent markdown link interpretation
            lines.append(f"- **\\[{k}\\]** {title} — {url}")
        
        md = md.rstrip() + "\n\n## References\n" + "\n".join(lines)
        logger.info(f"Added references section with {len(lines)} citations")

    # Apply text cleaning: spell-check and remove duplicate headings
    original_length = len(md)
    md = clean_report_text(md)
    logger.info(f"Text cleaning applied: {original_length} -> {len(md)} chars")

    # Final validation
    if not md or len(md) < 500:
        logger.error(f"Final report is too short ({len(md)} chars)")
        md = f"# {topic}\n\n*Report generation incomplete. Please review individual sections.*\n\n" + md

    await db().reports.insert_one({"runId": run["_id"], "markdown": md})
    await runs.update_one({"_id": run["_id"]}, {"$set":{"status":"done"}})
    await live.set_live(run_id, "done", "Done.")
    
    # Add completion message
    await emit_msg(run_id, role="system", kind="complete", text="done")
    logger.info(f"Research run {run_id} completed successfully")

async def _work_outline_item(
    oi_id: ObjectId, 
    R: int, 
    TOP: int, 
    KEEP: int, 
    run_id: str, 
    cfg: dict,
    topic: str,
    total_sections: int
):
    oi = await db().outlineItems.find_one({"_id": oi_id})
    if not oi: 
        return
    
    current_idx = oi["idx"]
    logger.info(f"Processing section {current_idx}/{total_sections}: {oi['heading']}")
    
    # Update status to searching
    await db().outlineItems.update_one({"_id": oi_id}, {"$set":{"status":"searching"}})
    
    # Add section start message
    await emit_msg(run_id, role="system", kind="status", text=f"section {oi['idx']}: {oi['heading']}")

    seen_urls: list[str] = []
    kept_pages: list[Dict[str,Any]] = []
    last_reflection = None
    topic_terms = cfg.get("topic_terms", {})

    for r in range(1, R+1):
        # Use reflection-guided query generation after first round
        if r == 1:
            q = await llm.propose_query(oi["brief"], seen_urls, topic, topic_terms)
        else:
            q = await llm.propose_query_with_reflection(
                oi["brief"], 
                seen_urls, 
                last_reflection,
                topic,
                topic_terms
            )
        
        await live.set_live(oi["runId"], "search", f'Searching: "{_short(q.get("query",""), 48)}" (round {r})', {"outlineItemId": str(oi_id)})
        
        # Add search message with reasoning
        logger.info(f"Search query: {q.get('query','')} | Reasoning: {q.get('rationale','')[:100]}")
        await emit_msg(run_id, role="assistant", kind="query", text=q.get("query", ""), meta={
            "round": r,
            "idx": oi["idx"],
            "rationale": q.get("rationale", "")[:200]
        })
        
        await db().searchQueries.insert_one({
            "outlineItemId": oi_id,
            "round": r,
            "query": q.get("query",""),
            "rationale": q.get("rationale","")
        })
        
        provider = cfg.get("searchProvider", "hybrid")
        use_academic = cfg.get("useAcademicSources", True)
        
        # Prioritize academic sources
        results = []
        if use_academic:
            logger.info(f"Deep academic search for query: {q.get('query','')}")
            academic_results = await deep_academic_search(q.get("query",""), int(TOP * 0.7))
            results.extend(academic_results)
        
        # Add regular web search for balance
        logger.info(f"Web search with provider '{provider}' for query: {q.get('query','')}")
        web_results = await search.web_search(q.get("query",""), int(TOP * 0.3), provider) or []
        results.extend(web_results)
        
        logger.info(f"Found {len(results)} total search results ({len([r for r in results if r.get('type')=='academic'])} academic, {len([r for r in results if r.get('type')=='web'])} web)")
        
        # ENHANCED FILTER: Apply stricter topic filtering
        results = _filter_results_by_topic(results, topic_terms, topic)
        
        # Add search results message
        await emit_msg(run_id, role="assistant", kind="fetch", text=f"Found {len(results)} sources", meta={
            "sources": len(results),
            "academic": len([r for r in results if r.get('type')=='academic']),
            "web": len([r for r in results if r.get('type')=='web']),
            "round": r
        })
        
        pages = []
        for res in results:
            url = res.get("url","")
            if not url or url in seen_urls: 
                continue
            seen_urls.append(url)
            
            # Extract content
            doc = await extract.fetch_and_extract(url)
            
            # POST-EXTRACTION VALIDATION: Verify content relevance
            if doc and not _validate_content_relevance(doc, topic, topic_terms):
                logger.warning(f"Skipping irrelevant content: {doc.get('title', '')[:60]}")
                continue
            
            if doc:
                # Preserve academic metadata
                doc["title"] = res.get("title","")
                doc["type"] = res.get("type", "web")
                doc["authors"] = res.get("authors", "")
                doc["year"] = res.get("year", "")
                doc["citations"] = res.get("citations", 0)
                doc["venue"] = res.get("venue", "")
                doc["runId"] = oi["runId"]
                doc["outlineItemId"] = oi_id
                
                # Quality scoring
                doc["score"] = res.get("score", score_source_quality(res))
                
                # PDF processing for academic papers
                pdf_url = res.get("pdf_url")
                if pdf_url and doc["type"] == "academic":
                    logger.info(f"Processing academic PDF: {_short(res.get('title',''), 40)}")
                    try:
                        pdf_content = await process_academic_pdf(pdf_url)
                        if not pdf_content.get("error"):
                            doc["text"] = pdf_content.get("text", doc.get("text", ""))
                            doc["pdf_metadata"] = pdf_content.get("metadata", {})
                            logger.info(f"PDF processed: {len(doc.get('text',''))} chars, {len(pdf_content.get('figures',[]))} figures")
                            
                            # Store figures as assets
                            for fig in pdf_content.get("figures", [])[:5]:
                                asset = {
                                    "runId": oi["runId"],
                                    "outlineItemId": oi_id,
                                    "type": "figure",
                                    "sourceUrl": pdf_url,
                                    "caption": f"Figure {fig['number']} from page {fig['page']}",
                                    "ocrText": "",
                                    "tags": ["pdf", "figure"],
                                    "pngB64": fig.get("pngB64", ""),
                                    "page": fig.get("page", 0),
                                    "meta": {"xref": fig.get("xref", 0), "format": fig.get("format", "png")}
                                }
                                await db().assets.insert_one(asset)
                                await emit_msg(run_id, role="assistant", kind="asset", text=f"Found figure on page {fig['page']}", meta={"type": "figure", "page": fig['page']})
                    except Exception as e:
                        logger.warning(f"PDF processing failed for {url}: {e}")
                
                # Visual extraction from HTML sources
                if doc.get("html") and doc["type"] == "web":
                    logger.info(f"Extracting visuals from HTML: {_short(res.get('title',''), 40)}")
                    try:
                        visuals = await analyze_source_visuals(doc)
                        for visual in visuals:
                            asset = {
                                "runId": oi["runId"],
                                "outlineItemId": oi_id,
                                "type": "image",
                                "sourceUrl": doc["url"],
                                "caption": visual.get("caption", ""),
                                "ocrText": visual.get("ocrText", ""),
                                "tags": visual.get("tags", []),
                                "imageUrl": visual.get("url", ""),
                                "meta": {
                                    "objects": visual.get("objects", []),
                                    "confidence": visual.get("confidence", 0.0)
                                }
                            }
                            await db().assets.insert_one(asset)
                            await emit_msg(run_id, role="assistant", kind="asset", text=f"Found diagram: {visual.get('caption', 'visual')[:50]}", meta={"type": "image", "caption": visual.get("caption", "")})
                        logger.info(f"Extracted {len(visuals)} visuals")
                    except Exception as e:
                        logger.warning(f"Visual extraction failed for {url}: {e}")
                
                await db().sources.insert_one(doc)
                pages.append(doc)
                
                source_indicator = "📚" if doc["type"] == "academic" else "🌐"
                await live.set_live(oi["runId"], "fetch", f'{source_indicator} {_short(res.get("title","Untitled"), 45)} ({_domain(url)})', {"url": url})
        
        # Filter by quality threshold
        high_quality_pages = [p for p in pages if p.get("score", 0) >= 0.5]
        logger.info(f"Filtered to {len(high_quality_pages)} high-quality sources (score >= 0.5) from {len(pages)} total")
        
        # Reflection with topic context
        notes = await llm.reflect_with_context(
            oi["brief"], 
            [p.get("text","")[:500] for p in high_quality_pages],
            topic,
            oi["heading"]
        )
        
        await live.set_live(oi["runId"], "reflect", "Analyzing gaps…", {"round": r})
        last_reflection = notes
        nxt = notes.get("next_query")
        
        # Always use reflection query in subsequent rounds
        if nxt and r < R:
            logger.info(f"Reflection suggests follow-up: {nxt[:80]}")
            results2 = await search.web_search(nxt, TOP//2, provider) or []
            
            # Apply filtering to reflection results too
            results2 = _filter_results_by_topic(results2, topic_terms, topic)
            
            for res in results2:
                url = res.get("url","")
                if not url or url in seen_urls: 
                    continue
                seen_urls.append(url)
                doc = await extract.fetch_and_extract(url)
                
                # Validate relevance
                if doc and not _validate_content_relevance(doc, topic, topic_terms):
                    logger.warning(f"Skipping irrelevant reflection result: {doc.get('title', '')[:60]}")
                    continue
                
                if doc:
                    doc["title"] = res.get("title","")
                    doc["runId"] = oi["runId"]
                    doc["outlineItemId"] = oi_id
                    doc["score"] = score_source_quality(res)
                    doc["type"] = res.get("type", "web")
                    await db().sources.insert_one(doc)
                    high_quality_pages.append(doc)
        
        kept_pages.extend(high_quality_pages)
        await db().reflections.insert_one({
            "outlineItemId": oi_id,
            "round": r,
            "notes": notes.get("notes",""),
            "next_query": nxt,
            "gaps_identified": notes.get("gaps", [])
        })

    # Keep top sources
    kept_pages = kept_pages[:KEEP]
    
    # Ensure at least 70% academic sources
    academic_count = len([p for p in kept_pages if p.get("type") == "academic"])
    academic_percentage = (academic_count / len(kept_pages) * 100) if kept_pages else 0
    
    logger.info(f"Source breakdown: {academic_count}/{len(kept_pages)} academic ({academic_percentage:.0f}%)")
    
    if academic_percentage < 70 and len(kept_pages) >= 3:
        logger.warning(f"Academic percentage ({academic_percentage:.0f}%) below 70% threshold, boosting academic sources...")
        boost_query = oi["brief"][:100] + " systematic review meta-analysis"
        academic_boost = await deep_academic_search(boost_query, 5)
        
        # Apply filtering to boosted results
        academic_boost = _filter_results_by_topic(academic_boost, topic_terms, topic)
        
        for res in academic_boost:
            if res.get("url") not in seen_urls:
                doc = await extract.fetch_and_extract(res.get("url",""))
                
                # Validate relevance
                if doc and not _validate_content_relevance(doc, topic, topic_terms):
                    logger.warning(f"Skipping irrelevant boosted result: {doc.get('title', '')[:60]}")
                    continue
                
                if doc:
                    doc["title"] = res.get("title","")
                    doc["type"] = "academic"
                    doc["authors"] = res.get("authors", "")
                    doc["year"] = res.get("year", "")
                    doc["citations"] = res.get("citations", 0)
                    doc["venue"] = res.get("venue", "")
                    doc["runId"] = oi["runId"]
                    doc["outlineItemId"] = oi_id
                    doc["score"] = res.get("score", 0.7)
                    await db().sources.insert_one(doc)
                    kept_pages.append(doc)
                    seen_urls.append(res.get("url",""))
        
        # Re-sort by quality and keep top KEEP
        kept_pages.sort(key=lambda x: x.get("score", 0), reverse=True)
        kept_pages = kept_pages[:KEEP]
        
        academic_count = len([p for p in kept_pages if p.get("type") == "academic"])
        logger.info(f"After boosting: {academic_count}/{len(kept_pages)} academic ({academic_count/len(kept_pages)*100:.0f}%)")
    
    # Add reflection message
    await emit_msg(run_id, role="assistant", kind="reflect", text=notes.get("notes",""), meta={
        "round": R,
        "academicPercentage": academic_percentage,
        "gaps": notes.get("gaps", [])[:3]
    })
    
    await db().outlineItems.update_one({"_id": oi_id}, {"$set": {"status": "drafting"}})
    await live.set_live(oi["runId"], "draft", f'Writing section {oi["idx"]}…')
    
    # Add drafting message
    await emit_msg(run_id, role="assistant", kind="draft", text=f"writing section {oi['idx']}")
    
    sources = kept_pages
    
    # Check minimum source threshold - CRITICAL FIX for extraction failures
    if len(sources) < 2:
        logger.error(f"Section {oi['idx']} has only {len(sources)} usable sources after extraction failures")
        logger.error(f"   Brief was: {oi['brief'][:100]}")
        
        # Try emergency search
        logger.warning(f"Attempting emergency backup search...")
        emergency_query = oi["heading"]
        alt_provider = "brave" if cfg.get("searchProvider") != "brave" else "serpapi"
        
        alt = await search.web_search(emergency_query, top=10, provider=alt_provider)
        
        # Apply filtering even to emergency results
        alt = _filter_results_by_topic(alt, topic_terms, topic)
        
        fetched = []
        for r in alt[:8]:
            url = r.get("url", "")
            if url not in seen_urls:
                doc = await extract.fetch_and_extract(url)
                
                # Validate relevance
                if doc and _validate_content_relevance(doc, topic, topic_terms):
                    if doc.get("text") and len(doc.get("text", "")) > 100:
                        doc["title"] = r.get("title","")
                        doc["score"] = 0.5
                        doc["type"] = "web"
                        fetched.append(doc)
                        seen_urls.append(url)
        
        sources = (sources + fetched)[:8]
        logger.info(f"Emergency search added {len(fetched)} sources, total now {len(sources)}")
    
    # CRITICAL: If still insufficient, skip section gracefully
    if len(sources) < 2:
        logger.error(f"CRITICAL: Section {oi['idx']} still has insufficient sources ({len(sources)})")
        
        # Create placeholder paragraph
        await db().paragraphs.insert_one({
            "runId": oi["runId"],
            "outlineItemId": oi_id,
            "idx": oi["idx"],
            "draftMd": f"## {oi['heading']}\n\n*Insufficient sources available for comprehensive analysis. This section experienced extraction failures (likely due to paywalls, access restrictions, or network issues). Manual research recommended.*\n\nResearch question: {oi['brief'][:200]}",
            "citations": {},
            "quality": 0.0,
            "visualsUsed": []
        })
        
        await db().outlineItems.update_one({"_id": oi_id}, {"$set": {"status": "failed"}})
        await live.set_live(oi["runId"], "section", f'Section {oi["idx"]} skipped (extraction failures)')
        await emit_msg(run_id, role="system", kind="section", text=f"section {oi['idx']} skipped - insufficient sources")
        return

    # Fetch visual assets
    assets_cursor = db().assets.find({"outlineItemId": oi_id})
    assets = [a async for a in assets_cursor]
    
    # Generate diagrams and charts if appropriate
    visual_decisions = await should_generate_visuals(topic, oi["brief"], len(sources))
    
    # Generate diagram if recommended
    if visual_decisions.get("diagram", False):
        logger.info(f"Generating diagram for section {oi['idx']}")
        diagram = await generate_diagram(topic, oi["brief"], sources)
        if diagram:
            diagram_asset = {
                "runId": oi["runId"],
                "outlineItemId": oi_id,
                "type": "diagram",
                "sourceUrl": "",
                "caption": f"Process diagram for: {oi['heading']}",
                "ocrText": "",
                "tags": ["mermaid", "diagram", "generated"],
                "mermaidCode": diagram.get("code", ""),
                "meta": {"format": "mermaid", "generated": True}
            }
            await db().assets.insert_one(diagram_asset)
            assets.append(diagram_asset)
            await emit_msg(run_id, role="assistant", kind="asset", text=f"Generated diagram for {oi['heading']}", meta={"type": "diagram", "format": "mermaid"})
    
    logger.info(f"Writing paragraph for section {oi['idx']} with {len(sources)} sources and {len(assets)} visual assets")
    
    try:
        # Pass paragraph position for style variation
        para = await llm.write_paragraph_with_context(
            oi["brief"], 
            sources, 
            assets,
            topic,
            oi["heading"],
            paragraph_index=current_idx,
            total_paragraphs=total_sections
        )
        logger.info(f"Generated paragraph: {len(para.get('draftMd', ''))} chars, quality={para.get('quality', 0):.2f}")
        
        # Generate chart if recommended
        if visual_decisions.get("chart", False):
            logger.info(f"Extracting chart data from paragraph {oi['idx']}")
            chart = await extract_chart_data(para.get("draftMd", ""), sources)
            if chart:
                chart_asset = {
                    "runId": oi["runId"],
                    "outlineItemId": oi_id,
                    "type": "chart",
                    "sourceUrl": "",
                    "caption": chart.get("title", f"Data for {oi['heading']}"),
                    "ocrText": "",
                    "tags": ["chart", "data", "generated"],
                    "chartData": chart.get("data", []),
                    "meta": {
                        "chartType": chart.get("type", "bar"),
                        "unit": chart.get("unit", ""),
                        "generated": True
                    }
                }
                await db().assets.insert_one(chart_asset)
                await emit_msg(run_id, role="assistant", kind="asset", text=f"Generated chart: {chart.get('title', 'Data visualization')}", meta={"type": "chart", "chartType": chart.get("type", "bar")})
        
    except Exception as e:
        logger.error(f"Paragraph generation failed: {str(e)}")
        para = {"draftMd": f"Error generating paragraph: {str(e)}", "citations": {}, "quality": 0.0, "visualsUsed": []}
    
    # FIXED: Proper citation mapping
    # Get raw citations from LLM (keys are "1", "2", etc.)
    raw_cites: dict = para.get("citations", {})
    
    # Get markdown with original citation numbers [1], [2], etc.
    md = para.get("draftMd","")
    
    # Transform markdown to use scoped references [S1-1], [S2-1], etc.
    md = re.sub(r"\[(\d+)\]", lambda m: f"[S{oi['idx']}-{m.group(1)}]", md)
    
    # Create scoped citations dict to match transformed markdown
    scoped_cites = {f"S{oi['idx']}-{str(k)}": v for k, v in raw_cites.items()}
    
    # Validate we have content
    if not md or len(md) < 300:
        logger.warning(f"Writer returned short paragraph ({len(md)} chars); brief='{oi['brief'][:120]}', sources={len(sources)}")
    
    quality_score = _parse_quality_score(para.get("quality", 0.0))
    
    logger.info(f"Section {oi['idx']} completed with {len(scoped_cites)} citations")
    
    await db().paragraphs.insert_one({
        "runId": oi["runId"],
        "outlineItemId": oi_id,
        "idx": oi["idx"],
        "draftMd": md,
        "citations": scoped_cites,
        "quality": quality_score,
        "visualsUsed": para.get("visualsUsed", [])
    })
    
    await db().outlineItems.update_one({"_id": oi_id}, {"$set": {"status": "done"}})
    await live.set_live(oi["runId"], "section", f'Section {oi["idx"]} done')
    
    # Add completion message
    await emit_msg(run_id, role="system", kind="section", text=f"section {oi['idx']} done")

# --- Public helpers for endpoints ---
async def get_run_progress(run_id: str, user_sub: str):
    rid = ObjectId(run_id)
    run = await db().runs.find_one({"_id": rid})
    if not run: 
        return None
    total = await db().outlineItems.count_documents({"runId": rid}) or 1
    done_by_status = await db().outlineItems.count_documents({"runId": rid, "status": "done"})
    done_by_paras  = await db().paragraphs.count_documents({"runId": rid})
    done = max(done_by_status, done_by_paras)
    progress = int(100 * min(done, total) / total)
    return {"status": run.get("status","queued"), "progress": progress}

async def get_outline(run_id: str, user_sub: str):
    rid = ObjectId(run_id)
    cur = db().outlineItems.find({"runId": rid}).sort("idx", 1)
    items = []
    async for i in cur:
        items.append({
            "_id": str(i["_id"]), 
            "idx": i["idx"], 
            "heading": i["heading"], 
            "brief": i["brief"], 
            "status": i.get("status","")
        })
    return items

async def get_report(run_id: str, user_sub: str):
    rid = ObjectId(run_id)

    # First check if report is stored in runs collection (agentic runs)
    run = await db().runs.find_one({"_id": rid})
    if run and run.get("report"):
        return {
            "markdown": run.get("report", ""),
            "citations": run.get("citations", {})
        }

    # Then check reports collection (simple runs)
    rep = await db().reports.find_one({"runId": rid}) \
       or await db().reports.find_one({"RunId": rid})
    if rep:
        return {"markdown": rep.get("markdown","")}

    # Fallback: stitch paragraphs together ONLY if run is complete
    # This prevents returning partial content during synthesis
    if run and run.get("status") == "done":
        paras = [p async for p in db().paragraphs.find({"runId": rid}).sort("idx", 1)]
        if paras:
            md = "\n\n".join(p.get("draftMd","") for p in paras)
            return {"markdown": md}

    # Return None if report not ready yet (run still in progress)
    return None

async def get_research_threads(user_sub: str, limit: int = 20):
    """Get research threads for a user"""
    threads_cursor = db().runs.find().sort("createdAt", -1).limit(limit)
    threads = []
    async for run in threads_cursor:
        project = await db().projects.find_one({"_id": run["projectId"]})
        if not project:
            continue
            
        message_count = await db().researchMessages.count_documents({"runId": run["_id"]})
        
        latest_msg = await db().researchMessages.find_one(
            {"runId": run["_id"]}, 
            sort=[("timestamp", -1)]
        )
        
        threads.append({
            "id": str(run["_id"]),
            "title": project.get("title", "Unknown Topic"),
            "status": "completed" if run.get("status") == "done" else run.get("status", "queued"),
            "progress": run.get("progress", 0),
            "createdAt": run.get("createdAt"),
            "updatedAt": latest_msg.get("timestamp") if latest_msg else run.get("createdAt"),
            "messageCount": message_count,
            "latestMessage": latest_msg.get("content", "") if latest_msg else ""
        })
    return threads

async def get_research_messages(thread_id: str, user_sub: str, limit: int = 50):
    """Get messages for a research thread"""
    try:
        rid = ObjectId(thread_id)
    except Exception:
        return []
    
    messages_cursor = db().researchMessages.find({"runId": rid}).sort("timestamp", 1).limit(limit)
    messages = []
    async for msg in messages_cursor:
        messages.append({
            "id": str(msg["_id"]),
            "threadId": thread_id,
            "type": msg.get("type", "system"),
            "content": msg.get("content", ""),
            "timestamp": msg.get("timestamp"),
            "metadata": msg.get("metadata", {}),
            "isStreaming": msg.get("isStreaming", False)
        })
    return messages

async def get_research_thread(thread_id: str, user_sub: str):
    """Get full research thread details"""
    try:
        rid = ObjectId(thread_id)
    except Exception:
        return None
    
    run = await db().runs.find_one({"_id": rid})
    if not run:
        return None
    
    project = await db().projects.find_one({"_id": run["projectId"]})
    if not project:
        return None
    
    outline_items = []
    outline_cursor = db().outlineItems.find({"runId": rid}).sort("idx", 1)
    async for item in outline_cursor:
        outline_items.append({
            "id": str(item["_id"]),
            "index": item.get("idx", 0),
            "title": item.get("heading", ""),
            "brief": item.get("brief", ""),
            "status": item.get("status", "queued"),
            "progress": 100 if item.get("status") == "done" else 40 if item.get("status") == "drafting" else 20 if item.get("status") == "searching" else 0
        })
    
    report = await get_report(thread_id, user_sub)
    final_report = report.get("markdown", "") if report else ""
    
    messages = await get_research_messages(thread_id, user_sub, 100)
    
    return {
        "id": thread_id,
        "title": project.get("title", "Unknown Topic"),
        "status": "completed" if run.get("status") == "done" else run.get("status", "queued"),
        "messages": messages,
        "createdAt": run.get("createdAt"),
        "updatedAt": run.get("updatedAt", run.get("createdAt")),
        "progress": run.get("progress", 0),
        "outline": outline_items,
        "finalReport": final_report,
        "metadata": {
            "maxParagraphs": project.get("maxParagraphs", 6),
            "roundsPerParagraph": run.get("config", {}).get("rounds", 3),
            "searchProvider": run.get("config", {}).get("searchProvider", "hybrid"),
            "totalSources": await db().sources.count_documents({"runId": rid}),
            "qualityScore": 0
        }
    }