"""
API Dependencies (API 의존성)
============================

인증을 처리하는 공통 의존성 함수입니다.

인증 플로우 (Hybrid 방식)
--------------------------
1. Gateway에서 X-User-* 헤더가 전달되면 해당 정보 사용
2. Authorization 헤더가 있으면 직접 JWT 검증
3. 둘 다 없으면 401 에러

사용 예시
---------
```python
from shared_lib.api import create_auth_dependency, CurrentUserInfo

get_current_user_info = create_auth_dependency(
    secret_key=settings.secret_key,
    algorithm=settings.algorithm
)

@router.get("/me")
async def get_me(user_info: CurrentUserInfo = Depends(get_current_user_info)):
    return {"user_id": user_info.id}
```
"""

from typing import Optional, Callable
from dataclasses import dataclass
from fastapi import Request, HTTPException, status

from shared_lib.utils.auth import decode_access_token


# =============================================================================
# Gateway Header Constants
# =============================================================================
X_USER_ID = "X-User-ID"
X_USER_EMAIL = "X-User-Email"
X_USER_USERNAME = "X-User-Username"
X_USER_AUTHENTICATED = "X-User-Authenticated"


# =============================================================================
# Data Classes
# =============================================================================
@dataclass
class CurrentUserInfo:
    """현재 사용자 정보"""
    id: int
    email: Optional[str] = None
    username: Optional[str] = None


# =============================================================================
# Helper Functions
# =============================================================================
def extract_token_from_header(authorization: str) -> Optional[str]:
    """Authorization 헤더에서 Bearer 토큰 추출"""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


# =============================================================================
# Dependency Factory
# =============================================================================
def create_auth_dependency(
    secret_key: str,
    algorithm: str = "HS256"
) -> Callable[[Request], CurrentUserInfo]:
    """
    인증 의존성 함수 생성

    Args:
        secret_key: JWT 시크릿 키
        algorithm: JWT 알고리즘

    Returns:
        FastAPI 의존성 함수
    """
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
        token = extract_token_from_header(authorization)

        if token:
            payload = decode_access_token(token, secret_key, algorithm)
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

    return get_current_user_info


def create_optional_auth_dependency(
    secret_key: str,
    algorithm: str = "HS256"
) -> Callable[[Request], Optional[CurrentUserInfo]]:
    """
    선택적 인증 의존성 함수 생성

    Args:
        secret_key: JWT 시크릿 키
        algorithm: JWT 알고리즘

    Returns:
        FastAPI 의존성 함수 (인증 실패시 None 반환)
    """
    get_current_user_info = create_auth_dependency(secret_key, algorithm)

    def get_optional_user_info(request: Request) -> Optional[CurrentUserInfo]:
        try:
            return get_current_user_info(request)
        except HTTPException:
            return None

    return get_optional_user_info
