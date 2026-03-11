"""
Friend Service Test Configuration

pytest fixtures for unit and integration tests
"""

import pytest
import asyncio
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

import sys
import os

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database.mysql import Base
from app.models.user import User
from app.models.friendship import Friendship, BlockUser


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
async def user_1(db_session: AsyncSession) -> User:
    """Create first test user"""
    user = User(
        email="user1@example.com",
        username="user1",
        password_hash="hashed_password",
        display_name="User One",
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
async def user_2(db_session: AsyncSession) -> User:
    """Create second test user"""
    user = User(
        email="user2@example.com",
        username="user2",
        password_hash="hashed_password",
        display_name="User Two",
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
async def user_3(db_session: AsyncSession) -> User:
    """Create third test user"""
    user = User(
        email="user3@example.com",
        username="user3",
        password_hash="hashed_password",
        display_name="User Three",
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
    """Create inactive test user"""
    user = User(
        email="inactive@example.com",
        username="inactive_user",
        password_hash="hashed_password",
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
# Friendship Fixtures
# =============================================================================

@pytest.fixture
async def pending_friendship(db_session: AsyncSession, user_1: User, user_2: User) -> Friendship:
    """Create a pending friend request from user_1 to user_2"""
    friendship = Friendship(
        user_id_1=user_1.id,
        user_id_2=user_2.id,
        status="pending",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db_session.add(friendship)
    await db_session.commit()
    await db_session.refresh(friendship)

    return friendship


@pytest.fixture
async def accepted_friendship(db_session: AsyncSession, user_1: User, user_2: User) -> Friendship:
    """Create an accepted friendship between user_1 and user_2"""
    friendship = Friendship(
        user_id_1=user_1.id,
        user_id_2=user_2.id,
        status="accepted",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db_session.add(friendship)
    await db_session.commit()
    await db_session.refresh(friendship)

    return friendship


@pytest.fixture
async def blocked_user_relationship(db_session: AsyncSession, user_1: User, user_3: User) -> BlockUser:
    """Create a block relationship where user_1 blocks user_3"""
    block = BlockUser(
        user_id=user_1.id,
        blocked_user_id=user_3.id,
        created_at=datetime.utcnow()
    )

    db_session.add(block)
    await db_session.commit()
    await db_session.refresh(block)

    return block
