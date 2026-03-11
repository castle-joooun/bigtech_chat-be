"""
Chat Service Test Configuration

pytest fixtures for unit and integration tests
"""

import pytest
import asyncio
from datetime import datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

import sys
import os

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database.mysql import Base
from app.models.user import User
from app.models.chat_rooms import ChatRoom


# =============================================================================
# Test Database Configuration (MySQL - SQLite for testing)
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
        id=1,
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
        id=2,
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
        id=3,
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


# =============================================================================
# Chat Room Fixtures
# =============================================================================

@pytest.fixture
async def chat_room(db_session: AsyncSession, user_1: User, user_2: User) -> ChatRoom:
    """Create a test chat room between user_1 and user_2"""
    room = ChatRoom(
        user_1_id=user_1.id,
        user_2_id=user_2.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db_session.add(room)
    await db_session.commit()
    await db_session.refresh(room)

    return room


@pytest.fixture
async def chat_room_2(db_session: AsyncSession, user_1: User, user_3: User) -> ChatRoom:
    """Create a second test chat room between user_1 and user_3"""
    room = ChatRoom(
        user_1_id=user_1.id,
        user_2_id=user_3.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db_session.add(room)
    await db_session.commit()
    await db_session.refresh(room)

    return room


# =============================================================================
# Message Mocks (MongoDB is mocked)
# =============================================================================

@pytest.fixture
def mock_message():
    """Create a mock message object"""
    message = MagicMock()
    message.id = "507f1f77bcf86cd799439011"
    message.user_id = 1
    message.room_id = 1
    message.room_type = "private"
    message.content = "Hello, World!"
    message.message_type = "text"
    message.is_deleted = False
    message.created_at = datetime.utcnow()
    message.updated_at = datetime.utcnow()
    return message


@pytest.fixture
def mock_message_list():
    """Create a list of mock messages"""
    messages = []
    for i in range(5):
        msg = MagicMock()
        msg.id = f"507f1f77bcf86cd79943901{i}"
        msg.user_id = (i % 2) + 1  # Alternate between user 1 and 2
        msg.room_id = 1
        msg.room_type = "private"
        msg.content = f"Message {i}"
        msg.message_type = "text"
        msg.is_deleted = False
        msg.created_at = datetime.utcnow()
        msg.updated_at = datetime.utcnow()
        messages.append(msg)
    return messages
