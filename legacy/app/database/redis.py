"""
Redis 연결 설정 및 관리 모듈 (Redis Connection Management Module)

================================================================================
아키텍처 개요 (Architecture Overview)
================================================================================
이 모듈은 Redis 비동기 연결을 관리하고, 캐싱, Rate Limiting, 세션 관리 등
다양한 Redis 작업을 위한 유틸리티 함수를 제공합니다.

Connection Pooling을 통해 효율적인 연결 관리를 수행하며,
모든 작업은 비동기로 처리됩니다.

연결 아키텍처:
    Application → ConnectionPool → Redis Server
                       ↓
              최대 20개 연결 관리 (설정 가능)
              자동 재연결 및 Keep-Alive

주요 기능:
    ├── 캐시 (Cache): set_cache, get_cache, delete_cache
    ├── 카운터 (Counter): increment_counter, get_counter
    ├── 세션 (Session): set_session, get_session, delete_session
    ├── Rate Limiting: check_rate_limit
    └── 상태 확인: health_check, get_stats

================================================================================
디자인 패턴 (Design Patterns)
================================================================================
1. Singleton Pattern (싱글톤 패턴)
   - redis_client, redis_pool 전역 인스턴스
   - init_redis()로 한 번만 초기화

2. Connection Pool Pattern (연결 풀 패턴)
   - 연결 재사용으로 성능 최적화
   - 최대 연결 수 제한으로 리소스 보호

3. Fail-Open Pattern (페일 오픈 패턴)
   - Rate Limiting 실패 시 요청 허용
   - 서비스 가용성 우선

================================================================================
SOLID 원칙 적용 (SOLID Principles)
================================================================================
- SRP (단일 책임): 각 함수는 하나의 Redis 작업만 담당
- OCP (개방-폐쇄): 새로운 Redis 작업 추가 시 기존 코드 수정 없음
- DIP (의존성 역전): settings를 통해 설정 주입

================================================================================
사용 예시 (Usage Examples)
================================================================================
>>> from legacy.app.database.redis import get_redis, set_cache, get_cache
>>>
>>> # 캐시 저장 (1시간 TTL)
>>> await set_cache("user:123", user_json, expire=3600)
>>>
>>> # 캐시 조회
>>> cached = await get_cache("user:123")
>>>
>>> # Rate Limiting
>>> allowed, count, ttl = await check_rate_limit("ip:192.168.1.1", limit=100)
>>> if not allowed:
...     raise RateLimitException(retry_after=ttl)
"""

import asyncio
import logging
from typing import Optional
import redis.asyncio as redis
from redis.asyncio import ConnectionPool
from redis.exceptions import ConnectionError, TimeoutError, RedisError

from legacy.app.core.config import settings
from legacy.app.core.logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# 전역 Redis 인스턴스 (Global Redis Instances)
# =============================================================================
# 싱글톤 패턴으로 애플리케이션 전체에서 공유합니다.
# init_redis()로 초기화하고, close_redis()로 종료합니다.
# =============================================================================
redis_client: Optional[redis.Redis] = None
redis_pool: Optional[ConnectionPool] = None


async def create_redis_pool() -> ConnectionPool:
    """
    Redis 연결 풀 생성

    설정 파일의 옵션에 따라 연결 풀을 생성합니다.
    - 최대 연결 수, 타임아웃 재시도, Keep-Alive 등 설정

    Returns:
        ConnectionPool: 생성된 연결 풀 인스턴스

    Raises:
        Exception: 연결 풀 생성 실패 시
    """
    try:
        pool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=settings.redis_max_connections,
            retry_on_timeout=settings.redis_retry_on_timeout,
            socket_keepalive=settings.redis_socket_keepalive,
            socket_keepalive_options=settings.redis_socket_keepalive_options,
            decode_responses=True,  # 자동으로 bytes를 string으로 디코딩
            encoding='utf-8'
        )

        logger.info(f"Redis connection pool created with max {settings.redis_max_connections} connections")
        return pool

    except Exception as e:
        logger.error(f"Failed to create Redis connection pool: {e}")
        raise


async def init_redis():
    """
    Redis 연결 초기화

    애플리케이션 시작 시 호출하여 Redis 연결을 설정합니다.
    연결 테스트(ping)를 수행하고 서버 정보를 로깅합니다.

    Raises:
        ConnectionError: Redis 서버 연결 실패 시

    Note:
        main.py의 lifespan 함수에서 호출됩니다.
    """
    global redis_client, redis_pool

    try:
        # 연결 풀 생성
        redis_pool = await create_redis_pool()

        # Redis 클라이언트 생성
        redis_client = redis.Redis(connection_pool=redis_pool)

        # 연결 테스트
        await redis_client.ping()

        logger.info("Redis connection initialized successfully")

        # 기본 설정 확인
        info = await redis_client.info()
        logger.info(f"Redis server version: {info.get('redis_version', 'unknown')}")
        logger.info(f"Redis used memory: {info.get('used_memory_human', 'unknown')}")

    except ConnectionError as e:
        logger.error(f"Redis connection failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Redis initialization failed: {e}")
        raise


async def close_redis():
    """Redis 연결 종료"""
    global redis_client, redis_pool

    try:
        if redis_client:
            await redis_client.aclose()
            logger.info("Redis client closed")

        if redis_pool:
            await redis_pool.aclose()
            logger.info("Redis connection pool closed")

    except Exception as e:
        logger.error(f"Error closing Redis connections: {e}")
    finally:
        redis_client = None
        redis_pool = None


async def get_redis() -> redis.Redis:
    """Redis 클라이언트 인스턴스 반환"""
    global redis_client

    if redis_client is None:
        await init_redis()

    return redis_client


# =============================================================================
# 캐시 유틸리티 함수들 (Cache Utility Functions)
# =============================================================================
# 캐시 데이터의 CRUD 작업을 위한 함수들입니다.
# 모든 함수는 에러 발생 시 False/None을 반환하고 로깅합니다.
# =============================================================================

async def set_cache(key: str, value: str, expire: int = 3600) -> bool:
    """
    캐시 데이터 저장

    Args:
        key: 캐시 키
        value: 저장할 값 (문자열)
        expire: TTL 초 단위 (기본: 1시간)

    Returns:
        bool: 저장 성공 여부

    Example:
        >>> await set_cache("user:123", json.dumps(user_data), expire=3600)
        True
    """
    try:
        client = await get_redis()
        result = await client.setex(key, expire, value)
        logger.debug(f"Cache set: {key} (expires in {expire}s)")
        return result
    except Exception as e:
        logger.error(f"Failed to set cache {key}: {e}")
        return False


async def get_cache(key: str) -> Optional[str]:
    """
    캐시 데이터 조회

    Args:
        key: 캐시 키

    Returns:
        Optional[str]: 캐시된 값 또는 None (캐시 미스 또는 에러)

    Example:
        >>> cached = await get_cache("user:123")
        >>> if cached:
        ...     user_data = json.loads(cached)
    """
    try:
        client = await get_redis()
        result = await client.get(key)
        if result:
            logger.debug(f"Cache hit: {key}")
        else:
            logger.debug(f"Cache miss: {key}")
        return result
    except Exception as e:
        logger.error(f"Failed to get cache {key}: {e}")
        return None


async def delete_cache(key: str) -> bool:
    """캐시 데이터 삭제"""
    try:
        client = await get_redis()
        result = await client.delete(key)
        logger.debug(f"Cache deleted: {key}")
        return bool(result)
    except Exception as e:
        logger.error(f"Failed to delete cache {key}: {e}")
        return False


async def increment_counter(key: str, expire: int = 60) -> int:
    """카운터 증가 (Rate Limiting용)"""
    try:
        client = await get_redis()

        # 파이프라인을 사용하여 원자적 연산 수행
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, expire)
        results = await pipe.execute()

        count = results[0]
        logger.debug(f"Counter incremented: {key} = {count}")
        return count

    except Exception as e:
        logger.error(f"Failed to increment counter {key}: {e}")
        return 0


async def get_counter(key: str) -> int:
    """카운터 값 조회"""
    try:
        client = await get_redis()
        result = await client.get(key)
        return int(result) if result else 0
    except Exception as e:
        logger.error(f"Failed to get counter {key}: {e}")
        return 0


async def reset_counter(key: str) -> bool:
    """카운터 리셋"""
    try:
        return await delete_cache(key)
    except Exception as e:
        logger.error(f"Failed to reset counter {key}: {e}")
        return False


async def set_session(session_id: str, data: str, expire: int = 86400) -> bool:
    """세션 데이터 저장 (24시간 기본)"""
    try:
        session_key = f"session:{session_id}"
        return await set_cache(session_key, data, expire)
    except Exception as e:
        logger.error(f"Failed to set session {session_id}: {e}")
        return False


async def get_session(session_id: str) -> Optional[str]:
    """세션 데이터 조회"""
    try:
        session_key = f"session:{session_id}"
        return await get_cache(session_key)
    except Exception as e:
        logger.error(f"Failed to get session {session_id}: {e}")
        return None


async def delete_session(session_id: str) -> bool:
    """세션 데이터 삭제"""
    try:
        session_key = f"session:{session_id}"
        return await delete_cache(session_key)
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}")
        return False


# =============================================================================
# Redis 상태 확인 함수들
# =============================================================================

async def health_check() -> dict:
    """Redis 헬스 체크"""
    try:
        client = await get_redis()

        # 연결 테스트
        start_time = asyncio.get_event_loop().time()
        await client.ping()
        ping_time = (asyncio.get_event_loop().time() - start_time) * 1000

        # 서버 정보 조회
        info = await client.info()

        return {
            "status": "healthy",
            "ping_ms": round(ping_time, 2),
            "version": info.get("redis_version", "unknown"),
            "used_memory": info.get("used_memory_human", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
            "total_commands_processed": info.get("total_commands_processed", 0)
        }

    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def get_stats() -> dict:
    """Redis 통계 정보 조회"""
    try:
        client = await get_redis()
        info = await client.info()

        return {
            "server": {
                "version": info.get("redis_version"),
                "uptime_seconds": info.get("uptime_in_seconds"),
                "uptime_days": info.get("uptime_in_days")
            },
            "memory": {
                "used_memory": info.get("used_memory"),
                "used_memory_human": info.get("used_memory_human"),
                "used_memory_peak": info.get("used_memory_peak"),
                "used_memory_peak_human": info.get("used_memory_peak_human")
            },
            "clients": {
                "connected_clients": info.get("connected_clients"),
                "blocked_clients": info.get("blocked_clients")
            },
            "stats": {
                "total_connections_received": info.get("total_connections_received"),
                "total_commands_processed": info.get("total_commands_processed"),
                "instantaneous_ops_per_sec": info.get("instantaneous_ops_per_sec"),
                "keyspace_hits": info.get("keyspace_hits"),
                "keyspace_misses": info.get("keyspace_misses")
            }
        }

    except Exception as e:
        logger.error(f"Failed to get Redis stats: {e}")
        return {"error": str(e)}


# =============================================================================
# Rate Limiting 함수들 (Rate Limiting Functions)
# =============================================================================
# 슬라이딩 윈도우 방식의 Rate Limiting을 구현합니다.
# 카운터 기반으로 특정 시간 내 요청 수를 제한합니다.
# =============================================================================

async def check_rate_limit(identifier: str, limit: int, window: int = 60) -> tuple[bool, int, int]:
    """
    Rate limit 확인

    Args:
        identifier: 사용자/IP 식별자
        limit: 허용 요청 수
        window: 시간 윈도우 (초)

    Returns:
        (허용 여부, 현재 카운트, 남은 시간)
    """
    try:
        key = f"rate_limit:{identifier}"
        current_count = await increment_counter(key, window)

        if current_count <= limit:
            return True, current_count, window
        else:
            # TTL 조회 (남은 시간)
            client = await get_redis()
            remaining_time = await client.ttl(key)
            return False, current_count, remaining_time

    except Exception as e:
        logger.error(f"Rate limit check failed for {identifier}: {e}")
        # 에러 시 허용 (fail-open)
        return True, 0, 0