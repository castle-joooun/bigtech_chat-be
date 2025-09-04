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
engine = create_async_engine(
    settings.mysql_url,
    echo=settings.debug,  # Log SQL queries in debug mode
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_pre_ping=True,  # Validate connections before use
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


async def init_mysql_db():
    """Initialize MySQL database"""
    try:
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
