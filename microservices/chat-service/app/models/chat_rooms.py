"""
ChatRoom Model (채팅방 모델)
============================

1:1 채팅방 정보를 저장하는 SQLAlchemy 모델입니다.

MSA 원칙
--------
- FK 제약조건 제거 (user_id만 정수로 저장)
- User 정보는 user-service API를 통해 조회
- relationship 제거 (User 모델이 없음)
"""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.orm import relationship
from app.database.mysql import Base


class ChatRoom(Base):
    """
    1:1 채팅방 엔티티

    Attributes:
        id: 채팅방 고유 ID
        user_1_id: 첫 번째 사용자 ID
        user_2_id: 두 번째 사용자 ID
        created_at: 생성 시각
        updated_at: 마지막 수정 시각
    """
    __tablename__ = "chat_rooms"

    id = Column(Integer, primary_key=True, index=True)

    # Note: MSA 원칙에 따라 FK 제약조건 제거
    # User 데이터는 user-service에서 관리, user_id만 정수로 저장
    user_1_id = Column(Integer, nullable=False, index=True, comment="첫 번째 사용자 ID")
    user_2_id = Column(Integer, nullable=False, index=True, comment="두 번째 사용자 ID")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships (동일 서비스 내 모델만)
    room_members = relationship("RoomMember", back_populates="chat_room", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChatRoom(id={self.id}, user_1_id={self.user_1_id}, user_2_id={self.user_2_id})>"
