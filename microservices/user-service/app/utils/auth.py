"""
Authentication Utilities (인증 유틸리티)
======================================

JWT 토큰 및 비밀번호 해싱을 담당하는 보안 유틸리티입니다.

인증 플로우
-----------
```
1. 회원가입
   Password → bcrypt hash → DB 저장

2. 로그인
   Password + Stored Hash → bcrypt verify → JWT 발급

3. API 요청
   JWT → decode & verify → 사용자 정보 추출
```

JWT 토큰 구조
-------------
```
Header.Payload.Signature

Payload:
{
    "sub": "user_id",          # 사용자 ID
    "email": "user@example.com",
    "exp": 1234567890,         # 만료 시간 (Unix timestamp)
    "type": "access"           # 토큰 타입
}
```

bcrypt 비동기 처리
------------------
bcrypt는 CPU-bound 작업이므로 이벤트 루프를 블로킹합니다.
ThreadPoolExecutor로 오프로드하여 비동기 처리합니다.

```
┌─────────────┐     ┌─────────────────────┐
│ Event Loop  │────▶│   ThreadPoolExecutor │
│  (async)    │     │   (bcrypt 연산)      │
└─────────────┘     └─────────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  CPU Core   │
                    └─────────────┘
```

보안 고려사항
-------------
- bcrypt: work factor 12 (기본값)
- JWT: HS256 (HMAC-SHA256)
- 비밀번호: 8-16자, 영문+숫자+특수문자

SOLID 원칙
----------
- SRP: 인증 관련 유틸리티만 담당
- OCP: 새 해싱 알고리즘 추가 시 CryptContext 설정만 변경

관련 파일
---------
- app/core/config.py: secret_key, algorithm 설정
- app/services/auth_service.py: 로그인/회원가입 로직
- app/api/auth.py: 인증 API 엔드포인트
"""

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


# =============================================================================
# Password Hashing Configuration
# =============================================================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
"""
비밀번호 해싱 컨텍스트

schemes=["bcrypt"]:
    bcrypt 알고리즘 사용 (현재 가장 안전한 선택)
    - work factor: 12 (기본값, 약 250ms/hash)
    - salt: 자동 생성

deprecated="auto":
    향후 다른 알고리즘 추가 시 자동 마이그레이션
"""


# =============================================================================
# Thread Pool for CPU-bound Operations
# =============================================================================
_executor = ThreadPoolExecutor(max_workers=4)
"""
bcrypt 연산용 스레드 풀

bcrypt는 의도적으로 느린 알고리즘이므로 (약 250ms)
이벤트 루프를 블로킹하지 않도록 별도 스레드에서 실행합니다.

max_workers=4:
    CPU 코어 수에 맞춰 조정 가능
    너무 많으면 컨텍스트 스위칭 오버헤드 발생
"""


# =============================================================================
# Password Functions (비밀번호 함수)
# =============================================================================

def verify_password(plain_password, hashed_password):
    """
    비밀번호 검증 (동기 버전)

    평문 비밀번호와 해시된 비밀번호를 비교합니다.

    Args:
        plain_password: 사용자 입력 비밀번호
        hashed_password: DB에 저장된 해시

    Returns:
        bool: 일치하면 True

    참고:
        동기 함수이므로 이벤트 루프를 블로킹합니다.
        가능하면 verify_password_async()를 사용하세요.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """
    비밀번호 해싱 (동기 버전)

    평문 비밀번호를 bcrypt로 해싱합니다.

    Args:
        password: 해싱할 비밀번호

    Returns:
        str: bcrypt 해시 (salt 포함)

    해시 형식:
        $2b$12$[22자 salt][31자 hash]
        예: $2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36

    참고:
        동기 함수이므로 이벤트 루프를 블로킹합니다.
        가능하면 get_password_hash_async()를 사용하세요.
    """
    return pwd_context.hash(password)


async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    """
    비밀번호 검증 (비동기 버전, 권장)

    ThreadPoolExecutor로 CPU-bound bcrypt 연산을 오프로드합니다.

    Args:
        plain_password: 사용자 입력 비밀번호
        hashed_password: DB에 저장된 해시

    Returns:
        bool: 일치하면 True

    성능:
        이벤트 루프를 블로킹하지 않아 동시 요청 처리 가능

    사용 예시:
        is_valid = await verify_password_async(
            request.password,
            user.hashed_password
        )
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor, pwd_context.verify, plain_password, hashed_password
    )


async def get_password_hash_async(password: str) -> str:
    """
    비밀번호 해싱 (비동기 버전, 권장)

    ThreadPoolExecutor로 CPU-bound bcrypt 연산을 오프로드합니다.

    Args:
        password: 해싱할 비밀번호

    Returns:
        str: bcrypt 해시 (salt 포함)

    사용 예시:
        hashed = await get_password_hash_async(request.password)
        user.hashed_password = hashed
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, pwd_context.hash, password)


def validate_password(password: str) -> bool:
    """
    비밀번호 정책 검증

    비밀번호가 보안 정책을 만족하는지 확인합니다.

    정책:
        - 길이: 8-16자
        - 영문자: 최소 1개 (대소문자 무관)
        - 숫자: 최소 1개
        - 특수문자: 최소 1개

    특수문자 목록:
        !"#$%&'()*+,-./:;<=>?@[\]^_`{|}~

    Args:
        password: 검증할 비밀번호

    Returns:
        bool: 정책 만족 시 True

    참고:
        상세한 에러 메시지가 필요하면 Validator.validate_password_strength() 사용
    """
    if len(password) < 8 or len(password) > 16:
        return False

    special_symbols = r'!"#$%&\'()*+,\-.\/:;<=>?@[\\\]^_`{|}~'

    # 영문자, 숫자, 특수문자 각각 1개 이상 포함 확인
    has_letter = bool(re.search(r'[a-zA-Z]', password))
    has_digit = bool(re.search(r'\d', password))
    has_special = bool(re.search(rf'[{re.escape(special_symbols)}]', password))

    return has_letter and has_digit and has_special


# =============================================================================
# JWT Token Functions (JWT 토큰 함수)
# =============================================================================

def create_access_token(data: Dict[str, Any],
                        expires_delta: Optional[timedelta] = None) -> str:
    """
    JWT 액세스 토큰 생성

    사용자 정보를 담은 JWT 토큰을 생성합니다.

    Args:
        data: 토큰에 포함할 데이터 (sub, email 등)
        expires_delta: 만료 시간 (기본: settings.access_token_expire_hours)

    Returns:
        str: 서명된 JWT 토큰

    토큰 구조:
        {
            ...data,
            "exp": <만료 Unix timestamp>,
            "type": "access"
        }

    알고리즘:
        HS256 (HMAC-SHA256) - 대칭키 서명

    사용 예시:
        token = create_access_token(
            data={"sub": str(user.id), "email": user.email}
        )
        # → eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

    보안 참고:
        secret_key는 환경 변수로 관리
        프로덕션에서는 256비트 이상 권장
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


# =============================================================================
# MVP에서 제거된 기능: Refresh Token
# =============================================================================
# Refresh Token은 SPA 환경에서의 토큰 갱신을 위해 사용됩니다.
# MVP에서는 단순화를 위해 Access Token만 사용합니다.
# 필요 시 향후 구현 예정.


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    JWT 액세스 토큰 디코드 및 검증

    토큰의 서명을 검증하고 페이로드를 추출합니다.

    Args:
        token: JWT 토큰 문자열

    Returns:
        Optional[Dict]: 페이로드 또는 None (유효하지 않은 경우)

    검증 항목:
        1. 서명 유효성 (secret_key로 검증)
        2. 만료 시간 (exp claim)
        3. 토큰 타입 (type == "access")

    실패 케이스:
        - 서명 불일치: JWTError → None
        - 만료됨: ExpiredSignatureError → None
        - 잘못된 타입: type != "access" → None

    사용 예시:
        payload = decode_access_token(token)
        if payload:
            user_id = payload.get("sub")
        else:
            raise AuthenticationException()

    보안 참고:
        algorithms 파라미터로 허용 알고리즘 명시
        알고리즘 혼동 공격 방지
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


# =============================================================================
# MVP에서 제거된 기능들
# =============================================================================
# - Refresh Token: Access Token만 사용 (단순화)
# - CSRF Protection: SPA + JWT 환경에서 불필요
#   (JWT는 쿠키가 아닌 Authorization 헤더로 전송)
