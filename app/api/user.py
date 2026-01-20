from typing import List
from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mysql import get_async_session
from app.models.users import User
from app.schemas.user import UserProfile, UserSearchResponse
from app.api.auth import get_current_user
from app.services import auth_service
from app.core.errors import ResourceNotFoundException
from app.core.validators import Validator
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/search", response_model=UserSearchResponse)
async def search_users(
    query: str = Query(..., min_length=1, max_length=50, description="검색 쿼리"),
    limit: int = Query(default=10, ge=1, le=50, description="결과 개수"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> UserSearchResponse:
    """
    사용자를 검색합니다.

    Args:
        query: 검색 쿼리 (사용자명 또는 이메일)
        limit: 결과 개수
        current_user: 현재 사용자
        db: 데이터베이스 세션

    Returns:
        UserSearchResponse: 검색 결과
    """
    try:
        # 사용자 검색 (자신 제외)
        users = await auth_service.search_users_by_username(
            db=db,
            query=query,
            limit=limit,
            exclude_user_id=current_user.id
        )

        # 전체 검색 결과 수
        total_count = await auth_service.get_user_count_by_query(
            db=db,
            query=query,
            exclude_user_id=current_user.id
        )

        # UserProfile 스키마 변환
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


@router.get("/{user_id}", response_model=UserProfile)
async def get_user_by_id(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> UserProfile:
    """
    특정 ID의 사용자를 조회합니다.

    Args:
        user_id: 조회할 사용자 ID
        current_user: 현재 사용자
        db: 데이터베이스 세션

    Returns:
        UserProfile: 사용자 프로필
    """
    # 입력 검증
    user_id = Validator.validate_positive_integer(user_id, "user_id")

    # 사용자 조회
    user = await auth_service.find_user_by_id(db, user_id)
    if not user:
        raise ResourceNotFoundException("User")

    return UserProfile.model_validate(user)


@router.get("", response_model=List[UserProfile])
async def get_users_by_ids(
    user_ids: str = Query(..., description="쉼표로 구분된 사용자 ID 목록"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> List[UserProfile]:
    """
    사용자 ID 목록으로 여러 사용자를 조회합니다.

    Args:
        user_ids: 쉼표로 구분된 사용자 ID 목록 (예: "1,2,3")
        current_user: 현재 사용자
        db: 데이터베이스 세션

    Returns:
        List[UserProfile]: 사용자 프로필 목록
    """
    try:
        # 사용자 ID 목록 파싱
        id_list = []
        for id_str in user_ids.split(','):
            try:
                user_id = int(id_str.strip())
                if user_id > 0:
                    id_list.append(user_id)
            except ValueError:
                continue

        if not id_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user IDs provided"
            )

        # 사용자들 조회
        users = await auth_service.get_users_by_ids(db, id_list)

        # UserProfile 스키마 변환
        user_profiles = [UserProfile.model_validate(user) for user in users]

        return user_profiles

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting users by IDs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get users"
        )
