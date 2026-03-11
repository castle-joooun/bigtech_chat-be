"""
Database Module (데이터베이스 모듈)
=================================

MySQL, MongoDB, Redis 연결 관리를 제공합니다.
"""

from .mysql import (
    Base,
    create_mysql_engine,
    create_async_session_factory,
    get_db_dependency,
    init_database,
    check_connection,
    close_database,
)

__all__ = [
    # MySQL
    "Base",
    "create_mysql_engine",
    "create_async_session_factory",
    "get_db_dependency",
    "init_database",
    "check_connection",
    "close_database",
]

# MongoDB는 optional (motor, beanie 패키지가 설치된 경우에만)
try:
    from .mongodb import MongoDBManager, get_mongodb_manager
    __all__.extend(["MongoDBManager", "get_mongodb_manager"])
except ImportError:
    pass

# Redis는 optional (redis 패키지가 설치된 경우에만)
try:
    from .redis import RedisManager, get_redis_manager
    __all__.extend(["RedisManager", "get_redis_manager"])
except ImportError:
    pass
