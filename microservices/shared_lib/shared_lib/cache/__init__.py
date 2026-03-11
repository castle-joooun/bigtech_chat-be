"""
Cache Module (캐시 모듈)
========================

Redis 기반 캐싱 유틸리티를 제공합니다.

사용 예시
---------
```python
from shared_lib.cache import CacheService, get_cache_service

# 초기화
cache = get_cache_service()
await cache.init(redis_url)

# 기본 캐싱
await cache.set("user:123", user_data, ttl=300)
user = await cache.get("user:123")

# 데코레이터 사용
@cache.cached(prefix="user", ttl=300)
async def get_user(user_id: int):
    return await db.get(User, user_id)
```
"""

from .service import CacheService, get_cache_service
from .decorators import cached, cache_aside

__all__ = [
    "CacheService",
    "get_cache_service",
    "cached",
    "cache_aside",
]
