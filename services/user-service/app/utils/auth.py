import os
import re
import secrets
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Thread pool for CPU-bound bcrypt operations
_executor = ThreadPoolExecutor(max_workers=4)


def verify_password(plain_password, hashed_password):
    """Synchronous password verification (for backward compatibility)"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """Synchronous password hashing (for backward compatibility)"""
    return pwd_context.hash(password)


async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    """Async password verification - offloads bcrypt to thread pool"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor, pwd_context.verify, plain_password, hashed_password
    )


async def get_password_hash_async(password: str) -> str:
    """Async password hashing - offloads bcrypt to thread pool"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, pwd_context.hash, password)


def validate_password(password: str) -> bool:
    """
    비밀번호 검증
    - 8-16자
    - 영문자, 숫자, 특수문자 포함
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
    """JWT 액세스 토큰 생성"""
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
    """JWT 액세스 토큰 디코드"""
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


# CSRF 기능은 MVP에서 제거됨


# CSRF 기능은 MVP에서 제거됨
