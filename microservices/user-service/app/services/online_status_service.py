"""
Online Status Service (온라인 상태 서비스)
==========================================

Redis를 사용한 실시간 온라인 상태 관리 서비스입니다.
shared_lib의 RedisManager를 사용하여 연결을 관리합니다.

아키텍처 개요
-------------
```
┌─────────────────────────────────────────────────────────┐
│  Client (로그인)                                         │
└─────────────────┬───────────────────────────────────────┘
                  │ 1. Login API 호출
                  ▼
┌─────────────────────────────────────────────────────────┐
│  User Service (auth.py)                                  │
└─────────────────┬───────────────────────────────────────┘
                  │ 2. set_online() 호출
                  ▼
┌─────────────────────────────────────────────────────────┐
│  Online Status Service (현재 파일)                        │
│  ┌────────────┐  ┌──────────────────┐                   │
│  │ set_online │  │ update_activity  │                   │
│  │ set_offline│  │ (heartbeat)      │                   │
│  └─────┬──────┘  └────────┬─────────┘                   │
│        │                  │                             │
└────────┼──────────────────┼─────────────────────────────┘
         │                  │
         ▼                  ▼
┌─────────────────────────────────────────────────────────┐
│  Redis (via shared_lib.database.RedisManager)           │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Key: user:online:{user_id}                        │   │
│  │ Value: session_id                                 │   │
│  │ TTL: 3600 (1시간)                                 │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

설계 원칙
---------
1. TTL (Time To Live) 기반 만료:
   - 키가 자동으로 만료되어 좀비 세션 방지
   - Heartbeat로 TTL을 갱신하여 활성 상태 유지

2. Redis 단일 진실 소스 (Single Source of Truth):
   - 온라인 상태는 Redis에서만 조회
   - MySQL은 last_seen_at 기록용 (히스토리)

3. shared_lib 사용:
   - RedisManager를 사용하여 연결 관리 일원화
   - 다른 서비스와 동일한 패턴 사용

Redis Key 설계
--------------
| Key Pattern          | Value     | TTL    | 용도              |
|---------------------|-----------|--------|-------------------|
| user:online:{id}    | session_id| 3600s  | 온라인 상태        |
| user:activity:{id}  | timestamp | 300s   | 마지막 활동 시간   |

관련 파일
---------
- app/api/auth.py: 로그인/로그아웃 시 이 서비스 호출
- shared_lib/database/redis.py: Redis 연결 관리
"""

import logging
from shared_lib.database import RedisManager, get_redis_manager
from app.core.config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# Redis Connection (shared_lib 사용)
# =============================================================================
_redis_manager: RedisManager = get_redis_manager()


async def init_redis():
    """
    Redis 연결 초기화

    애플리케이션 시작 시 (lifespan startup) 호출.
    shared_lib의 RedisManager를 사용합니다.

    Raises:
        Exception: Redis 연결 실패 시
    """
    await _redis_manager.init(settings.redis_url)
    logger.info("Redis connected for online status")


async def get_redis():
    """
    Redis 클라이언트 획득

    Returns:
        redis.Redis: 비동기 Redis 클라이언트
    """
    return _redis_manager.client


async def close_redis():
    """
    Redis 연결 종료

    애플리케이션 종료 시 (lifespan shutdown) 호출.
    """
    await _redis_manager.close()
    logger.info("Redis connection closed")


# =============================================================================
# Online Status Operations
# =============================================================================

async def set_online(user_id: int, session_id: str = None):
    """
    사용자 온라인 상태 설정

    로그인 성공 시 호출. Redis에 온라인 상태를 저장하고
    TTL을 설정하여 자동 만료되도록 합니다.

    Redis Key:
        user:online:{user_id}

    Value:
        session_id (또는 "default")
        - 다중 세션 관리 시 세션 식별에 사용

    TTL:
        3600초 (1시간)
        - Heartbeat 없으면 자동 오프라인 처리
        - update_activity()로 TTL 갱신

    Args:
        user_id: 사용자 ID
        session_id: 세션 식별자 (선택, 기본값: "default")

    Redis 명령:
        SET user:online:123 "session_abc" EX 3600
    """
    redis_conn = await get_redis()
    key = f"user:online:{user_id}"

    # Redis에 온라인 상태 저장 (TTL 1시간)
    await redis_conn.set(key, session_id or "default", ex=3600)

    # TODO: Kafka 이벤트 발행
    # producer = get_event_producer()
    # await producer.publish(
    #     topic="user.online_status",
    #     event=UserOnlineStatusChanged(user_id=user_id, is_online=True),
    #     key=str(user_id)
    # )


async def set_offline(user_id: int):
    """
    사용자 오프라인 상태 설정

    로그아웃 또는 세션 만료 시 호출.
    Redis에서 온라인 상태 키를 삭제합니다.

    Args:
        user_id: 사용자 ID

    Redis 명령:
        DEL user:online:123
    """
    redis_conn = await get_redis()
    key = f"user:online:{user_id}"

    # Redis에서 온라인 상태 제거
    await redis_conn.delete(key)

    # TODO: Kafka 이벤트 발행
    # producer = get_event_producer()
    # await producer.publish(
    #     topic="user.online_status",
    #     event=UserOnlineStatusChanged(user_id=user_id, is_online=False),
    #     key=str(user_id)
    # )


async def is_online(user_id: int) -> bool:
    """
    사용자 온라인 상태 확인

    Redis에 해당 키가 존재하면 온라인, 없으면 오프라인.

    Args:
        user_id: 확인할 사용자 ID

    Returns:
        True if 온라인, False if 오프라인

    Redis 명령:
        EXISTS user:online:123

    성능:
        O(1) - Redis EXISTS 명령은 상수 시간
    """
    redis_conn = await get_redis()
    key = f"user:online:{user_id}"
    return await redis_conn.exists(key) > 0


async def update_activity(user_id: int):
    """
    사용자 활동 시간 갱신 (Heartbeat)

    주기적으로 호출하여 TTL을 갱신합니다.
    클라이언트가 활성 상태임을 서버에 알리는 역할.

    Heartbeat 메커니즘:
        1. 클라이언트: 30초마다 API 호출 (예: GET /profile/me)
        2. get_current_user() 디펜던시에서 이 함수 호출
        3. Redis TTL 갱신 → 온라인 상태 유지

    TTL이 만료되면:
        - Redis 키가 자동 삭제됨
        - 다음 is_online() 호출 시 오프라인으로 판정

    Args:
        user_id: 활동 갱신할 사용자 ID

    Redis 명령:
        EXPIRE user:online:123 3600
    """
    redis_conn = await get_redis()
    key = f"user:online:{user_id}"

    # 키가 존재하면 TTL 갱신
    if await redis_conn.exists(key):
        await redis_conn.expire(key, 3600)  # 1시간 연장
