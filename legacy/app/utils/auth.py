"""
인증 유틸리티 모듈 (Authentication Utilities Module)

================================================================================
아키텍처 개요 (Architecture Overview)
================================================================================
JWT 토큰 생성/검증과 비밀번호 해싱을 처리하는 유틸리티 모듈입니다.
python-jose와 passlib 라이브러리를 사용합니다.

보안 구성:
    ├── 비밀번호: bcrypt 해싱 (salt 자동 생성)
    ├── JWT: HS256 알고리즘, 만료 시간 설정
    └── 토큰 타입: access (refresh token은 MVP에서 제외)

================================================================================
사용 예시 (Usage Examples)
================================================================================
>>> from legacy.app.utils.auth import get_password_hash, verify_password
>>> from legacy.app.utils.auth import create_access_token, decode_access_token
>>>
>>> # 비밀번호 해싱
>>> hashed = get_password_hash("plain_password")
>>>
>>> # 비밀번호 검증
>>> is_valid = verify_password("plain_password", hashed)
>>>
>>> # JWT 토큰 생성
>>> token = create_access_token({"sub": "123", "email": "user@example.com"})
>>>
>>> # JWT 토큰 검증
>>> payload = decode_access_token(token)
>>> user_id = payload.get("sub")
"""

import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from legacy.app.core.config import settings

# =============================================================================
# 비밀번호 해싱 설정 (Password Hashing Configuration)
# =============================================================================
# bcrypt 알고리즘 사용, deprecated 방식 자동 업그레이드
# =============================================================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    비밀번호 검증

    평문 비밀번호와 해시된 비밀번호를 비교합니다.

    Args:
        plain_password: 사용자가 입력한 평문 비밀번호
        hashed_password: DB에 저장된 해시 비밀번호

    Returns:
        bool: 일치 여부
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    비밀번호 해싱

    평문 비밀번호를 bcrypt로 해싱합니다.
    salt는 자동 생성되어 해시에 포함됩니다.

    Args:
        password: 해싱할 평문 비밀번호

    Returns:
        str: bcrypt 해시 문자열
    """
    return pwd_context.hash(password)


def validate_password(password: str) -> bool:
    """
    비밀번호 정책 검증

    비밀번호가 다음 규칙을 만족하는지 확인합니다:
    - 8-16자 길이
    - 영문자 1개 이상 포함
    - 숫자 1개 이상 포함
    - 특수문자 1개 이상 포함

    Args:
        password: 검증할 비밀번호

    Returns:
        bool: 정책 충족 여부
    """
    if len(password) < 8 or len(password) > 16:
        return False

    special_symbols = r'!"#$%&\'()*+,\-.\/:;<=>?@[\\\]^_`{|}~'

    # 영문자, 숫자, 특수문자 각각 1개 이상 포함 확인
    has_letter = bool(re.search(r'[a-zA-Z]', password))
    has_digit = bool(re.search(r'\d', password))
    has_special = bool(re.search(rf'[{re.escape(special_symbols)}]', password))

    return has_letter and has_digit and has_special


def create_access_token(data: Dict[str, Any],
                        expires_delta: Optional[timedelta] = None) -> str:
    """
    JWT 액세스 토큰 생성

    사용자 정보를 담은 JWT 토큰을 생성합니다.
    토큰에는 만료 시간과 타입 정보가 자동으로 추가됩니다.

    Args:
        data: 토큰에 담을 데이터 (sub: 사용자 ID 권장)
        expires_delta: 만료 시간 (기본: settings.access_token_expire_hours)

    Returns:
        str: JWT 토큰 문자열

    Example:
        >>> token = create_access_token(
        ...     data={"sub": "123", "email": "user@example.com"},
        ...     expires_delta=timedelta(hours=2)
        ... )
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            hours=settings.access_token_expire_hours)

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key,
                             algorithm=settings.algorithm)
    return encoded_jwt


# refresh_token 기능은 MVP에서 제거됨


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    JWT 액세스 토큰 디코드 및 검증

    토큰을 디코드하여 페이로드를 반환합니다.
    만료되었거나 유효하지 않은 토큰은 None을 반환합니다.

    Args:
        token: JWT 토큰 문자열

    Returns:
        Optional[Dict]: 토큰 페이로드 또는 None (유효하지 않은 경우)

    Example:
        >>> payload = decode_access_token(token)
        >>> if payload:
        ...     user_id = payload.get("sub")
    """
    try:
        payload = jwt.decode(token, settings.secret_key,
                             algorithms=[settings.algorithm])
        # 액세스 토큰인지 확인
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


# refresh_token 기능은 MVP에서 제거됨


# CSRF 기능은 MVP에서 제거됨

