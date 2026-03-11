"""
MongoDB Database (MongoDB 데이터베이스)
=====================================

MongoDB 연결 및 Beanie ODM 초기화를 제공합니다.

사용 예시
---------
```python
from shared_lib.database import MongoDBManager, get_mongodb_manager

# 초기화
mongodb = get_mongodb_manager()
await mongodb.init(
    mongo_url=settings.mongo_url,
    db_name=settings.mongodb_db_name,
    document_models=[Message, MessageReadStatus]
)

# 클라이언트 접근
client = mongodb.client
db = mongodb.database

# 종료
await mongodb.close()
```
"""

import logging
from typing import Optional, List, Type

logger = logging.getLogger(__name__)

# Optional imports (motor, beanie가 설치된 경우에만)
try:
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
    from beanie import init_beanie, Document
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    AsyncIOMotorClient = None
    AsyncIOMotorDatabase = None
    Document = None


class MongoDBManager:
    """MongoDB 연결 관리자"""

    def __init__(self):
        self._client: Optional["AsyncIOMotorClient"] = None
        self._database: Optional["AsyncIOMotorDatabase"] = None
        self._db_name: Optional[str] = None

    @property
    def client(self) -> Optional["AsyncIOMotorClient"]:
        """MongoDB 클라이언트 반환"""
        return self._client

    @property
    def database(self) -> Optional["AsyncIOMotorDatabase"]:
        """MongoDB 데이터베이스 반환"""
        return self._database

    async def init(
        self,
        mongo_url: str,
        db_name: str,
        document_models: List[Type] = None
    ):
        """
        MongoDB 연결 및 Beanie 초기화

        Args:
            mongo_url: MongoDB 연결 URL
            db_name: 데이터베이스 이름
            document_models: Beanie Document 모델 목록
        """
        if not MONGODB_AVAILABLE:
            raise ImportError(
                "MongoDB dependencies not installed. "
                "Install with: pip install motor beanie"
            )

        try:
            self._client = AsyncIOMotorClient(mongo_url)
            self._database = self._client[db_name]
            self._db_name = db_name

            # Beanie 초기화 (document_models가 있는 경우)
            if document_models:
                await init_beanie(
                    database=self._database,
                    document_models=document_models
                )

            logger.info(f"MongoDB connected: {db_name}")

        except Exception as e:
            logger.error(f"Failed to initialize MongoDB: {e}")
            self._client = None
            self._database = None
            raise

    async def close(self):
        """MongoDB 연결 종료"""
        if self._client:
            self._client.close()
            self._client = None
            self._database = None
            logger.info("MongoDB connection closed")

    async def health_check(self) -> bool:
        """MongoDB 연결 상태 확인"""
        if not self._client:
            return False
        try:
            await self._client.admin.command('ping')
            return True
        except Exception as e:
            logger.error(f"MongoDB health check failed: {e}")
            return False


# Singleton instance
_mongodb_manager: Optional[MongoDBManager] = None


def get_mongodb_manager() -> MongoDBManager:
    """MongoDB 매니저 싱글톤 반환"""
    global _mongodb_manager
    if _mongodb_manager is None:
        _mongodb_manager = MongoDBManager()
    return _mongodb_manager
