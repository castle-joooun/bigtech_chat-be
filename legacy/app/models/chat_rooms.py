"""
1:1 채팅방 모델 (Direct Chat Room Model)

================================================================================
아키텍처 개요 (Architecture Overview)
================================================================================
1:1 채팅방 정보를 저장하는 SQLAlchemy ORM 모델입니다.
두 사용자 간의 개인 채팅을 관리합니다.

설계 원칙:
    - user_1_id는 항상 user_2_id보다 작은 값 (중복 방지)
    - 두 사용자 간에는 하나의 채팅방만 존재

관계 구조:
    ChatRoom
    ├── user_1 → User (첫 번째 참여자)
    ├── user_2 → User (두 번째 참여자)
    └── room_members → RoomMember[] (멤버십, 그룹 채팅용 예약)

================================================================================
사용 예시 (Usage Examples)
================================================================================
>>> # 채팅방 생성 (user_id 정렬하여 저장)
>>> room = ChatRoom(
...     user_1_id=min(user_a, user_b),
...     user_2_id=max(user_a, user_b)
... )
>>>
>>> # 기존 채팅방 조회
>>> room = await find_existing_chat_room(db, user_a, user_b)
"""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from legacy.app.database.mysql import Base


class ChatRoom(Base):
    """
    1:1 채팅방 SQLAlchemy 모델

    Attributes:
        id (int): 채팅방 고유 ID
        user_1_id (int): 첫 번째 사용자 ID (항상 작은 값)
        user_2_id (int): 두 번째 사용자 ID (항상 큰 값)
        created_at (datetime): 생성 일시
        updated_at (datetime): 마지막 메시지 시간 (정렬용)

    Note:
        updated_at은 마지막 메시지 전송 시 업데이트되어
        채팅방 목록에서 최근 순 정렬에 사용됩니다.
    """
    __tablename__ = "chat_rooms"

    id = Column(Integer, primary_key=True, index=True)
    user_1_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # First user in 1:1 chat
    user_2_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # Second user in 1:1 chat
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user_1 = relationship("User", foreign_keys=[user_1_id], back_populates="chat_rooms_as_user_1")
    user_2 = relationship("User", foreign_keys=[user_2_id], back_populates="chat_rooms_as_user_2")
    room_members = relationship("RoomMember", back_populates="chat_room", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChatRoom(id={self.id}, user_1_id={self.user_1_id}, user_2_id={self.user_2_id})>"
