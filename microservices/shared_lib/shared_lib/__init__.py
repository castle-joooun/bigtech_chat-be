"""
BigTech Chat Shared Library
===========================

MSA 서비스들의 공통 인프라 코드를 제공합니다.

모듈 구성
---------
- core: 에러 처리, 검증, 설정
- utils: JWT 인증 유틸리티
- database: MySQL, Redis 연결 관리
- cache: Redis 기반 범용 캐싱
- api: FastAPI 의존성 (인증)
- kafka: Kafka Producer
"""

__version__ = "0.1.0"

# Cache 모듈 export (redis 패키지가 있는 경우)
try:
    from .cache import CacheService, get_cache_service, cached, cache_aside
    __all__ = ["CacheService", "get_cache_service", "cached", "cache_aside"]
except ImportError:
    __all__ = []

# Clients 모듈 export (httpx 패키지가 있는 경우)
try:
    from .clients import (
        UserClient, UserClientError, UserNotFoundError,
        UserServiceUnavailableError, get_user_client, init_user_client
    )
    __all__.extend([
        "UserClient", "UserClientError", "UserNotFoundError",
        "UserServiceUnavailableError", "get_user_client", "init_user_client"
    ])
except ImportError:
    pass

# Schemas 모듈 export
try:
    from .schemas import UserProfile, UserProfileMinimal
    __all__.extend(["UserProfile", "UserProfileMinimal"])
except ImportError:
    pass
