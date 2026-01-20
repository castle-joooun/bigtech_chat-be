"""
온라인 상태 관리 API

사용자의 온라인 상태 조회 및 관리 기능을 제공합니다.
"""

from typing import List, Dict
from fastapi import APIRouter, Depends, Query

from app.models.users import User
from app.api.auth import get_current_user
from app.services.online_status_service import (
    OnlineStatusService,
    get_online_users,
    set_online,
    set_offline
)
from app.services import auth_service
from app.database.mysql import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/online-status", tags=["Online Status"])


@router.get("/users", response_model=List[Dict])
async def get_online_users_list(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> List[Dict]:
    """
    현재 온라인 사용자 목록 조회

    Returns:
        온라인 사용자 정보 리스트
    """
    # Redis에서 온라인 사용자 ID 목록 조회
    online_user_ids = await get_online_users()

    if not online_user_ids:
        return []

    # 사용자 정보를 데이터베이스에서 조회
    users = await auth_service.get_users_by_ids(db, online_user_ids)

    # 온라인 상태 정보와 결합
    users_status = await OnlineStatusService.get_users_status(online_user_ids)

    result = []
    for user in users:
        user_status = users_status.get(user.id, {})

        result.append({
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "profile_image_url": user.profile_image_url,
            "status": user_status.get("status", "unknown"),
            "is_online": user_status.get("is_online", False),
            "last_activity": user_status.get("last_activity"),
            "last_seen": user_status.get("last_seen")
        })

    return result


@router.get("/count")
async def get_online_count(
    current_user: User = Depends(get_current_user)
) -> Dict:
    """
    온라인 사용자 수 조회

    Returns:
        온라인 사용자 수
    """
    count = await OnlineStatusService.get_online_count()

    return {
        "online_count": count,
        "timestamp": "now"
    }


@router.get("/user/{user_id}")
async def get_user_status(
    user_id: int,
    current_user: User = Depends(get_current_user)
) -> Dict:
    """
    특정 사용자의 온라인 상태 조회

    Args:
        user_id: 조회할 사용자 ID

    Returns:
        사용자 온라인 상태 정보
    """
    status = await OnlineStatusService.get_user_status(user_id)

    if not status:
        return {
            "user_id": user_id,
            "status": "unknown",
            "is_online": False,
            "message": "User status not found"
        }

    return status


@router.post("/heartbeat")
async def send_heartbeat(
    current_user: User = Depends(get_current_user)
) -> Dict:
    """
    사용자 활동 heartbeat 전송

    클라이언트에서 주기적으로 호출하여 온라인 상태를 유지합니다.

    Returns:
        업데이트 결과
    """
    success = await OnlineStatusService.update_user_activity(current_user.id)

    return {
        "success": success,
        "user_id": current_user.id,
        "message": "Heartbeat updated" if success else "Failed to update heartbeat"
    }


@router.post("/set-online")
async def set_user_online(
    current_user: User = Depends(get_current_user)
) -> Dict:
    """
    사용자를 수동으로 온라인 상태로 설정

    Returns:
        설정 결과
    """
    success = await set_online(current_user.id)

    return {
        "success": success,
        "user_id": current_user.id,
        "status": "online" if success else "failed"
    }


@router.post("/set-offline")
async def set_user_offline(
    current_user: User = Depends(get_current_user)
) -> Dict:
    """
    사용자를 수동으로 오프라인 상태로 설정

    Returns:
        설정 결과
    """
    success = await set_offline(current_user.id)

    return {
        "success": success,
        "user_id": current_user.id,
        "status": "offline" if success else "failed"
    }


@router.get("/friends", response_model=List[Dict])
async def get_friends_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> List[Dict]:
    """
    친구들의 온라인 상태 조회

    Returns:
        친구들의 온라인 상태 정보 리스트
    """
    # 친구 목록 조회 (friendship 서비스 사용)
    try:
        from app.services import friendship_service
        friends = await friendship_service.get_user_friends(db, current_user.id)

        if not friends:
            return []

        friend_ids = [friend.id for friend in friends]

        # 친구들의 온라인 상태 조회
        friends_status = await OnlineStatusService.get_users_status(friend_ids)

        result = []
        for friend in friends:
            friend_status = friends_status.get(friend.id, {})

            result.append({
                "user_id": friend.id,
                "username": friend.username,
                "display_name": friend.display_name,
                "profile_image_url": friend.profile_image_url,
                "status": friend_status.get("status", "unknown"),
                "is_online": friend_status.get("is_online", False),
                "last_activity": friend_status.get("last_activity"),
                "last_seen": friend_status.get("last_seen")
            })

        return result

    except ImportError:
        # friendship_service가 아직 구현되지 않은 경우
        return []


@router.get("/cleanup")
async def cleanup_expired_users(
    current_user: User = Depends(get_current_user)
) -> Dict:
    """
    만료된 온라인 사용자 정리 (관리자용)

    Returns:
        정리 결과
    """
    cleaned_count = await OnlineStatusService.cleanup_expired_users()

    return {
        "cleaned_count": cleaned_count,
        "message": f"Cleaned up {cleaned_count} expired users"
    }