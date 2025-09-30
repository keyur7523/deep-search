import os, asyncio
import logging
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from bson import ObjectId
from dotenv import load_dotenv
import json
from models.db import db, ensure_indexes
from services.s3util import presign_put_url
from logic.research import start_run_task, get_run_progress, get_outline, get_report

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()
logger.info("Environment variables loaded")

app = FastAPI(title="Deep Research API", version="0.1.0")
logger.info("FastAPI app created")

# Allow localhost for development and production Vercel URL
origins = [
    "http://localhost:3000",
    "http://localhost:3001", 
    "http://localhost:3002",
    "http://localhost:3003",
    "https://deep-search-ruby.vercel.app",
    "https://deep-search.vercel.app",  # Alternative Vercel URL
    *[o.strip() for o in os.getenv("WEB_ORIGINS", "").split(",") if o.strip()]
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # e.g. ["http://localhost:3001", "http://localhost:3000"]
    allow_credentials=True,         # only if you send cookies/Authorization
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info(f"CORS origins configured: {origins}")

class User(BaseModel):
    sub: str

async def get_user(request: Request) -> User:
    # TODO: replace with JWT validation. For now, a static demo user is used.
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

@app.on_event("startup")
async def _startup():
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
    
    if api_key:
        logger.info(f"🔑 API Key starts with: {api_key[:10]}...")
    else:
        logger.error("❌ LLM_API_KEY is not set!")
    
    try:
        logger.info("📊 Ensuring database indexes...")
        await ensure_indexes()
        logger.info("✅ Database indexes created successfully")
    except Exception as e:
        logger.error(f"❌ Startup index error: {e}")
        logger.warning("⚠️ Continuing startup despite index error...")
    
    logger.info("🎉 Deep Research API startup complete!")

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

# --- Projects ---
@app.post("/projects")
async def create_project(p: NewProject, user: User = Depends(get_user)):
    logger.info(f"📝 Creating new project: '{p.title}' for user: {user.sub}")
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
        })
    return {"runs": runs}

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
            while True:
                doc = await db().liveStatus.find_one({"runId": rid})
                if doc and (not last_iso or doc["ts"].isoformat() != last_iso):
                    last_iso = doc["ts"].isoformat()
                    yield f"data: {json.dumps(_ser_live(doc))}\n\n"
                else:
                    yield ": keep-alive\n\n"
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

# uvicorn app:app --host 0.0.0.0 --port 8000