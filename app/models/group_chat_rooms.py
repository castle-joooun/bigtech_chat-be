from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.mysql import Base


class GroupChatRoom(Base):
    __tablename__ = "group_chat_rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)  # User ID who created the group
    max_members = Column(Integer, default=50)  # 고정값으로 단순화
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    creator = relationship("User", back_populates="created_groups")
    members = relationship("GroupRoomMember", back_populates="group_room")

    def __repr__(self):
        return f"<GroupChatRoom(id={self.id}, name={self.name}, created_by={self.created_by})>"