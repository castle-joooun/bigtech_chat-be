"""
사용자 모델 (User Model)

================================================================================
아키텍처 개요 (Architecture Overview)
================================================================================
사용자 정보를 저장하는 SQLAlchemy ORM 모델입니다.
MySQL 데이터베이스의 'users' 테이블과 매핑됩니다.

데이터 구조:
    User
    ├── 기본 정보: id, email, password_hash, username, display_name
    ├── 프로필: status_message
    ├── 상태: is_online, last_seen_at, is_active
    └── 관계: chat_rooms, friendships

================================================================================
관계 다이어그램 (Relationship Diagram)
================================================================================
    User (1) ─── (*) ChatRoom (as user_1 or user_2)
      │
      └── (1) ─── (*) Friendship (as requester or target)

================================================================================
사용 예시 (Usage Examples)
================================================================================
>>> from legacy.app.models.users import User
>>> from sqlalchemy import select
>>>
>>> # 사용자 생성
>>> user = User(
...     email="user@example.com",
...     password_hash="hashed_password",
...     username="john_doe"
... )
>>> db.add(user)
>>> await db.commit()
>>>
>>> # 사용자 조회
>>> result = await db.execute(select(User).where(User.id == 1))
>>> user = result.scalar_one_or_none()
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from legacy.app.database.mysql import Base


class User(Base):
    """
    사용자 SQLAlchemy 모델

    MySQL 'users' 테이블과 매핑되는 ORM 모델입니다.
    인증, 프로필, 상태 정보를 관리합니다.

    Attributes:
        id (int): 사용자 고유 ID (Primary Key, Auto Increment)
        email (str): 이메일 주소 (Unique, 로그인 식별자)
        password_hash (str): bcrypt 해시된 비밀번호
        username (str): 사용자명 (Unique, 검색/표시용)
        display_name (str): 표시 이름 (Optional)
        status_message (str): 상태 메시지 (최대 500자)
        is_online (bool): 현재 온라인 상태
        last_seen_at (datetime): 마지막 접속 시간
        is_active (bool): 계정 활성화 상태
        created_at (datetime): 가입 일시
        updated_at (datetime): 마지막 수정 일시
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=False)
    display_name = Column(String(100), nullable=True)

    # Profile fields
    status_message = Column(String(500), nullable=True, comment="사용자 상태 메시지")
    is_online = Column(Boolean, default=False, nullable=False, comment="온라인 상태")
    last_seen_at = Column(DateTime, nullable=True, comment="마지막 접속 시간")
    is_active = Column(Boolean, default=True, nullable=False, comment="계정 활성화 상태")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    # Chat rooms (1:1 chat)
    chat_rooms_as_user_1 = relationship("ChatRoom", foreign_keys="ChatRoom.user_1_id", back_populates="user_1")
    chat_rooms_as_user_2 = relationship("ChatRoom", foreign_keys="ChatRoom.user_2_id", back_populates="user_2")

    # Room memberships (개인 설정)
    room_memberships = relationship("RoomMember", back_populates="user", cascade="all, delete-orphan")

    # Friendships
    friendship_requests = relationship("Friendship", foreign_keys="Friendship.user_id_1", back_populates="requester")
    friendship_receives = relationship("Friendship", foreign_keys="Friendship.user_id_2", back_populates="target")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"
