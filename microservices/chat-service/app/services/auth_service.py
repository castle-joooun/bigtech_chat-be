"""
User Query Service (via user-service API)
==========================================

사용자 정보 조회는 user-service API를 통해 수행합니다.
MSA 원칙에 따라 User DB에 직접 접근하지 않습니다.

변경 이력:
    - v1.0: 직접 DB 조회 (User 모델 사용)
    - v2.0: user-service API 호출 (UserClient 사용)
"""

from typing import Optional, List
from shared_lib.clients import get_user_client, UserClientError
from shared_lib.schemas import UserProfile
import logging

logger = logging.getLogger(__name__)


async def get_user_by_id(user_id: int) -> Optional[UserProfile]:
    """
    사용자 ID로 조회 (user-service API 호출)

    Args:
        user_id: 조회할 사용자 ID

    Returns:
        UserProfile 또는 None
    """
    try:
        user_client = get_user_client()
        return await user_client.get_user_by_id(user_id)
    except UserClientError as e:
        logger.error(f"Failed to get user {user_id}: {e}")
        return None


async def get_users_by_ids(user_ids: List[int]) -> List[UserProfile]:
    """
    여러 사용자 ID로 Batch 조회 (user-service API 호출)

    Args:
        user_ids: 조회할 사용자 ID 목록

    Returns:
        List[UserProfile]: 조회된 사용자 목록
    """
    if not user_ids:
        return []

    try:
        user_client = get_user_client()
        return await user_client.get_users_by_ids(user_ids)
    except UserClientError as e:
        logger.error(f"Failed to get users {user_ids}: {e}")
        return []


async def user_exists(user_id: int) -> bool:
    """
    사용자 존재 여부 확인 (user-service API 호출)

    Args:
        user_id: 확인할 사용자 ID

    Returns:
        bool: 존재 여부
    """
    try:
        user_client = get_user_client()
        return await user_client.user_exists(user_id)
    except UserClientError as e:
        logger.error(f"Failed to check user existence {user_id}: {e}")
        return False


# Backward compatibility aliases
find_user_by_id = get_user_by_id


