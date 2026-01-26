# api/models/db.py

import os
import logging
from contextlib import asynccontextmanager
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from typing import Optional, List, Callable, Any
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
        # Use certifi for proper TLS certificate validation
        import certifi
        _client = AsyncIOMotorClient(
            mongodb_uri,
            serverSelectionTimeoutMS=5000,
            tlsCAFile=certifi.where()
        )
        logger.info("✅ MongoDB client created successfully")
    return _client

def db():
    return get_client()[_dbname]


# ============= Transaction Support =============

@asynccontextmanager
async def transaction():
    """
    Context manager for MongoDB transactions.

    Provides atomic multi-document operations with automatic
    retry on transient errors.

    Usage:
        async with transaction() as session:
            await db().collection1.delete_many({"field": value}, session=session)
            await db().collection2.delete_many({"field": value}, session=session)
            # All operations committed together or rolled back on error

    Note: Requires MongoDB 4.0+ with replica set (MongoDB Atlas supports this)
    """
    client = get_client()
    async with await client.start_session() as session:
        async with session.start_transaction():
            try:
                yield session
                # Transaction commits automatically when context exits normally
            except Exception as e:
                # Transaction aborts automatically on exception
                logger.error(f"Transaction failed, rolling back: {e}")
                raise


async def run_in_transaction(operations: Callable[[Any], Any], max_retries: int = 3):
    """
    Execute operations in a transaction with automatic retry.

    Args:
        operations: Async function that takes a session and performs DB operations
        max_retries: Maximum retry attempts on transient errors

    Returns:
        Result of the operations function

    Example:
        async def delete_run_data(session):
            await db().sources.delete_many({"runId": rid}, session=session)
            await db().runs.delete_one({"_id": rid}, session=session)
            return True

        result = await run_in_transaction(delete_run_data)
    """
    from pymongo.errors import (
        ConnectionFailure,
        OperationFailure
    )

    client = get_client()

    for attempt in range(max_retries):
        async with await client.start_session() as session:
            try:
                async with session.start_transaction():
                    result = await operations(session)
                    return result
            except (ConnectionFailure, OperationFailure) as e:
                # Check if error is transient and retryable
                if hasattr(e, 'has_error_label') and e.has_error_label('TransientTransactionError'):
                    logger.warning(f"Transient transaction error (attempt {attempt + 1}): {e}")
                    if attempt < max_retries - 1:
                        continue
                raise
            except Exception as e:
                logger.error(f"Transaction failed: {e}")
                raise

    raise RuntimeError(f"Transaction failed after {max_retries} attempts")


async def delete_run_atomically(run_id: ObjectId) -> bool:
    """
    Delete a run and all associated data atomically.

    Uses a MongoDB transaction to ensure all-or-nothing deletion.
    If any delete fails, all changes are rolled back.

    Args:
        run_id: ObjectId of the run to delete

    Returns:
        True if deletion was successful

    Raises:
        Exception: If deletion fails (data remains unchanged)
    """
    logger.info(f"Starting atomic deletion of run: {run_id}")

    async def delete_operations(session):
        database = db()

        # Get outline item IDs first (within transaction)
        outline_cursor = database.outlineItems.find(
            {"runId": run_id},
            {"_id": 1},
            session=session
        )
        outline_ids = [item["_id"] async for item in outline_cursor]

        # Delete all related data in order
        if outline_ids:
            await database.reflections.delete_many(
                {"outlineItemId": {"$in": outline_ids}},
                session=session
            )
            await database.searchQueries.delete_many(
                {"outlineItemId": {"$in": outline_ids}},
                session=session
            )

        # Delete run-level collections
        collections_to_delete = [
            "outlineItems",
            "paragraphs",
            "sources",
            "assets",
            "reports",
            "researchMessages",
            "liveStatus",
            "agentTasks",
            "agentEvents"
        ]

        for collection_name in collections_to_delete:
            collection = database[collection_name]
            result = await collection.delete_many({"runId": run_id}, session=session)
            logger.debug(f"Deleted {result.deleted_count} documents from {collection_name}")

        # Finally delete the run itself
        result = await database.runs.delete_one({"_id": run_id}, session=session)
        if result.deleted_count == 0:
            raise RuntimeError(f"Run {run_id} not found for deletion")

        logger.info(f"Successfully deleted run {run_id} and all associated data")
        return True

    return await run_in_transaction(delete_operations)


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

        # Idempotency keys collection - for preventing duplicate run creation
        logger.info("🔑 Creating idempotencyKeys collection indexes...")
        await database.idempotencyKeys.create_index("key", unique=True)
        # Auto-expire keys after 24 hours
        await database.idempotencyKeys.create_index("createdAt", expireAfterSeconds=86400)
        logger.info("✅ IdempotencyKeys indexes created")

        # Add userId index to runs for efficient user isolation queries
        logger.info("👤 Creating user isolation indexes...")
        await database.runs.create_index([("userId", 1), ("createdAt", -1)])
        logger.info("✅ User isolation indexes created")

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


# ============= Idempotency Key Functions =============

async def check_idempotency_key(key: str, user_id: str) -> Optional[dict]:
    """
    Check if an idempotency key exists and return its stored result.

    Args:
        key: The idempotency key provided by the client
        user_id: The user ID to scope the key

    Returns:
        The stored result if key exists, None otherwise
    """
    # Key is scoped to user to prevent cross-user collisions
    full_key = f"{user_id}:{key}"

    doc = await db().idempotencyKeys.find_one({"key": full_key})
    if doc:
        logger.info(f"Found existing idempotency key: {key[:20]}...")
        return doc.get("result")
    return None


async def store_idempotency_key(key: str, user_id: str, result: dict) -> bool:
    """
    Store an idempotency key with its result.

    Args:
        key: The idempotency key provided by the client
        user_id: The user ID to scope the key
        result: The result to store (will be returned on duplicate requests)

    Returns:
        True if stored successfully, False if key already exists
    """
    full_key = f"{user_id}:{key}"

    try:
        await db().idempotencyKeys.insert_one({
            "key": full_key,
            "userId": user_id,
            "result": result,
            "createdAt": datetime.utcnow()
        })
        logger.info(f"Stored idempotency key: {key[:20]}...")
        return True
    except Exception as e:
        # Likely duplicate key error
        logger.warning(f"Failed to store idempotency key (may already exist): {e}")
        return False


async def delete_idempotency_key(key: str, user_id: str) -> bool:
    """
    Delete an idempotency key (useful for cleanup or retry scenarios).

    Args:
        key: The idempotency key to delete
        user_id: The user ID the key is scoped to

    Returns:
        True if deleted, False if not found
    """
    full_key = f"{user_id}:{key}"
    result = await db().idempotencyKeys.delete_one({"key": full_key})
    return result.deleted_count > 0


# ============= Optimized Query Helpers =============
# These use projections to minimize data transfer

# Common projection presets for different use cases
PROJECTIONS = {
    "run_summary": {
        "_id": 1, "topic": 1, "status": 1, "progress": 1,
        "createdAt": 1, "mode": 1, "userId": 1
    },
    "run_status": {
        "_id": 1, "status": 1, "progress": 1, "currentStep": 1, "mode": 1
    },
    "run_full": None,  # No projection = return all fields
    "source_summary": {
        "_id": 1, "title": 1, "url": 1, "score": 1, "type": 1, "source": 1
    },
    "source_content": {
        "_id": 1, "title": 1, "url": 1, "text": 1, "snippet": 1
    },
    "outline_headers": {
        "_id": 1, "heading": 1, "idx": 1, "brief": 1
    },
    "paragraph_content": {
        "_id": 1, "draftMd": 1, "citations": 1, "quality": 1
    },
    "task_status": {
        "_id": 1, "type": 1, "status": 1, "attempts": 1, "createdAt": 1
    }
}


async def get_run(
    run_id: ObjectId,
    projection: str = "run_full",
    user_id: Optional[str] = None
) -> Optional[dict]:
    """
    Get a run by ID with optional projection.

    Args:
        run_id: ObjectId of the run
        projection: Projection preset name or None for all fields
        user_id: Optional user ID for access control

    Returns:
        Run document or None if not found
    """
    query = {"_id": run_id}
    if user_id:
        query["userId"] = user_id

    proj = PROJECTIONS.get(projection)
    return await db().runs.find_one(query, proj)


async def get_runs_for_user(
    user_id: str,
    limit: int = 50,
    skip: int = 0,
    projection: str = "run_summary"
) -> List[dict]:
    """
    Get runs for a user with pagination.

    Uses projection to minimize data transfer - returns only
    summary fields by default.

    Args:
        user_id: User ID to filter by
        limit: Maximum runs to return
        skip: Number of runs to skip (pagination)
        projection: Projection preset name

    Returns:
        List of run summary documents
    """
    proj = PROJECTIONS.get(projection)
    cursor = db().runs.find(
        {"userId": user_id},
        proj
    ).sort("createdAt", -1).skip(skip).limit(limit)

    return await cursor.to_list(length=limit)


async def get_run_status(run_id: ObjectId) -> Optional[dict]:
    """
    Get minimal run status for progress updates.

    Only returns status, progress, and currentStep fields.
    """
    return await db().runs.find_one(
        {"_id": run_id},
        PROJECTIONS["run_status"]
    )


async def get_sources_for_outline_item(
    outline_item_id: ObjectId,
    limit: int = 20,
    projection: str = "source_summary"
) -> List[dict]:
    """
    Get sources for an outline item, sorted by score.

    Uses projection to minimize data transfer.
    """
    proj = PROJECTIONS.get(projection)
    cursor = db().sources.find(
        {"outlineItemId": outline_item_id},
        proj
    ).sort("score", -1).limit(limit)

    return await cursor.to_list(length=limit)


async def get_outline_items_for_run(
    run_id: ObjectId,
    projection: str = "outline_headers"
) -> List[dict]:
    """
    Get outline items for a run.

    Uses projection to minimize data transfer - returns only
    headers by default.
    """
    proj = PROJECTIONS.get(projection)
    cursor = db().outlineItems.find(
        {"runId": run_id},
        proj
    ).sort("idx", 1)

    return await cursor.to_list(length=50)


async def get_paragraphs_for_run(
    run_id: ObjectId,
    projection: str = "paragraph_content"
) -> List[dict]:
    """
    Get paragraphs for a run in order.
    """
    proj = PROJECTIONS.get(projection)
    cursor = db().paragraphs.find(
        {"runId": run_id},
        proj
    ).sort("idx", 1)

    return await cursor.to_list(length=50)


async def batch_get_sources(
    source_ids: List[ObjectId],
    projection: str = "source_content"
) -> List[dict]:
    """
    Batch fetch multiple sources by ID.

    More efficient than individual queries when fetching
    multiple documents.
    """
    if not source_ids:
        return []

    proj = PROJECTIONS.get(projection)
    cursor = db().sources.find(
        {"_id": {"$in": source_ids}},
        proj
    )

    return await cursor.to_list(length=len(source_ids))


async def update_run_progress(
    run_id: ObjectId,
    progress: int,
    current_step: Optional[str] = None,
    status: Optional[str] = None
) -> bool:
    """
    Update run progress efficiently with partial update.

    Only updates specified fields instead of replacing the
    entire document.
    """
    update_doc = {
        "$set": {
            "progress": progress,
            "updatedAt": datetime.utcnow()
        }
    }

    if current_step:
        update_doc["$set"]["currentStep"] = current_step
    if status:
        update_doc["$set"]["status"] = status

    result = await db().runs.update_one(
        {"_id": run_id},
        update_doc
    )

    return result.modified_count > 0


async def bulk_insert_sources(
    sources: List[dict],
    run_id: ObjectId,
    outline_item_id: ObjectId
) -> int:
    """
    Efficiently insert multiple sources using bulk write.

    Args:
        sources: List of source documents to insert
        run_id: Run ID to associate with sources
        outline_item_id: Outline item ID to associate with sources

    Returns:
        Number of documents inserted
    """
    if not sources:
        return 0

    # Prepare documents with common fields
    now = datetime.utcnow()
    docs = []
    for source in sources:
        doc = {
            **source,
            "runId": run_id,
            "outlineItemId": outline_item_id,
            "createdAt": now
        }
        docs.append(doc)

    result = await db().sources.insert_many(docs, ordered=False)
    return len(result.inserted_ids)


async def count_sources_for_run(run_id: ObjectId) -> int:
    """
    Efficiently count sources for a run.

    Uses count_documents instead of fetching all documents.
    """
    return await db().sources.count_documents({"runId": run_id})


async def aggregate_run_stats(run_id: ObjectId) -> dict:
    """
    Aggregate statistics for a run using MongoDB aggregation.

    More efficient than multiple queries for dashboard/stats.
    """
    database = db()

    # Run aggregation pipeline
    pipeline = [
        {"$match": {"runId": run_id}},
        {"$group": {
            "_id": None,
            "totalSources": {"$sum": 1},
            "avgScore": {"$avg": "$score"},
            "academicCount": {
                "$sum": {"$cond": [{"$eq": ["$type", "academic"]}, 1, 0]}
            },
            "webCount": {
                "$sum": {"$cond": [{"$eq": ["$type", "web"]}, 1, 0]}
            }
        }}
    ]

    cursor = database.sources.aggregate(pipeline)
    results = await cursor.to_list(length=1)

    if results:
        stats = results[0]
        del stats["_id"]
        return stats

    return {
        "totalSources": 0,
        "avgScore": 0,
        "academicCount": 0,
        "webCount": 0
    }

