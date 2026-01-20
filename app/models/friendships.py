from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database.mysql import Base


class Friendship(Base):
    __tablename__ = "friendships"

    id = Column(Integer, primary_key=True, index=True)
    user_id_1 = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # Friend requester
    user_id_2 = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # Friend target
    status = Column(String(20), default="pending")  # pending, accepted (rejected는 soft delete 처리)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)  # soft delete를 위한 필드
    
    # Relationships
    requester = relationship("User", foreign_keys=[user_id_1], back_populates="friendship_requests")
    target = relationship("User", foreign_keys=[user_id_2], back_populates="friendship_receives")

    def __repr__(self):
        return f"<Friendship(user_id_1={self.user_id_1}, user_id_2={self.user_id_2}, status={self.status})>"
