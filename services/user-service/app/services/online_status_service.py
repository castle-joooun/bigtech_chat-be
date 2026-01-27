"""
Online status management service using Redis and Kafka.
"""

from datetime import datetime, timezone
import redis.asyncio as redis
from app.core.config import settings
from typing import Optional


# Redis connection
redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """Get Redis client"""
    global redis_client
    if redis_client is None:
        redis_client = await redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
    return redis_client


async def close_redis():
    """Close Redis connection"""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


async def set_online(user_id: int, session_id: str = None):
    """Set user online status in Redis and publish Kafka event"""
    redis_conn = await get_redis()
    key = f"user:online:{user_id}"

    # Redis에 온라인 상태 저장
    await redis_conn.set(key, session_id or "default", ex=3600)  # 1시간

    # TODO: Kafka 이벤트 발행
    # UserOnlineStatusChanged 이벤트를 user.online_status 토픽으로 발행


async def set_offline(user_id: int):
    """Set user offline status in Redis and publish Kafka event"""
    redis_conn = await get_redis()
    key = f"user:online:{user_id}"

    # Redis에서 온라인 상태 제거
    await redis_conn.delete(key)

    # TODO: Kafka 이벤트 발행
    # UserOnlineStatusChanged 이벤트를 user.online_status 토픽으로 발행


async def is_online(user_id: int) -> bool:
    """Check if user is online"""
    redis_conn = await get_redis()
    key = f"user:online:{user_id}"
    return await redis_conn.exists(key) > 0


async def update_activity(user_id: int):
    """Update user activity (heartbeat)"""
    redis_conn = await get_redis()
    key = f"user:online:{user_id}"

    # 키가 존재하면 TTL 갱신
    if await redis_conn.exists(key):
        await redis_conn.expire(key, 3600)  # 1시간 연장
