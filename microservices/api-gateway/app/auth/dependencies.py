"""
Authentication Dependencies

FastAPI 의존성 주입용 인증 함수
"""
from typing import Optional
from dataclasses import dataclass
from fastapi import Request, HTTPException, status

from .jwt import JWTPayload


@dataclass
class CurrentUser:
    """현재 인증된 사용자 정보"""
    id: str
    email: Optional[str] = None
    username: Optional[str] = None

    @classmethod
    def from_payload(cls, payload: JWTPayload) -> "CurrentUser":
        """JWTPayload에서 CurrentUser 생성"""
        return cls(
            id=payload.user_id,
            email=payload.email,
            username=payload.username
        )


async def get_current_user(request: Request) -> CurrentUser:
    """
    현재 인증된 사용자 반환 (필수)

    인증되지 않은 경우 401 에러 발생

    Usage:
        @router.get("/profile")
        async def get_profile(user: CurrentUser = Depends(get_current_user)):
            return {"user_id": user.id}
    """
    if not getattr(request.state, "authenticated", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = getattr(request.state, "user", None)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return CurrentUser.from_payload(payload)


async def get_optional_user(request: Request) -> Optional[CurrentUser]:
    """
    현재 인증된 사용자 반환 (선택적)

    인증되지 않은 경우 None 반환

    Usage:
        @router.get("/items")
        async def list_items(user: Optional[CurrentUser] = Depends(get_optional_user)):
            if user:
                # 로그인한 사용자
                return {"items": [...], "user_id": user.id}
            else:
                # 비로그인 사용자
                return {"items": [...]}
    """
    if not getattr(request.state, "authenticated", False):
        return None

    payload = getattr(request.state, "user", None)
    if not payload:
        return None

    return CurrentUser.from_payload(payload)
