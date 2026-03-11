"""
User Entity (사용자 엔티티)
===========================

사용자 정보를 관리하는 핵심 도메인 엔티티입니다.

테이블 스키마
-------------
```sql
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    status_message VARCHAR(500),
    is_online BOOLEAN DEFAULT FALSE,
    last_seen_at DATETIME,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW() ON UPDATE NOW(),

    INDEX idx_email (email),
    INDEX idx_username (username)
);
```

필드 분류
---------
| 분류      | 필드                              |
|----------|----------------------------------|
| 인증 정보 | email, password_hash             |
| 식별 정보 | id, username, display_name       |
| 프로필    | status_message                   |
| 상태 정보 | is_online, last_seen_at, is_active|
| 시간 정보 | created_at, updated_at           |

관련 파일
---------
- app/schemas/user.py: API 스키마
- app/services/auth_service.py: 사용자 CRUD
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.database.mysql import Base


class User(Base):
    """
    사용자 엔티티 (SQLAlchemy ORM 모델)

    채팅 애플리케이션의 핵심 사용자 정보를 관리합니다.

    Attributes:
        id: 사용자 고유 식별자 (PK)
        email: 이메일 (UNIQUE, 로그인 ID)
        password_hash: bcrypt 해시된 비밀번호
        username: 사용자명 (UNIQUE, 검색용)
        display_name: 표시명 (선택)
        status_message: 상태 메시지
        is_online: 현재 온라인 여부
        last_seen_at: 마지막 접속 시간
        is_active: 계정 활성화 상태
        created_at: 계정 생성 시간
        updated_at: 마지막 수정 시간

    Relationships:
        - chat_rooms_*: 1:1 채팅방 (양방향)
        - room_memberships: 채팅방 멤버십
        - friendship_*: 친구 관계 (양방향)

    인덱스:
        - email: UNIQUE INDEX (로그인 조회)
        - username: UNIQUE INDEX (검색, 친구 추가)
    """
    __tablename__ = "users"

    # ==========================================================================
    # Primary Key
    # ==========================================================================
    id = Column(Integer, primary_key=True, index=True)

    # ==========================================================================
    # Authentication Fields (인증 정보)
    # ==========================================================================
    email = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="사용자 이메일 (로그인 ID)"
    )
    password_hash = Column(
        String(255),
        nullable=False,
        comment="bcrypt 해시 비밀번호"
    )

    # ==========================================================================
    # Identity Fields (식별 정보)
    # ==========================================================================
    username = Column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="사용자명 (고유, 검색용)"
    )
    display_name = Column(
        String(100),
        nullable=True,
        comment="표시명 (없으면 username 사용)"
    )

    # ==========================================================================
    # Profile Fields (프로필 정보)
    # ==========================================================================
    status_message = Column(String(500), nullable=True, comment="사용자 상태 메시지")

    # ==========================================================================
    # Status Fields (상태 정보)
    # ==========================================================================
    is_online = Column(Boolean, default=False, nullable=False, comment="온라인 상태")
    last_seen_at = Column(DateTime, nullable=True, comment="마지막 접속 시간")
    is_active = Column(Boolean, default=True, nullable=False, comment="계정 활성화 상태")

    # ==========================================================================
    # Timestamp Fields (시간 정보)
    # ==========================================================================
    created_at = Column(DateTime, default=datetime.utcnow, comment="계정 생성 시간")
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="마지막 수정 시간"
    )

    # ==========================================================================
    # Relationships (관계 정의)
    # ==========================================================================
    # NOTE: MSA 아키텍처에서는 서비스 간 관계를 직접 정의하지 않습니다.
    # - ChatRoom, RoomMember → chat-service
    # - Friendship → friend-service
    # 서비스 간 통신은 API 또는 이벤트를 통해 처리됩니다.

    # ==========================================================================
    # Magic Methods
    # ==========================================================================
    def __repr__(self):
        """디버깅용 문자열 표현"""
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"
