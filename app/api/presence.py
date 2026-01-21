"""
온라인 상태 관리 API (SSE + Redis Pub/Sub)

SSE를 통해 실시간으로 친구들의 온라인 상태 변화를 클라이언트에 전송합니다.
"""

import asyncio
import json
import logging
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.models.users import User
from app.database.mysql import get_async_session
from app.database.redis import get_redis
from app.services.online_status_service import set_online, set_offline, update_activity
from app.services.friendship_service import FriendshipService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/presence", tags=["Presence"])


async def presence_event_generator(
    user_id: int,
    friend_ids: list[int],
    redis_client
) -> AsyncGenerator[str, None]:
    """
    SSE 이벤트 생성기

    Args:
        user_id: 현재 사용자 ID
        friend_ids: 친구 ID 목록
        redis_client: Redis 클라이언트

    Yields:
        SSE 형식의 이벤트 문자열
    """
    # Redis Pub/Sub 채널 구독
    pubsub = redis_client.pubsub()

    try:
        # 1. 자신의 온라인 상태를 온라인으로 설정
        await set_online(user_id, session_id=f"sse_{user_id}")

        # 2. 친구들의 상태 변화 채널 구독
        channels = [f"user:status:{friend_id}" for friend_id in friend_ids]
        if channels:
            await pubsub.subscribe(*channels)

        # 3. 전체 온라인 상태 브로드캐스트 채널도 구독
        await pubsub.subscribe("presence:broadcast")

        # 4. 초기 연결 성공 메시지
        yield f"event: connected\ndata: {json.dumps({'user_id': user_id, 'status': 'connected'})}\n\n"

        # 5. 초기 친구들 상태 전송
        from app.services.online_status_service import get_users_status
        initial_statuses = await get_users_status(friend_ids)
        yield f"event: initial\ndata: {json.dumps(initial_statuses)}\n\n"

        # 6. Heartbeat + 상태 변화 수신 루프
        last_heartbeat = asyncio.get_event_loop().time()

        while True:
            try:
                # Heartbeat (30초마다)
                current_time = asyncio.get_event_loop().time()
                if current_time - last_heartbeat > 30:
                    await update_activity(user_id)
                    yield f"event: heartbeat\ndata: {json.dumps({'timestamp': int(current_time)})}\n\n"
                    last_heartbeat = current_time

                # Redis Pub/Sub 메시지 확인 (0.5초 타임아웃)
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5),
                    timeout=1.0
                )

                if message and message['type'] == 'message':
                    # 상태 변화 메시지 파싱
                    data = message['data']
                    if isinstance(data, bytes):
                        data = data.decode('utf-8')

                    # 클라이언트에 전송
                    yield f"event: status_change\ndata: {data}\n\n"

                # 짧은 대기 (CPU 사용량 감소)
                await asyncio.sleep(0.1)

            except asyncio.TimeoutError:
                # 타임아웃은 정상 (메시지가 없는 경우)
                continue
            except asyncio.CancelledError:
                # 연결 종료
                logger.info(f"SSE connection cancelled for user {user_id}")
                break
            except Exception as e:
                logger.error(f"Error in SSE generator for user {user_id}: {e}")
                break

    finally:
        # 7. 정리 작업
        await pubsub.unsubscribe()
        await pubsub.close()
        await set_offline(user_id)

        logger.info(f"SSE connection closed for user {user_id}")


@router.get("/stream")
async def presence_stream(
    request: Request,
    token: str = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    SSE를 통한 실시간 온라인 상태 스트림

    클라이언트는 이 엔드포인트에 연결하여 친구들의 온라인 상태 변화를 실시간으로 수신합니다.

    Args:
        request: FastAPI Request 객체
        token: 선택적 쿼리 파라미터 토큰 (EventSource 호환용)
        current_user: 현재 인증된 사용자
        db: 데이터베이스 세션

    Returns:
        StreamingResponse: SSE 스트림

    Events:
        - connected: 연결 성공
        - initial: 초기 친구 목록 상태
        - status_change: 친구의 상태 변화
        - heartbeat: 30초마다 heartbeat

    Example 1 (with query parameter):
        ```javascript
        const eventSource = new EventSource(
            `/api/presence/stream?token=${accessToken}`
        );
        ```

    Example 2 (with EventSource polyfill):
        ```javascript
        import { EventSourcePolyfill } from 'event-source-polyfill';

        const eventSource = new EventSourcePolyfill('/api/presence/stream', {
            headers: {
                'Authorization': 'Bearer ' + token
            }
        });
        ```
    """
    try:
        # 1. 친구 목록 조회
        friends = await FriendshipService.get_friends_list(db, current_user.id)
        friend_ids = [friend_user.id for friend_user, _ in friends]

        # 2. Redis 클라이언트 가져오기
        redis_client = await get_redis()

        # 3. SSE 스트림 반환
        return StreamingResponse(
            presence_event_generator(current_user.id, friend_ids, redis_client),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Nginx 버퍼링 비활성화
            }
        )

    except Exception as e:
        logger.error(f"Error creating SSE stream for user {current_user.id}: {e}")
        raise


@router.post("/notify")
async def notify_status_change(
    current_user: User = Depends(get_current_user)
):
    """
    사용자 상태 변화를 수동으로 브로드캐스트

    일반적으로는 자동으로 처리되지만, 필요시 수동으로 상태 변화를 알릴 수 있습니다.

    Args:
        current_user: 현재 인증된 사용자

    Returns:
        dict: 성공 메시지
    """
    try:
        redis_client = await get_redis()

        # 현재 사용자 상태 조회
        from app.services.online_status_service import get_user_status
        status = await get_user_status(current_user.id)

        # 상태 변화 메시지 생성
        message = {
            "user_id": current_user.id,
            "is_online": status.get("is_online", False),
            "last_activity": status.get("last_activity"),
            "timestamp": asyncio.get_event_loop().time()
        }

        # Redis Pub/Sub으로 브로드캐스트
        await redis_client.publish(
            f"user:status:{current_user.id}",
            json.dumps(message)
        )

        return {
            "message": "Status change broadcasted",
            "user_id": current_user.id,
            "status": status
        }

    except Exception as e:
        logger.error(f"Error broadcasting status change for user {current_user.id}: {e}")
        raise
