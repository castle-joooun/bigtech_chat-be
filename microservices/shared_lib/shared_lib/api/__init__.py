"""
API Module (API 모듈)
====================

FastAPI 인증 의존성을 제공합니다.
"""

from .dependencies import (
    # Constants
    X_USER_ID,
    X_USER_EMAIL,
    X_USER_USERNAME,
    X_USER_AUTHENTICATED,
    # Data Classes
    CurrentUserInfo,
    # Functions
    extract_token_from_header,
    create_auth_dependency,
)

__all__ = [
    "X_USER_ID",
    "X_USER_EMAIL",
    "X_USER_USERNAME",
    "X_USER_AUTHENTICATED",
    "CurrentUserInfo",
    "extract_token_from_header",
    "create_auth_dependency",
]
