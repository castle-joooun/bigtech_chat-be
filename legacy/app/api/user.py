"""
사용자 API 엔드포인트 (User API Endpoints)

================================================================================
API 엔드포인트 (API Endpoints)
================================================================================
- GET /users/search: 사용자 검색 (친구 추가용)
- GET /users/{user_id}: 특정 사용자 조회
- GET /users?user_ids=1,2,3: 여러 사용자 일괄 조회

NOTE: 내 프로필 조회/수정은 /profile/me 엔드포인트를 사용하세요.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from legacy.app.database.mysql import get_async_session
from legacy.app.models.users import User
from legacy.app.schemas.user import UserProfile, UserSearchResponse
from legacy.app.api.auth import get_current_user
from legacy.app.services import auth_service
from legacy.app.core.errors import ResourceNotFoundException
from legacy.app.core.validators import Validator
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
    사용자 검색

    사용자명(username) 또는 표시명(display_name)으로 사용자를 검색합니다.
    친구 추가 시 사용자를 찾는 데 사용됩니다.

    Args:
        query: 검색어 (1-50자)
        limit: 최대 결과 수 (1-50, 기본값: 10)
        current_user: 현재 인증된 사용자 (검색 결과에서 제외됨)
        db: 데이터베이스 세션

    Returns:
        UserSearchResponse: 검색된 사용자 목록과 전체 개수
    """
    try:
        users = await auth_service.search_users_by_username(
            db=db,
            query=query,
            limit=limit,
            exclude_user_id=current_user.id
        )

        total_count = await auth_service.get_user_count_by_query(
            db=db,
            query=query,
            exclude_user_id=current_user.id
        )

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
    특정 사용자 조회

    ID로 단일 사용자의 프로필을 조회합니다.

    Args:
        user_id: 조회할 사용자 ID
        current_user: 현재 인증된 사용자
        db: 데이터베이스 세션

    Returns:
        UserProfile: 사용자 프로필 정보
    """
    user_id = Validator.validate_positive_integer(user_id, "user_id")

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
        id_list = []
        for id_str in user_ids.split(','):
            try:
                uid = int(id_str.strip())
                if uid > 0:
                    id_list.append(uid)
            except ValueError:
                continue

        if not id_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user IDs provided"
            )

        users = await auth_service.get_users_by_ids(db, id_list)
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
