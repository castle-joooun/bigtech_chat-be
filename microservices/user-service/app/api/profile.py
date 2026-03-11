"""
Profile API Endpoints (프로필 API 엔드포인트)
============================================

현재 사용자 프로필 관리(조회, 수정)를 처리하는 API 레이어입니다.

엔드포인트 목록
---------------
| Method | Path              | 설명                    | 인증 |
|--------|-------------------|------------------------|------|
| GET    | /profile/me       | 내 프로필 조회          | O    |
| PUT    | /profile/me       | 내 프로필 수정          | O    |

Note: 다른 사용자 프로필 조회는 /users/{user_id} 사용

관련 파일
---------
- app/services/auth_service.py: 프로필 데이터 CRUD
- app/schemas/user.py: 요청/응답 스키마
"""

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mysql import get_async_session
from app.models.user import User
from app.schemas.user import (
    UserProfile,
    ProfileUpdateRequest
)
from app.api.dependencies import get_current_user
from app.services import auth_service
from shared_lib.core import ResourceNotFoundException
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile", tags=["User Profile"])


@router.get("/me", response_model=UserProfile)
async def get_my_profile(
    current_user: User = Depends(get_current_user)
) -> UserProfile:
    """
    현재 사용자 프로필 조회

    인증된 사용자 본인의 프로필 정보를 반환합니다.
    """
    return UserProfile.model_validate(current_user)


# =============================================================================
# Profile 수정 API
# =============================================================================

@router.put("/me", response_model=UserProfile)
async def update_my_profile(
    profile_data: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> UserProfile:
    """
    현재 사용자 프로필 수정

    display_name과 status_message를 수정할 수 있습니다.
    부분 업데이트: 제공된 필드만 수정됩니다.

    Args:
        profile_data: 수정할 프로필 정보
            - display_name: 표시 이름 (선택)
            - status_message: 상태 메시지 (선택)
        current_user: 현재 인증된 사용자
        db: 데이터베이스 세션

    Returns:
        UserProfile: 수정된 프로필 정보

    Raises:
        HTTPException 404: 사용자를 찾을 수 없음
        HTTPException 500: 업데이트 실패

    요청 예시:
        PUT /profile/me
        Content-Type: application/json
        {
            "display_name": "New Name",
            "status_message": "Hello World!"
        }

    부분 업데이트:
        - None이 아닌 필드만 업데이트됨
        - display_name만 보내면 status_message는 유지
    """
    try:
        # 프로필 업데이트 (부분 업데이트)
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
