"""
Friendship Domain Models (친구 관계 도메인 모델)
==============================================

친구 관계를 위한 SQLAlchemy ORM 모델입니다.

양방향 관계 설계
----------------
친구 관계는 양방향으로 저장하지 않습니다.
- 저장: (user_id_1=A, user_id_2=B) 한 번만
- 조회: OR 조건으로 양방향 검색

```
A → B 친구 요청: user_id_1=A, user_id_2=B
B → A 조회 시:  WHERE user_id_1=B OR user_id_2=B
```

데이터베이스 스키마
-------------------
```sql
CREATE TABLE friendships (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id_1 INT NOT NULL,          -- 요청자 (FK → users.id)
    user_id_2 INT NOT NULL,          -- 대상자 (FK → users.id)
    status VARCHAR(20) DEFAULT 'pending',
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW() ON UPDATE NOW(),
    deleted_at DATETIME NULL,        -- Soft Delete

    INDEX idx_user_1 (user_id_1),
    INDEX idx_user_2 (user_id_2),
    UNIQUE idx_unique_friendship (user_id_1, user_id_2)
);
```

Soft Delete
-----------
- deleted_at: 논리적 삭제 시각
- NULL이면 활성 레코드
- 모든 쿼리에 deleted_at IS NULL 조건 필요
"""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, String
from app.database.mysql import Base


class Friendship(Base):
    """
    친구 관계 엔티티 (Aggregate Root)

    두 사용자 간의 친구 관계를 나타냅니다.

    상태 머신:
        ```
        pending ──accept──▶ accepted
           │
           │ reject/cancel
           ▼
        deleted (soft)
        ```

    Attributes:
        id: Primary Key
        user_id_1: 친구 요청을 보낸 사용자 (FK)
        user_id_2: 친구 요청을 받은 사용자 (FK)
        status: 관계 상태 ('pending', 'accepted')
        created_at: 요청 생성 시각
        updated_at: 마지막 수정 시각
        deleted_at: 삭제 시각 (Soft Delete)

    비즈니스 규칙:
        - user_id_1이 항상 요청자
        - user_id_2만 수락/거절 가능
        - 중복 관계 불가 (UNIQUE 인덱스)
    """

    __tablename__ = "friendships"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        comment="친구 관계 고유 식별자"
    )

    # Note: MSA 원칙에 따라 FK 제약조건 제거
    # User 데이터는 user-service에서 관리, user_id만 정수로 저장
    user_id_1 = Column(
        Integer,
        nullable=False,
        index=True,
        comment="친구 요청을 보낸 사용자 ID"
    )

    user_id_2 = Column(
        Integer,
        nullable=False,
        index=True,
        comment="친구 요청을 받은 사용자 ID"
    )

    status = Column(
        String(20),
        default="pending",
        comment="관계 상태: pending(대기), accepted(수락)"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        comment="요청 생성 시각 (UTC)"
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="마지막 수정 시각 (UTC)"
    )

    deleted_at = Column(
        DateTime,
        nullable=True,
        comment="삭제 시각 (Soft Delete, NULL이면 활성)"
    )

    def __repr__(self):
        return f"<Friendship(user_id_1={self.user_id_1}, user_id_2={self.user_id_2}, status={self.status})>"
