from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, Boolean, String
from app.database.mysql import Base


class GroupRoomMember(Base):
    __tablename__ = "group_room_members"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    group_room_id = Column(Integer, nullable=False, index=True)
    role = Column(String(20), default="member")  # owner, admin, member
    is_active = Column(Boolean, default=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
    left_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<GroupRoomMember(user_id={self.user_id}, group_room_id={self.group_room_id}, role={self.role})>"