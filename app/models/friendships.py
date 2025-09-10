from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, String
from app.database.mysql import Base


class Friendship(Base):
    __tablename__ = "friendships"

    id = Column(Integer, primary_key=True, index=True)
    user_id_1 = Column(Integer, nullable=False, index=True)
    user_id_2 = Column(Integer, nullable=False, index=True)
    status = Column(String(20), default="pending")  # pending, accepted, rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Friendship(user_id_1={self.user_id_1}, user_id_2={self.user_id_2}, status={self.status})>"
