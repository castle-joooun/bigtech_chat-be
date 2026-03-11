"""
User Service Test Configuration

pytest fixtures for unit and integration tests
"""

import pytest
import asyncio
from datetime import datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import StaticPool

import sys
import os

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database.mysql import Base
from app.models.user import User


# =============================================================================
# Test Database Configuration
# =============================================================================

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False}
)

TestAsyncSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# =============================================================================
# Pytest Configuration
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_database():
    """Setup and teardown test database for each test"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get test database session"""
    async with TestAsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


# =============================================================================
# User Fixtures
# =============================================================================

@pytest.fixture
def user_data():
    """Sample user data for testing"""
    return {
        "email": "test@example.com",
        "username": "testuser",
        "password": "Test123!@#",
        "display_name": "Test User"
    }


@pytest.fixture
def user_data_2():
    """Second sample user data"""
    return {
        "email": "test2@example.com",
        "username": "testuser2",
        "password": "Test456!@#",
        "display_name": "Test User 2"
    }


@pytest.fixture
async def test_user(db_session: AsyncSession, user_data: dict) -> User:
    """Create and return a test user"""
    from app.utils.auth import get_password_hash

    user = User(
        email=user_data["email"],
        username=user_data["username"],
        password_hash=get_password_hash(user_data["password"]),
        display_name=user_data["display_name"],
        is_active=True,
        is_online=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest.fixture
async def test_user_2(db_session: AsyncSession, user_data_2: dict) -> User:
    """Create and return a second test user"""
    from app.utils.auth import get_password_hash

    user = User(
        email=user_data_2["email"],
        username=user_data_2["username"],
        password_hash=get_password_hash(user_data_2["password"]),
        display_name=user_data_2["display_name"],
        is_active=True,
        is_online=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest.fixture
async def inactive_user(db_session: AsyncSession) -> User:
    """Create and return an inactive test user"""
    from app.utils.auth import get_password_hash

    user = User(
        email="inactive@example.com",
        username="inactiveuser",
        password_hash=get_password_hash("Test123!@#"),
        display_name="Inactive User",
        is_active=False,
        is_online=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


# =============================================================================
# Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis_mock = AsyncMock()
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.delete = AsyncMock(return_value=1)
    redis_mock.exists = AsyncMock(return_value=0)
    redis_mock.expire = AsyncMock(return_value=True)
    return redis_mock


@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    settings_mock = MagicMock()
    settings_mock.secret_key = "test-secret-key-for-testing-only"
    settings_mock.algorithm = "HS256"
    settings_mock.access_token_expire_hours = 2
    settings_mock.redis_url = "redis://localhost:6379"
    settings_mock.mysql_url = TEST_DATABASE_URL
    return settings_mock
