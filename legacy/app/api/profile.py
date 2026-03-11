"""
프로필 API 엔드포인트 (Profile API Endpoints)

현재 사용자 프로필 조회 및 수정 기능을 제공합니다.

API 엔드포인트
--------------
- GET /profile/me: 내 프로필 조회
- PUT /profile/me: 내 프로필 수정 (display_name, status_message)

Note: 다른 사용자 프로필 조회는 /users/{user_id} 사용
"""

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from legacy.app.database.mysql import get_async_session
from legacy.app.models.users import User
from legacy.app.schemas.user import (
    UserProfile,
    ProfileUpdateRequest,
)
from legacy.app.api.auth import get_current_user
from legacy.app.services import auth_service
from legacy.app.core.errors import ResourceNotFoundException
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["User Profile"])


@router.get("/me", response_model=UserProfile)
async def get_my_profile(
    current_user: User = Depends(get_current_user)
) -> UserProfile:
    """
    현재 사용자의 프로필 정보를 조회합니다.

    Returns:
        UserProfile: 현재 사용자의 프로필 정보
    """
    return UserProfile.model_validate(current_user)


@router.put("/me", response_model=UserProfile)
async def update_my_profile(
    profile_data: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> UserProfile:
    """
    현재 사용자의 프로필 정보를 수정합니다.

    Args:
        profile_data: 수정할 프로필 정보
        current_user: 현재 인증된 사용자
        db: 데이터베이스 세션

    Returns:
        UserProfile: 수정된 프로필 정보
    """
    try:
        updated_user = await auth_service.update_user_profile(
            db=db,
            user_id=current_user.id,
            display_name=profile_data.display_name,
            status_message=profile_data.status_message
        )

        if not updated_user:
            raise ResourceNotFoundException("User")

        return UserProfile.model_validate(updated_user)

    except Exception as e:
        logger.error(f"Error updating user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )
