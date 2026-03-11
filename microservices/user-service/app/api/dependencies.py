"""
API Dependencies (API 의존성)
============================

인증을 처리하는 의존성 함수입니다.

인증 플로우 (Hybrid 방식)
--------------------------
1. Gateway에서 X-User-* 헤더가 전달되면 해당 정보 사용
2. Authorization 헤더가 있으면 직접 JWT 검증
3. 둘 다 없으면 401 에러

주의사항
--------
- 프로덕션에서는 Gateway를 통한 접근만 허용해야 합니다.
- 직접 접근은 개발/테스트 환경에서만 사용하세요.

관련 파일
---------
- app/utils/auth.py: JWT 검증 유틸리티
"""

from typing import Optional
from dataclasses import dataclass
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mysql import get_async_session
from app.models.user import User
from app.services.auth_service import find_user_by_id
from app.utils.auth import decode_access_token


# =============================================================================
# Gateway에서 전달하는 인증 헤더
# =============================================================================
X_USER_ID = "X-User-ID"
X_USER_EMAIL = "X-User-Email"
X_USER_USERNAME = "X-User-Username"
X_USER_AUTHENTICATED = "X-User-Authenticated"


# =============================================================================
# CurrentUser 데이터 클래스
# =============================================================================
@dataclass
class CurrentUserInfo:
    """현재 사용자 정보"""
    id: int
    email: Optional[str] = None
    username: Optional[str] = None


# =============================================================================
# Authentication Dependencies
# =============================================================================

def _extract_token_from_header(authorization: str) -> Optional[str]:
    """Authorization 헤더에서 Bearer 토큰 추출"""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


def get_current_user_info(request: Request) -> CurrentUserInfo:
    """
    현재 사용자 정보 추출 (Hybrid 인증)

    1. Gateway에서 X-User-* 헤더가 있으면 사용
    2. Authorization 헤더가 있으면 JWT 직접 검증
    3. 둘 다 없으면 401 에러

    Returns:
        CurrentUserInfo: 사용자 ID, 이메일, 사용자명

    Raises:
        HTTPException 401: 인증되지 않은 경우
    """
    # 1. Gateway 헤더 확인
    authenticated = request.headers.get(X_USER_AUTHENTICATED, "false")
    if authenticated.lower() == "true":
        user_id = request.headers.get(X_USER_ID)
        if user_id:
            return CurrentUserInfo(
                id=int(user_id),
                email=request.headers.get(X_USER_EMAIL),
                username=request.headers.get(X_USER_USERNAME)
            )

    # 2. Authorization 헤더로 직접 JWT 검증
    authorization = request.headers.get("Authorization", "")
    token = _extract_token_from_header(authorization)

    if token:
        payload = decode_access_token(token)
        if payload:
            return CurrentUserInfo(
                id=int(payload.get("sub")),
                email=payload.get("email"),
                username=payload.get("username")
            )

    # 3. 인증 실패
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"}
    )


def get_optional_user_info(request: Request) -> Optional[CurrentUserInfo]:
    """
    선택적 사용자 정보 추출 (인증 없어도 됨)

    Returns:
        CurrentUserInfo 또는 None
    """
    try:
        return get_current_user_info(request)
    except HTTPException:
        return None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_async_session)
) -> User:
    """
    현재 인증된 사용자 조회 (DB에서 전체 User 객체 반환)

    Args:
        request: FastAPI Request 객체
        db: 데이터베이스 세션

    Returns:
        User: 인증된 사용자 객체

    Raises:
        HTTPException 401: 인증되지 않은 경우
        HTTPException 404: 사용자가 존재하지 않는 경우
    """
    user_info = get_current_user_info(request)

    # DB에서 사용자 조회
    user = await find_user_by_id(db, user_info.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_async_session)
) -> Optional[User]:
    """
    선택적 사용자 인증 (DB에서 전체 User 객체 반환)

    인증되지 않은 경우 None을 반환합니다.

    Args:
        request: FastAPI Request 객체
        db: 데이터베이스 세션

    Returns:
        User 또는 None
    """
    user_info = get_optional_user_info(request)
    if not user_info:
        return None

    user = await find_user_by_id(db, user_info.id)
    return user
