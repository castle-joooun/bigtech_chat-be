"""
=============================================================================
Cache Service Tests - Redis 캐싱 기능 테스트
=============================================================================

테스트 항목:
    1. 기본 CRUD (get, set, delete, exists)
    2. get_or_set (Cache-Aside 패턴)
    3. TTL 동작
    4. 리스트 작업
    5. 해시 작업
    6. @cached 데코레이터
    7. 캐시 무효화
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from shared_lib.cache.service import CacheService, get_cache_service
from shared_lib.cache.decorators import cached, cache_aside, invalidate_cache


# =============================================================================
# Mock Redis Client
# =============================================================================

class MockRedis:
    """테스트용 Mock Redis 클라이언트"""

    def __init__(self):
        self._data = {}
        self._ttls = {}

    async def ping(self):
        return True

    async def close(self):
        pass

    async def get(self, key):
        return self._data.get(key)

    async def set(self, key, value, ex=None):
        self._data[key] = value
        if ex:
            self._ttls[key] = ex
        return True

    async def delete(self, *keys):
        count = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                count += 1
        return count

    async def exists(self, key):
        return 1 if key in self._data else 0

    async def expire(self, key, ttl):
        if key in self._data:
            self._ttls[key] = ttl
            return True
        return False

    async def ttl(self, key):
        if key not in self._data:
            return -2
        return self._ttls.get(key, -1)

    async def incrby(self, key, amount):
        if key not in self._data:
            self._data[key] = "0"
        current = int(self._data[key])
        new_value = current + amount
        self._data[key] = str(new_value)
        return new_value

    async def scan(self, cursor, match, count):
        # 간단한 패턴 매칭 (glob 패턴)
        import fnmatch
        matched = [k for k in self._data.keys() if fnmatch.fnmatch(k, match)]
        return (0, matched)  # cursor=0은 종료

    async def lpush(self, key, *values):
        if key not in self._data:
            self._data[key] = []
        # lpush는 왼쪽에 추가 (마지막 인자가 가장 앞에)
        for v in values:
            self._data[key].insert(0, v)
        return len(self._data[key])

    async def ltrim(self, key, start, end):
        if key in self._data:
            self._data[key] = self._data[key][start:end+1]
        return True

    async def lrange(self, key, start, end):
        if key not in self._data:
            return []
        if end == -1:
            return self._data[key][start:]
        return self._data[key][start:end+1]

    async def hset(self, key, mapping):
        if key not in self._data:
            self._data[key] = {}
        self._data[key].update(mapping)
        return len(mapping)

    async def hget(self, key, field):
        if key not in self._data:
            return None
        return self._data[key].get(field)

    async def hgetall(self, key):
        return self._data.get(key, {})


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis 인스턴스"""
    return MockRedis()


@pytest.fixture
async def cache_service(mock_redis):
    """캐시 서비스 인스턴스 (Mock Redis 사용)"""
    service = CacheService()
    service._client = mock_redis
    service._prefix = "test:"
    return service


# =============================================================================
# 기본 CRUD 테스트
# =============================================================================

class TestCacheBasicCRUD:
    """기본 CRUD 작업 테스트"""

    @pytest.mark.asyncio
    async def test_set_and_get_string(self, cache_service):
        """문자열 저장 및 조회"""
        await cache_service.set("key1", "value1")
        result = await cache_service.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_set_and_get_dict(self, cache_service):
        """딕셔너리 저장 및 조회"""
        data = {"name": "홍길동", "age": 30}
        await cache_service.set("user:123", data)
        result = await cache_service.get("user:123")
        assert result == data
        assert result["name"] == "홍길동"

    @pytest.mark.asyncio
    async def test_set_and_get_list(self, cache_service):
        """리스트 저장 및 조회"""
        data = [1, 2, 3, "four", {"five": 5}]
        await cache_service.set("list:key", data)
        result = await cache_service.get("list:key")
        assert result == data

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, cache_service):
        """존재하지 않는 키 조회"""
        result = await cache_service.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_with_default(self, cache_service):
        """기본값과 함께 조회"""
        result = await cache_service.get("nonexistent", default={"empty": True})
        assert result == {"empty": True}

    @pytest.mark.asyncio
    async def test_delete(self, cache_service):
        """키 삭제"""
        await cache_service.set("to_delete", "value")
        assert await cache_service.exists("to_delete") is True

        result = await cache_service.delete("to_delete")
        assert result is True
        assert await cache_service.exists("to_delete") is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, cache_service):
        """존재하지 않는 키 삭제"""
        result = await cache_service.delete("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists(self, cache_service):
        """키 존재 여부 확인"""
        await cache_service.set("exists_key", "value")
        assert await cache_service.exists("exists_key") is True
        assert await cache_service.exists("not_exists") is False


# =============================================================================
# get_or_set 테스트 (Cache-Aside)
# =============================================================================

class TestCacheAside:
    """Cache-Aside 패턴 테스트"""

    @pytest.mark.asyncio
    async def test_get_or_set_cache_miss(self, cache_service):
        """캐시 MISS 시 fallback 실행"""
        call_count = 0

        async def fallback():
            nonlocal call_count
            call_count += 1
            return {"fetched": True}

        result = await cache_service.get_or_set("miss_key", fallback, ttl=300)

        assert result == {"fetched": True}
        assert call_count == 1

        # 캐시에 저장되었는지 확인
        cached = await cache_service.get("miss_key")
        assert cached == {"fetched": True}

    @pytest.mark.asyncio
    async def test_get_or_set_cache_hit(self, cache_service):
        """캐시 HIT 시 fallback 미실행"""
        call_count = 0

        async def fallback():
            nonlocal call_count
            call_count += 1
            return {"fetched": True}

        # 먼저 캐시에 저장
        await cache_service.set("hit_key", {"cached": True})

        result = await cache_service.get_or_set("hit_key", fallback, ttl=300)

        assert result == {"cached": True}
        assert call_count == 0  # fallback 호출 안 됨

    @pytest.mark.asyncio
    async def test_get_or_set_sync_fallback(self, cache_service):
        """동기 fallback 함수 지원"""
        def sync_fallback():
            return {"sync": True}

        result = await cache_service.get_or_set("sync_key", sync_fallback)
        assert result == {"sync": True}


# =============================================================================
# TTL 테스트
# =============================================================================

class TestCacheTTL:
    """TTL(Time To Live) 테스트"""

    @pytest.mark.asyncio
    async def test_set_with_ttl(self, cache_service, mock_redis):
        """TTL 설정 확인"""
        await cache_service.set("ttl_key", "value", ttl=600)

        # Mock에서 TTL 확인
        full_key = "test:ttl_key"
        assert full_key in mock_redis._ttls
        assert mock_redis._ttls[full_key] == 600

    @pytest.mark.asyncio
    async def test_set_ttl(self, cache_service):
        """기존 키의 TTL 변경"""
        await cache_service.set("key", "value", ttl=300)
        result = await cache_service.set_ttl("key", 600)
        assert result is True

    @pytest.mark.asyncio
    async def test_get_ttl(self, cache_service):
        """TTL 조회"""
        await cache_service.set("ttl_check", "value", ttl=300)
        ttl = await cache_service.get_ttl("ttl_check")
        assert ttl == 300


# =============================================================================
# 패턴 삭제 테스트
# =============================================================================

class TestDeletePattern:
    """패턴 기반 삭제 테스트"""

    @pytest.mark.asyncio
    async def test_delete_pattern(self, cache_service):
        """패턴 매칭 삭제"""
        await cache_service.set("user:123:profile", {"name": "A"})
        await cache_service.set("user:123:friends", [1, 2, 3])
        await cache_service.set("user:456:profile", {"name": "B"})

        # user:123:* 패턴 삭제
        deleted = await cache_service.delete_pattern("user:123:*")

        assert deleted == 2
        assert await cache_service.exists("user:123:profile") is False
        assert await cache_service.exists("user:123:friends") is False
        assert await cache_service.exists("user:456:profile") is True


# =============================================================================
# 카운터 테스트
# =============================================================================

class TestCacheCounter:
    """카운터 기능 테스트"""

    @pytest.mark.asyncio
    async def test_increment(self, cache_service):
        """카운터 증가"""
        result = await cache_service.increment("counter:views")
        assert result == 1

        result = await cache_service.increment("counter:views")
        assert result == 2

        result = await cache_service.increment("counter:views", amount=5)
        assert result == 7


# =============================================================================
# 리스트 작업 테스트
# =============================================================================

class TestCacheList:
    """리스트 작업 테스트"""

    @pytest.mark.asyncio
    async def test_list_push_and_range(self, cache_service):
        """리스트 추가 및 조회"""
        await cache_service.list_push("notifications", {"id": 1}, {"id": 2})

        items = await cache_service.list_range("notifications", 0, -1)
        assert len(items) == 2
        assert items[0]["id"] == 2  # 최신이 앞
        assert items[1]["id"] == 1

    @pytest.mark.asyncio
    async def test_list_max_length(self, cache_service, mock_redis):
        """리스트 최대 길이 제한"""
        for i in range(10):
            await cache_service.list_push("limited", {"id": i}, max_length=5)

        items = await cache_service.list_range("limited", 0, -1)
        assert len(items) == 5


# =============================================================================
# 해시 작업 테스트
# =============================================================================

class TestCacheHash:
    """해시 작업 테스트"""

    @pytest.mark.asyncio
    async def test_hash_set_and_get(self, cache_service):
        """해시 저장 및 조회"""
        await cache_service.hash_set("user:hash:123", {
            "name": "홍길동",
            "email": "hong@example.com"
        })

        name = await cache_service.hash_get("user:hash:123", "name")
        assert name == "홍길동"

    @pytest.mark.asyncio
    async def test_hash_get_all(self, cache_service):
        """해시 전체 조회"""
        await cache_service.hash_set("user:hash:456", {
            "name": "김철수",
            "age": 25
        })

        data = await cache_service.hash_get_all("user:hash:456")
        assert data["name"] == "김철수"
        # hash_set에서 int를 str로 변환하고, hash_get_all에서 JSON 파싱
        assert data["age"] == 25 or str(data["age"]) == "25"


# =============================================================================
# @cached 데코레이터 테스트
# =============================================================================

class TestCachedDecorator:
    """@cached 데코레이터 테스트"""

    @pytest.mark.asyncio
    async def test_cached_decorator_miss_then_hit(self):
        """데코레이터: MISS 후 HIT"""
        call_count = 0

        # Mock 캐시 서비스 설정
        mock_cache = CacheService()
        mock_cache._client = MockRedis()
        mock_cache._prefix = ""

        # 싱글톤 패치 (.service 모듈의 함수를 패치)
        with patch('shared_lib.cache.service._cache_service', mock_cache):
            @cached(prefix="test", ttl=300)
            async def get_data(item_id: int):
                nonlocal call_count
                call_count += 1
                return {"id": item_id, "value": "data"}

            # 첫 호출 - MISS
            result1 = await get_data(123)
            assert result1 == {"id": 123, "value": "data"}
            assert call_count == 1

            # 두 번째 호출 - HIT
            result2 = await get_data(123)
            assert result2 == {"id": 123, "value": "data"}
            assert call_count == 1  # 함수 호출 안 됨

    @pytest.mark.asyncio
    async def test_cached_decorator_skip_condition(self):
        """데코레이터: 스킵 조건"""
        call_count = 0

        mock_cache = CacheService()
        mock_cache._client = MockRedis()
        mock_cache._prefix = ""

        with patch('shared_lib.cache.service._cache_service', mock_cache):
            @cached(
                prefix="test",
                ttl=300,
                skip_cache_if=lambda item_id: item_id == 999
            )
            async def get_data(item_id: int):
                nonlocal call_count
                call_count += 1
                return {"id": item_id}

            # item_id=999는 캐시 스킵
            await get_data(999)
            await get_data(999)
            assert call_count == 2  # 매번 호출됨

    @pytest.mark.asyncio
    async def test_cached_decorator_invalidate(self):
        """데코레이터: 캐시 무효화"""
        mock_cache = CacheService()
        mock_cache._client = MockRedis()
        mock_cache._prefix = ""

        with patch('shared_lib.cache.service._cache_service', mock_cache):
            @cached(prefix="test", ttl=300)
            async def get_data(item_id: int):
                return {"id": item_id}

            # 캐시 생성
            await get_data(123)

            # 캐시 존재 확인
            key = "test:get_data:123"
            assert await mock_cache.exists(key) is True

            # 무효화
            await get_data.invalidate(123)
            assert await mock_cache.exists(key) is False


# =============================================================================
# 헬스 체크 테스트
# =============================================================================

class TestCacheHealth:
    """헬스 체크 테스트"""

    @pytest.mark.asyncio
    async def test_health_check_connected(self, cache_service):
        """연결된 상태 헬스 체크"""
        result = await cache_service.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_disconnected(self):
        """연결 안 된 상태 헬스 체크"""
        service = CacheService()
        result = await service.health_check()
        assert result is False

    def test_is_connected(self, cache_service):
        """연결 상태 프로퍼티"""
        assert cache_service.is_connected is True

        disconnected = CacheService()
        assert disconnected.is_connected is False


# =============================================================================
# 싱글톤 테스트
# =============================================================================

class TestCacheSingleton:
    """싱글톤 패턴 테스트"""

    def test_get_cache_service_singleton(self):
        """싱글톤 인스턴스 반환"""
        service1 = get_cache_service()
        service2 = get_cache_service()
        assert service1 is service2


# =============================================================================
# 에러 핸들링 테스트
# =============================================================================

class TestCacheErrorHandling:
    """에러 처리 테스트"""

    @pytest.mark.asyncio
    async def test_get_without_connection(self):
        """연결 없이 get 호출"""
        service = CacheService()
        result = await service.get("any_key", default="default_value")
        assert result == "default_value"

    @pytest.mark.asyncio
    async def test_set_without_connection(self):
        """연결 없이 set 호출"""
        service = CacheService()
        result = await service.set("any_key", "value")
        assert result is False
