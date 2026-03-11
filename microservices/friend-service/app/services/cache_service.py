"""
=============================================================================
Friend Service Cache (친구 서비스 캐시)
=============================================================================

📌 이 파일이 하는 일:
    친구 서비스에서 사용하는 캐시 로직을 관리합니다.
    shared_lib의 CacheService를 래핑하여 친구 관련 캐시를 제공합니다.

💡 캐시를 사용하는 이유:
    친구 목록은 자주 조회되지만 자주 변경되지 않습니다.
    DB 조회 대신 Redis 캐시를 사용하면 응답 속도가 크게 향상됩니다.

📊 캐시 키 설계:
    | 키 패턴                      | 설명                 | TTL   |
    |----------------------------|---------------------|-------|
    | friend:list:{user_id}      | 친구 목록            | 300s  |
    | friend:requests:{user_id}  | 친구 요청 목록        | 60s   |
    | friend:status:{u1}:{u2}    | 친구 관계 상태        | 600s  |
    | friend:count:{user_id}     | 친구 수              | 300s  |

⚠️ 캐시 무효화 시점:
    - 친구 요청 전송 시 → 양쪽 requests 캐시 삭제
    - 친구 수락 시 → 양쪽 list, requests, status 캐시 삭제
    - 친구 삭제 시 → 양쪽 list, status, count 캐시 삭제

관련 파일
---------
- shared_lib/cache/service.py: CacheService 구현
- app/services/friendship_service.py: 친구 관계 서비스
"""

import logging
from typing import List, Optional, Tuple

from shared_lib.cache import get_cache_service, CacheService

from app.core.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# 캐시 키 상수
# =============================================================================

class CacheKeys:
    """캐시 키 패턴 정의"""
    FRIEND_LIST = "list:{user_id}"                     # 친구 목록
    FRIEND_REQUESTS_RECEIVED = "requests:recv:{user_id}"  # 받은 요청
    FRIEND_REQUESTS_SENT = "requests:sent:{user_id}"      # 보낸 요청
    FRIEND_STATUS = "status:{user_id_1}:{user_id_2}"   # 친구 관계 상태
    FRIEND_COUNT = "count:{user_id}"                   # 친구 수
    ARE_FRIENDS = "are:{user_id_1}:{user_id_2}"        # 친구 여부


class CacheTTL:
    """캐시 TTL 정의"""
    SHORT = 60       # 1분 - 요청 목록 (자주 변경)
    MEDIUM = 300     # 5분 - 친구 목록, 친구 수
    LONG = 600       # 10분 - 친구 상태


# =============================================================================
# 친구 캐시 서비스
# =============================================================================

class FriendCacheService:
    """
    📌 친구 서비스 전용 캐시

    사용 예시:
        friend_cache = get_friend_cache()

        # 친구 목록 캐시
        friends = await friend_cache.get_friends_list(user_id)
        if friends is None:
            friends = await fetch_from_db(user_id)
            await friend_cache.set_friends_list(user_id, friends)
    """

    def __init__(self, cache: CacheService):
        self._cache = cache

    # =========================================================================
    # 친구 목록 캐시
    # =========================================================================

    async def get_friends_list(self, user_id: int) -> Optional[List[dict]]:
        """
        친구 목록 캐시 조회

        Args:
            user_id: 사용자 ID

        Returns:
            캐시된 친구 목록 또는 None
        """
        key = CacheKeys.FRIEND_LIST.format(user_id=user_id)
        return await self._cache.get(key)

    async def set_friends_list(self, user_id: int, friends: List[dict]) -> bool:
        """
        친구 목록 캐시 저장

        Args:
            user_id: 사용자 ID
            friends: 친구 목록 데이터

        Returns:
            저장 성공 여부
        """
        key = CacheKeys.FRIEND_LIST.format(user_id=user_id)
        return await self._cache.set(key, friends, ttl=CacheTTL.MEDIUM)

    async def invalidate_friends_list(self, user_id: int) -> bool:
        """친구 목록 캐시 삭제"""
        key = CacheKeys.FRIEND_LIST.format(user_id=user_id)
        return await self._cache.delete(key)

    # =========================================================================
    # 친구 요청 캐시
    # =========================================================================

    async def get_received_requests(self, user_id: int) -> Optional[List[dict]]:
        """받은 친구 요청 캐시 조회"""
        key = CacheKeys.FRIEND_REQUESTS_RECEIVED.format(user_id=user_id)
        return await self._cache.get(key)

    async def set_received_requests(self, user_id: int, requests: List[dict]) -> bool:
        """받은 친구 요청 캐시 저장"""
        key = CacheKeys.FRIEND_REQUESTS_RECEIVED.format(user_id=user_id)
        return await self._cache.set(key, requests, ttl=CacheTTL.SHORT)

    async def get_sent_requests(self, user_id: int) -> Optional[List[dict]]:
        """보낸 친구 요청 캐시 조회"""
        key = CacheKeys.FRIEND_REQUESTS_SENT.format(user_id=user_id)
        return await self._cache.get(key)

    async def set_sent_requests(self, user_id: int, requests: List[dict]) -> bool:
        """보낸 친구 요청 캐시 저장"""
        key = CacheKeys.FRIEND_REQUESTS_SENT.format(user_id=user_id)
        return await self._cache.set(key, requests, ttl=CacheTTL.SHORT)

    async def invalidate_requests(self, user_id: int) -> int:
        """친구 요청 캐시 삭제 (받은 요청 + 보낸 요청)"""
        deleted = 0
        if await self._cache.delete(CacheKeys.FRIEND_REQUESTS_RECEIVED.format(user_id=user_id)):
            deleted += 1
        if await self._cache.delete(CacheKeys.FRIEND_REQUESTS_SENT.format(user_id=user_id)):
            deleted += 1
        return deleted

    # =========================================================================
    # 친구 관계 상태 캐시
    # =========================================================================

    def _make_status_key(self, user_id_1: int, user_id_2: int) -> str:
        """양방향 일관된 키 생성 (작은 ID가 먼저)"""
        if user_id_1 > user_id_2:
            user_id_1, user_id_2 = user_id_2, user_id_1
        return CacheKeys.FRIEND_STATUS.format(user_id_1=user_id_1, user_id_2=user_id_2)

    async def get_friendship_status(
        self,
        user_id_1: int,
        user_id_2: int
    ) -> Optional[str]:
        """
        친구 관계 상태 캐시 조회

        Args:
            user_id_1: 첫 번째 사용자 ID
            user_id_2: 두 번째 사용자 ID

        Returns:
            상태 문자열 ("pending", "accepted", None)
        """
        key = self._make_status_key(user_id_1, user_id_2)
        return await self._cache.get(key)

    async def set_friendship_status(
        self,
        user_id_1: int,
        user_id_2: int,
        status: str
    ) -> bool:
        """
        친구 관계 상태 캐시 저장

        Args:
            user_id_1: 첫 번째 사용자 ID
            user_id_2: 두 번째 사용자 ID
            status: 관계 상태 ("pending", "accepted")

        Returns:
            저장 성공 여부
        """
        key = self._make_status_key(user_id_1, user_id_2)
        return await self._cache.set(key, status, ttl=CacheTTL.LONG)

    async def invalidate_friendship_status(
        self,
        user_id_1: int,
        user_id_2: int
    ) -> bool:
        """친구 관계 상태 캐시 삭제"""
        key = self._make_status_key(user_id_1, user_id_2)
        return await self._cache.delete(key)

    # =========================================================================
    # 친구 여부 캐시 (Boolean)
    # =========================================================================

    def _make_are_friends_key(self, user_id_1: int, user_id_2: int) -> str:
        """양방향 일관된 키 생성"""
        if user_id_1 > user_id_2:
            user_id_1, user_id_2 = user_id_2, user_id_1
        return CacheKeys.ARE_FRIENDS.format(user_id_1=user_id_1, user_id_2=user_id_2)

    async def get_are_friends(self, user_id_1: int, user_id_2: int) -> Optional[bool]:
        """친구 여부 캐시 조회"""
        key = self._make_are_friends_key(user_id_1, user_id_2)
        return await self._cache.get(key)

    async def set_are_friends(self, user_id_1: int, user_id_2: int, are_friends: bool) -> bool:
        """친구 여부 캐시 저장"""
        key = self._make_are_friends_key(user_id_1, user_id_2)
        return await self._cache.set(key, are_friends, ttl=CacheTTL.LONG)

    async def invalidate_are_friends(self, user_id_1: int, user_id_2: int) -> bool:
        """친구 여부 캐시 삭제"""
        key = self._make_are_friends_key(user_id_1, user_id_2)
        return await self._cache.delete(key)

    # =========================================================================
    # 친구 수 캐시
    # =========================================================================

    async def get_friends_count(self, user_id: int) -> Optional[int]:
        """친구 수 캐시 조회"""
        key = CacheKeys.FRIEND_COUNT.format(user_id=user_id)
        return await self._cache.get(key)

    async def set_friends_count(self, user_id: int, count: int) -> bool:
        """친구 수 캐시 저장"""
        key = CacheKeys.FRIEND_COUNT.format(user_id=user_id)
        return await self._cache.set(key, count, ttl=CacheTTL.MEDIUM)

    async def invalidate_friends_count(self, user_id: int) -> bool:
        """친구 수 캐시 삭제"""
        key = CacheKeys.FRIEND_COUNT.format(user_id=user_id)
        return await self._cache.delete(key)

    # =========================================================================
    # 전체 캐시 무효화
    # =========================================================================

    async def invalidate_friendship(self, user_id_1: int, user_id_2: int) -> int:
        """
        친구 관계 변경 시 양쪽 사용자의 모든 관련 캐시 삭제

        친구 수락/삭제/차단 시 호출합니다.

        Args:
            user_id_1: 첫 번째 사용자 ID
            user_id_2: 두 번째 사용자 ID

        Returns:
            삭제된 캐시 키 수
        """
        deleted = 0

        # 양쪽 친구 목록 삭제
        if await self.invalidate_friends_list(user_id_1):
            deleted += 1
        if await self.invalidate_friends_list(user_id_2):
            deleted += 1

        # 양쪽 요청 목록 삭제
        deleted += await self.invalidate_requests(user_id_1)
        deleted += await self.invalidate_requests(user_id_2)

        # 관계 상태 삭제
        if await self.invalidate_friendship_status(user_id_1, user_id_2):
            deleted += 1

        # 친구 여부 삭제
        if await self.invalidate_are_friends(user_id_1, user_id_2):
            deleted += 1

        # 양쪽 친구 수 삭제
        if await self.invalidate_friends_count(user_id_1):
            deleted += 1
        if await self.invalidate_friends_count(user_id_2):
            deleted += 1

        logger.info(f"Invalidated {deleted} cache entries for friendship {user_id_1}<->{user_id_2}")
        return deleted

    # =========================================================================
    # 헬스 체크
    # =========================================================================

    async def health_check(self) -> bool:
        """캐시 연결 상태 확인"""
        return await self._cache.health_check()


# =============================================================================
# 싱글톤 인스턴스
# =============================================================================

_friend_cache: Optional[FriendCacheService] = None


async def init_friend_cache():
    """
    📌 친구 캐시 초기화

    애플리케이션 시작 시 (lifespan startup) 호출합니다.
    """
    global _friend_cache

    cache = get_cache_service()
    await cache.init(settings.redis_url, prefix="friend")
    _friend_cache = FriendCacheService(cache)

    logger.info("Friend cache service initialized")


async def close_friend_cache():
    """
    📌 친구 캐시 종료

    애플리케이션 종료 시 (lifespan shutdown) 호출합니다.
    """
    global _friend_cache

    cache = get_cache_service()
    await cache.close()
    _friend_cache = None

    logger.info("Friend cache service closed")


def get_friend_cache() -> Optional[FriendCacheService]:
    """
    📌 친구 캐시 서비스 싱글톤 반환

    Returns:
        FriendCacheService 또는 None

    사용 예시:
        friend_cache = get_friend_cache()
        if friend_cache:
            friends = await friend_cache.get_friends_list(user_id)
    """
    return _friend_cache
