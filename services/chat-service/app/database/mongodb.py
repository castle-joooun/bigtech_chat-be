"""
MongoDB 연결 및 Beanie ODM 초기화
"""

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.core.config import settings
from app.models.messages import Message, MessageReaction, MessageReadStatus

# MongoDB Client
mongo_client: AsyncIOMotorClient = None


async def init_mongodb():
    """MongoDB 연결 및 Beanie 초기화"""
    global mongo_client

    mongo_client = AsyncIOMotorClient(settings.mongo_url)

    await init_beanie(
        database=mongo_client[settings.mongodb_db_name],
        document_models=[
            Message,
            MessageReaction,
            MessageReadStatus,
        ]
    )

    print(f"✅ MongoDB connected: {settings.mongodb_db_name}")


async def close_mongodb():
    """MongoDB 연결 종료"""
    global mongo_client

    if mongo_client:
        mongo_client.close()
        print("🔌 MongoDB connection closed")


def get_mongo_client() -> AsyncIOMotorClient:
    """MongoDB Client 반환"""
    return mongo_client
