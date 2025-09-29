import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize client as None, will be created when needed
_client = None
_dbname = os.getenv("MONGODB_DB", "deep-search")

def get_client():
    global _client
    if _client is None:
        mongodb_uri = os.getenv("MONGODB_URI")
        if not mongodb_uri:
            raise ValueError("MONGODB_URI environment variable is not set")
        
        # Create client with SSL certificate handling for macOS
        _client = AsyncIOMotorClient(
            mongodb_uri,
            tlsCAFile=None,
            tlsAllowInvalidCertificates=True
        )
    return _client

def db():
    return get_client()[_dbname]

async def ensure_indexes():
    await db().sources.create_index("hash", unique=False)
    await db().sources.create_index([("outlineItemId", 1), ("score", -1)])
    await db().searchQueries.create_index([("outlineItemId", 1), ("round", 1)])
    await db().paragraphs.create_index([("outlineItemId", 1)])
    await db().runs.create_index([("projectId", 1), ("createdAt", -1)])
