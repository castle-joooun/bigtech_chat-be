from datetime import datetime
from sqlalchemy import Column, Integer, DateTime
from app.database.mysql import Base


class BlockUser(Base):
    __tablename__ = "block_users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # User who blocks
    blocked_user_id = Column(Integer, nullable=False, index=True)  # User being blocked
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<BlockUser(user_id={self.user_id}, blocked_user_id={self.blocked_user_id})>"

