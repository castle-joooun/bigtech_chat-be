from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.mysql import Base


class BlockUser(Base):
    __tablename__ = "block_users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # User who blocks
    blocked_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # User being blocked
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    blocker = relationship("User", foreign_keys=[user_id], back_populates="blocking")
    blocked = relationship("User", foreign_keys=[blocked_user_id], back_populates="blocked_by")

    def __repr__(self):
        return f"<BlockUser(user_id={self.user_id}, blocked_user_id={self.blocked_user_id})>"

