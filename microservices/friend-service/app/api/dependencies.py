"""
API Dependencies (API 의존성)
============================

인증을 처리하는 의존성 함수입니다.

인증 플로우 (Hybrid 방식)
--------------------------
1. Gateway에서 X-User-* 헤더가 전달되면 해당 정보 사용
2. Authorization 헤더가 있으면 직접 JWT 검증
3. 둘 다 없으면 401 에러

MSA 원칙
--------
- User DB에 직접 접근하지 않음
- JWT에서 추출한 사용자 정보(CurrentUserInfo)로 인증 처리
- 필요시 user-service API 호출로 상세 정보 조회

관련 파일
---------
- app/utils/auth.py: JWT 검증 유틸리티
- app/services/auth_service.py: user-service API 클라이언트
"""

from typing import Optional
from dataclasses import dataclass
from fastapi import Request, HTTPException, status

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
    """
    현재 사용자 정보

    JWT 토큰 또는 Gateway 헤더에서 추출한 사용자 정보입니다.
    User DB 조회 없이 인증에 필요한 최소 정보만 포함합니다.

    Attributes:
        id: 사용자 고유 ID
        email: 사용자 이메일 (선택)
        username: 사용자명 (선택)
    """
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


# =============================================================================
# Backward Compatibility Aliases
# =============================================================================
# 기존 코드와의 호환성을 위해 get_current_user를 get_current_user_info의 별칭으로 제공
get_current_user = get_current_user_info
get_optional_user = get_optional_user_info
