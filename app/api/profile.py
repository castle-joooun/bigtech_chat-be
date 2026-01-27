from typing import List
from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mysql import get_async_session
from app.models.users import User
from app.schemas.user import (
    UserProfile,
    ProfileUpdateRequest,
    UserSearchRequest,
    UserSearchResponse
)
from app.api.auth import get_current_user
from app.services import auth_service, file_service
from app.core.errors import ResourceNotFoundException, BusinessLogicException
from app.core.validators import Validator
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


@router.get("/{user_id}", response_model=UserProfile)
async def get_user_profile(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> UserProfile:
    """
    특정 사용자의 프로필 정보를 조회합니다.

    Args:
        user_id: 조회할 사용자 ID
        current_user: 현재 인증된 사용자
        db: 데이터베이스 세션

    Returns:
        UserProfile: 사용자 프로필 정보
    """
    # 입력 검증
    user_id = Validator.validate_positive_integer(user_id, "user_id")

    # 사용자 조회
    user = await auth_service.find_user_by_id(db, user_id)
    if not user:
        raise ResourceNotFoundException("User")

    return UserProfile.model_validate(user)


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
        # 프로필 업데이트
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


@router.post("/me/image", response_model=UserProfile)
async def upload_profile_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> UserProfile:
    """
    프로필 이미지를 업로드합니다.

    Args:
        file: 업로드할 이미지 파일
        current_user: 현재 인증된 사용자
        db: 데이터베이스 세션

    Returns:
        UserProfile: 업데이트된 프로필 정보
    """
    try:
        # 기존 프로필 이미지 삭제 (있다면)
        if current_user.profile_image_url:
            await file_service.delete_profile_image(current_user.profile_image_url)

        # 새 이미지 저장
        image_url = await file_service.save_profile_image(file, current_user.id)

        # 사용자 프로필 이미지 URL 업데이트
        updated_user = await auth_service.update_profile_image(
            db=db,
            user_id=current_user.id,
            profile_image_url=image_url
        )

        if not updated_user:
            raise ResourceNotFoundException("User")

        return UserProfile.model_validate(updated_user)

    except HTTPException:
        # file_service에서 발생한 HTTPException은 다시 발생
        raise
    except Exception as e:
        logger.error(f"Error uploading profile image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload profile image"
        )


@router.delete("/me/image", response_model=UserProfile)
async def delete_profile_image(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> UserProfile:
    """
    프로필 이미지를 삭제합니다.

    Args:
        current_user: 현재 인증된 사용자
        db: 데이터베이스 세션

    Returns:
        UserProfile: 업데이트된 프로필 정보
    """
    try:
        # 프로필 이미지가 있는지 확인
        if not current_user.profile_image_url:
            raise BusinessLogicException("No profile image to delete")

        # 파일 시스템에서 이미지 삭제
        await file_service.delete_profile_image(current_user.profile_image_url)

        # 데이터베이스에서 프로필 이미지 URL 제거
        updated_user = await auth_service.update_profile_image(
            db=db,
            user_id=current_user.id,
            profile_image_url=None
        )

        if not updated_user:
            raise ResourceNotFoundException("User")

        return UserProfile.model_validate(updated_user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting profile image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete profile image"
        )


