"""
User Service Client (user-service API 클라이언트)
================================================

다른 마이크로서비스에서 user-service API를 호출하기 위한 HTTP 클라이언트입니다.

사용 예시:
    ```python
    from shared_lib import UserClient

    # 클라이언트 인스턴스 (싱글톤 패턴 권장)
    user_client = UserClient()

    # 단일 사용자 조회
    user = await user_client.get_user_by_id(123)
    if user:
        print(f"User: {user.username}")

    # 다중 사용자 조회
    users = await user_client.get_users_by_ids([1, 2, 3])
    for user in users:
        print(f"User: {user.username}")

    # 존재 여부 확인
    exists = await user_client.user_exists(123)
    ```

MSA 원칙:
    - friend-service, chat-service는 User DB에 직접 접근하지 않음
    - user-service API를 통해서만 사용자 정보 접근
    - 캐싱으로 API 호출 오버헤드 최소화
"""

import httpx
import logging
from typing import Optional, List, Dict, Any
from functools import lru_cache
from datetime import datetime, timedelta

from .config import ServiceConfig
from shared_lib.schemas.user import UserProfile


logger = logging.getLogger(__name__)


class UserClientError(Exception):
    """UserClient 관련 예외"""
    pass


class UserNotFoundError(UserClientError):
    """사용자를 찾을 수 없음"""
    pass


class UserServiceUnavailableError(UserClientError):
    """user-service 연결 불가"""
    pass


class SimpleCache:
    """간단한 TTL 캐시 (프로덕션에서는 Redis 사용 권장)"""

    def __init__(self):
        self._cache: Dict[str, tuple[Any, datetime]] = {}

    def get(self, key: str) -> Optional[Any]:
        """캐시 조회"""
        if key in self._cache:
            value, expires_at = self._cache[key]
            if datetime.utcnow() < expires_at:
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl_seconds: int):
        """캐시 저장"""
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        self._cache[key] = (value, expires_at)

    def delete(self, key: str):
        """캐시 삭제"""
        if key in self._cache:
            del self._cache[key]

    def clear(self):
        """전체 캐시 삭제"""
        self._cache.clear()


class UserClient:
    """
    User Service API 클라이언트

    Attributes:
        base_url: user-service 기본 URL
        timeout: HTTP 요청 타임아웃
        _cache: 인메모리 캐시 (선택적)

    Note:
        프로덕션 환경에서는 Redis 캐시 사용을 권장합니다.
        Circuit Breaker 패턴도 고려하세요.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        enable_cache: bool = True
    ):
        """
        Args:
            base_url: user-service URL (기본값: 환경변수)
            timeout: HTTP 타임아웃 (초)
            enable_cache: 캐시 사용 여부
        """
        self.base_url = base_url or ServiceConfig.USER_SERVICE_URL
        self.timeout = timeout or ServiceConfig.HTTP_TIMEOUT
        self._cache = SimpleCache() if enable_cache else None

    # =========================================================================
    # Single User Operations
    # =========================================================================

    async def get_user_by_id(self, user_id: int) -> Optional[UserProfile]:
        """
        사용자 ID로 단일 사용자 조회

        Args:
            user_id: 조회할 사용자 ID

        Returns:
            UserProfile 또는 None (사용자 없음)

        Raises:
            UserServiceUnavailableError: user-service 연결 실패
        """
        # 캐시 확인
        if self._cache:
            cache_key = f"user:profile:{user_id}"
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for user {user_id}")
                return cached

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/users/{user_id}"
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                data = response.json()
                user = UserProfile.model_validate(data)

                # 캐시 저장
                if self._cache:
                    self._cache.set(
                        cache_key,
                        user,
                        ServiceConfig.CACHE_TTL_USER_PROFILE
                    )

                return user

        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to user-service: {e}")
            raise UserServiceUnavailableError(f"Cannot connect to user-service: {e}")

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from user-service: {e}")
            raise UserClientError(f"HTTP error: {e}")

        except Exception as e:
            logger.error(f"Unexpected error in get_user_by_id: {e}")
            raise UserClientError(f"Unexpected error: {e}")

    # =========================================================================
    # Batch User Operations
    # =========================================================================

    async def get_users_by_ids(self, user_ids: List[int]) -> List[UserProfile]:
        """
        여러 사용자 ID로 Batch 조회

        Args:
            user_ids: 조회할 사용자 ID 목록

        Returns:
            List[UserProfile]: 조회된 사용자 목록 (존재하지 않는 ID는 제외)

        Raises:
            UserServiceUnavailableError: user-service 연결 실패
        """
        if not user_ids:
            return []

        # 캐시에서 찾을 수 있는 사용자와 못 찾는 사용자 분리
        cached_users: List[UserProfile] = []
        missing_ids: List[int] = []

        if self._cache:
            for uid in user_ids:
                cache_key = f"user:profile:{uid}"
                cached = self._cache.get(cache_key)
                if cached is not None:
                    cached_users.append(cached)
                else:
                    missing_ids.append(uid)
        else:
            missing_ids = list(user_ids)

        # 모두 캐시에서 찾은 경우
        if not missing_ids:
            logger.debug(f"All {len(user_ids)} users found in cache")
            return cached_users

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/users/batch",
                    json={"user_ids": missing_ids}
                )
                response.raise_for_status()

                data = response.json()
                fetched_users = [UserProfile.model_validate(u) for u in data]

                # 캐시 저장
                if self._cache:
                    for user in fetched_users:
                        cache_key = f"user:profile:{user.id}"
                        self._cache.set(
                            cache_key,
                            user,
                            ServiceConfig.CACHE_TTL_USER_PROFILE
                        )

                return cached_users + fetched_users

        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to user-service: {e}")
            raise UserServiceUnavailableError(f"Cannot connect to user-service: {e}")

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from user-service: {e}")
            raise UserClientError(f"HTTP error: {e}")

        except Exception as e:
            logger.error(f"Unexpected error in get_users_by_ids: {e}")
            raise UserClientError(f"Unexpected error: {e}")

    # =========================================================================
    # User Existence Check
    # =========================================================================

    async def user_exists(self, user_id: int) -> bool:
        """
        사용자 존재 여부 확인

        get_user_by_id보다 가볍게 존재 여부만 확인합니다.

        Args:
            user_id: 확인할 사용자 ID

        Returns:
            bool: 존재 여부

        Raises:
            UserServiceUnavailableError: user-service 연결 실패
        """
        # 캐시 확인
        if self._cache:
            cache_key = f"user:exists:{user_id}"
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/users/{user_id}/exists"
                )
                response.raise_for_status()

                data = response.json()
                exists = data.get("exists", False)

                # 캐시 저장
                if self._cache:
                    self._cache.set(
                        cache_key,
                        exists,
                        ServiceConfig.CACHE_TTL_USER_EXISTS
                    )

                return exists

        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to user-service: {e}")
            raise UserServiceUnavailableError(f"Cannot connect to user-service: {e}")

        except httpx.HTTPStatusError as e:
            # 404의 경우 존재하지 않음으로 처리
            if e.response.status_code == 404:
                return False
            logger.error(f"HTTP error from user-service: {e}")
            raise UserClientError(f"HTTP error: {e}")

        except Exception as e:
            logger.error(f"Unexpected error in user_exists: {e}")
            raise UserClientError(f"Unexpected error: {e}")

    # =========================================================================
    # Cache Management
    # =========================================================================

    def invalidate_user_cache(self, user_id: int):
        """특정 사용자 캐시 무효화"""
        if self._cache:
            self._cache.delete(f"user:profile:{user_id}")
            self._cache.delete(f"user:exists:{user_id}")

    def clear_cache(self):
        """전체 캐시 삭제"""
        if self._cache:
            self._cache.clear()


# =============================================================================
# Singleton Instance
# =============================================================================

_user_client_instance: Optional[UserClient] = None


def get_user_client() -> UserClient:
    """
    UserClient 싱글톤 인스턴스 반환

    Returns:
        UserClient: 싱글톤 인스턴스

    사용 예시:
        from shared_lib.user_client import get_user_client

        user_client = get_user_client()
        user = await user_client.get_user_by_id(123)
    """
    global _user_client_instance
    if _user_client_instance is None:
        _user_client_instance = UserClient()
    return _user_client_instance


def init_user_client(
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
    enable_cache: bool = True
) -> UserClient:
    """
    UserClient 싱글톤 초기화

    애플리케이션 시작 시 커스텀 설정으로 초기화할 때 사용합니다.

    Args:
        base_url: user-service URL
        timeout: HTTP 타임아웃
        enable_cache: 캐시 사용 여부

    Returns:
        UserClient: 초기화된 인스턴스
    """
    global _user_client_instance
    _user_client_instance = UserClient(
        base_url=base_url,
        timeout=timeout,
        enable_cache=enable_cache
    )
    return _user_client_instance
