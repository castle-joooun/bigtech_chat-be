"""
데이터베이스 초기화 및 상태 관리 모듈 (Database Initialization & Health Module)

================================================================================
아키텍처 개요 (Architecture Overview)
================================================================================
이 모듈은 애플리케이션에서 사용하는 모든 데이터베이스(MySQL, MongoDB, Redis)의
초기화, 종료, 상태 확인을 통합 관리합니다.

Polyglot Persistence 패턴을 적용하여 각 데이터 유형에 최적화된 저장소를 사용합니다:
    - MySQL: 사용자, 친구관계, 채팅방 등 관계형 데이터
    - MongoDB: 메시지, 반응 등 비정형 채팅 데이터
    - Redis: 캐시, 세션, 온라인 상태 등 실시간 데이터

데이터베이스 초기화 흐름:
    애플리케이션 시작 → init_databases()
                            ↓
            ├── init_mysql_db() → MySQL 연결
            ├── init_mongodb() → MongoDB 연결
            └── init_redis() → Redis 연결

================================================================================
사용 예시 (Usage Examples)
================================================================================
>>> from legacy.app.database import init_databases, close_databases, check_database_health
>>>
>>> # 애플리케이션 시작 시
>>> await init_databases()
>>>
>>> # 헬스 체크
>>> health = await check_database_health()
>>> if not health["overall"]:
...     logger.error("Database unhealthy")
>>>
>>> # 애플리케이션 종료 시
>>> await close_databases()
"""

import logging
from .mysql import init_mysql_db, close_mysql_db, check_mysql_connection, get_db
from .mongodb import init_mongodb, close_mongo_connection, check_mongo_connection, get_database
from .redis import init_redis, close_redis, health_check as redis_health_check, get_redis

logger = logging.getLogger(__name__)


async def init_databases():
    """
    모든 데이터베이스 초기화

    MySQL, MongoDB, Redis 연결을 순차적으로 초기화합니다.
    하나라도 실패하면 예외가 발생합니다.

    Raises:
        Exception: 데이터베이스 초기화 실패 시

    Note:
        main.py의 lifespan 함수에서 호출됩니다.
    """
    """Initialize MySQL, MongoDB, and Redis"""
    try:
        # Initialize MySQL
        await init_mysql_db()
        logger.info("MySQL initialization completed")

        # Initialize MongoDB
        await init_mongodb()
        logger.info("MongoDB initialization completed")

        # Initialize Redis
        await init_redis()
        logger.info("Redis initialization completed")

        logger.info("All databases initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def close_databases():
    """
    모든 데이터베이스 연결 종료

    애플리케이션 종료 시 호출하여 리소스를 정리합니다.
    개별 종료 실패는 로깅만 하고 계속 진행합니다.
    """
    try:
        await close_mysql_db()
        await close_mongo_connection()
        await close_redis()
        logger.info("All database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")


async def check_database_health():
    """
    모든 데이터베이스 연결 상태 확인

    Kubernetes 헬스 체크나 모니터링에서 사용합니다.

    Returns:
        dict: 각 데이터베이스 상태와 전체 상태
            - mysql (bool): MySQL 연결 상태
            - mongodb (bool): MongoDB 연결 상태
            - redis (dict): Redis 상세 상태
            - overall (bool): 전체 상태 (모두 정상일 때만 True)

    Example:
        >>> health = await check_database_health()
        >>> print(health)
        {"mysql": True, "mongodb": True, "redis": {"status": "healthy"}, "overall": True}
    """
    mysql_status = await check_mysql_connection()
    mongo_status = await check_mongo_connection()
    redis_status = await redis_health_check()

    return {
        "mysql": mysql_status,
        "mongodb": mongo_status,
        "redis": redis_status,
        "overall": mysql_status and mongo_status and redis_status.get("status") == "healthy"
    }

__all__ = [
    "init_databases",
    "close_databases",
    "check_database_health",
    "get_db",
    "get_database",
    "get_redis"
]
