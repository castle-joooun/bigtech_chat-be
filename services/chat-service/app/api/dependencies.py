"""
API Dependencies

FastAPI dependency functions for authentication and authorization
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mysql import get_async_session
from app.models.user import User
from app.services.auth_service import find_user_by_id
from app.utils.auth import decode_access_token
from app.core.errors import (
    invalid_token_error,
    user_not_found_error
)

# OAuth2 설정
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_async_session)
) -> User:
    """
    현재 인증된 사용자를 조회합니다.

    Args:
        token: JWT 액세스 토큰
        db: 데이터베이스 세션

    Returns:
        User: 인증된 사용자 객체

    Raises:
        HTTPException: 토큰이 유효하지 않거나 사용자가 존재하지 않는 경우
    """
    # JWT 토큰 디코드
    payload = decode_access_token(token)
    if not payload:
        raise invalid_token_error()

    # 사용자 ID 추출
    user_id = payload.get("sub")
    if not user_id:
        raise invalid_token_error()

    # 사용자 조회
    user = await find_user_by_id(db, int(user_id))
    if not user:
        raise user_not_found_error()

    return user
