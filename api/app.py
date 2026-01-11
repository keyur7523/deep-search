import os, asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import json
from pydantic import BaseModel, Field
from bson import ObjectId
from dotenv import load_dotenv
import json
from models.db import db, ensure_indexes
from services.s3util import presign_put_url
from logic.research import start_run_task, get_run_progress, get_outline, get_report, get_research_threads, get_research_messages, get_research_thread
from agents.research_agentic import start_agentic_run
from models.schemas import (
    CreateRunRequest, AgentModeRequest,
    AgentGraphResponse, AgentGraphNode, AgentGraphEdge
)
from models.db import init_agent_collections, create_agent_event
from agents import route_research_mode, explain_routing_decision

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()
logger.info("Environment variables loaded")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("🚀 Starting up Deep Research API...")

    # Check environment variables
    logger.info("🔍 Checking environment variables...")
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    model_planner = os.getenv("LLM_MODEL_PLANNER", "gpt-4o-mini")
    model_writer = os.getenv("LLM_MODEL_WRITER", "gpt-4o-mini")

    logger.info(f"🔑 LLM_API_KEY: {'✅ Set' if api_key else '❌ Missing'}")
    logger.info(f"🌐 LLM_BASE_URL: {base_url}")
    logger.info(f"🧠 LLM_MODEL_PLANNER: {model_planner}")
    logger.info(f"✍️ LLM_MODEL_WRITER: {model_writer}")

    if not api_key:
        logger.error("❌ LLM_API_KEY is not set!")

    try:
        logger.info("📊 Ensuring database indexes...")
        await ensure_indexes()
        logger.info("✅ Database indexes created successfully")

        # Initialize agent collections
        logger.info("🤖 Initializing agent collections...")
        await init_agent_collections()
        logger.info("✅ Agent collections initialized")
    except Exception as e:
        logger.error(f"❌ Startup index error: {e}")
        logger.warning("⚠️ Continuing startup despite index error...")

    logger.info("🎉 Deep Research API startup complete!")

    yield  # Application runs here

    # Shutdown (if needed)
    logger.info("👋 Shutting down Deep Research API...")

app = FastAPI(title="Deep Research API", version="0.1.0", lifespan=lifespan)
logger.info("FastAPI app created")

# Allow localhost for development and production URLs
# SECURITY: Always explicitly configure allowed origins via WEB_ORIGINS env var
origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:3003",
    "https://deep-search-ruby.vercel.app",
    "https://deep-search-lovat.vercel.app",
    "https://deep-search-two.vercel.app",
    # Add additional origins via WEB_ORIGINS env var (comma-separated)
    *[o.strip() for o in os.getenv("WEB_ORIGINS", "").split(",") if o.strip()]
]

# SECURITY: Never use "*" for CORS in production
# If you need additional origins on Render, add them via WEB_ORIGINS env var
if os.getenv("RENDER"):
    logger.info("Running on Render - ensure WEB_ORIGINS is configured for production")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
logger.info(f"CORS origins configured: {origins}")

class User(BaseModel):
    sub: str

# SECURITY WARNING: This is a placeholder authentication.
# In production, implement proper JWT validation or OAuth2.
# Current implementation allows ALL requests as "demo-user".
_AUTH_WARNING_LOGGED = False

async def get_user(request: Request) -> User:
    """
    SECURITY: Replace with proper authentication before production use!

    Recommended implementations:
    - JWT validation with proper secret key
    - OAuth2 with your identity provider
    - API key validation for service-to-service calls
    """
    global _AUTH_WARNING_LOGGED
    if not _AUTH_WARNING_LOGGED and os.getenv("RENDER"):
        logger.warning("⚠️ SECURITY: Using demo authentication in production! Implement proper auth.")
        _AUTH_WARNING_LOGGED = True
    return User(sub="demo-user")

def _ser_live(doc):
    if not doc: return {}
    out = dict(doc)
    out["_id"] = str(out.get("_id",""))
    out["runId"] = str(out["runId"])
    # ts is datetime; serialize ISO
    if "ts" in out:
        out["ts"] = out["ts"].isoformat()
    return out

class NewProject(BaseModel):
    title: str
    goal: str = Field(default="")
    maxParagraphs: int = Field(default=int(os.getenv("MAX_PARAGRAPHS", 6)))

class NewRun(BaseModel):
    rounds: int = Field(default=int(os.getenv("ROUNDS_PER_PARAGRAPH", 2)))
    resultsPerRound: int = Field(default=int(os.getenv("RESULTS_PER_ROUND", 8)))
    keepPerParagraph: int = Field(default=int(os.getenv("KEEP_PER_PARAGRAPH", 6)))
    searchProvider: str = Field(default="hybrid")

# --- Root and Health ---
@app.get("/")
async def root():
    return {
        "message": "Deep Research API", 
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
async def health():
    return {"ok": True}

# Handle CORS preflight requests manually
@app.options("/{path:path}")
async def options_handler(path: str):
    return {"message": "OK"}

# --- Projects ---
@app.post("/projects")
async def create_project(request: Request, user: User = Depends(get_user)):
    try:
        # Get the raw body
        body = await request.body()
        logger.info(f"📝 Raw body: {body}")
        
        # Parse JSON
        import json
        data = json.loads(body.decode())
        logger.info(f"📝 Parsed data: {data}")
        
        # Validate the data
        p = NewProject(**data)
        logger.info(f"📝 Validated project: title='{p.title}', goal='{p.goal}', maxParagraphs={p.maxParagraphs}")
        
        doc = {
            "userId": user.sub,
            "title": p.title,
            "goalMd": p.goal,
            "maxParagraphs": p.maxParagraphs,
            "createdAt": asyncio.get_event_loop().time(),
        }
        res = await db().projects.insert_one(doc)
        project_id = str(res.inserted_id)
        logger.info(f"✅ Project created successfully with ID: {project_id}")
        return {"project_id": project_id}
        
    except Exception as e:
        logger.error(f"📝 Error creating project: {e}")
        raise HTTPException(status_code=422, detail=str(e))

@app.post("/projects/{project_id}/runs")
async def create_run(project_id: str, cfg: NewRun, user: User = Depends(get_user)):
    logger.info(f"🏃 Starting new research run for project: {project_id}")
    try:
        pid = ObjectId(project_id)
        logger.info(f"✅ Valid project ID: {project_id}")
    except Exception:
        logger.error(f"❌ Invalid project ID format: {project_id}")
        raise HTTPException(400, "bad project id")
    
    project = await db().projects.find_one({"_id": pid, "userId": user.sub})
    if not project:
        logger.error(f"❌ Project not found: {project_id} for user: {user.sub}")
        raise HTTPException(404, "project not found")
    
    logger.info(f"📋 Found project: '{project.get('title', 'Unknown')}'")
    run_doc = {
        "projectId": pid,
        "status": "queued",
        "config": cfg.model_dump(),
        "createdAt": asyncio.get_event_loop().time(),
    }
    res = await db().runs.insert_one(run_doc)
    run_id = str(res.inserted_id)
    logger.info(f"🚀 Created run with ID: {run_id}, starting background task...")
    asyncio.create_task(start_run_task(run_id))  # fire and forget
    return {"run_id": run_id}

# --- Progress + data ---
@app.get("/runs/{run_id}/status")
async def run_status(run_id: str, user: User = Depends(get_user)):
    data = await get_run_progress(run_id, user.sub)
    if not data: raise HTTPException(404, "run not found")
    return data

@app.get("/runs/{run_id}/outline")
async def run_outline(run_id: str, user: User = Depends(get_user)):
    items = await get_outline(run_id, user.sub)
    return {"items": items}

@app.get("/runs/{run_id}/report")
async def run_report(run_id: str, user: User = Depends(get_user)):
    rep = await get_report(run_id, user.sub)
    if not rep: raise HTTPException(404, "report not ready")
    return rep

@app.get("/runs/{run_id}/assets")
async def run_assets(run_id: str, user: User = Depends(get_user)):
    """Get all visual assets (figures, diagrams) for a run"""
    try:
        rid = ObjectId(run_id)
    except Exception:
        raise HTTPException(400, "invalid run id")
    
    assets_cursor = db().assets.find({"runId": rid}).sort("outlineItemId", 1)
    assets = []
    async for asset in assets_cursor:
        assets.append({
            "_id": str(asset["_id"]),
            "outlineItemId": str(asset.get("outlineItemId", "")),
            "type": asset.get("type", "image"),
            "caption": asset.get("caption", ""),
            "ocrText": asset.get("ocrText", ""),
            "imageUrl": asset.get("imageUrl", asset.get("sourceUrl", "")),
            "tags": asset.get("tags", []),
            "meta": asset.get("meta", {})
        })
    
    return {"assets": assets}

@app.get("/runs/{run_id}/sources")
async def run_sources(run_id: str, user: User = Depends(get_user)):
    """Get all sources used in a research run"""
    try:
        rid = ObjectId(run_id)
    except Exception:
        raise HTTPException(400, "invalid run id")
    
    # Get all sources for this run
    sources_cursor = db().sources.find({"runId": rid}).sort([("score", -1), ("_id", 1)])
    sources = []
    
    async for source in sources_cursor:
        # Get the outline item to know which section this source belongs to
        outline_item = None
        if source.get("outlineItemId"):
            outline_item = await db().outlineItems.find_one({"_id": source["outlineItemId"]})
        
        sources.append({
            "_id": str(source["_id"]),
            "url": source.get("url", ""),
            "title": source.get("title", "Untitled"),
            "type": source.get("type", "web"),
            "authors": source.get("authors", ""),
            "year": source.get("year", ""),
            "venue": source.get("venue", ""),
            "citations": source.get("citations", 0),
            "score": source.get("score", 0.0),
            "textLength": len(source.get("text", "")),
            "sectionTitle": outline_item.get("heading", "") if outline_item else "",
            "sectionIdx": outline_item.get("idx", 0) if outline_item else 0
        })
    
    # Get unique sources (deduplicate by URL)
    unique_sources = {}
    for src in sources:
        url = src["url"]
        if url not in unique_sources or src["score"] > unique_sources[url]["score"]:
            unique_sources[url] = src
    
    return {
        "sources": list(unique_sources.values()),
        "total": len(unique_sources),
        "academic": len([s for s in unique_sources.values() if s["type"] == "academic"]),
        "web": len([s for s in unique_sources.values() if s["type"] == "web"])
    }

@app.get("/runs/{run_id}/paragraphs")
async def run_paragraphs(run_id: str, user: User = Depends(get_user)):
    """Get individual paragraphs for a run"""
    try:
        rid = ObjectId(run_id)
    except Exception:
        raise HTTPException(400, "bad run id")
    
    cur = db().paragraphs.find({"runId": rid}).sort("idx", 1)
    paragraphs = []
    async for p in cur:
        paragraphs.append({
            "_id": str(p["_id"]),
            "idx": p["idx"],
            "draftMd": p.get("draftMd", ""),
            "quality": p.get("quality", 0.0),
            "citations": p.get("citations", {})
        })
    return {"paragraphs": paragraphs}

@app.get("/runs")
async def list_runs(user: User = Depends(get_user), limit: int = Query(5, ge=1, le=20)):
    """List recent runs for the user"""
    # For now, get all runs since userId filtering isn't working
    runs_cursor = db().runs.find().sort("createdAt", -1).limit(limit)
    runs = []
    async for run in runs_cursor:
        # Get topic from project if available
        topic = "Unknown Topic"
        if run.get("projectId"):
            project = await db().projects.find_one({"_id": run["projectId"]})
            if project:
                topic = project.get("title", "Unknown Topic")
        
        runs.append({
            "id": str(run["_id"]),
            "topic": topic,
            "status": "completed" if run.get("status") == "done" else run.get("status", "unknown"),
            "progress": run.get("progress", 100 if run.get("status") == "done" else 0),
            "createdAt": run.get("createdAt"),
            "mode": run.get("mode", "unknown"),
            "routing": run.get("routing", {})
        })
    return {"runs": runs}

# New Research Thread endpoints
@app.get("/research/threads")
async def get_threads(user: User = Depends(get_user), limit: int = Query(20, ge=1, le=100)):
    """Get research threads for the user"""
    threads = await get_research_threads(user.sub, limit)
    return {"threads": threads}

@app.get("/research/threads/{thread_id}/messages")
async def get_messages(thread_id: str, user: User = Depends(get_user), limit: int = Query(50, ge=1, le=200)):
    """Get messages for a specific research thread"""
    messages = await get_research_messages(thread_id, user.sub, limit)
    return {"messages": messages}

@app.get("/research/threads/{thread_id}")
async def get_thread(thread_id: str, user: User = Depends(get_user)):
    """Get a specific research thread with full details"""
    thread = await get_research_thread(thread_id, user.sub)
    if not thread:
        raise HTTPException(404, "thread not found")
    return thread

def _ser(m):
    out = dict(m); out["_id"] = str(out["_id"]); out["runId"] = str(out["runId"])
    if "t" in out: out["t"] = out["t"].isoformat()
    return out

@app.get("/runs/{run_id}/events/stream")
async def events_stream(run_id: str):
    try:
        rid = ObjectId(run_id)
    except Exception as e:
        logger.error(f"Invalid run_id: {run_id}")
        raise HTTPException(400, "Invalid run ID")
    
    async def gen():
        # backlog
        cursor = db().researchMessages.find({"runId": rid}).sort("t", 1)
        async for m in cursor:
            yield f"data: {json.dumps(_ser(m))}\n\n"
        # live: change streams if available, else poll
        try:
            pipeline = [{"$match": {"fullDocument.runId": rid}}]
            async with db().researchMessages.watch(pipeline=pipeline, full_document="updateLookup") as cs:
                async for ch in cs:
                    yield f"data: {json.dumps(_ser(ch['fullDocument']))}\n\n"
        except Exception:
            last_id = None
            poll_count = 0
            max_polls = 600  # Exit after ~10 minutes of polling
            while poll_count < max_polls:
                poll_count += 1
                q = {"runId": rid}
                if last_id: q["_id"] = {"$gt": last_id}
                cursor = db().researchMessages.find(q).sort("_id", 1)
                async for m in cursor:
                    last_id = m["_id"]; yield f"data: {json.dumps(_ser(m))}\n\n"
                # Check if run is done
                run = await db().runs.find_one({"_id": rid})
                if run and run.get("status") in ["done", "failed"]:
                    yield f"data: {json.dumps({'done': True, 'status': run.get('status')})}\n\n"
                    break
                yield ": keep-alive\n\n"
                await asyncio.sleep(1.0)
    headers = {"Cache-Control":"no-cache","Connection":"keep-alive"}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)

@app.get("/runs/{run_id}/messages")
async def list_messages(run_id: str, since_id: str|None = Query(None, alias="sinceId")):
    try:
        rid = ObjectId(run_id)
        q = {"runId": rid}
        if since_id: 
            q["_id"] = {"$gt": ObjectId(since_id)}
        cur = db().researchMessages.find(q).sort("_id", 1).limit(500)
        out = [ _ser(m) async for m in cur ]
        return {"items": out}
    except Exception as e:
        logger.error(f"Error fetching messages for run {run_id}: {e}")
        return {"items": []}

@app.get("/runs/{run_id}/live/stream")
async def live_stream(run_id: str):
    rid = ObjectId(run_id)
    async def gen():
        # send current snapshot
        cur = await db().liveStatus.find_one({"runId": rid})
        if cur:
            yield f"data: {json.dumps(_ser_live(cur))}\n\n"
        # try change streams; fallback to polling
        try:
            pipeline=[{"$match":{"fullDocument.runId": rid}}]
            async with db().liveStatus.watch(pipeline=pipeline, full_document="updateLookup") as cs:
                async for ch in cs:
                    yield f"data: {json.dumps(_ser_live(ch['fullDocument']))}\n\n"
        except Exception:
            last_iso = cur["ts"].isoformat() if cur and "ts" in cur else None
            poll_count = 0
            max_polls = 600  # Exit after ~10 minutes of polling
            while poll_count < max_polls:
                poll_count += 1
                doc = await db().liveStatus.find_one({"runId": rid})
                if doc and (not last_iso or doc["ts"].isoformat() != last_iso):
                    last_iso = doc["ts"].isoformat()
                    yield f"data: {json.dumps(_ser_live(doc))}\n\n"
                else:
                    yield ": keep-alive\n\n"
                # Check if run is done
                run = await db().runs.find_one({"_id": rid})
                if run and run.get("status") in ["done", "failed"]:
                    yield f"data: {json.dumps({'done': True, 'status': run.get('status')})}\n\n"
                    break
                await asyncio.sleep(1.0)

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive"}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)

# --- S3 presign ---
@app.get("/s3/presign")
async def s3_presign(
    key: str = Query(..., description="S3 object key"),
    content_type: str = Query("application/octet-stream"),
    user: User = Depends(get_user),
):
    url = presign_put_url(key, content_type)
    return {"url": url}

@app.post("/runs")
async def create_run_v2(
    request: CreateRunRequest,
    user: User = Depends(get_user)
):
    """
    Create research run with automatic simple/agentic routing.
    
    Body:
        projectId: MongoDB project ID
        config: {
            forceMode?: "simple" | "agentic"  // Override routing
            deepMode?: boolean                 // Request thorough research
            minCitations?: number              // Minimum sources required
            requireRecent?: boolean            // Prioritize recent papers
            maxParagraphs?: number             // Report length
        }
    """
    logger.info(f"🔄 V2 run creation for project: {request.projectId}")
    
    try:
        pid = ObjectId(request.projectId)
    except Exception:
        raise HTTPException(400, "Invalid project ID")
    
    # Get project to extract topic
    project = await db().projects.find_one({"_id": pid, "userId": user.sub})
    if not project:
        raise HTTPException(404, "Project not found")
    
    topic = project.get("title", "")
    logger.info(f"📋 Topic: {topic}")
    
    # Determine mode using coordinator
    mode = route_research_mode(topic, request.config)
    routing_info = explain_routing_decision(topic, request.config)
    logger.info(f"🎯 Routing decision: {mode} (score: {routing_info['score']})")
    logger.info(f"💡 Reasoning: {routing_info['reasoning']}")
    
    # Create run document
    from datetime import datetime
    run_doc = {
        "projectId": pid,
        "status": "queued",
        "mode": mode,
        "config": request.config,
        "routing": routing_info,
        "createdAt": asyncio.get_event_loop().time(),
    }
    res = await db().runs.insert_one(run_doc)
    run_id = str(res.inserted_id)
    
    # Dispatch to appropriate pipeline
    if mode == "simple":
        logger.info(f"🚀 Starting simple pipeline for run: {run_id}")
        asyncio.create_task(start_run_task(run_id))
    else:
        logger.info(f"🤖 Starting agentic pipeline for run: {run_id}")
        asyncio.create_task(start_agentic_run(run_id))
    
    return {
        "run_id": run_id,
        "mode": mode,
        "routing": routing_info
    }

@app.post("/runs/{run_id}/agent-mode")
async def set_agent_mode(
    run_id: str, 
    request: AgentModeRequest,
    user: User = Depends(get_user)
):
    """
    Override agent mode for a run.
    Only works before run starts.
    """
    try:
        rid = ObjectId(run_id)
    except Exception:
        raise HTTPException(400, "Invalid run ID")
    
    run = await db().runs.find_one({"_id": rid})
    if not run:
        raise HTTPException(404, "Run not found")
    
    if run.get("status") not in ["queued", "planning"]:
        raise HTTPException(
            400, 
            detail="Cannot change mode after run has started"
        )
    
    await db().runs.update_one(
        {"_id": rid},
        {"$set": {"mode": request.mode}}
    )
    
    logger.info(f"🔄 Mode changed to {request.mode} for run: {run_id}")
    return {"status": "ok", "mode": request.mode}

@app.get("/runs/{run_id}/graph", response_model=AgentGraphResponse)
async def get_task_graph(run_id: str, user: User = Depends(get_user)):
    """
    Return current task DAG for visualization.
    
    Response:
        nodes: [{id, type, status, label}]
        edges: [{source, target}]
    """
    try:
        rid = ObjectId(run_id)
    except Exception:
        raise HTTPException(400, "Invalid run ID")
    
    tasks = await db().agentTasks.find(
        {"runId": rid}
    ).to_list(length=None)
    
    if not tasks:
        return AgentGraphResponse(nodes=[], edges=[])
    
    # Build nodes
    nodes = []
    for task in tasks:
        nodes.append(AgentGraphNode(
            id=str(task["_id"]),
            type=task["type"],
            status=task["status"],
            label=f"{task['type']} ({task['status']})"
        ))
    
    # Build edges from parent relationships
    edges = []
    for task in tasks:
        if task.get("parentId"):
            edges.append(AgentGraphEdge(
                source=str(task["parentId"]),
                target=str(task["_id"])
            ))
    
    return AgentGraphResponse(nodes=nodes, edges=edges)

@app.get("/runs/{run_id}/agent-events/stream")
async def stream_agent_events(run_id: str):
    """
    Server-Sent Events stream of agent activities.
    
    Events:
        data: {"agent": "Strategy", "kind": "thinking", "text": "...", ...}
    """
    try:
        rid = ObjectId(run_id)
    except Exception:
        raise HTTPException(400, "Invalid run ID")
    
    async def event_generator():
        from datetime import datetime
        
        # Send existing events first
        existing = await db().agentEvents.find(
            {"runId": rid}
        ).sort("timestamp", 1).to_list(length=100)
        
        for event in existing:
            event["id"] = str(event["_id"])
            event["runId"] = str(event["runId"])
            event["taskId"] = str(event["taskId"])
            yield f"data: {json.dumps(event, default=str)}\n\n"
        
        # Then poll for new events
        last_seen = existing[-1]["timestamp"] if existing else datetime.utcnow()
        
        while True:
            new_events = await db().agentEvents.find({
                "runId": rid,
                
                "timestamp": {"$gt": last_seen}
            }).sort("timestamp", 1).to_list(length=10)
            
            for event in new_events:
                event["id"] = str(event["_id"])
                event["runId"] = str(event["runId"])
                event["taskId"] = str(event["taskId"])
                yield f"data: {json.dumps(event, default=str)}\n\n"
                last_seen = event["timestamp"]
            
            # Check if run is done
            run = await db().runs.find_one({"_id": rid})
            if run and run.get("status") == "done":
                yield "data: {\"done\": true}\n\n"
                break
            
            await asyncio.sleep(1)  # Poll every second
    
    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive"}
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=headers
    )
    

    

    

# uvicorn app:app --host 0.0.0.0 --port 8000