# api/models/db.py

import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from typing import Optional
from datetime import datetime
from bson import ObjectId

logger = logging.getLogger(__name__)

load_dotenv()
logger.info("📚 Database module loaded, environment variables loaded")

_client = None
_dbname = os.getenv("MONGODB_DB", "deep-search")
logger.info(f"🗄️ Database name configured: {_dbname}")
_db = None

def get_client():
    global _client
    if _client is None:
        logger.info("🔌 Creating new MongoDB client connection...")
        mongodb_uri = os.getenv("MONGODB_URI")
        if not mongodb_uri:
            logger.error("❌ MONGODB_URI environment variable not set")
            raise RuntimeError("MONGODB_URI not set")
        
        logger.info(f"🔗 Connecting to MongoDB Atlas...")
        logger.info(f"🔐 URI: {mongodb_uri[:20]}...{mongodb_uri[-10:]}")
        _client = AsyncIOMotorClient(
            mongodb_uri, 
            serverSelectionTimeoutMS=5000,
            tlsCAFile=None,
            tlsAllowInvalidCertificates=True
        )
        logger.info("✅ MongoDB client created successfully")
    return _client

def db():
    return get_client()[_dbname]

async def ensure_indexes():
    logger.info("📊 Starting database index creation...")
    try:
        database = db()
        logger.info(f"🗄️ Using database: {database.name}")
        
        logger.info("📇 Creating sources collection indexes...")
        await database.sources.create_index("hash", unique=False)
        await database.sources.create_index([("outlineItemId", 1), ("score", -1)])
        logger.info("✅ Sources indexes created")
        
        logger.info("🔍 Creating searchQueries collection indexes...")
        await database.searchQueries.create_index([("outlineItemId", 1), ("round", 1)])
        logger.info("✅ SearchQueries indexes created")
        
        logger.info("📄 Creating paragraphs collection indexes...")
        await database.paragraphs.create_index([("outlineItemId", 1)])
        logger.info("✅ Paragraphs indexes created")
        
        logger.info("🏃 Creating runs collection indexes...")
        await database.runs.create_index([("projectId", 1), ("createdAt", -1)])
        logger.info("✅ Runs indexes created")
        
        logger.info("📡 Creating liveStatus collection indexes...")
        await database.liveStatus.create_index([("runId", 1)], unique=True)
        await database.liveStatus.create_index("ts", expireAfterSeconds=1800)
        logger.info("✅ LiveStatus indexes created")
        
        logger.info("💬 Creating researchMessages collection indexes...")
        await database.researchMessages.create_index([("runId", 1), ("t", 1)])
        await database.researchMessages.create_index([("runId", 1), ("_id", 1)])
        logger.info("✅ ResearchMessages indexes created")
        
        logger.info("🖼️ Creating assets collection indexes...")
        await database.assets.create_index([("runId", 1), ("outlineItemId", 1)])
        await database.assets.create_index([("runId", 1)])
        logger.info("✅ Assets indexes created")
        
        # NEW: Agent collections
        logger.info("🤖 Creating agentTasks collection indexes...")
        await database.agentTasks.create_index([
            ("runId", 1),
            ("status", 1),
            ("createdAt", -1)
        ])
        await database.agentTasks.create_index([("parentId", 1)])
        await database.agentTasks.create_index([("type", 1)])
        logger.info("✅ AgentTasks indexes created")
        
        logger.info("📋 Creating agentEvents collection indexes...")
        await database.agentEvents.create_index([
            ("runId", 1),
            ("timestamp", 1)
        ])
        await database.agentEvents.create_index([("taskId", 1)])
        logger.info("✅ AgentEvents indexes created")
        
        logger.info("🎉 All database indexes created successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error creating database indexes: {e}")
        raise

# ============= NEW: Agent Helper Functions =============

async def init_agent_collections():
    """Create indexes for agent-related collections"""
    database = db()
    
    # agentTasks collection
    await database.agentTasks.create_index([
        ("runId", 1),
        ("status", 1),
        ("createdAt", -1)
    ])
    await database.agentTasks.create_index([("parentId", 1)])
    await database.agentTasks.create_index([("type", 1)])
    
    # agentEvents collection
    await database.agentEvents.create_index([
        ("runId", 1),
        ("timestamp", 1)
    ])
    await database.agentEvents.create_index([("taskId", 1)])
    
    print("✅ Agent collections initialized")

async def create_agent_task(
    run_id: str,
    task_type: str,
    payload: dict,
    parent_id: Optional[str] = None
) -> str:
    """
    Insert a new agent task and return its ID.
    
    Args:
        run_id: MongoDB ObjectId of the run
        task_type: Type of task (STRATEGY, DISCOVERY, WRITER, etc.)
        payload: Task-specific data
        parent_id: Optional parent task ID for dependency tracking
    
    Returns:
        String ID of created task
    """
    task_doc = {
        "runId": ObjectId(run_id),
        "type": task_type,
        "payload": payload,
        "status": "pending",
        "parentId": ObjectId(parent_id) if parent_id else None,
        "attempts": 0,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow()
    }
    
    result = await db().agentTasks.insert_one(task_doc)
    logger.info(f"✅ Created agent task: {task_type} (ID: {result.inserted_id})")
    return str(result.inserted_id)

async def update_task_status(
    task_id: str, 
    status: str, 
    result: Optional[dict] = None
):
    """
    Update task status and optionally store execution result.
    
    Args:
        task_id: MongoDB ObjectId of the task
        status: New status (pending, running, done, failed)
        result: Optional result data to store
    """
    update_doc = {
        "$set": {
            "status": status,
            "updatedAt": datetime.utcnow()
        }
    }
    
    if result:
        update_doc["$set"]["result"] = result
    
    await db().agentTasks.update_one(
        {"_id": ObjectId(task_id)},
        update_doc
    )
    logger.debug(f"Updated task {task_id} status to {status}")

async def increment_task_attempts(task_id: str):
    """Increment retry attempt counter for a task"""
    await db().agentTasks.update_one(
        {"_id": ObjectId(task_id)},
        {
            "$inc": {"attempts": 1},
            "$set": {"updatedAt": datetime.utcnow()}
        }
    )

async def create_agent_event(
    run_id: str,
    task_id: str,
    agent: str,
    kind: str,
    text: str,
    meta: Optional[dict] = None
):
    """
    Insert an agent event for streaming to UI.
    
    Args:
        run_id: MongoDB ObjectId of the run
        task_id: MongoDB ObjectId of the task
        agent: Name of the agent (Strategy, Discovery, Writer, etc.)
        kind: Event type (thinking, action, result, error)
        text: Human-readable event description
        meta: Optional metadata dict
    """
    event_doc = {
        "runId": ObjectId(run_id),
        "taskId": ObjectId(task_id),
        "agent": agent,
        "kind": kind,
        "text": text,
        "meta": meta or {},
        "timestamp": datetime.utcnow()
    }
    
    result = await db().agentEvents.insert_one(event_doc)
    logger.debug(f"📝 Agent event: [{agent}] {kind}: {text[:50]}")
    return str(result.inserted_id)

async def get_pending_tasks(run_id: str, limit: int = 10) -> list:
    """
    Get pending tasks that are ready to run (no pending parents).
    
    Args:
        run_id: MongoDB ObjectId of the run
        limit: Maximum number of tasks to return
    
    Returns:
        List of task documents ready for execution
    """
    # Get all tasks for this run
    all_tasks = await db().agentTasks.find({
        "runId": ObjectId(run_id)
    }).to_list(length=None)
    
    if not all_tasks:
        return []
    
    # Build task map for quick lookup
    task_map = {str(t["_id"]): t for t in all_tasks}
    
    # Find runnable tasks (pending with no pending parents)
    runnable = []
    
    for task in all_tasks:
        if task["status"] != "pending":
            continue
        
        # Check if parent is done (if exists)
        parent_id = task.get("parentId")
        if parent_id:
            parent = task_map.get(str(parent_id))
            if not parent or parent["status"] not in ["done"]:
                continue  # Parent not ready
        
        runnable.append(task)
        if len(runnable) >= limit:
            break
    
    return runnable

async def has_pending_tasks(run_id: str) -> bool:
    """Check if run has any pending or running tasks"""
    count = await db().agentTasks.count_documents({
        "runId": ObjectId(run_id),
        "status": {"$in": ["pending", "running"]}
    })
    return count > 0

async def get_task_by_id(task_id: str):
    """Get task document by ID"""
    return await db().agentTasks.find_one({"_id": ObjectId(task_id)})

async def get_tasks_for_run(run_id: str):
    """Get all tasks for a run"""
    return await db().agentTasks.find({
        "runId": ObjectId(run_id)
    }).to_list(length=None)

async def get_events_for_run(run_id: str, since: Optional[datetime] = None):
    """Get agent events for a run, optionally since a timestamp"""
    query = {"runId": ObjectId(run_id)}
    if since:
        query["timestamp"] = {"$gt": since}
    
    return await db().agentEvents.find(query).sort("timestamp", 1).to_list(length=100)

