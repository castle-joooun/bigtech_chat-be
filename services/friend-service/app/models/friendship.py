from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database.mysql import Base


class Friendship(Base):
    __tablename__ = "friendships"

    id = Column(Integer, primary_key=True, index=True)
    user_id_1 = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # Friend requester
    user_id_2 = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # Friend target
    status = Column(String(20), default="pending")  # pending, accepted
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)  # soft delete

    def __repr__(self):
        return f"<Friendship(user_id_1={self.user_id_1}, user_id_2={self.user_id_2}, status={self.status})>"


class BlockUser(Base):
    __tablename__ = "block_users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # Blocker
    blocked_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # Blocked user
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<BlockUser(user_id={self.user_id}, blocked_user_id={self.blocked_user_id})>"
