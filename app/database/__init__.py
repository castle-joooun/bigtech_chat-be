import logging
from .mysql import init_mysql_db, close_mysql_db, check_mysql_connection, get_db
from .mongodb import init_mongodb, close_mongo_connection, check_mongo_connection, get_database

logger = logging.getLogger(__name__)


async def init_databases():
    """Initialize both MySQL and MongoDB"""
    try:
        # Initialize MySQL
        await init_mysql_db()
        logger.info("MySQL initialization completed")
        
        # Initialize MongoDB
        await init_mongodb()
        logger.info("MongoDB initialization completed")
        
        logger.info("All databases initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def close_databases():
    """Close all database connections"""
    try:
        await close_mysql_db()
        await close_mongo_connection()
        logger.info("All database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")


async def check_database_health():
    """Check health of all database connections"""
    mysql_status = await check_mysql_connection()
    mongo_status = await check_mongo_connection()
    
    return {
        "mysql": mysql_status,
        "mongodb": mongo_status,
        "overall": mysql_status and mongo_status
    }

__all__ = [
    "init_databases",
    "close_databases", 
    "check_database_health",
    "get_db",
    "get_database"
]
