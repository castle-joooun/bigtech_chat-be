"""
=============================================================================
Cache Decorators (캐시 데코레이터) - 함수 레벨 캐싱
=============================================================================

📌 이 파일이 하는 일:
    함수에 데코레이터를 붙여서 자동으로 캐싱하는 기능을 제공합니다.
    반복적인 캐시 코드를 줄이고 깔끔하게 캐싱을 적용할 수 있습니다.

💡 데코레이터란?
    함수를 감싸서 추가 기능을 부여하는 파이썬 문법입니다.
    @cached를 함수 위에 붙이면 자동으로 캐싱이 적용됩니다.

사용 예시
---------
```python
from shared_lib.cache import cached, cache_aside

# 1. 기본 캐싱 (5분)
@cached(prefix="user", ttl=300)
async def get_user(user_id: int):
    return await db.get(User, user_id)

# 호출 시 자동으로:
# - 캐시 키: "user:get_user:123" (user_id=123인 경우)
# - 캐시 HIT → 캐시에서 반환
# - 캐시 MISS → DB 조회 → 캐시 저장 → 반환

# 2. 커스텀 키 생성
@cached(prefix="chat", ttl=60, key_builder=lambda room_id, page: f"room:{room_id}:page:{page}")
async def get_messages(room_id: int, page: int):
    return await db.query(Message, room_id=room_id, page=page)

# 3. 캐시 무효화 포함
@cache_aside(
    prefix="user",
    ttl=300,
    invalidate_on=["update_user", "delete_user"]
)
async def get_user_profile(user_id: int):
    return await db.get(User, user_id)
```

관련 파일
---------
- shared_lib/cache/service.py: CacheService 클래스
"""

import functools
import hashlib
import json
import logging
from typing import Any, Callable, Optional, Union

logger = logging.getLogger(__name__)


def cached(
    prefix: str = "",
    ttl: int = 300,
    key_builder: Optional[Callable[..., str]] = None,
    skip_cache_if: Optional[Callable[..., bool]] = None
):
    """
    📌 함수 결과 캐싱 데코레이터

    함수의 인자를 기반으로 캐시 키를 생성하고,
    결과를 자동으로 캐시합니다.

    동작 흐름:
        1. 캐시 키 생성 (prefix:함수명:인자해시)
        2. 캐시 조회
        3. HIT → 캐시 값 반환
        4. MISS → 함수 실행 → 결과 캐시 → 반환

    Args:
        prefix: 캐시 키 프리픽스
                예: "user" → "user:get_user:abc123"
        ttl: 캐시 만료 시간 (초, 기본: 300 = 5분)
        key_builder: 커스텀 키 생성 함수
                     인자를 받아 키 문자열 반환
        skip_cache_if: 캐시 스킵 조건 함수
                       True 반환 시 캐시 안 함

    Returns:
        데코레이터 함수

    사용 예시:
        @cached(prefix="user", ttl=300)
        async def get_user(user_id: int):
            return await db.get(User, user_id)

        # 커스텀 키
        @cached(prefix="chat", key_builder=lambda room_id: f"room:{room_id}")
        async def get_room(room_id: int):
            return await db.get(ChatRoom, room_id)

        # 조건부 캐싱 (admin은 캐시 안 함)
        @cached(prefix="user", skip_cache_if=lambda user_id: user_id == 1)
        async def get_user(user_id: int):
            return await db.get(User, user_id)
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 캐시 서비스 가져오기 (순환 import 방지)
            from .service import get_cache_service
            cache = get_cache_service()

            # 캐시 서비스가 초기화되지 않은 경우 원본 함수 실행
            if not cache.is_connected:
                return await func(*args, **kwargs)

            # 캐시 스킵 조건 확인
            if skip_cache_if and skip_cache_if(*args, **kwargs):
                return await func(*args, **kwargs)

            # 캐시 키 생성
            if key_builder:
                cache_key = f"{prefix}:{key_builder(*args, **kwargs)}"
            else:
                cache_key = _build_cache_key(prefix, func.__name__, args, kwargs)

            # 캐시 조회
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return cached_value

            # 캐시 MISS → 함수 실행
            logger.debug(f"Cache MISS: {cache_key}")
            result = await func(*args, **kwargs)

            # 결과 캐싱 (None이 아닌 경우)
            if result is not None:
                await cache.set(cache_key, result, ttl=ttl)

            return result

        # 캐시 무효화 헬퍼 메서드 추가
        async def invalidate(*args, **kwargs):
            """이 함수의 캐시 무효화"""
            from .service import get_cache_service
            cache = get_cache_service()

            if key_builder:
                cache_key = f"{prefix}:{key_builder(*args, **kwargs)}"
            else:
                cache_key = _build_cache_key(prefix, func.__name__, args, kwargs)

            await cache.delete(cache_key)
            logger.debug(f"Cache invalidated: {cache_key}")

        wrapper.invalidate = invalidate
        wrapper.cache_prefix = prefix

        return wrapper
    return decorator


def cache_aside(
    prefix: str = "",
    ttl: int = 300,
    key_builder: Optional[Callable[..., str]] = None
):
    """
    📌 Cache-Aside 패턴 데코레이터

    cached와 동일하지만, 명시적으로 Cache-Aside 패턴임을 표시합니다.
    의미적으로 더 명확하게 표현하고 싶을 때 사용합니다.

    Cache-Aside 패턴:
        1. 애플리케이션이 캐시를 먼저 확인
        2. 캐시 미스 시 DB 조회
        3. 결과를 캐시에 저장
        4. 결과 반환

    Args:
        prefix: 캐시 키 프리픽스
        ttl: 캐시 만료 시간 (초)
        key_builder: 커스텀 키 생성 함수

    사용 예시:
        @cache_aside(prefix="user", ttl=300)
        async def get_user_profile(user_id: int):
            return await db.get(UserProfile, user_id)
    """
    return cached(prefix=prefix, ttl=ttl, key_builder=key_builder)


def _build_cache_key(
    prefix: str,
    func_name: str,
    args: tuple,
    kwargs: dict
) -> str:
    """
    캐시 키 생성

    형식: prefix:func_name:args_hash

    인자가 단순하면 직접 사용, 복잡하면 해시 사용.
    """
    # 인자 직렬화
    key_parts = []

    # 위치 인자
    for arg in args:
        if isinstance(arg, (str, int, float, bool)):
            key_parts.append(str(arg))
        elif hasattr(arg, 'id'):
            # ORM 객체인 경우 id 사용
            key_parts.append(f"id:{arg.id}")
        else:
            # 복잡한 객체는 해시
            key_parts.append(_hash_value(arg))

    # 키워드 인자
    for k, v in sorted(kwargs.items()):
        if isinstance(v, (str, int, float, bool)):
            key_parts.append(f"{k}:{v}")
        else:
            key_parts.append(f"{k}:{_hash_value(v)}")

    # 키 조합
    args_str = ":".join(key_parts) if key_parts else "no_args"

    if prefix:
        return f"{prefix}:{func_name}:{args_str}"
    return f"{func_name}:{args_str}"


def _hash_value(value: Any) -> str:
    """값을 해시하여 짧은 문자열 반환"""
    try:
        serialized = json.dumps(value, sort_keys=True, default=str)
        return hashlib.md5(serialized.encode()).hexdigest()[:8]
    except (TypeError, ValueError):
        return hashlib.md5(str(value).encode()).hexdigest()[:8]


# =============================================================================
# 캐시 무효화 유틸리티
# =============================================================================

async def invalidate_cache(prefix: str, pattern: str = "*"):
    """
    📌 패턴 기반 캐시 무효화

    특정 프리픽스의 모든 캐시 또는 패턴에 맞는 캐시를 삭제합니다.

    Args:
        prefix: 캐시 프리픽스
        pattern: 삭제 패턴 (기본: "*" = 모두)

    사용 예시:
        # user 관련 모든 캐시 삭제
        await invalidate_cache("user")

        # 특정 사용자 캐시만 삭제
        await invalidate_cache("user", "get_user:123")
    """
    from .service import get_cache_service
    cache = get_cache_service()

    full_pattern = f"{prefix}:{pattern}"
    deleted = await cache.delete_pattern(full_pattern)
    logger.info(f"Invalidated {deleted} cache entries for pattern '{full_pattern}'")
    return deleted
