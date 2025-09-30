import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()
logger.info("📁 Database module loaded, environment variables loaded")

_client = None
_dbname = os.getenv("MONGODB_DB", "deep-search")
logger.info(f"🗄️ Database name configured: {_dbname}")

def get_client():
    global _client
    if _client is None:
        logger.info("🔌 Creating new MongoDB client connection...")
        mongodb_uri = os.getenv("MONGODB_URI")
        if not mongodb_uri:
            logger.error("❌ MONGODB_URI environment variable not set")
            raise RuntimeError("MONGODB_URI not set")
        
        logger.info(f"🔗 Connecting to MongoDB Atlas...")
        logger.info(f"📍 URI: {mongodb_uri[:20]}...{mongodb_uri[-10:]}")
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
        
        logger.info("📝 Creating paragraphs collection indexes...")
        await database.paragraphs.create_index([("outlineItemId", 1)])
        logger.info("✅ Paragraphs indexes created")
        
        logger.info("🏃 Creating runs collection indexes...")
        await database.runs.create_index([("projectId", 1), ("createdAt", -1)])
        logger.info("✅ Runs indexes created")
        
        logger.info("📡 Creating liveStatus collection indexes...")
        await database.liveStatus.create_index([("runId", 1)], unique=True)
        await database.liveStatus.create_index("ts", expireAfterSeconds=1800)
        logger.info("✅ LiveStatus indexes created")
        
        logger.info("🎉 All database indexes created successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error creating database indexes: {e}")
        raise
