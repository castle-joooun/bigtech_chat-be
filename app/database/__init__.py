import logging
from .mysql import init_mysql_db, close_mysql_db, check_mysql_connection, get_db
from .mongodb import init_mongodb, close_mongo_connection, check_mongo_connection, get_database
from .redis import init_redis, close_redis, health_check as redis_health_check, get_redis

logger = logging.getLogger(__name__)


async def init_databases():
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
    """Close all database connections"""
    try:
        await close_mysql_db()
        await close_mongo_connection()
        await close_redis()
        logger.info("All database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")


async def check_database_health():
    """Check health of all database connections"""
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
