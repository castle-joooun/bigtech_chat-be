from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.mysql import Base


class RoomMember(Base):
    """
    채팅방 멤버십 테이블 (단순화된 MVP 버전)
    """
    __tablename__ = "room_members"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    chat_room_id = Column(Integer, ForeignKey("chat_rooms.id"), nullable=False, index=True)
    
    # 시간 정보
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="room_memberships")
    chat_room = relationship("ChatRoom", back_populates="room_members")

    def __repr__(self):
        return f"<RoomMember(id={self.id}, user_id={self.user_id}, chat_room_id={self.chat_room_id})>"