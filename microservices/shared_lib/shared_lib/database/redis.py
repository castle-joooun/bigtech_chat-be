"""
Redis Database (Redis 데이터베이스)
==================================

Redis 연결 관리를 제공합니다.

사용 예시
---------
```python
from shared_lib.database import RedisManager, get_redis_manager

redis_manager = get_redis_manager()
await redis_manager.init(settings.redis_url)
redis = redis_manager.client

# 사용
await redis.set("key", "value")
value = await redis.get("key")

# 종료
await redis_manager.close()
```
"""

import logging
from typing import Optional
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisManager:
    """Redis 연결 관리자"""

    def __init__(self):
        self._client: Optional[redis.Redis] = None

    @property
    def client(self) -> Optional[redis.Redis]:
        """Redis 클라이언트 반환"""
        return self._client

    async def init(self, redis_url: str):
        """
        Redis 연결 초기화

        Args:
            redis_url: Redis 연결 URL
        """
        try:
            self._client = redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            # 연결 테스트
            await self._client.ping()
            logger.info("Redis connection initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {e}")
            self._client = None
            raise

    async def close(self):
        """Redis 연결 종료"""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Redis connection closed")

    async def health_check(self) -> bool:
        """Redis 연결 상태 확인"""
        if not self._client:
            return False
        try:
            await self._client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False


# Singleton instance
_redis_manager: Optional[RedisManager] = None


def get_redis_manager() -> RedisManager:
    """Redis 매니저 싱글톤 반환"""
    global _redis_manager
    if _redis_manager is None:
        _redis_manager = RedisManager()
    return _redis_manager
