"""
MySQL Database Module (MySQL 데이터베이스 모듈)
=============================================

shared_lib의 공통 DB 유틸리티를 사용하여 MySQL 연결을 관리합니다.

관련 파일
---------
- shared_lib/database/mysql.py: 공통 DB 연결 유틸리티
- app/core/config.py: mysql_url 설정
- app/models/*.py: SQLAlchemy 모델 정의
"""

import logging
from shared_lib.database import (
    Base,
    create_mysql_engine,
    create_async_session_factory,
    get_db_dependency,
    init_database,
    close_database,
    check_connection,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# Database Engine & Session Factory (shared_lib 사용)
# =============================================================================
engine = create_mysql_engine(
    settings.mysql_url,
    debug=settings.debug,
    pool_size=50,
    max_overflow=100,
    pool_recycle=3600,
    pool_timeout=30,
)

AsyncSessionLocal = create_async_session_factory(engine)

# FastAPI Dependency
get_db = get_db_dependency(AsyncSessionLocal)
get_async_session = get_db  # Alias


# =============================================================================
# Lifecycle Functions
# =============================================================================
async def init_mysql_db():
    """
    MySQL 데이터베이스 초기화

    Chat Service 모델만 등록합니다.
    User 모델은 user-service에서 관리합니다.
    """
    try:
        # Import models to register with Base.metadata
        from app.models.chat_rooms import ChatRoom
        from app.models.room_members import RoomMember

        await init_database(engine)
        logger.info("MySQL database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize MySQL database: {e}")
        raise


async def check_mysql_connection() -> bool:
    """MySQL 연결 상태 확인"""
    return await check_connection(engine)


async def close_mysql_db():
    """MySQL 연결 풀 종료"""
    await close_database(engine)
