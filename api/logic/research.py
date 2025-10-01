import asyncio
import logging
import os
from typing import List, Dict, Any
from bson import ObjectId
from models.db import db
from services import llm, search, extract, live
from services.academic import deep_academic_search, score_source_quality
from services.pdf_processor import process_academic_pdf
from services.vision import analyze_source_visuals
from services.agents import generate_diagram, extract_chart_data, should_generate_visuals
from services.messages import emit_msg
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

async def start_run_task(run_id: str):
    logger.info(f"🚀 Starting research run task for ID: {run_id}")
    runs = db().runs
    run = await runs.find_one({"_id": ObjectId(run_id)})
    if not run:
        logger.error(f"❌ Run not found: {run_id}")
        return
    
    # Get project info for user message
    project = await db().projects.find_one({"_id": run["projectId"]})
    topic = project.get("title", "") if project else ""
    
    # Add user message
    await emit_msg(run_id, role="user", kind="info", text=f"Research '{topic}'")
    
    logger.info(f"📋 Found run, updating status to 'planning'...")
    await runs.update_one({"_id": run["_id"]}, {"$set":{"status":"planning"}})
    await live.set_live(run_id, "planning", "Planning outline…")
    
    # Add system message
    await emit_msg(run_id, role="system", kind="status", text="planning outline")

    project = await db().projects.find_one({"_id": run["projectId"]})
    topic = project.get("title","")
    n = project.get("maxParagraphs", 6)
    
    logger.info(f"📚 Research topic: '{topic}' with {n} max paragraphs")
    logger.info("🧠 Planning research outline with LLM...")
    
    try:
        logger.info("🔧 Calling LLM plan_outline...")
        outline = await llm.plan_outline(topic, n)
        logger.info(f"📋 Generated outline with {len(outline)} items")
        
        # Add outline message
        outline_text = f"outline ready ({len(outline)} sections)"
        await emit_msg(run_id, role="system", kind="status", text=outline_text)
        
    except Exception as e:
        logger.error(f"❌ LLM API Error during outline planning: {e}")
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
        logger.info(f"📝 Created outline item {i+1}: '{doc['heading']}'")

    logger.info("🏃 Updating run status to 'running'...")
    await runs.update_one({"_id": run["_id"]}, {"$set":{"status":"running"}})
    await live.set_live(run_id, "outline", f"Outline ready ({len(oi_ids)} sections)")

    # Add research phase message
    await emit_msg(run_id, role="system", kind="status", text="starting research phase")

    # ENHANCED: More rounds, more sources, keep more per paragraph
    cfg = run.get("config", {})
    logger.info(f"⚙️ Processing {len(oi_ids)} outline items with config: {cfg}")
    R = int(cfg.get("rounds", 3))  # Increased from 2 to 3
    TOP = int(cfg.get("resultsPerRound", 12))  # Increased from 8 to 12
    KEEP = int(cfg.get("keepPerParagraph", 10))  # Increased from 6 to 10

    for oi_id in oi_ids:
        await _work_outline_item(oi_id, R, TOP, KEEP, run_id, cfg)

    # aggregate
    await live.set_live(run_id, "aggregate", "Assembling final report…")
    await emit_msg(run_id, role="system", kind="status", text="assembling final report")
    
    paras = [p async for p in db().paragraphs.find({"runId": run["_id"]}).sort("idx", 1)]
    try:
        md = await llm.aggregate_report(topic, paras)
    except Exception:
        md = ""
    if not md or not md.strip():
        # fallback: stitch drafts
        parts = [p.get("draftMd","") for p in paras]
        md = "# " + topic + "\n\n" + "\n\n---\n\n".join(parts)

    await db().reports.insert_one({"runId": run["_id"], "markdown": md})
    await runs.update_one({"_id": run["_id"]}, {"$set":{"status":"done"}})
    await live.set_live(run_id, "done", "Done.")
    
    # Add completion message
    await emit_msg(run_id, role="system", kind="complete", text="done")

async def _work_outline_item(oi_id: ObjectId, R: int, TOP: int, KEEP: int, run_id: str, cfg: dict):
    oi = await db().outlineItems.find_one({"_id": oi_id})
    if not oi: return
    
    # Update status to searching
    await db().outlineItems.update_one({"_id": oi_id}, {"$set":{"status":"searching"}})
    
    # Add section start message
    await emit_msg(run_id, role="system", kind="status", text=f"section {oi['idx']}: {oi['heading']}")

    seen_urls: list[str] = []
    kept_pages: list[Dict[str,Any]] = []

    for r in range(1, R+1):
        q = await llm.propose_query(oi["brief"], seen_urls)
        await live.set_live(oi["runId"], "search", f'Searching: "{_short(q.get("query",""), 48)}" (round {r})', {"outlineItemId": str(oi_id)})
        
        # Add search message
        logger.info(f"🔍 Emitting search message for query: {q.get('query','')}")
        await emit_msg(run_id, role="assistant", kind="query", text=q.get("query", ""), meta={
            "round": r,
            "idx": oi["idx"]
        })
        
        await db().searchQueries.insert_one({
            "outlineItemId": oi_id,
            "round": r,
            "query": q.get("query",""),
            "rationale": q.get("rationale","")
        })
        provider = cfg.get("searchProvider", "hybrid")
        use_academic = cfg.get("useAcademicSources", True)
        
        # ENHANCED: Prioritize academic sources - allocate more budget to academic search
        results = []
        if use_academic:
            logger.info(f"🎓 Deep academic search for query: {q.get('query','')}")
            academic_results = await deep_academic_search(q.get("query",""), int(TOP * 0.7))  # 70% academic
            results.extend(academic_results)
        
        # Add regular web search for balance (only 30% now)
        logger.info(f"🌐 Web search with provider '{provider}' for query: {q.get('query','')}")
        web_results = await search.web_search(q.get("query",""), int(TOP * 0.3), provider) or []
        results.extend(web_results)
        
        logger.info(f"📊 Found {len(results)} total search results ({len([r for r in results if r.get('type')=='academic'])} academic, {len([r for r in results if r.get('type')=='web'])} web)")
        
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
            if not url or url in seen_urls: continue
            seen_urls.append(url)
            
            # Extract content
            doc = await extract.fetch_and_extract(url)
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
                
                # Quality scoring (already done in academic.py but ensure it's set)
                doc["score"] = res.get("score", score_source_quality(res))
                
                # PDF processing for academic papers
                pdf_url = res.get("pdf_url")
                if pdf_url and doc["type"] == "academic":
                    logger.info(f"📄 Processing academic PDF: {_short(res.get('title',''), 40)}")
                    try:
                        pdf_content = await process_academic_pdf(pdf_url)
                        if not pdf_content.get("error"):
                            doc["text"] = pdf_content.get("text", doc.get("text", ""))
                            doc["pdf_metadata"] = pdf_content.get("metadata", {})
                            logger.info(f"✅ PDF processed: {len(doc.get('text',''))} chars, {len(pdf_content.get('figures',[]))} figures")
                            
                            # Store figures as assets
                            for fig in pdf_content.get("figures", [])[:5]:  # Limit to 5 figures
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
                        logger.warning(f"⚠️ PDF processing failed for {url}: {e}")
                
                # Visual extraction from HTML sources
                if doc.get("html") and doc["type"] == "web":
                    logger.info(f"🖼️ Extracting visuals from HTML: {_short(res.get('title',''), 40)}")
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
                        logger.info(f"✅ Extracted {len(visuals)} visuals")
                    except Exception as e:
                        logger.warning(f"⚠️ Visual extraction failed for {url}: {e}")
                
                await db().sources.insert_one(doc)
                pages.append(doc)
                
                source_indicator = "📚" if doc["type"] == "academic" else "🌐"
                await live.set_live(oi["runId"], "fetch", f'{source_indicator} {_short(res.get("title","Untitled"), 45)} ({_domain(url)})', {"url": url})
        
        # ENHANCED: Filter by quality threshold (minimum 0.5 score)
        high_quality_pages = [p for p in pages if p.get("score", 0) >= 0.5]
        logger.info(f"✅ Filtered to {len(high_quality_pages)} high-quality sources (score >= 0.5) from {len(pages)} total")
        
        notes = await llm.reflect(oi["brief"], [p.get("text","")[:500] for p in high_quality_pages])
        await live.set_live(oi["runId"], "reflect", "Analyzing gaps…", {"round": r})
        nxt = notes.get("next_query")
        
        if nxt:  # optional second pass tweak
            results2 = await search.web_search(nxt, TOP//2, provider) or []
            for res in results2:
                url = res.get("url","")
                if not url or url in seen_urls: continue
                seen_urls.append(url)
                doc = await extract.fetch_and_extract(url)
                if doc:
                    doc["title"] = res.get("title","")
                    doc["runId"] = oi["runId"]
                    doc["outlineItemId"] = oi_id
                    doc["score"] = score_source_quality(res)
                    await db().sources.insert_one(doc)
                    high_quality_pages.append(doc)
        
        kept_pages.extend(high_quality_pages)
        await db().reflections.insert_one({
            "outlineItemId": oi_id,
            "round": r,
            "notes": notes.get("notes",""),
            "next_query": nxt
        })

    # ENHANCED: Keep more sources, ensure academic majority
    kept_pages = kept_pages[:KEEP]
    
    # CRITICAL: Ensure at least 70% academic sources
    academic_count = len([p for p in kept_pages if p.get("type") == "academic"])
    academic_percentage = (academic_count / len(kept_pages) * 100) if kept_pages else 0
    
    logger.info(f"📊 Source breakdown: {academic_count}/{len(kept_pages)} academic ({academic_percentage:.0f}%)")
    
    if academic_percentage < 70 and len(kept_pages) >= 3:
        logger.warning(f"⚠️ Academic percentage ({academic_percentage:.0f}%) below 70% threshold, boosting academic sources...")
        # Boost with additional academic-only search
        boost_query = oi["brief"][:100] + " systematic review meta-analysis"
        academic_boost = await deep_academic_search(boost_query, 5)
        
        for res in academic_boost:
            if res.get("url") not in seen_urls:
                doc = await extract.fetch_and_extract(res.get("url",""))
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
        logger.info(f"✅ After boosting: {academic_count}/{len(kept_pages)} academic ({academic_count/len(kept_pages)*100:.0f}%)")
    
    # Add reflection message
    await emit_msg(run_id, role="assistant", kind="reflect", text=notes.get("notes",""), meta={
        "round": r,
        "academicPercentage": academic_percentage
    })
    
    await db().outlineItems.update_one({"_id": oi_id}, {"$set": {"status": "drafting"}})
    await live.set_live(oi["runId"], "draft", f'Writing section {oi["idx"]}…')
    
    # Add drafting message
    await emit_msg(run_id, role="assistant", kind="draft", text=f"writing section {oi['idx']}")
    
    sources = kept_pages
    
    # ENHANCED: Check minimum source threshold - CRITICAL FIX for extraction failures
    if len(sources) < 2:
        logger.error(f"❌ Section {oi['idx']} has only {len(sources)} usable sources after extraction failures")
        logger.error(f"   Brief was: {oi['brief'][:100]}")
        logger.error(f"   This usually means URLs returned 403/timeout or are paywalled")
        
        # Try emergency search with different provider and broader query
        logger.warning(f"⚠️ Attempting emergency backup search...")
        emergency_query = oi["heading"]  # Use heading instead of brief for broader results
        alt_provider = "brave" if cfg.get("searchProvider") != "brave" else "serpapi"
        
        alt = await search.web_search(emergency_query, top=10, provider=alt_provider)
        fetched = []
        for r in alt[:8]:
            url = r.get("url", "")
            if url not in seen_urls:
                doc = await extract.fetch_and_extract(url)
                if doc and doc.get("text") and len(doc.get("text", "")) > 100:
                    doc["title"] = r.get("title","")
                    doc["score"] = 0.5
                    doc["type"] = "web"
                    fetched.append(doc)
                    seen_urls.append(url)
        
        sources = (sources + fetched)[:8]
        logger.info(f"✅ Emergency search added {len(fetched)} sources, total now {len(sources)}")
    
    # CRITICAL: If still insufficient, skip this section gracefully
    if len(sources) < 2:
        logger.error(f"❌ CRITICAL: Section {oi['idx']} still has insufficient sources ({len(sources)}) after emergency search")
        logger.error(f"   Skipping this section to avoid system hang")
        
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
        await emit_msg(run_id, role="system", kind="section", text=f"section {oi['idx']} skipped - insufficient sources after extraction failures")
        return  # Skip to next section

    # Fetch visual assets for this section
    assets_cursor = db().assets.find({"outlineItemId": oi_id})
    assets = [a async for a in assets_cursor]
    
    # Generate diagrams and charts if appropriate
    project = await db().projects.find_one({"_id": oi["runId"]})
    topic = project.get("title", "") if project else ""
    
    visual_decisions = await should_generate_visuals(topic, oi["brief"], len(sources))
    
    # Generate diagram if recommended
    if visual_decisions.get("diagram", False):
        logger.info(f"🎨 Generating diagram for section {oi['idx']}")
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
    
    logger.info(f"🔧 Writing paragraph for section {oi['idx']} with {len(sources)} sources ({len([s for s in sources if s.get('type')=='academic'])} academic) and {len(assets)} visual assets")
    try:
        para = await llm.write_paragraph(oi["brief"], sources, assets)
        logger.info(f"📝 Generated paragraph: {len(para.get('draftMd', ''))} chars, quality={para.get('quality', 0):.2f}")
        
        # Generate chart from paragraph content if recommended
        if visual_decisions.get("chart", False):
            logger.info(f"📊 Extracting chart data from paragraph {oi['idx']}")
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
        logger.error(f"❌ Paragraph generation failed: {str(e)}")
        para = {"draftMd": f"Error generating paragraph: {str(e)}", "citations": {}, "quality": 0.0, "visualsUsed": []}
    
    # Log failures
    md = para.get("draftMd","")
    if not md or len(md) < 300:
        logger.error(f"⚠️ Writer returned short paragraph ({len(md)} chars); brief='{oi['brief'][:120]}', sources={len(sources)}")

    # Convert numeric keys to string keys for MongoDB compatibility
    citations = para.get("citations", {})
    citations_str_keys = {str(k): v for k, v in citations.items()}
    
    quality_score = _parse_quality_score(para.get("quality", 0.0))
    
    await db().paragraphs.insert_one({
        "runId": oi["runId"],
        "outlineItemId": oi_id,
        "idx": oi["idx"],
        "draftMd": para.get("draftMd",""),
        "citations": citations_str_keys,
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
    if not run: return None
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
        items.append({"_id": str(i["_id"]), "idx": i["idx"], "heading": i["heading"], "brief": i["brief"], "status": i.get("status","")})
    return items

async def get_report(run_id: str, user_sub: str):
    rid = ObjectId(run_id)
    rep = await db().reports.find_one({"runId": rid}) \
       or await db().reports.find_one({"RunId": rid})  # legacy
    if rep: return {"markdown": rep.get("markdown","")}
    # synthesize on the fly if needed
    paras = [p async for p in db().paragraphs.find({"runId": rid}).sort("idx", 1)]
    if paras:
        md = "\n\n".join(p.get("draftMd","") for p in paras)
        return {"markdown": md}
    return None

# Research Thread functions
async def get_research_threads(user_sub: str, limit: int = 20):
    """Get research threads for a user"""
    threads_cursor = db().runs.find().sort("createdAt", -1).limit(limit)
    threads = []
    async for run in threads_cursor:
        # Get project info
        project = await db().projects.find_one({"_id": run["projectId"]})
        if not project:
            continue
            
        # Get message count
        message_count = await db().researchMessages.count_documents({"runId": run["_id"]})
        
        # Get latest message
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
    
    # Get project info
    project = await db().projects.find_one({"_id": run["projectId"]})
    if not project:
        return None
    
    # Get outline
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
    
    # Get final report
    report = await get_report(thread_id, user_sub)
    final_report = report.get("markdown", "") if report else ""
    
    # Get messages
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
            "qualityScore": 0  # TODO: Calculate average quality score
        }
    }