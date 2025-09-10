from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, Boolean
from app.database.mysql import Base


class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id = Column(Integer, primary_key=True, index=True)
    user_id_1 = Column(Integer, nullable=False, index=True)  # First user in 1:1 chat
    user_id_2 = Column(Integer, nullable=False, index=True)  # Second user in 1:1 chat
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ChatRoom(id={self.id}, user_id_1={self.user_id_1}, user_id_2={self.user_id_2})>"
