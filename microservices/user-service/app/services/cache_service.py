"""
=============================================================================
User Service Cache (사용자 서비스 캐시)
=============================================================================

📌 이 파일이 하는 일:
    사용자 서비스에서 사용하는 캐시 로직을 관리합니다.
    shared_lib의 CacheService를 래핑하여 사용자 관련 캐시를 제공합니다.

💡 캐시를 사용하는 이유:
    사용자 프로필, 검색 결과 등은 자주 조회되지만 자주 변경되지 않습니다.
    DB 조회 대신 Redis 캐시를 사용하면 응답 속도가 크게 향상됩니다.

📊 캐시 키 설계:
    | 키 패턴                    | 설명                  | TTL   |
    |--------------------------|----------------------|-------|
    | user:profile:{id}        | 사용자 프로필          | 300s  |
    | user:search:{query}      | 사용자 검색 결과        | 60s   |
    | user:exists:{id}         | 사용자 존재 여부        | 600s  |

⚠️ 캐시 무효화 시점:
    - 프로필 수정 시 → profile 캐시 삭제
    - 회원가입 시 → 관련 search 캐시 삭제
    - 회원 탈퇴 시 → 모든 관련 캐시 삭제

관련 파일
---------
- shared_lib/cache/service.py: CacheService 구현
- app/services/auth_service.py: 사용자 CRUD 서비스
"""

import logging
from typing import List, Optional, Any

from shared_lib.cache import get_cache_service, CacheService

from app.core.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# 캐시 키 상수
# =============================================================================

class CacheKeys:
    """캐시 키 패턴 정의"""
    USER_PROFILE = "profile:{user_id}"          # 사용자 프로필
    USER_BY_EMAIL = "email:{email}"             # 이메일로 조회
    USER_BY_USERNAME = "username:{username}"    # 사용자명으로 조회
    USER_EXISTS = "exists:{user_id}"            # 존재 여부
    USER_SEARCH = "search:{query}:{limit}"      # 검색 결과


class CacheTTL:
    """캐시 TTL 정의"""
    SHORT = 60       # 1분 - 검색 결과
    MEDIUM = 300     # 5분 - 프로필
    LONG = 600       # 10분 - 존재 여부


# =============================================================================
# 사용자 캐시 서비스
# =============================================================================

class UserCacheService:
    """
    📌 사용자 서비스 전용 캐시

    사용 예시:
        user_cache = get_user_cache()

        # 프로필 캐시
        profile = await user_cache.get_user_profile(user_id)
        if profile is None:
            profile = await fetch_from_db(user_id)
            await user_cache.set_user_profile(user_id, profile)
    """

    def __init__(self, cache: CacheService):
        self._cache = cache

    # =========================================================================
    # 사용자 프로필 캐시
    # =========================================================================

    async def get_user_profile(self, user_id: int) -> Optional[dict]:
        """
        사용자 프로필 캐시 조회

        Args:
            user_id: 사용자 ID

        Returns:
            캐시된 프로필 또는 None
        """
        key = CacheKeys.USER_PROFILE.format(user_id=user_id)
        return await self._cache.get(key)

    async def set_user_profile(self, user_id: int, profile: dict) -> bool:
        """
        사용자 프로필 캐시 저장

        Args:
            user_id: 사용자 ID
            profile: 프로필 데이터

        Returns:
            저장 성공 여부
        """
        key = CacheKeys.USER_PROFILE.format(user_id=user_id)
        return await self._cache.set(key, profile, ttl=CacheTTL.MEDIUM)

    async def invalidate_user_profile(self, user_id: int) -> bool:
        """사용자 프로필 캐시 삭제"""
        key = CacheKeys.USER_PROFILE.format(user_id=user_id)
        return await self._cache.delete(key)

    # =========================================================================
    # 사용자 조회 캐시 (이메일, 사용자명)
    # =========================================================================

    async def get_user_by_email(self, email: str) -> Optional[dict]:
        """이메일로 사용자 캐시 조회"""
        key = CacheKeys.USER_BY_EMAIL.format(email=email)
        return await self._cache.get(key)

    async def set_user_by_email(self, email: str, user: dict) -> bool:
        """이메일로 사용자 캐시 저장"""
        key = CacheKeys.USER_BY_EMAIL.format(email=email)
        return await self._cache.set(key, user, ttl=CacheTTL.MEDIUM)

    async def get_user_by_username(self, username: str) -> Optional[dict]:
        """사용자명으로 사용자 캐시 조회"""
        key = CacheKeys.USER_BY_USERNAME.format(username=username)
        return await self._cache.get(key)

    async def set_user_by_username(self, username: str, user: dict) -> bool:
        """사용자명으로 사용자 캐시 저장"""
        key = CacheKeys.USER_BY_USERNAME.format(username=username)
        return await self._cache.set(key, user, ttl=CacheTTL.MEDIUM)

    # =========================================================================
    # 사용자 존재 여부 캐시
    # =========================================================================

    async def get_user_exists(self, user_id: int) -> Optional[bool]:
        """사용자 존재 여부 캐시 조회"""
        key = CacheKeys.USER_EXISTS.format(user_id=user_id)
        return await self._cache.get(key)

    async def set_user_exists(self, user_id: int, exists: bool) -> bool:
        """사용자 존재 여부 캐시 저장"""
        key = CacheKeys.USER_EXISTS.format(user_id=user_id)
        return await self._cache.set(key, exists, ttl=CacheTTL.LONG)

    # =========================================================================
    # 사용자 검색 캐시
    # =========================================================================

    async def get_search_results(
        self,
        query: str,
        limit: int = 10
    ) -> Optional[List[dict]]:
        """
        사용자 검색 결과 캐시 조회

        Args:
            query: 검색어
            limit: 결과 수

        Returns:
            캐시된 검색 결과 또는 None
        """
        key = CacheKeys.USER_SEARCH.format(query=query, limit=limit)
        return await self._cache.get(key)

    async def set_search_results(
        self,
        query: str,
        limit: int,
        results: List[dict]
    ) -> bool:
        """
        사용자 검색 결과 캐시 저장

        Args:
            query: 검색어
            limit: 결과 수
            results: 검색 결과 목록

        Returns:
            저장 성공 여부
        """
        key = CacheKeys.USER_SEARCH.format(query=query, limit=limit)
        return await self._cache.set(key, results, ttl=CacheTTL.SHORT)

    async def invalidate_search_cache(self) -> int:
        """모든 검색 캐시 삭제 (회원가입/탈퇴 시)"""
        return await self._cache.delete_pattern("search:*")

    # =========================================================================
    # 전체 캐시 무효화
    # =========================================================================

    async def invalidate_user(self, user_id: int, email: str = None, username: str = None) -> int:
        """
        사용자 관련 모든 캐시 삭제

        프로필 수정, 회원 탈퇴 시 호출합니다.

        Args:
            user_id: 사용자 ID
            email: 사용자 이메일 (선택)
            username: 사용자명 (선택)

        Returns:
            삭제된 캐시 키 수
        """
        deleted = 0

        # 프로필 캐시 삭제
        if await self.invalidate_user_profile(user_id):
            deleted += 1

        # 존재 여부 캐시 삭제
        key = CacheKeys.USER_EXISTS.format(user_id=user_id)
        if await self._cache.delete(key):
            deleted += 1

        # 이메일 캐시 삭제
        if email:
            key = CacheKeys.USER_BY_EMAIL.format(email=email)
            if await self._cache.delete(key):
                deleted += 1

        # 사용자명 캐시 삭제
        if username:
            key = CacheKeys.USER_BY_USERNAME.format(username=username)
            if await self._cache.delete(key):
                deleted += 1

        logger.info(f"Invalidated {deleted} cache entries for user {user_id}")
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

_user_cache: Optional[UserCacheService] = None


async def init_user_cache():
    """
    📌 사용자 캐시 초기화

    애플리케이션 시작 시 (lifespan startup) 호출합니다.
    """
    global _user_cache

    cache = get_cache_service()
    await cache.init(settings.redis_url, prefix="user")
    _user_cache = UserCacheService(cache)

    logger.info("User cache service initialized")


async def close_user_cache():
    """
    📌 사용자 캐시 종료

    애플리케이션 종료 시 (lifespan shutdown) 호출합니다.
    """
    global _user_cache

    cache = get_cache_service()
    await cache.close()
    _user_cache = None

    logger.info("User cache service closed")


def get_user_cache() -> Optional[UserCacheService]:
    """
    📌 사용자 캐시 서비스 싱글톤 반환

    Returns:
        UserCacheService 또는 None

    사용 예시:
        user_cache = get_user_cache()
        if user_cache:
            profile = await user_cache.get_user_profile(user_id)
    """
    return _user_cache
