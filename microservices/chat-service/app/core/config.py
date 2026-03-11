"""
Chat Service Configuration (채팅 서비스 설정)
============================================

환경 변수를 통한 설정 관리를 담당합니다.

Polyglot Persistence
--------------------
Chat Service는 여러 데이터베이스를 사용합니다:

```
┌─────────────────────────────────────────────────────────────┐
│                     Chat Service                             │
│                                                              │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │
│  │     MySQL     │  │    MongoDB    │  │     Redis     │   │
│  │  채팅방 정보   │  │    메시지     │  │    캐시       │   │
│  │  참여자 관계   │  │  읽음 상태    │  │  온라인 상태   │   │
│  └───────────────┘  └───────────────┘  └───────────────┘   │
│                                                              │
│  포트: 8002                                                   │
│  Kafka Topic: message.events                                 │
└─────────────────────────────────────────────────────────────┘
```

데이터베이스 선택 이유
----------------------
| 데이터       | DB      | 이유                          |
|-------------|---------|------------------------------|
| ChatRoom    | MySQL   | 관계형 데이터, JOIN 필요        |
| Message     | MongoDB | 고성능 쓰기, 비정형 데이터       |
| Cache       | Redis   | 실시간 데이터, TTL 지원         |

관련 파일
---------
- main.py: 서비스 엔트리포인트, DB 초기화
- app/database/mongodb.py: MongoDB 연결
- app/database/mysql.py: MySQL 연결
- app/database/redis.py: Redis 연결
"""

from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    """
    Chat Service 설정 클래스

    Pydantic Settings를 사용하여 환경 변수를 자동 로딩합니다.

    Attributes:
        app_name: 서비스 이름
        version: API 버전
        port: 서버 포트 (Chat Service: 8002)
        mysql_url: MySQL 연결 URL (채팅방 저장)
        mongo_url: MongoDB 연결 URL (메시지 저장)
        mongodb_db_name: MongoDB 데이터베이스 이름
        redis_url: Redis 연결 URL (캐시)
        kafka_topic_message_events: 메시지 이벤트 토픽
    """

    # ==========================================================================
    # Application Settings
    # ==========================================================================
    app_name: str = "Chat Service"
    version: str = "1.0.0"
    debug: bool = True

    # ==========================================================================
    # Server Settings
    # ==========================================================================
    host: str = "0.0.0.0"
    port: int = 8002  # Chat Service 전용 포트

    # ==========================================================================
    # Database Settings - MySQL (채팅방 메타데이터)
    # ==========================================================================
    mysql_url: str = "mysql+aiomysql://root:password@localhost:3306/chatdb"

    # ==========================================================================
    # Database Settings - MongoDB (메시지 저장)
    # ==========================================================================
    mongo_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "chatdb"

    # ==========================================================================
    # Database Settings - Redis (캐시)
    # ==========================================================================
    redis_url: str = "redis://localhost:6379"

    # ==========================================================================
    # Kafka Settings (실시간 메시지 스트리밍)
    # ==========================================================================
    kafka_bootstrap_servers: str = "localhost:19092,localhost:19093,localhost:19094"
    kafka_topic_message_events: str = "message.events"

    # ==========================================================================
    # JWT Settings (토큰 검증용)
    # ==========================================================================
    secret_key: str = "your-secret-key-here"  # User Service와 동일한 키 사용
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
    # File Upload Settings (메시지 첨부 파일용)
    # ==========================================================================
    upload_dir: str = "uploads"
    max_upload_size: int = 5 * 1024 * 1024  # 5MB

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


# Singleton 인스턴스
settings = Settings()
