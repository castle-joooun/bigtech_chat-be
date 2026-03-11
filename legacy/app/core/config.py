"""
환경 설정 관리 모듈 (Configuration Management Module)

================================================================================
아키텍처 개요 (Architecture Overview)
================================================================================
이 모듈은 Pydantic Settings를 사용하여 애플리케이션의 환경 설정을 관리합니다.
12-Factor App 원칙을 따라 모든 설정을 환경 변수로 관리하며,
.env 파일을 통해 로컬 개발 환경을 지원합니다.

설정 흐름:
    .env 파일 → 환경 변수 → Pydantic Settings → settings 인스턴스
                              ↓
                    타입 검증 & 기본값 적용

================================================================================
디자인 패턴 (Design Patterns)
================================================================================
1. Singleton Pattern (싱글톤 패턴)
   - settings 인스턴스가 모듈 로드 시 한 번만 생성됨
   - 애플리케이션 전체에서 동일한 설정 인스턴스 공유

2. Configuration Object Pattern (설정 객체 패턴)
   - 설정 값들을 하나의 객체로 캡슐화
   - 타입 안전성과 자동 완성 지원

================================================================================
SOLID 원칙 적용 (SOLID Principles)
================================================================================
- SRP (단일 책임): 환경 설정 로드 및 검증만 담당
- OCP (개방-폐쇄): 새로운 설정 추가 시 기존 코드 수정 없이 확장 가능
- DIP (의존성 역전): 다른 모듈들이 settings 객체에 의존하여 설정 접근

================================================================================
사용 예시 (Usage Examples)
================================================================================
>>> from legacy.app.core.config import settings
>>> print(settings.app_name)
'BigTech Chat Backend'
>>> print(settings.redis_url)
'redis://localhost:6379/0'

환경 변수 우선순위:
    시스템 환경 변수 > .env 파일 > 기본값
"""

from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()  # .env 파일 로드


class Settings(BaseSettings):
    """
    애플리케이션 전역 설정 클래스

    Pydantic Settings를 상속하여 환경 변수 자동 로딩 및 타입 검증을 제공합니다.
    모든 설정 값은 환경 변수 또는 .env 파일에서 로드됩니다.

    Attributes:
        mongo_url (str): MongoDB 연결 URL (필수)
        mysql_url (str): MySQL 연결 URL (필수)
        redis_url (str): Redis 연결 URL (기본: redis://localhost:6379/0)
        secret_key (str): JWT 토큰 암호화 키 (필수, 보안상 강력한 키 사용 권장)
        algorithm (str): JWT 알고리즘 (기본: HS256)
        access_token_expire_hours (int): 액세스 토큰 만료 시간 (기본: 2시간)
        debug (bool): 디버그 모드 활성화 (기본: False)
        app_name (str): 애플리케이션 이름
        version (str): 애플리케이션 버전
        redis_max_connections (int): Redis 연결 풀 최대 연결 수 (기본: 20)
        rate_limit_enabled (bool): Rate Limiting 활성화 여부
        rate_limit_requests_per_minute (int): 분당 최대 요청 수

    Example:
        >>> settings = Settings()
        >>> settings.debug
        False
        >>> settings.access_token_expire_hours
        2
    """
    # Database URLs
    mongo_url: str
    mysql_url: str
    redis_url: str = "redis://localhost:6379/0"

    # JWT Settings
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_hours: int = 2

    # App Settings
    debug: bool = False
    app_name: str = "BigTech Chat Backend"
    version: str = "1.0.0"

    # Redis Settings
    redis_max_connections: int = 20
    redis_retry_on_timeout: bool = True
    redis_socket_keepalive: bool = True
    redis_socket_keepalive_options: dict = {}

    # Rate Limiting Settings
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60
    rate_limit_burst: int = 10

    class Config:
        """
        Pydantic Settings 메타 설정

        Attributes:
            env_file: 환경 변수 파일 경로 (.env)
            case_sensitive: 환경 변수 대소문자 구분 여부 (False = 구분 안함)
        """
        env_file = ".env"
        case_sensitive = False


# =============================================================================
# 전역 설정 인스턴스 (Global Settings Instance)
# =============================================================================
# 모듈 로드 시 한 번만 생성되는 싱글톤 인스턴스입니다.
# 애플리케이션 전체에서 이 인스턴스를 import하여 설정에 접근합니다.
#
# 사용 예시:
#     from legacy.app.core.config import settings
#     jwt_key = settings.secret_key
# =============================================================================
settings = Settings()
