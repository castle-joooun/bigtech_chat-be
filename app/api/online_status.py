"""
온라인 상태 관리 API

사용자의 온라인 상태 조회 기능을 제공합니다.
"""

import json
import asyncio
from typing import List, Dict
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.models.users import User
from app.api.auth import get_current_user
from app.services.online_status_service import OnlineStatusService
from app.services.friendship_service import FriendshipService
from app.database.mysql import get_async_session
from app.database.redis import get_redis
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/online-status", tags=["Online Status"])


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


@router.get("/friends", response_model=List[Dict])
async def get_friends_status(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
) -> List[Dict]:
    """
    친구들의 온라인 상태 조회 (accepted 상태의 친구만)

    Returns:
        친구들의 온라인 상태 정보 리스트 (user_id, is_online만 포함)
    """
    # 친구 목록 조회 (accepted 상태만)
    friends = await FriendshipService.get_friends_list(db, current_user.id)

    if not friends:
        return []

    # 친구 사용자 정보 추출
    friend_users = [friend_user for friend_user, _ in friends]
    friend_ids = [friend_user.id for friend_user in friend_users]

    # 친구들의 온라인 상태 조회 (Redis)
    friends_status = await OnlineStatusService.get_users_status(friend_ids)

    result = []
    for friend_user in friend_users:
        friend_status = friends_status.get(friend_user.id, {})

        result.append({
            "user_id": friend_user.id,
            "is_online": friend_status.get("is_online", False)
        })

    return result


@router.get("/stream")
async def stream_friends_status(
    current_user: User = Depends(get_current_user)
):
    """
    친구들의 온라인 상태 실시간 스트리밍 (SSE + Redis Pub/Sub)

    클라이언트는 이 엔드포인트로 연결하여 친구들의 온라인 상태 변화를 실시간으로 받습니다.

    Returns:
        SSE 스트림
    """
    async def event_generator():
        pubsub = None
        pubsub_client = None

        try:
            # SSE 연결 시작 - 현재 사용자를 온라인 상태로 설정
            # (미들웨어보다 먼저 실행되어야 함)
            await OnlineStatusService.update_user_activity(current_user.id)
            logger.info(f"User {current_user.id} set online via SSE connection")

            # Redis 연결 (전역 클라이언트 재사용)
            redis = await get_redis()

            # Pub/Sub 전용 연결 생성 (독립적인 연결 필요)
            import redis.asyncio as redis_lib
            from app.core.config import settings
            pubsub_client = redis_lib.from_url(settings.redis_url, decode_responses=True)
            pubsub = pubsub_client.pubsub()

            # DB 세션 생성하여 친구 목록만 조회하고 즉시 닫기
            from app.database.mysql import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                # 친구 목록 조회
                friends = await FriendshipService.get_friends_list(db, current_user.id)
            # DB 세션은 여기서 자동으로 닫힘

            if not friends:
                # 친구가 없으면 빈 이벤트 전송 후 종료
                yield {
                    "event": "connected",
                    "data": json.dumps({"message": "No friends to monitor"})
                }
                return

            # 친구들의 상태 변화 채널 구독
            friend_ids = [friend_user.id for friend_user, _ in friends]
            channels = [f"user:status:{friend_id}" for friend_id in friend_ids]

            await pubsub.subscribe(*channels)

            # 초기 상태 전송
            initial_statuses = await OnlineStatusService.get_users_status(friend_ids)

            # 연결 성공 알림 (초기 온라인 상태 포함)
            online_users = []
            for friend_id in friend_ids:
                friend_status = initial_statuses.get(friend_id, {})
                online_users.append({
                    "user_id": friend_id,
                    "is_online": friend_status.get("is_online", False)
                })

            yield {
                "event": "connected",
                "data": json.dumps({
                    "message": f"Monitoring {len(friend_ids)} friends",
                    "friend_ids": friend_ids,
                    "online_users": online_users  # 초기 온라인 상태 포함
                })
            }

            # 상태 변화 추적용 캐시 (중복 전송 방지)
            status_cache = {friend_id: initial_statuses.get(friend_id, {}).get("is_online", False)
                           for friend_id in friend_ids}

            # 친구 목록을 Set으로 저장 (빠른 조회)
            friend_ids_set = set(friend_ids)

            # Redis Pub/Sub 메시지 수신 및 전송
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        # Redis에서 받은 상태 변화 메시지
                        status_data = json.loads(message["data"])
                        user_id = status_data["user_id"]
                        is_online = status_data["is_online"]

                        # 친구의 상태 변화만 처리
                        if user_id not in friend_ids_set:
                            continue

                        # 이전 상태와 비교하여 변화가 있을 때만 전송
                        previous_status = status_cache.get(user_id, None)

                        # 변화가 있거나, 처음 받는 상태면 전송
                        if previous_status != is_online:
                            status_cache[user_id] = is_online

                            # SSE 이벤트로 전송
                            yield {
                                "event": "status",
                                "data": json.dumps({
                                    "user_id": user_id,
                                    "is_online": is_online
                                })
                            }
                            logger.info(f"Status change detected: user {user_id} -> {'online' if is_online else 'offline'}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse Redis message: {e}")
                        continue
                    except KeyError as e:
                        logger.error(f"Missing key in status data: {e}")
                        continue

        except asyncio.CancelledError:
            logger.info(f"SSE connection cancelled for user {current_user.id}")
            raise

        except Exception as e:
            logger.error(f"Error in SSE stream for user {current_user.id}: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"message": "Stream error occurred"})
            }

        finally:
            # 정리 작업
            if pubsub:
                try:
                    await pubsub.unsubscribe()
                    await pubsub.aclose()
                except Exception as e:
                    logger.error(f"Error closing pubsub: {e}")

            if pubsub_client:
                try:
                    await pubsub_client.aclose()
                except Exception as e:
                    logger.error(f"Error closing pubsub_client: {e}")

            logger.info(f"SSE stream closed for user {current_user.id}")

    return EventSourceResponse(event_generator(), ping=3600)
