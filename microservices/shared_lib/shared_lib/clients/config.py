"""
Service Configuration
=====================

마이크로서비스 간 통신을 위한 서비스 URL 설정입니다.

환경 변수:
    - USER_SERVICE_URL: user-service의 기본 URL
    - HTTP_TIMEOUT: HTTP 요청 타임아웃 (초)
"""

import os


class ServiceConfig:
    """서비스 URL 및 설정"""

    # User Service
    USER_SERVICE_URL: str = os.getenv("USER_SERVICE_URL", "http://localhost:8005")

    # HTTP 설정
    HTTP_TIMEOUT: float = float(os.getenv("HTTP_TIMEOUT", "10.0"))

    # 캐시 TTL (초)
    CACHE_TTL_USER_PROFILE: int = int(os.getenv("CACHE_TTL_USER_PROFILE", "300"))  # 5분
    CACHE_TTL_USER_EXISTS: int = int(os.getenv("CACHE_TTL_USER_EXISTS", "60"))  # 1분
