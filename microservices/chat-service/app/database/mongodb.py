"""
MongoDB Database Module (MongoDB 데이터베이스 모듈)
=================================================

shared_lib의 MongoDBManager를 사용하여 MongoDB 연결을 관리합니다.

관련 파일
---------
- shared_lib/database/mongodb.py: 공통 MongoDB 연결 유틸리티
- app/core/config.py: mongo_url 설정
- app/models/messages.py: Beanie Document 모델
"""

import logging
from shared_lib.database import MongoDBManager, get_mongodb_manager
from app.core.config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# MongoDB Manager (shared_lib 사용)
# =============================================================================
_mongodb_manager: MongoDBManager = get_mongodb_manager()


async def init_mongodb():
    """MongoDB 연결 및 Beanie 초기화"""
    from app.models.messages import Message, MessageReadStatus

    await _mongodb_manager.init(
        mongo_url=settings.mongo_url,
        db_name=settings.mongodb_db_name,
        document_models=[Message, MessageReadStatus]
    )
    logger.info(f"MongoDB connected: {settings.mongodb_db_name}")


async def close_mongodb():
    """MongoDB 연결 종료"""
    await _mongodb_manager.close()
    logger.info("MongoDB connection closed")


def get_mongo_client():
    """MongoDB Client 반환"""
    return _mongodb_manager.client


def get_mongo_database():
    """MongoDB Database 반환"""
    return _mongodb_manager.database


async def check_mongodb_connection() -> bool:
    """MongoDB 연결 상태 확인"""
    return await _mongodb_manager.health_check()
