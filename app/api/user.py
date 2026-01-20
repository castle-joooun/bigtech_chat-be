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
    query: str = Query(..., min_length=1, max_length=50, description="�� ���"),
    limit: int = Query(default=10, ge=1, le=50, description="�� �� "),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> UserSearchResponse:
    """
    ����<\ ���| ��i��.

    Args:
        query: �� ��� (���� � \܅)
        limit: �� �� 
        current_user: � x� ���
        db: pt0�t� 8X

    Returns:
        UserSearchResponse: �� ��
    """
    try:
        # ��� �� (� ��� x)
        users = await auth_service.search_users_by_username(
            db=db,
            query=query,
            limit=limit,
            exclude_user_id=current_user.id
        )

        # � �� ��  p�
        total_count = await auth_service.get_user_count_by_query(
            db=db,
            query=query,
            exclude_user_id=current_user.id
        )

        # UserProfile �\ �X
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
    ��� ID\ ��� �| p�i��.

    Args:
        user_id: p�` ��� ID
        current_user: � x� ���
        db: pt0�t� 8X

    Returns:
        UserProfile: ��� \D �
    """
    # �% ��
    user_id = Validator.validate_positive_integer(user_id, "user_id")

    # ��� p�
    user = await auth_service.find_user_by_id(db, user_id)
    if not user:
        raise ResourceNotFoundException("User")

    return UserProfile.model_validate(user)


@router.get("", response_model=List[UserProfile])
async def get_users_by_ids(
    user_ids: str = Query(..., description="|\\ l� ��� ID �]"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> List[UserProfile]:
    """
    ��� ID �]<\ �� ��� �| p�i��.

    Args:
        user_ids: |\\ l� ��� ID �] (: "1,2,3")
        current_user: � x� ���
        db: pt0�t� 8X

    Returns:
        List[UserProfile]: ��� \D �]
    """
    try:
        # ��� ID �] �
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

        # ���� p�
        users = await auth_service.get_users_by_ids(db, id_list)

        # UserProfile �\ �X
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