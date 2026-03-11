"""
Friend Service Configuration (친구 서비스 설정)
=============================================

환경 변수를 통한 설정 관리를 담당합니다.

서비스 역할
-----------
Friend Service는 친구 관계 관리를 담당하는 마이크로서비스입니다.

```
┌─────────────────────────────────────────────────────────────┐
│                     Friend Service                           │
│                                                              │
│  기능:                                                       │
│  - 친구 요청 전송/수락/거절                                   │
│  - 친구 목록 조회                                             │
│  - 사용자 검색 (친구 추가용)                                   │
│  - 사용자 차단                                                │
│                                                              │
│  포트: 8003                                                   │
│  Kafka Topic: friend.events                                  │
└─────────────────────────────────────────────────────────────┘
```

다른 서비스와의 관계
--------------------
| 서비스       | 포트 | 역할                    |
|-------------|------|------------------------|
| User        | 8001 | 사용자 인증/프로필       |
| Chat        | 8002 | 채팅 메시지              |
| Friend      | 8003 | 친구 관계 (현재 서비스)   |

관련 파일
---------
- main.py: 서비스 엔트리포인트
- app/services/friendship_service.py: 비즈니스 로직
- app/api/friend.py: API 엔드포인트
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """
    Friend Service 설정 클래스

    Pydantic Settings를 사용하여 환경 변수를 자동 로딩합니다.

    Attributes:
        app_name: 서비스 이름
        version: API 버전
        port: 서버 포트 (Friend Service: 8003)
        mysql_url: MySQL 연결 URL
        redis_url: Redis 연결 URL
        kafka_bootstrap_servers: Kafka 브로커 주소
        kafka_topic_friend_events: 친구 이벤트 토픽
        secret_key: JWT 서명 키
    """

    # ==========================================================================
    # Application Settings
    # ==========================================================================
    app_name: str = "Friend Service"
    version: str = "1.0.0"
    debug: bool = True

    # ==========================================================================
    # Server Settings
    # ==========================================================================
    host: str = "0.0.0.0"
    port: int = 8003  # Friend Service 전용 포트

    # ==========================================================================
    # Database Settings
    # ==========================================================================
    mysql_url: str  # 필수: 친구 관계 저장
    redis_url: str = "redis://localhost:6379"  # 캐시용 (선택)

    # ==========================================================================
    # Kafka Settings
    # ==========================================================================
    kafka_bootstrap_servers: str = "localhost:19092,localhost:19093,localhost:19094"
    kafka_topic_friend_events: str = "friend.events"

    # ==========================================================================
    # JWT Settings (토큰 검증용)
    # ==========================================================================
    secret_key: str  # User Service와 동일한 키 사용
    algorithm: str = "HS256"
    access_token_expire_hours: int = 2

    # ==========================================================================
    # Service URLs (MSA 서비스 간 통신)
    # ==========================================================================
    user_service_url: str = "http://localhost:8005"  # user-service API URL

    # ==========================================================================
    # CORS Settings
    # ==========================================================================
    cors_origins: List[str] = ["http://localhost:3000"]

    # ==========================================================================
    # File Upload Settings (미사용, 호환성 유지)
    # ==========================================================================
    upload_dir: str = "uploads"
    max_upload_size: int = 5 * 1024 * 1024  # 5MB

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


# Singleton 인스턴스
settings = Settings()
