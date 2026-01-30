from typing import AsyncGenerator
import logging
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from app.core.config import settings

# Base class for SQLAlchemy models
Base = declarative_base()

# Database engine with connection pooling
# Increased pool_size and max_overflow for high concurrency load testing
engine = create_async_engine(
    settings.mysql_url,
    echo=settings.debug,  # Log SQL queries in debug mode
    pool_size=50,         # Increased from 10 for high load
    max_overflow=100,     # Increased from 20 for burst traffic
    pool_recycle=3600,    # Recycle connections after 1 hour
    pool_pre_ping=True,   # Validate connections before use
    pool_timeout=30,      # Wait up to 30s for connection
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

logger = logging.getLogger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


# Alias for consistency with naming convention
get_async_session = get_db


async def init_mysql_db():
    """Initialize MySQL database"""
    try:
        # Import models to register with Base.metadata
        from app.models.user import User
        from app.models.chat_rooms import ChatRoom
        from app.models.room_members import RoomMember

        async with engine.begin() as conn:
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
        logger.info("MySQL database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize MySQL database: {e}")
        raise


async def check_mysql_connection():
    """Check MySQL database connection"""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.fetchone() is not None
    except Exception as e:
        logger.error(f"MySQL connection check failed: {e}")
        return False


async def close_mysql_db():
    """Close MySQL database connections"""
    await engine.dispose()
    logger.info("MySQL database connections closed")
