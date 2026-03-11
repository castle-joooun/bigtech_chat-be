from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.mysql import Base


class RoomMember(Base):
    """
    채팅방 멤버십 테이블 (MSA 버전)
    NOTE: MSA에서는 서비스 간 외래 키 참조가 불가능하므로
          user_id는 외래 키 없이 정수로만 저장
    """
    __tablename__ = "room_members"

    id = Column(Integer, primary_key=True, index=True)
    # MSA: users 테이블은 user-service에 있으므로 ForeignKey 제거
    user_id = Column(Integer, nullable=False, index=True)
    chat_room_id = Column(Integer, ForeignKey("chat_rooms.id"), nullable=False, index=True)

    # 시간 정보
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships - chat_room만 유지 (같은 서비스 내 테이블)
    chat_room = relationship("ChatRoom", back_populates="room_members")

    def __repr__(self):
        return f"<RoomMember(id={self.id}, user_id={self.user_id}, chat_room_id={self.chat_room_id})>"