import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import AsyncMock, patch
from datetime import datetime

from app.main import app
from app.database.mysql import Base, get_async_session
from app.models.users import User
from app.models.friendships import Friendship
from app.models.chat_rooms import ChatRoom
from app.models.room_members import RoomMember
from app.utils.auth import get_password_hash, create_access_token
from app.services import message_service


# 테스트용 인메모리 SQLite 데이터베이스 설정
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_engine():
    """테스트용 비동기 데이터베이스 엔진 생성"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False
    )
    
    # 테이블 생성
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # 정리
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """테스트용 데이터베이스 세션"""
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_session) -> AsyncGenerator[AsyncClient, None]:
    """테스트용 비동기 HTTP 클라이언트"""
    def get_test_session():
        return test_session
    
    app.dependency_overrides[get_async_session] = get_test_session
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user_1(test_session) -> User:
    """테스트용 사용자 1"""
    user = User(
        username="testuser1",
        email="test1@example.com",
        password_hash=get_password_hash("testpass123!")
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_2(test_session) -> User:
    """테스트용 사용자 2"""
    user = User(
        username="testuser2",
        email="test2@example.com",
        password_hash=get_password_hash("testpass123!")
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_3(test_session) -> User:
    """테스트용 사용자 3"""
    user = User(
        username="testuser3",
        email="test3@example.com",
        password_hash=get_password_hash("testpass123!")
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_token_user_1(test_user_1) -> str:
    """사용자 1의 인증 토큰"""
    return create_access_token(data={"sub": str(test_user_1.id), "email": test_user_1.email})


@pytest_asyncio.fixture
async def auth_token_user_2(test_user_2) -> str:
    """사용자 2의 인증 토큰"""
    return create_access_token(data={"sub": str(test_user_2.id), "email": test_user_2.email})


@pytest_asyncio.fixture
async def auth_token_user_3(test_user_3) -> str:
    """사용자 3의 인증 토큰"""
    return create_access_token(data={"sub": str(test_user_3.id), "email": test_user_3.email})


@pytest_asyncio.fixture
async def accepted_friendship(test_session, test_user_1, test_user_2) -> Friendship:
    """수락된 친구 관계"""
    friendship = Friendship(
        user_id_1=test_user_1.id,
        user_id_2=test_user_2.id,
        status="accepted"
    )
    test_session.add(friendship)
    await test_session.commit()
    await test_session.refresh(friendship)
    return friendship


@pytest_asyncio.fixture
async def pending_friendship(test_session, test_user_1, test_user_3) -> Friendship:
    """대기 중인 친구 요청"""
    friendship = Friendship(
        user_id_1=test_user_1.id,
        user_id_2=test_user_3.id,
        status="pending"
    )
    test_session.add(friendship)
    await test_session.commit()
    await test_session.refresh(friendship)
    return friendship


@pytest_asyncio.fixture
async def test_chat_room(test_session, test_user_1, test_user_2) -> ChatRoom:
    """테스트용 채팅방"""
    chat_room = ChatRoom(
        user_1_id=test_user_1.id,
        user_2_id=test_user_2.id
    )
    test_session.add(chat_room)
    await test_session.commit()
    await test_session.refresh(chat_room)
    return chat_room


# Mock Message 서비스 클래스
class MockMessage:
    def __init__(self, user_id, room_id, room_type, content, message_type="text", reply_to=None):
        self.id = "mock_message_id_123"
        self.user_id = user_id
        self.room_id = room_id
        self.room_type = room_type
        self.content = content
        self.message_type = message_type
        self.reply_to = reply_to
        self.created_at = datetime.utcnow()
    
    async def save(self):
        return self
    
    def model_dump(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "room_id": self.room_id,
            "room_type": self.room_type,
            "content": self.content,
            "message_type": self.message_type,
            "reply_to": self.reply_to,
            "created_at": self.created_at
        }


@pytest_asyncio.fixture
async def mock_message_service():
    """Mock message service"""
    
    # 메시지를 저장할 가짜 스토리지
    fake_messages = {}
    
    async def mock_create_message(user_id, room_id, room_type, content, message_type="text", reply_to=None):
        message = MockMessage(user_id, room_id, room_type, content, message_type, reply_to)
        room_key = f"{room_id}_{room_type}"
        if room_key not in fake_messages:
            fake_messages[room_key] = []
        fake_messages[room_key].append(message)
        return message
    
    async def mock_get_room_messages(room_id, room_type="private", limit=50, skip=0):
        room_key = f"{room_id}_{room_type}"
        messages = fake_messages.get(room_key, [])
        return messages[skip:skip+limit] if messages else []
    
    async def mock_get_room_messages_count(room_id, room_type="private"):
        room_key = f"{room_id}_{room_type}"
        return len(fake_messages.get(room_key, []))
    
    with patch('app.services.message_service.create_message', side_effect=mock_create_message), \
         patch('app.services.message_service.get_room_messages', side_effect=mock_get_room_messages), \
         patch('app.services.message_service.get_room_messages_count', side_effect=mock_get_room_messages_count):
        yield


def pytest_configure(config):
    """pytest 설정"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )