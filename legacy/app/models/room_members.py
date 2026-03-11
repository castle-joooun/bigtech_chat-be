"""
채팅방 멤버 모델 (Room Member Model)

================================================================================
아키텍처 개요 (Architecture Overview)
================================================================================
채팅방 멤버십을 관리하는 SQLAlchemy ORM 모델입니다.
현재 MVP에서는 1:1 채팅에서 사용하지 않지만,
향후 그룹 채팅 확장을 위해 준비되어 있습니다.

용도:
    - 채팅방별 사용자 멤버십 관리
    - 채팅방 참여/나가기 시간 추적
    - 그룹 채팅에서 개인별 설정 저장 (예정)

================================================================================
사용 예시 (Usage Examples)
================================================================================
>>> # 멤버십 생성
>>> member = RoomMember(user_id=1, chat_room_id=10)
>>>
>>> # 멤버 조회
>>> members = await db.execute(
...     select(RoomMember).where(RoomMember.chat_room_id == 10)
... )
"""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from legacy.app.database.mysql import Base


class RoomMember(Base):
    """
    채팅방 멤버십 SQLAlchemy 모델 (MVP 단순화 버전)

    Attributes:
        id (int): 멤버십 고유 ID
        user_id (int): 사용자 ID
        chat_room_id (int): 채팅방 ID
        created_at (datetime): 참여 일시
        updated_at (datetime): 마지막 수정 일시

    Note:
        1:1 채팅방에서는 ChatRoom.user_1_id, user_2_id로 직접 관리하므로
        이 테이블은 주로 그룹 채팅에서 사용됩니다.
    """
    __tablename__ = "room_members"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    chat_room_id = Column(Integer, ForeignKey("chat_rooms.id"), nullable=False, index=True)
    
    # 시간 정보
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="room_memberships")
    chat_room = relationship("ChatRoom", back_populates="room_members")

    def __repr__(self):
        return f"<RoomMember(id={self.id}, user_id={self.user_id}, chat_room_id={self.chat_room_id})>"