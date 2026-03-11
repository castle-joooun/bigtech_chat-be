"""
친구 관계 모델 (Friendship Model)

================================================================================
아키텍처 개요 (Architecture Overview)
================================================================================
사용자 간의 친구 관계를 저장하는 SQLAlchemy ORM 모델입니다.
친구 요청, 수락, 거절 상태를 관리합니다.

상태 흐름:
    친구 요청 → pending → accepted (친구 성립)
                      └→ soft delete (거절/취소)

관계 설계:
    - user_id_1: 친구 요청을 보낸 사용자 (requester)
    - user_id_2: 친구 요청을 받은 사용자 (target)
    - 양방향 관계이지만 단일 레코드로 관리

소프트 삭제:
    거절된 친구 요청은 deleted_at 필드로 소프트 삭제 처리됩니다.
    추후 다시 친구 요청이 가능합니다.

================================================================================
사용 예시 (Usage Examples)
================================================================================
>>> # 친구 요청 생성
>>> friendship = Friendship(user_id_1=1, user_id_2=2, status="pending")
>>>
>>> # 친구 수락
>>> friendship.status = "accepted"
>>> friendship.updated_at = datetime.utcnow()
>>>
>>> # 친구 거절 (소프트 삭제)
>>> friendship.deleted_at = datetime.utcnow()
"""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, String, ForeignKey
from sqlalchemy.orm import relationship
from legacy.app.database.mysql import Base


class Friendship(Base):
    """
    친구 관계 SQLAlchemy 모델

    Attributes:
        id (int): 친구 관계 고유 ID
        user_id_1 (int): 친구 요청 발신자 ID
        user_id_2 (int): 친구 요청 수신자 ID
        status (str): 상태 ("pending", "accepted")
        created_at (datetime): 친구 요청 시간
        updated_at (datetime): 상태 변경 시간
        deleted_at (datetime): 소프트 삭제 시간 (Optional)

    Relationships:
        requester (User): 요청을 보낸 사용자
        target (User): 요청을 받은 사용자
    """
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
