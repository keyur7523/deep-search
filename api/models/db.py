import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

_client = None
_dbname = os.getenv("MONGODB_DB", "deep-search")

def get_client():
    global _client
    if _client is None:
        mongodb_uri = os.getenv("MONGODB_URI")
        if not mongodb_uri:
            raise RuntimeError("MONGODB_URI not set")
        _client = AsyncIOMotorClient(mongodb_uri, serverSelectionTimeoutMS=5000)
    return _client

def db():
    return get_client()[_dbname]

async def ensure_indexes():
    await db().sources.create_index("hash", unique=False)
    await db().sources.create_index([("outlineItemId", 1), ("score", -1)])
    await db().searchQueries.create_index([("outlineItemId", 1), ("round", 1)])
    await db().paragraphs.create_index([("outlineItemId", 1)])
    await db().runs.create_index([("projectId", 1), ("createdAt", -1)])
