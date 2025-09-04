from typing import List
import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from beanie import init_beanie, Document
from app.core.config import settings

# MongoDB client and database
client: AsyncIOMotorClient = None
database: AsyncIOMotorDatabase = None

logger = logging.getLogger(__name__)

# Document models will be imported here when created
# from app.models.chat import ChatMessage, ChatRoom
# from app.models.user import UserProfile

DOCUMENT_MODELS: List[Document] = [
    # ChatMessage,
    # ChatRoom,
    # UserProfile,
]


async def connect_to_mongo():
    """Create database connection"""
    global client, database
    try:
        client = AsyncIOMotorClient(
            settings.mongo_url,
            maxPoolSize=10,
            minPoolSize=1,
            maxIdleTimeMS=30000,
            waitQueueTimeoutMS=5000,
        )
        database = client.chat_db
        logger.info("Connected to MongoDB")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


async def init_mongodb():
    """Initialize MongoDB with Beanie"""
    try:
        await connect_to_mongo()
        await init_beanie(database=database, document_models=DOCUMENT_MODELS)
        logger.info("MongoDB initialized with Beanie successfully")
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB: {e}")
        raise


async def check_mongo_connection() -> bool:
    """Check MongoDB connection"""
    try:
        if client:
            await client.admin.command('ping')
            return True
        return False
    except Exception as e:
        logger.error(f"MongoDB connection check failed: {e}")
        return False


async def close_mongo_connection():
    """Close MongoDB connection"""
    global client
    if client:
        client.close()
        client = None
        logger.info("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    """Get MongoDB database instance"""
    if database is None:
        raise RuntimeError("MongoDB not initialized. Call init_mongodb() first.")
    return database
