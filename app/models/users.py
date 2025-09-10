from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.database.mysql import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=False)
    display_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    # Chat rooms (1:1 chat)
    chat_rooms_as_user_1 = relationship("ChatRoom", foreign_keys="ChatRoom.user_id_1", back_populates="user_1")
    chat_rooms_as_user_2 = relationship("ChatRoom", foreign_keys="ChatRoom.user_id_2", back_populates="user_2")
    
    # Friendships
    friendship_requests = relationship("Friendship", foreign_keys="Friendship.user_id_1", back_populates="requester")
    friendship_receives = relationship("Friendship", foreign_keys="Friendship.user_id_2", back_populates="target")
    
    # Group chat rooms
    created_groups = relationship("GroupChatRoom", back_populates="creator")
    group_memberships = relationship("GroupRoomMember", back_populates="user")
    
    # Block relationships
    blocking = relationship("BlockUser", foreign_keys="BlockUser.user_id", back_populates="blocker")
    blocked_by = relationship("BlockUser", foreign_keys="BlockUser.blocked_user_id", back_populates="blocked")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"
