"""
Database Initialization Module (데이터베이스 초기화 모듈)
========================================================

Friend Service에서 사용하는 모든 데이터베이스의 초기화/종료를 통합 관리합니다.

사용 데이터베이스:
    - MySQL: 친구 관계 저장
"""

import logging
from .mysql import init_mysql_db, close_mysql_db, get_async_session, get_db, Base

logger = logging.getLogger(__name__)


async def init_databases():
    """
    모든 데이터베이스 초기화

    초기화 순서 (레거시와 동일):
        1. MySQL

    Raises:
        Exception: 데이터베이스 초기화 실패 시
    """
    try:
        await init_mysql_db()
        logger.info("MySQL initialized")

        logger.info("All databases initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def close_databases():
    """
    모든 데이터베이스 연결 종료

    종료 순서:
        1. MySQL
    """
    try:
        await close_mysql_db()
        logger.info("MySQL closed")

        logger.info("All database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")


__all__ = [
    "init_databases",
    "close_databases",
    "init_mysql_db",
    "close_mysql_db",
    "get_async_session",
    "get_db",
    "Base",
]
