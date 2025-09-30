import os, asyncio
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId
from dotenv import load_dotenv
from models.db import db, ensure_indexes
from services.s3util import presign_put_url
from logic.research import start_run_task, get_run_progress, get_outline, get_report

load_dotenv()

app = FastAPI(title="Iris Research API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("WEB_ORIGIN", "*")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class User(BaseModel):
    sub: str

async def get_user(request: Request) -> User:
    # TODO: replace with JWT validation. For now, a static demo user is used.
    return User(sub="demo-user")

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
    try:
        await ensure_indexes()
    except Exception as e:
        print(f"Startup index error: {e}")

# --- Health ---
@app.get("/health")
async def health():
    return {"ok": True}

# --- Projects ---
@app.post("/projects")
async def create_project(p: NewProject, user: User = Depends(get_user)):
    doc = {
        "userId": user.sub,
        "title": p.title,
        "goalMd": p.goal,
        "maxParagraphs": p.maxParagraphs,
        "createdAt": asyncio.get_event_loop().time(),
    }
    res = await db().projects.insert_one(doc)
    return {"project_id": str(res.inserted_id)}

@app.post("/projects/{project_id}/runs")
async def create_run(project_id: str, cfg: NewRun, user: User = Depends(get_user)):
    try:
        pid = ObjectId(project_id)
    except Exception:
        raise HTTPException(400, "bad project id")
    project = await db().projects.find_one({"_id": pid, "userId": user.sub})
    if not project:
        raise HTTPException(404, "project not found")
    run_doc = {
        "projectId": pid,
        "status": "queued",
        "config": cfg.model_dump(),
        "createdAt": asyncio.get_event_loop().time(),
    }
    res = await db().runs.insert_one(run_doc)
    run_id = str(res.inserted_id)
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