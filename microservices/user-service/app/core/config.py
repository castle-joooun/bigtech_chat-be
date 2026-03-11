"""
User Service Configuration (사용자 서비스 설정)
=============================================

환경 변수를 통한 설정 관리를 담당합니다.
Pydantic Settings를 사용하여 타입 안전한 설정 관리를 구현합니다.

12-Factor App
-------------
Pydantic Settings는 12-Factor App 방법론의 설정 원칙을 따릅니다.

```
┌─────────────────────────────────────────────────────────────┐
│                    Configuration Sources                     │
├─────────────────────────────────────────────────────────────┤
│  1. 환경 변수 (우선순위 높음)                                 │
│     export MYSQL_URL="mysql://..."                          │
│                                                             │
│  2. .env 파일 (개발 환경)                                    │
│     MYSQL_URL=mysql://...                                   │
│                                                             │
│  3. 기본값 (코드에 정의)                                      │
│     port: int = 8001                                        │
└─────────────────────────────────────────────────────────────┘
```

설정 카테고리
-------------
| 카테고리     | 필드               | 필수 여부 |
|-------------|-------------------|-----------|
| Application | app_name, version | 기본값    |
| Server      | host, port        | 기본값    |
| Database    | mysql_url, redis  | 필수      |
| Kafka       | bootstrap_servers | 기본값    |
| JWT         | secret_key        | 필수      |
| CORS        | cors_origins      | 기본값    |
| File        | upload_dir, size  | 기본값    |

Design Pattern: Singleton
-------------------------
settings 객체는 모듈 레벨에서 한 번만 생성되어
애플리케이션 전체에서 동일한 인스턴스를 공유합니다.

```python
from app.core.config import settings

# 모든 곳에서 동일한 인스턴스
print(settings.app_name)  # "User Service"
```

SOLID 원칙
----------
- SRP: 설정 관리만 담당
- OCP: 새 설정 추가 시 기존 코드 수정 불필요
- DIP: 구체적인 값이 아닌 settings 객체에 의존

관련 파일
---------
- main.py: 서버 시작 시 설정 사용
- app/utils/auth.py: JWT 설정 사용
- app/database/mysql.py: DB URL 사용
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """
    User Service 설정 클래스

    Pydantic BaseSettings를 상속받아 환경 변수 자동 로딩을 지원합니다.

    환경 변수 매핑:
        - 필드명을 대문자로 변환하여 환경 변수와 매핑
        - mysql_url → MYSQL_URL
        - secret_key → SECRET_KEY

    Attributes:
        app_name: 서비스 이름 (Prometheus 라벨, 로그에 사용)
        version: API 버전 (OpenAPI 문서에 표시)
        debug: 디버그 모드 (상세 에러 메시지, 핫 리로드)
        host: 서버 바인딩 호스트
        port: 서버 포트 (User Service: 8001)
        mysql_url: MySQL 연결 URL (필수)
        redis_url: Redis 연결 URL (필수)
        kafka_bootstrap_servers: Kafka 브로커 주소
        secret_key: JWT 서명 키 (필수, 보안 중요)
        algorithm: JWT 알고리즘
        access_token_expire_hours: 토큰 만료 시간
        cors_origins: 허용된 CORS 출처
        upload_dir: 파일 업로드 디렉토리
        max_upload_size: 최대 업로드 크기 (바이트)

    사용 예시:
        from app.core.config import settings

        # 데이터베이스 연결
        engine = create_async_engine(settings.mysql_url)

        # JWT 토큰 생성
        token = jwt.encode(payload, settings.secret_key, settings.algorithm)
    """

    # ==========================================================================
    # Application Settings (애플리케이션 설정)
    # ==========================================================================
    app_name: str = "User Service"
    version: str = "1.0.0"
    debug: bool = True

    # ==========================================================================
    # Server Settings (서버 설정)
    # ==========================================================================
    host: str = "0.0.0.0"
    port: int = 8001  # User Service 전용 포트

    # ==========================================================================
    # Database Settings (데이터베이스 설정)
    # ==========================================================================
    mysql_url: str  # 필수: mysql+aiomysql://user:pass@host:port/db
    redis_url: str  # 필수: redis://host:port/db

    # ==========================================================================
    # Kafka Settings (이벤트 스트리밍 설정)
    # ==========================================================================
    kafka_bootstrap_servers: str = "localhost:19092,localhost:19093,localhost:19094"
    kafka_topic_user_events: str = "user.events"
    kafka_topic_user_online_status: str = "user.online_status"

    # ==========================================================================
    # JWT Settings (인증 설정)
    # ==========================================================================
    secret_key: str  # 필수: 256비트 이상 권장
    algorithm: str = "HS256"  # HMAC-SHA256
    access_token_expire_hours: int = 2  # 토큰 유효 시간

    # ==========================================================================
    # CORS Settings (교차 출처 리소스 공유)
    # ==========================================================================
    cors_origins: List[str] = ["http://localhost:3000"]

    # ==========================================================================
    # File Upload Settings (파일 업로드 설정)
    # ==========================================================================
    upload_dir: str = "uploads"
    max_upload_size: int = 5 * 1024 * 1024  # 5MB

    class Config:
        """
        Pydantic Settings 설정

        Attributes:
            env_file: 환경 변수 파일 경로
            case_sensitive: 환경 변수 대소문자 구분 (False: 무시)
            extra: 정의되지 않은 필드 처리 ("ignore": 무시)
        """
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


# =============================================================================
# Singleton Instance
# =============================================================================
settings = Settings()
