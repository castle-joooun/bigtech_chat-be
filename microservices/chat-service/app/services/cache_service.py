"""
=============================================================================
Chat Service Cache (채팅 서비스 캐시)
=============================================================================

📌 이 파일이 하는 일:
    채팅 서비스에서 사용하는 캐시 로직을 관리합니다.
    shared_lib의 CacheService를 래핑하여 채팅 관련 캐시를 제공합니다.

💡 캐시를 사용하는 이유:
    채팅방 목록, 메시지 등은 자주 조회되지만 자주 변경되지 않습니다.
    DB 조회 대신 Redis 캐시를 사용하면 응답 속도가 크게 향상됩니다.

🔄 캐시 전략:
    ┌─────────────────────────────────────────────────────────────┐
    │  채팅방 목록 조회                                            │
    │  1. 캐시 확인 (chat:rooms:user:123)                         │
    │  2. HIT → 캐시에서 반환 (1ms)                               │
    │  3. MISS → MySQL 조회 (50ms) → 캐시 저장 → 반환              │
    └─────────────────────────────────────────────────────────────┘

📊 캐시 키 설계:
    | 키 패턴                     | 설명                   | TTL   |
    |---------------------------|------------------------|-------|
    | chat:rooms:user:{id}      | 사용자의 채팅방 목록     | 60s   |
    | chat:room:{id}            | 채팅방 상세 정보         | 300s  |
    | chat:messages:{room}:p{n} | 채팅방 메시지 (페이지별)  | 30s   |
    | chat:unread:{room}:{user} | 안 읽은 메시지 수        | 60s   |

⚠️ 캐시 무효화 시점:
    - 새 메시지 전송 시 → 해당 room의 messages 캐시 삭제
    - 채팅방 생성/수정 시 → 참여자들의 rooms 캐시 삭제
    - 메시지 읽음 처리 시 → unread 캐시 삭제

관련 파일
---------
- shared_lib/cache/service.py: CacheService 구현
- shared_lib/cache/decorators.py: @cached 데코레이터
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
    """
    📌 캐시 키 패턴 정의

    일관된 키 네이밍을 위해 상수로 정의합니다.
    """
    # 채팅방 관련
    USER_ROOMS = "rooms:user:{user_id}"           # 사용자의 채팅방 목록
    ROOM_DETAIL = "room:{room_id}"                # 채팅방 상세
    ROOM_MEMBERS = "room:{room_id}:members"       # 채팅방 멤버

    # 메시지 관련
    ROOM_MESSAGES = "messages:{room_id}:p{page}"  # 채팅방 메시지 (페이지별)
    MESSAGE_COUNT = "messages:{room_id}:count"    # 채팅방 메시지 수

    # 읽음 상태
    UNREAD_COUNT = "unread:{room_id}:{user_id}"   # 안 읽은 메시지 수


class CacheTTL:
    """
    📌 캐시 TTL (Time To Live) 정의

    데이터 특성에 따라 적절한 TTL을 설정합니다.
    """
    SHORT = 30       # 30초 - 자주 변경되는 데이터 (메시지 목록)
    MEDIUM = 60      # 1분 - 보통 데이터 (채팅방 목록, 안 읽은 수)
    LONG = 300       # 5분 - 거의 안 변하는 데이터 (채팅방 상세)
    VERY_LONG = 3600 # 1시간 - 정적 데이터


# =============================================================================
# 채팅 캐시 서비스
# =============================================================================

class ChatCacheService:
    """
    📌 채팅 서비스 전용 캐시

    shared_lib의 CacheService를 래핑하여
    채팅 관련 캐시 기능을 제공합니다.

    사용 예시:
        chat_cache = get_chat_cache()

        # 채팅방 목록 캐시
        rooms = await chat_cache.get_user_rooms(user_id)
        if rooms is None:
            rooms = await fetch_rooms_from_db(user_id)
            await chat_cache.set_user_rooms(user_id, rooms)
    """

    def __init__(self, cache: CacheService):
        self._cache = cache

    # =========================================================================
    # 채팅방 캐시
    # =========================================================================

    async def get_user_rooms(self, user_id: int) -> Optional[List[dict]]:
        """
        사용자의 채팅방 목록 캐시 조회

        Args:
            user_id: 사용자 ID

        Returns:
            캐시된 채팅방 목록 또는 None
        """
        key = CacheKeys.USER_ROOMS.format(user_id=user_id)
        return await self._cache.get(key)

    async def set_user_rooms(self, user_id: int, rooms: List[dict]) -> bool:
        """
        사용자의 채팅방 목록 캐시 저장

        Args:
            user_id: 사용자 ID
            rooms: 채팅방 목록

        Returns:
            저장 성공 여부
        """
        key = CacheKeys.USER_ROOMS.format(user_id=user_id)
        return await self._cache.set(key, rooms, ttl=CacheTTL.MEDIUM)

    async def invalidate_user_rooms(self, user_id: int) -> bool:
        """사용자의 채팅방 목록 캐시 삭제"""
        key = CacheKeys.USER_ROOMS.format(user_id=user_id)
        return await self._cache.delete(key)

    async def get_room_detail(self, room_id: int) -> Optional[dict]:
        """채팅방 상세 정보 캐시 조회"""
        key = CacheKeys.ROOM_DETAIL.format(room_id=room_id)
        return await self._cache.get(key)

    async def set_room_detail(self, room_id: int, room: dict) -> bool:
        """채팅방 상세 정보 캐시 저장"""
        key = CacheKeys.ROOM_DETAIL.format(room_id=room_id)
        return await self._cache.set(key, room, ttl=CacheTTL.LONG)

    async def invalidate_room(self, room_id: int) -> int:
        """채팅방 관련 모든 캐시 삭제"""
        pattern = f"room:{room_id}*"
        return await self._cache.delete_pattern(pattern)

    # =========================================================================
    # 메시지 캐시
    # =========================================================================

    async def get_room_messages(
        self,
        room_id: int,
        page: int = 1
    ) -> Optional[List[dict]]:
        """
        채팅방 메시지 캐시 조회 (페이지별)

        Args:
            room_id: 채팅방 ID
            page: 페이지 번호

        Returns:
            캐시된 메시지 목록 또는 None
        """
        key = CacheKeys.ROOM_MESSAGES.format(room_id=room_id, page=page)
        return await self._cache.get(key)

    async def set_room_messages(
        self,
        room_id: int,
        page: int,
        messages: List[dict]
    ) -> bool:
        """
        채팅방 메시지 캐시 저장 (페이지별)

        Args:
            room_id: 채팅방 ID
            page: 페이지 번호
            messages: 메시지 목록

        Returns:
            저장 성공 여부

        TTL:
            메시지는 자주 변경되므로 짧은 TTL (30초) 사용
        """
        key = CacheKeys.ROOM_MESSAGES.format(room_id=room_id, page=page)
        return await self._cache.set(key, messages, ttl=CacheTTL.SHORT)

    async def invalidate_room_messages(self, room_id: int) -> int:
        """
        채팅방의 모든 메시지 캐시 삭제

        새 메시지 전송 시 호출하여 캐시를 갱신합니다.

        Args:
            room_id: 채팅방 ID

        Returns:
            삭제된 캐시 키 수
        """
        pattern = f"messages:{room_id}:*"
        return await self._cache.delete_pattern(pattern)

    # =========================================================================
    # 읽음 상태 캐시
    # =========================================================================

    async def get_unread_count(self, room_id: int, user_id: int) -> Optional[int]:
        """안 읽은 메시지 수 캐시 조회"""
        key = CacheKeys.UNREAD_COUNT.format(room_id=room_id, user_id=user_id)
        return await self._cache.get(key)

    async def set_unread_count(
        self,
        room_id: int,
        user_id: int,
        count: int
    ) -> bool:
        """안 읽은 메시지 수 캐시 저장"""
        key = CacheKeys.UNREAD_COUNT.format(room_id=room_id, user_id=user_id)
        return await self._cache.set(key, count, ttl=CacheTTL.MEDIUM)

    async def invalidate_unread_count(self, room_id: int, user_id: int) -> bool:
        """안 읽은 메시지 수 캐시 삭제"""
        key = CacheKeys.UNREAD_COUNT.format(room_id=room_id, user_id=user_id)
        return await self._cache.delete(key)

    async def increment_unread_count(self, room_id: int, user_id: int) -> Optional[int]:
        """
        안 읽은 메시지 수 증가 (새 메시지 도착 시)

        Atomic 연산으로 동시성 안전합니다.
        """
        key = CacheKeys.UNREAD_COUNT.format(room_id=room_id, user_id=user_id)
        return await self._cache.increment(key)

    # =========================================================================
    # 최근 메시지 (리스트 캐시)
    # =========================================================================

    async def push_recent_message(self, room_id: int, message: dict) -> int:
        """
        최근 메시지 추가 (실시간 업데이트용)

        새 메시지를 리스트 앞에 추가하고,
        최대 100개만 유지합니다.

        Args:
            room_id: 채팅방 ID
            message: 메시지 데이터

        Returns:
            현재 리스트 길이
        """
        key = f"recent:{room_id}"
        return await self._cache.list_push(
            key,
            message,
            max_length=100,
            ttl=CacheTTL.MEDIUM
        )

    async def get_recent_messages(
        self,
        room_id: int,
        count: int = 20
    ) -> List[dict]:
        """
        최근 메시지 조회

        Args:
            room_id: 채팅방 ID
            count: 조회할 메시지 수

        Returns:
            최근 메시지 목록
        """
        key = f"recent:{room_id}"
        return await self._cache.list_range(key, 0, count - 1)

    # =========================================================================
    # 헬스 체크
    # =========================================================================

    async def health_check(self) -> bool:
        """캐시 연결 상태 확인"""
        return await self._cache.health_check()


# =============================================================================
# 싱글톤 인스턴스
# =============================================================================

_chat_cache: Optional[ChatCacheService] = None


async def init_chat_cache():
    """
    📌 채팅 캐시 초기화

    애플리케이션 시작 시 (lifespan startup) 호출합니다.
    """
    global _chat_cache

    cache = get_cache_service()
    await cache.init(settings.redis_url, prefix="chat")
    _chat_cache = ChatCacheService(cache)

    logger.info("Chat cache service initialized")


async def close_chat_cache():
    """
    📌 채팅 캐시 종료

    애플리케이션 종료 시 (lifespan shutdown) 호출합니다.
    """
    global _chat_cache

    cache = get_cache_service()
    await cache.close()
    _chat_cache = None

    logger.info("Chat cache service closed")


def get_chat_cache() -> Optional[ChatCacheService]:
    """
    📌 채팅 캐시 서비스 싱글톤 반환

    Returns:
        ChatCacheService 또는 None (초기화 안 됨)

    사용 예시:
        chat_cache = get_chat_cache()
        if chat_cache:
            rooms = await chat_cache.get_user_rooms(user_id)
    """
    return _chat_cache
