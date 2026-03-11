"""
=============================================================================
Cache Service (캐시 서비스) - Redis 기반 범용 캐싱
=============================================================================

📌 이 파일이 하는 일:
    Redis를 사용한 범용 캐시 서비스입니다.
    모든 마이크로서비스에서 공통으로 사용할 수 있습니다.

💡 캐시란?
    자주 사용하는 데이터를 빠른 저장소(Redis)에 임시 저장하여
    데이터베이스 조회를 줄이고 응답 속도를 높이는 기술입니다.

🔄 캐시 전략:
    ┌─────────────────────────────────────────────────────────────┐
    │  1. Cache-Aside (Look-Aside) - 기본 전략                    │
    │                                                             │
    │     요청 → 캐시 확인 → HIT → 캐시에서 반환                   │
    │                    ↓ MISS                                   │
    │              DB 조회 → 캐시 저장 → 반환                      │
    └─────────────────────────────────────────────────────────────┘

📊 Redis Key 네이밍 규칙:
    {service}:{entity}:{id}

    예시:
    - user:profile:123        → 사용자 123의 프로필
    - chat:room:456           → 채팅방 456 정보
    - chat:messages:456:page1 → 채팅방 456의 1페이지 메시지
    - friend:list:123         → 사용자 123의 친구 목록

사용 예시
---------
```python
from shared_lib.cache import get_cache_service

cache = get_cache_service()
await cache.init(settings.redis_url)

# 1. 단순 캐싱
await cache.set("user:123", {"name": "홍길동"}, ttl=300)
user = await cache.get("user:123")

# 2. 패턴으로 삭제 (사용자 관련 모든 캐시 삭제)
await cache.delete_pattern("user:123:*")

# 3. get_or_set (캐시 없으면 함수 실행 후 저장)
user = await cache.get_or_set(
    key="user:123",
    fallback=lambda: fetch_user_from_db(123),
    ttl=300
)
```

관련 파일
---------
- shared_lib/cache/decorators.py: 캐시 데코레이터
- user-service/app/services/online_status_service.py: 온라인 상태 (별도 관리)
"""

import json
import logging
from typing import Any, Callable, Optional, TypeVar, Union
from datetime import timedelta

import redis.asyncio as redis

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheService:
    """
    📌 Redis 기반 범용 캐시 서비스

    기능:
        - 기본 CRUD (get, set, delete)
        - TTL (Time To Live) 자동 만료
        - 패턴 기반 삭제 (delete_pattern)
        - get_or_set (Cache-Aside 패턴)
        - 리스트/해시 지원

    Thread Safety:
        redis.asyncio는 thread-safe
        여러 코루틴에서 동시 사용 가능

    사용 예시:
        cache = CacheService()
        await cache.init("redis://localhost:6379")
        await cache.set("key", {"data": "value"}, ttl=300)
    """

    # =========================================================================
    # 기본 TTL 설정 (초 단위)
    # =========================================================================
    DEFAULT_TTL = 300           # 5분 (일반 데이터)
    SHORT_TTL = 60              # 1분 (자주 변경되는 데이터)
    LONG_TTL = 3600             # 1시간 (거의 변경 안 되는 데이터)
    SESSION_TTL = 86400         # 24시간 (세션 데이터)

    def __init__(self):
        """캐시 서비스 인스턴스 생성 (연결은 init에서)"""
        self._client: Optional[redis.Redis] = None
        self._prefix: str = ""  # 키 프리픽스 (서비스별 구분)

    async def init(
        self,
        redis_url: str,
        prefix: str = "",
        max_connections: int = 50
    ):
        """
        📌 캐시 서비스 초기화

        애플리케이션 시작 시 (lifespan startup) 호출합니다.

        Args:
            redis_url: Redis 연결 URL
                       예: "redis://localhost:6379"
            prefix: 키 프리픽스 (서비스별 네임스페이스)
                    예: "user" → 모든 키가 "user:" 로 시작
            max_connections: 연결 풀 최대 크기

        Connection Pool:
            - max_connections: 동시 연결 수 제한
            - Redis는 싱글 스레드지만 네트워크 I/O는 병렬 처리

        사용 예시:
            await cache.init("redis://localhost:6379", prefix="user")
        """
        try:
            self._client = redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=max_connections
            )
            self._prefix = f"{prefix}:" if prefix else ""

            # 연결 테스트
            await self._client.ping()
            logger.info(f"Cache service initialized (prefix: {prefix or 'none'})")

        except Exception as e:
            logger.error(f"Failed to initialize cache service: {e}")
            self._client = None
            raise

    async def close(self):
        """
        📌 캐시 서비스 종료

        애플리케이션 종료 시 (lifespan shutdown) 호출합니다.
        """
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Cache service closed")

    def _make_key(self, key: str) -> str:
        """프리픽스를 포함한 전체 키 생성"""
        return f"{self._prefix}{key}"

    # =========================================================================
    # 기본 CRUD 작업
    # =========================================================================

    async def get(self, key: str, default: T = None) -> Optional[Union[T, Any]]:
        """
        📌 캐시에서 값 조회

        Args:
            key: 캐시 키
            default: 값이 없을 때 반환할 기본값

        Returns:
            캐시된 값 또는 default

        사용 예시:
            user = await cache.get("user:123")
            user = await cache.get("user:123", default={})
        """
        if not self._client:
            return default

        try:
            full_key = self._make_key(key)
            value = await self._client.get(full_key)

            if value is None:
                return default

            # JSON 파싱 시도
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value

        except Exception as e:
            logger.warning(f"Cache get failed for key '{key}': {e}")
            return default

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        📌 캐시에 값 저장

        Args:
            key: 캐시 키
            value: 저장할 값 (dict, list, str, int 등)
            ttl: 만료 시간 (초), None이면 DEFAULT_TTL 사용

        Returns:
            성공 여부

        TTL 가이드:
            - 자주 변경: 60초 (SHORT_TTL)
            - 일반 데이터: 300초 (DEFAULT_TTL)
            - 거의 안 변함: 3600초 (LONG_TTL)

        사용 예시:
            await cache.set("user:123", {"name": "홍길동"}, ttl=300)
        """
        if not self._client:
            return False

        try:
            full_key = self._make_key(key)
            ttl = ttl or self.DEFAULT_TTL

            # dict/list는 JSON으로 직렬화
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, default=str)

            await self._client.set(full_key, value, ex=ttl)
            return True

        except Exception as e:
            logger.warning(f"Cache set failed for key '{key}': {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        📌 캐시에서 값 삭제

        Args:
            key: 삭제할 캐시 키

        Returns:
            삭제 성공 여부

        사용 예시:
            await cache.delete("user:123")
        """
        if not self._client:
            return False

        try:
            full_key = self._make_key(key)
            result = await self._client.delete(full_key)
            return result > 0

        except Exception as e:
            logger.warning(f"Cache delete failed for key '{key}': {e}")
            return False

    async def exists(self, key: str) -> bool:
        """
        📌 캐시 키 존재 여부 확인

        Args:
            key: 확인할 캐시 키

        Returns:
            존재하면 True

        사용 예시:
            if await cache.exists("user:123"):
                print("캐시에 있음")
        """
        if not self._client:
            return False

        try:
            full_key = self._make_key(key)
            return await self._client.exists(full_key) > 0

        except Exception as e:
            logger.warning(f"Cache exists check failed for key '{key}': {e}")
            return False

    # =========================================================================
    # 고급 작업
    # =========================================================================

    async def get_or_set(
        self,
        key: str,
        fallback: Callable[[], T],
        ttl: Optional[int] = None
    ) -> Optional[T]:
        """
        📌 Cache-Aside 패턴 구현

        캐시에 값이 있으면 반환, 없으면 fallback 함수 실행 후 캐시에 저장.

        동작 흐름:
            1. 캐시 조회 (HIT → 반환)
            2. 캐시 MISS → fallback() 실행
            3. 결과를 캐시에 저장
            4. 결과 반환

        Args:
            key: 캐시 키
            fallback: 캐시 미스 시 실행할 함수 (async 가능)
            ttl: 만료 시간 (초)

        Returns:
            캐시된 값 또는 fallback 결과

        사용 예시:
            user = await cache.get_or_set(
                key="user:123",
                fallback=lambda: db.get(User, 123),
                ttl=300
            )

            # async fallback
            user = await cache.get_or_set(
                key="user:123",
                fallback=fetch_user_async,
                ttl=300
            )
        """
        # 캐시 조회
        cached = await self.get(key)
        if cached is not None:
            return cached

        # fallback 실행
        try:
            import asyncio
            if asyncio.iscoroutinefunction(fallback):
                value = await fallback()
            else:
                value = fallback()

            # 결과 캐싱
            if value is not None:
                await self.set(key, value, ttl=ttl)

            return value

        except Exception as e:
            logger.error(f"Cache fallback failed for key '{key}': {e}")
            return None

    async def delete_pattern(self, pattern: str) -> int:
        """
        📌 패턴에 맞는 모든 키 삭제

        사용자 관련 모든 캐시 삭제 등에 유용합니다.

        Args:
            pattern: 삭제할 키 패턴 (glob 패턴)
                     예: "user:123:*" → user:123:profile, user:123:friends 등

        Returns:
            삭제된 키 개수

        ⚠️ 주의:
            KEYS 명령은 프로덕션에서 주의해서 사용
            대량의 키가 있으면 SCAN 사용 권장

        사용 예시:
            # 사용자 123의 모든 캐시 삭제
            count = await cache.delete_pattern("user:123:*")
        """
        if not self._client:
            return 0

        try:
            full_pattern = self._make_key(pattern)
            deleted = 0

            # SCAN으로 키 조회 (KEYS보다 안전)
            cursor = 0
            while True:
                cursor, keys = await self._client.scan(
                    cursor=cursor,
                    match=full_pattern,
                    count=100
                )
                if keys:
                    deleted += await self._client.delete(*keys)
                if cursor == 0:
                    break

            logger.info(f"Deleted {deleted} keys matching pattern '{pattern}'")
            return deleted

        except Exception as e:
            logger.warning(f"Cache delete_pattern failed for '{pattern}': {e}")
            return 0

    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """
        📌 카운터 증가

        조회수, 좋아요 수 등 카운터에 유용합니다.

        Args:
            key: 카운터 키
            amount: 증가량 (기본: 1)

        Returns:
            증가 후 값

        사용 예시:
            views = await cache.increment("post:123:views")
        """
        if not self._client:
            return None

        try:
            full_key = self._make_key(key)
            return await self._client.incrby(full_key, amount)

        except Exception as e:
            logger.warning(f"Cache increment failed for key '{key}': {e}")
            return None

    async def set_ttl(self, key: str, ttl: int) -> bool:
        """
        📌 기존 키의 TTL 설정/갱신

        Args:
            key: 캐시 키
            ttl: 새 만료 시간 (초)

        Returns:
            성공 여부

        사용 예시:
            await cache.set_ttl("user:123", 600)  # 10분으로 연장
        """
        if not self._client:
            return False

        try:
            full_key = self._make_key(key)
            return await self._client.expire(full_key, ttl)

        except Exception as e:
            logger.warning(f"Cache set_ttl failed for key '{key}': {e}")
            return False

    async def get_ttl(self, key: str) -> int:
        """
        📌 키의 남은 TTL 조회

        Args:
            key: 캐시 키

        Returns:
            남은 시간 (초), -2: 키 없음, -1: TTL 없음

        사용 예시:
            remaining = await cache.get_ttl("user:123")
        """
        if not self._client:
            return -2

        try:
            full_key = self._make_key(key)
            return await self._client.ttl(full_key)

        except Exception as e:
            logger.warning(f"Cache get_ttl failed for key '{key}': {e}")
            return -2

    # =========================================================================
    # 리스트 작업 (최근 메시지, 알림 등)
    # =========================================================================

    async def list_push(
        self,
        key: str,
        *values: Any,
        max_length: Optional[int] = None,
        ttl: Optional[int] = None
    ) -> int:
        """
        📌 리스트에 값 추가 (왼쪽에 추가 = 최신이 앞)

        최근 메시지, 최근 알림 등에 유용합니다.

        Args:
            key: 리스트 키
            values: 추가할 값들
            max_length: 최대 길이 (초과 시 오래된 것 삭제)
            ttl: 만료 시간 (초)

        Returns:
            리스트 길이

        사용 예시:
            await cache.list_push(
                "user:123:notifications",
                {"type": "message", "from": 456},
                max_length=100,
                ttl=86400
            )
        """
        if not self._client:
            return 0

        try:
            full_key = self._make_key(key)

            # JSON 직렬화
            serialized = [
                json.dumps(v, ensure_ascii=False, default=str)
                if isinstance(v, (dict, list)) else str(v)
                for v in values
            ]

            # 왼쪽에 추가 (최신이 앞)
            length = await self._client.lpush(full_key, *serialized)

            # 최대 길이 제한
            if max_length:
                await self._client.ltrim(full_key, 0, max_length - 1)

            # TTL 설정
            if ttl:
                await self._client.expire(full_key, ttl)

            return length

        except Exception as e:
            logger.warning(f"Cache list_push failed for key '{key}': {e}")
            return 0

    async def list_range(
        self,
        key: str,
        start: int = 0,
        end: int = -1
    ) -> list:
        """
        📌 리스트에서 범위 조회

        Args:
            key: 리스트 키
            start: 시작 인덱스 (0부터)
            end: 끝 인덱스 (-1은 끝까지)

        Returns:
            리스트 값들

        사용 예시:
            # 최근 10개 알림
            notifications = await cache.list_range("user:123:notifications", 0, 9)
        """
        if not self._client:
            return []

        try:
            full_key = self._make_key(key)
            values = await self._client.lrange(full_key, start, end)

            # JSON 파싱
            result = []
            for v in values:
                try:
                    result.append(json.loads(v))
                except (json.JSONDecodeError, TypeError):
                    result.append(v)

            return result

        except Exception as e:
            logger.warning(f"Cache list_range failed for key '{key}': {e}")
            return []

    # =========================================================================
    # 해시 작업 (객체 필드별 접근)
    # =========================================================================

    async def hash_set(
        self,
        key: str,
        mapping: dict,
        ttl: Optional[int] = None
    ) -> bool:
        """
        📌 해시에 여러 필드 저장

        객체의 일부 필드만 업데이트할 때 유용합니다.

        Args:
            key: 해시 키
            mapping: 필드-값 딕셔너리
            ttl: 만료 시간 (초)

        Returns:
            성공 여부

        사용 예시:
            await cache.hash_set(
                "user:123",
                {"name": "홍길동", "email": "hong@example.com"},
                ttl=3600
            )
        """
        if not self._client:
            return False

        try:
            full_key = self._make_key(key)

            # 값 직렬화
            serialized = {}
            for k, v in mapping.items():
                if isinstance(v, (dict, list)):
                    serialized[k] = json.dumps(v, ensure_ascii=False, default=str)
                else:
                    serialized[k] = str(v) if v is not None else ""

            await self._client.hset(full_key, mapping=serialized)

            if ttl:
                await self._client.expire(full_key, ttl)

            return True

        except Exception as e:
            logger.warning(f"Cache hash_set failed for key '{key}': {e}")
            return False

    async def hash_get(self, key: str, field: str) -> Optional[Any]:
        """
        📌 해시에서 특정 필드 조회

        Args:
            key: 해시 키
            field: 필드명

        Returns:
            필드 값

        사용 예시:
            name = await cache.hash_get("user:123", "name")
        """
        if not self._client:
            return None

        try:
            full_key = self._make_key(key)
            value = await self._client.hget(full_key, field)

            if value is None:
                return None

            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value

        except Exception as e:
            logger.warning(f"Cache hash_get failed for key '{key}': {e}")
            return None

    async def hash_get_all(self, key: str) -> dict:
        """
        📌 해시의 모든 필드 조회

        Args:
            key: 해시 키

        Returns:
            필드-값 딕셔너리

        사용 예시:
            user = await cache.hash_get_all("user:123")
        """
        if not self._client:
            return {}

        try:
            full_key = self._make_key(key)
            data = await self._client.hgetall(full_key)

            # JSON 파싱
            result = {}
            for k, v in data.items():
                try:
                    result[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    result[k] = v

            return result

        except Exception as e:
            logger.warning(f"Cache hash_get_all failed for key '{key}': {e}")
            return {}

    # =========================================================================
    # 헬스 체크
    # =========================================================================

    async def health_check(self) -> bool:
        """Redis 연결 상태 확인"""
        if not self._client:
            return False
        try:
            await self._client.ping()
            return True
        except Exception:
            return False

    @property
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self._client is not None


# =============================================================================
# 싱글톤 인스턴스
# =============================================================================

_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """
    📌 캐시 서비스 싱글톤 반환

    애플리케이션 전체에서 하나의 캐시 서비스 인스턴스 공유.

    Returns:
        CacheService: 싱글톤 인스턴스

    사용 예시:
        cache = get_cache_service()
        await cache.init("redis://localhost:6379")
    """
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
