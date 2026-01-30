"""
Redis 연결 관리
"""

import redis.asyncio as redis
from app.core.config import settings

# Redis 클라이언트
redis_client: redis.Redis = None


async def init_redis():
    """Redis 연결 초기화"""
    global redis_client

    redis_client = redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True
    )

    # 연결 테스트
    await redis_client.ping()
    print("✅ Redis connected")


async def close_redis():
    """Redis 연결 종료"""
    global redis_client

    if redis_client:
        await redis_client.close()
        print("🔌 Redis connection closed")


def get_redis() -> redis.Redis:
    """Redis 클라이언트 반환"""
    return redis_client
