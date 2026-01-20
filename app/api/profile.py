from typing import List
from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mysql import get_async_session
from app.models.users import User
from app.schemas.user import (
    UserProfile,
    ProfileUpdateRequest,
    UserSearchRequest,
    UserSearchResponse,
    OnlineStatusUpdate
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


@router.post("/upload-image", response_model=UserProfile)
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


@router.delete("/image", response_model=UserProfile)
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


@router.put("/status", response_model=UserProfile)
async def update_online_status(
    status_data: OnlineStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> UserProfile:
    """
    사용자의 온라인 상태를 업데이트합니다.

    Args:
        status_data: 온라인 상태 정보
        current_user: 현재 인증된 사용자
        db: 데이터베이스 세션

    Returns:
        UserProfile: 업데이트된 프로필 정보
    """
    try:
        # 온라인 상태 업데이트
        updated_user = await auth_service.update_online_status(
            db=db,
            user_id=current_user.id,
            is_online=status_data.is_online
        )

        if not updated_user:
            raise ResourceNotFoundException("User")

        return UserProfile.model_validate(updated_user)

    except Exception as e:
        logger.error(f"Error updating online status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update online status"
        )


@router.post("/last-seen")
async def update_last_seen(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    사용자의 마지막 접속 시간을 현재 시간으로 업데이트합니다.

    Args:
        current_user: 현재 인증된 사용자
        db: 데이터베이스 세션

    Returns:
        dict: 성공 메시지
    """
    try:
        # 마지막 접속 시간 업데이트
        updated_user = await auth_service.update_last_seen(
            db=db,
            user_id=current_user.id
        )

        if not updated_user:
            raise ResourceNotFoundException("User")

        return {"message": "Last seen updated successfully"}

    except Exception as e:
        logger.error(f"Error updating last seen: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update last seen"
        )


@router.get("/search/users", response_model=UserSearchResponse)
async def search_users(
    query: str = Query(..., min_length=1, max_length=50, description="검색 키워드"),
    limit: int = Query(default=10, ge=1, le=50, description="검색 결과 개수"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> UserSearchResponse:
    """
    사용자명으로 사용자를 검색합니다.

    Args:
        query: 검색 키워드 (사용자명 또는 표시명)
        limit: 검색 결과 개수
        current_user: 현재 인증된 사용자
        db: 데이터베이스 세션

    Returns:
        UserSearchResponse: 검색 결과
    """
    try:
        # 사용자 검색 (현재 사용자 제외)
        users = await auth_service.search_users_by_username(
            db=db,
            query=query,
            limit=limit,
            exclude_user_id=current_user.id
        )

        # 전체 검색 결과 수 조회
        total_count = await auth_service.get_user_count_by_query(
            db=db,
            query=query,
            exclude_user_id=current_user.id
        )

        # UserProfile 형태로 변환
        user_profiles = [UserProfile.model_validate(user) for user in users]

        return UserSearchResponse(
            users=user_profiles,
            total_count=total_count
        )

    except Exception as e:
        logger.error(f"Error searching users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search users"
        )