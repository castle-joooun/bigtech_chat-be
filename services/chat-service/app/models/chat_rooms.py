from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database.mysql import Base


class ChatRoom(Base):
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
