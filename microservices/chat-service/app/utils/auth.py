"""
JWT Token Utilities (JWT 토큰 유틸리티)
======================================

JWT 토큰 검증만 담당합니다.
토큰 생성, 비밀번호 해싱은 user-service에서만 처리합니다.
"""
from typing import Optional, Dict, Any
from jose import JWTError, jwt

from app.core.config import settings


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    JWT 액세스 토큰 디코드

    Args:
        token: JWT 토큰 문자열

    Returns:
        디코드된 페이로드 또는 None (검증 실패 시)
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        # 액세스 토큰인지 확인
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None
