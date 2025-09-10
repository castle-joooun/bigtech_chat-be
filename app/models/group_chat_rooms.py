from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from app.database.mysql import Base


class GroupChatRoom(Base):
    __tablename__ = "group_chat_rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_private = Column(Boolean, default=False)  # Private group vs Public group
    created_by = Column(Integer, nullable=False)  # User ID who created the group
    max_members = Column(Integer, default=100)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<GroupChatRoom(id={self.id}, name={self.name}, created_by={self.created_by})>"