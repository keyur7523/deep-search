import asyncio
from typing import List, Dict, Any
from bson import ObjectId
from models.db import db
from services import llm, search, extract

async def start_run_task(run_id: str):
    runs = db().runs
    run = await runs.find_one({"_id": ObjectId(run_id)})
    if not run:
        return
    await runs.update_one({"_id": run["_id"]}, {"$set":{"status":"planning"}})

    project = await db().projects.find_one({"_id": run["projectId"]})
    topic = project.get("title","")
    n = project.get("maxParagraphs", 6)

    outline = await llm.plan_outline(topic, n)
    oi_ids: List[ObjectId] = []
    for item in outline[:n]:
        doc = {
            "runId": run["_id"],
            "idx": item.get("idx", len(oi_ids)+1),
            "heading": item.get("heading", f"Section {len(oi_ids)+1}"),
            "brief": item.get("brief", ""),
            "status": "queued"
        }
        res = await db().outlineItems.insert_one(doc)
        oi_ids.append(res.inserted_id)

    await runs.update_one({"_id": run["_id"]}, {"$set":{"status":"running"}})

    # process each outline item
    cfg = run.get("config", {})
    R = int(cfg.get("rounds", 2))
    TOP = int(cfg.get("resultsPerRound", 8))
    KEEP = int(cfg.get("keepPerParagraph", 6))

    for oi_id in oi_ids:
        await _work_outline_item(oi_id, R, TOP, KEEP)

    # aggregate
    paras = db().paragraphs.find({"runId": run["_id"]}).sort("idx", 1)
    paragraphs = [p async for p in paras]
    md = await llm.aggregate_report(topic, paragraphs)

    await db().reports.insert_one({
        "runId": run["_id"],
        "markdown": md,
        "toc": [],
        "summaryMd": ""
    })
    await runs.update_one({"_id": run["_id"]}, {"$set":{"status":"done"}})

async def _work_outline_item(oi_id: ObjectId, R: int, TOP: int, KEEP: int):
    oi = await db().outlineItems.find_one({"_id": oi_id})
    if not oi: return
    await db().outlineItems.update_one({"_id": oi_id}, {"$set":{"status":"searching"}})

    seen_urls: list[str] = []
    kept_pages: list[Dict[str,Any]] = []

    for r in range(1, R+1):
        q = await llm.propose_query(oi["brief"], seen_urls)
        await db().searchQueries.insert_one({
            "outlineItemId": oi_id,
            "round": r,
            "query": q.get("query",""),
            "rationale": q.get("rationale","")
        })
        results = await search.web_search(q.get("query",""), TOP) or []
        pages = []
        for res in results:
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
        notes = await llm.reflect(oi["brief"], [p.get("text","")[:500] for p in pages])
        nxt = notes.get("next_query")
        if nxt:  # optional second pass tweak
            results2 = await search.web_search(nxt, TOP//2) or []
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
    await db().outlineItems.update_one({"_id": oi_id}, {"$set":{"status":"drafting"}})
    para = await llm.write_paragraph(oi["brief"], kept_pages)
    await db().paragraphs.insert_one({
        "runId": oi["runId"],
        "outlineItemId": oi_id,
        "idx": oi["idx"],
        "draftMd": para.get("draftMd",""),
        "citations": para.get("citations", {}),
        "quality": float(para.get("quality", 0.0))
    })
    await db().outlineItems.update_one({"_id": oi_id}, {"$set":{"status":"done"}})

# --- Public helpers for endpoints ---
async def get_run_progress(run_id: str, user_sub: str):
    try:
        rid = ObjectId(run_id)
    except Exception:
        return None
    run = await db().runs.find_one({"_id": rid})
    if not run: return None
    cnt_total = await db().outlineItems.count_documents({"runId": rid})
    cnt_done = await db().outlineItems.count_documents({"runId": rid, "status":"done"})
    progress = 0 if cnt_total==0 else int(100 * cnt_done / cnt_total)
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
    rep = await db().reports.find_one({"runId": rid})
    if not rep: return None
    return {"markdown": rep.get("markdown","")}
