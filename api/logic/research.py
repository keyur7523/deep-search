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
        # Test environment loading
        import os
        from dotenv import load_dotenv
        load_dotenv()
        key = os.getenv("LLM_API_KEY", "")
        logger.info(f"🔧 Environment check: LLM_API_KEY length = {len(key)}")
        
        outline = await llm.plan_outline(topic, n)
        logger.info(f"📋 Generated outline with {len(outline)} items: {outline}")
        
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

    # process each outline item
    cfg = run.get("config", {})
    logger.info(f"⚙️ Processing {len(oi_ids)} outline items with config: {cfg}")
    R = int(cfg.get("rounds", 2))
    TOP = int(cfg.get("resultsPerRound", 8))
    KEEP = int(cfg.get("keepPerParagraph", 6))

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
        logger.info(f"📝 Emitting search message for query: {q.get('query','')}")
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
        
        # Multi-source strategy: combine web + academic
        results = []
        if use_academic:
            logger.info(f"🎓 Deep academic search for query: {q.get('query','')}")
            academic_results = await deep_academic_search(q.get("query",""), TOP // 2)
            results.extend(academic_results)
        
        # Add regular web search for balance
        logger.info(f"🔍 Web search with provider '{provider}' for query: {q.get('query','')}")
        web_results = await search.web_search(q.get("query",""), TOP // 2, provider) or []
        results.extend(web_results)
        
        logger.info(f"📄 Found {len(results)} total search results ({len([r for r in results if r.get('type')=='academic'])} academic)")
        
        # Add search results message
        await emit_msg(run_id, role="assistant", kind="fetch", text=f"Found {len(results)} sources", meta={
            "sources": len(results),
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
                
                # Quality scoring
                doc["score"] = score_source_quality(res)
                
                # PDF processing for academic papers
                pdf_url = res.get("pdf_url")
                if pdf_url and doc["type"] == "academic":
                    logger.info(f"📄 Processing academic PDF: {_short(res.get('title',''), 40)}")
                    try:
                        pdf_content = await process_academic_pdf(pdf_url)
                        if not pdf_content.get("error"):
                            doc["text"] = pdf_content.get("text", doc.get("text", ""))
                            doc["pdf_metadata"] = pdf_content.get("metadata", {})
                            doc["figures"] = pdf_content.get("figures", [])
                            doc["references"] = pdf_content.get("references", [])
                            logger.info(f"✅ PDF processed: {len(doc.get('text',''))} chars, {len(doc.get('figures',[]))} figures")
                    except Exception as e:
                        logger.warning(f"⚠️ PDF processing failed: {e}")
                
                await db().sources.insert_one(doc)
                pages.append(doc)
                
                source_indicator = "📚" if doc["type"] == "academic" else "🌐"
                await live.set_live(oi["runId"], "fetch", f'{source_indicator} {_short(res.get("title","Untitled"), 45)} ({_domain(url)})', {"url": url})
        notes = await llm.reflect(oi["brief"], [p.get("text","")[:500] for p in pages])
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
                    doc["score"] = 0.0
                    await db().sources.insert_one(doc)
                    pages.append(doc)
        kept_pages.extend(pages)
        await db().reflections.insert_one({
            "outlineItemId": oi_id,
            "round": r,
            "notes": notes.get("notes",""),
            "next_query": nxt
        })

    # cap and write paragraph
    kept_pages = kept_pages[:KEEP]
    
    # Add reflection message
    await emit_msg(run_id, role="assistant", kind="reflect", text=notes.get("notes",""), meta={
        "round": r
    })
    
    await db().outlineItems.update_one({"_id": oi_id}, {"$set": {"status": "drafting"}})
    await live.set_live(oi["runId"], "draft", f'Writing section {oi["idx"]}…')
    
    # Add drafting message
    await emit_msg(run_id, role="assistant", kind="draft", text=f"writing section {oi['idx']}")
    
    sources = kept_pages
    if len(sources) < 2:
        # one retry: alternate provider or broader query
        alt = await search.web_search(oi["brief"], top=6, provider="brave" if os.getenv("SEARCH_PROVIDER","serpapi")=="serpapi" else "serpapi")
        # fetch a few quickly
        fetched = []
        for r in alt[:4]:
            doc = await extract.fetch_and_extract(r.get("url",""))
            if doc:
                doc["title"] = r.get("title","")
                fetched.append(doc)
        sources = (sources + fetched)[:6]

    logger.info(f"🔧 Writing paragraph for section {oi['idx']} with {len(sources)} sources")
    try:
        para = await llm.write_paragraph(oi["brief"], sources)
        logger.info(f"🔧 Generated paragraph: {para.get('draftMd', '')[:100]}...")
    except Exception as e:
        logger.error(f"❌ Paragraph generation failed: {str(e)}")
        para = {"draftMd": f"Error generating paragraph: {str(e)}", "citations": {}, "quality": 0.0}
    
    # Log real failures and block placeholders
    md = para.get("draftMd","")
    if not md or "Cover aspect" in md:
        logger.error(f"writer returned weak paragraph; brief='{oi['brief'][:120]}', sources={len(sources)}")

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
        "quality": quality_score
    })
    # after inserting paragraph
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
            "roundsPerParagraph": run.get("config", {}).get("rounds", 2),
            "searchProvider": run.get("config", {}).get("searchProvider", "hybrid"),
            "totalSources": await db().sources.count_documents({"runId": rid}),
            "qualityScore": 0  # TODO: Calculate average quality score
        }
    }

