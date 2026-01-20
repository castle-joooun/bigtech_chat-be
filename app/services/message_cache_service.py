"""
메시지 캐싱 서비스

Redis를 사용하여 채팅방별 최근 메시지를 캐싱하여 성능을 향상시킵니다.
"""

import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from app.database.redis import get_redis
from app.core.logging import get_logger, log_performance_metric
from app.services import message_service

logger = get_logger(__name__)

# Redis 키 패턴
ROOM_MESSAGES_CACHE_KEY = "room:messages:{room_id}:{room_type}"
CACHE_STATS_KEY = "cache:stats:messages"
CACHE_HIT_COUNTER = "cache:hit:messages"
CACHE_MISS_COUNTER = "cache:miss:messages"

# 캐시 설정
DEFAULT_CACHE_SIZE = 50  # 채팅방별 캐시할 메시지 수
CACHE_TTL = 86400  # 24시간
CACHE_STATS_TTL = 3600  # 1시간


class MessageCacheService:
    """메시지 캐싱 서비스"""

    @staticmethod
    async def get_cached_messages(
        room_id: int,
        room_type: str = "private",
        limit: int = 50,
        skip: int = 0
    ) -> Tuple[Optional[List[Dict]], bool]:
        """
        캐시에서 메시지 조회

        Args:
            room_id: 채팅방 ID
            room_type: 채팅방 타입
            limit: 조회할 메시지 수
            skip: 건너뛸 메시지 수

        Returns:
            (메시지 리스트, 캐시 히트 여부)
        """
        try:
            redis = await get_redis()
            cache_key = ROOM_MESSAGES_CACHE_KEY.format(room_id=room_id, room_type=room_type)

            start_time = time.time()

            # Redis List에서 메시지 조회 (최신순)
            cached_data = await redis.lrange(cache_key, skip, skip + limit - 1)

            if cached_data:
                # 캐시 히트
                messages = [json.loads(msg_str) for msg_str in cached_data]

                # 캐시 히트 통계 업데이트
                await MessageCacheService._update_cache_stats(True)

                # 성능 메트릭 로깅
                duration_ms = (time.time() - start_time) * 1000
                log_performance_metric(
                    logger,
                    "message_cache_hit",
                    duration_ms,
                    room_id=room_id,
                    room_type=room_type,
                    message_count=len(messages)
                )

                logger.debug(f"Cache hit for room {room_id}:{room_type}, {len(messages)} messages")
                return messages, True
            else:
                # 캐시 미스
                await MessageCacheService._update_cache_stats(False)

                logger.debug(f"Cache miss for room {room_id}:{room_type}")
                return None, False

        except Exception as e:
            logger.error(f"Failed to get cached messages for room {room_id}: {e}")
            return None, False

    @staticmethod
    async def cache_messages(
        room_id: int,
        room_type: str,
        messages: List[Dict],
        cache_size: int = DEFAULT_CACHE_SIZE
    ) -> bool:
        """
        메시지를 캐시에 저장

        Args:
            room_id: 채팅방 ID
            room_type: 채팅방 타입
            messages: 캐시할 메시지 리스트
            cache_size: 캐시 크기

        Returns:
            성공 여부
        """
        try:
            if not messages:
                return True

            redis = await get_redis()
            cache_key = ROOM_MESSAGES_CACHE_KEY.format(room_id=room_id, room_type=room_type)

            start_time = time.time()

            # 파이프라인을 사용한 원자적 연산
            pipe = redis.pipeline()

            # 기존 캐시 삭제
            pipe.delete(cache_key)

            # 메시지를 JSON 문자열로 변환하여 List에 추가 (최신순)
            for message in reversed(messages[-cache_size:]):  # 최신 메시지를 앞에
                message_str = json.dumps(message, default=str, ensure_ascii=False)
                pipe.lpush(cache_key, message_str)

            # 캐시 크기 제한
            pipe.ltrim(cache_key, 0, cache_size - 1)

            # TTL 설정
            pipe.expire(cache_key, CACHE_TTL)

            await pipe.execute()

            # 성능 메트릭 로깅
            duration_ms = (time.time() - start_time) * 1000
            log_performance_metric(
                logger,
                "message_cache_store",
                duration_ms,
                room_id=room_id,
                room_type=room_type,
                message_count=len(messages)
            )

            logger.debug(f"Cached {len(messages)} messages for room {room_id}:{room_type}")
            return True

        except Exception as e:
            logger.error(f"Failed to cache messages for room {room_id}: {e}")
            return False

    @staticmethod
    async def add_new_message_to_cache(
        room_id: int,
        room_type: str,
        message: Dict,
        cache_size: int = DEFAULT_CACHE_SIZE
    ) -> bool:
        """
        새 메시지를 캐시에 추가

        Args:
            room_id: 채팅방 ID
            room_type: 채팅방 타입
            message: 새 메시지
            cache_size: 캐시 크기

        Returns:
            성공 여부
        """
        try:
            redis = await get_redis()
            cache_key = ROOM_MESSAGES_CACHE_KEY.format(room_id=room_id, room_type=room_type)

            # 캐시 존재 확인
            cache_exists = await redis.exists(cache_key)
            if not cache_exists:
                # 캐시가 없으면 새 메시지만 추가하지 않고 전체 캐시 갱신 필요
                return False

            # 파이프라인을 사용한 원자적 연산
            pipe = redis.pipeline()

            # 새 메시지를 List 앞에 추가 (최신순 유지)
            message_str = json.dumps(message, default=str, ensure_ascii=False)
            pipe.lpush(cache_key, message_str)

            # 캐시 크기 제한
            pipe.ltrim(cache_key, 0, cache_size - 1)

            # TTL 갱신
            pipe.expire(cache_key, CACHE_TTL)

            await pipe.execute()

            logger.debug(f"Added new message to cache for room {room_id}:{room_type}")
            return True

        except Exception as e:
            logger.error(f"Failed to add new message to cache for room {room_id}: {e}")
            return False

    @staticmethod
    async def invalidate_room_cache(room_id: int, room_type: str) -> bool:
        """
        채팅방 캐시 무효화

        Args:
            room_id: 채팅방 ID
            room_type: 채팅방 타입

        Returns:
            성공 여부
        """
        try:
            redis = await get_redis()
            cache_key = ROOM_MESSAGES_CACHE_KEY.format(room_id=room_id, room_type=room_type)

            result = await redis.delete(cache_key)
            logger.debug(f"Invalidated cache for room {room_id}:{room_type}")
            return bool(result)

        except Exception as e:
            logger.error(f"Failed to invalidate cache for room {room_id}: {e}")
            return False

    @staticmethod
    async def get_or_set_messages(
        room_id: int,
        room_type: str = "private",
        limit: int = 50,
        skip: int = 0,
        include_deleted: bool = False
    ) -> List[Dict]:
        """
        캐시에서 메시지 조회, 없으면 DB에서 조회 후 캐시

        Args:
            room_id: 채팅방 ID
            room_type: 채팅방 타입
            limit: 조회할 메시지 수
            skip: 건너뛸 메시지 수
            include_deleted: 삭제된 메시지 포함 여부

        Returns:
            메시지 리스트
        """
        try:
            # 1. 캐시에서 먼저 조회
            cached_messages, cache_hit = await MessageCacheService.get_cached_messages(
                room_id, room_type, limit, skip
            )

            if cache_hit and cached_messages:
                return cached_messages

            # 2. 캐시 미스 - DB에서 조회
            start_time = time.time()

            db_messages = await message_service.get_room_messages(
                room_id=room_id,
                room_type=room_type,
                limit=max(limit, DEFAULT_CACHE_SIZE),  # 캐시용으로 더 많이 조회
                skip=0,  # 캐시용이므로 skip=0
                include_deleted=include_deleted
            )

            # 메시지를 딕셔너리로 변환
            messages_dict = []
            for msg in db_messages:
                msg_dict = msg.model_dump()
                msg_dict["id"] = str(msg.id)  # ObjectId를 문자열로 변환
                messages_dict.append(msg_dict)

            # 3. DB 조회 결과를 캐시에 저장
            if messages_dict:
                await MessageCacheService.cache_messages(
                    room_id, room_type, messages_dict, DEFAULT_CACHE_SIZE
                )

            # 4. 요청된 범위의 메시지 반환
            end_index = skip + limit
            result_messages = messages_dict[skip:end_index]

            # 성능 메트릭 로깅
            duration_ms = (time.time() - start_time) * 1000
            log_performance_metric(
                logger,
                "message_db_fallback",
                duration_ms,
                room_id=room_id,
                room_type=room_type,
                message_count=len(result_messages)
            )

            logger.debug(f"DB fallback for room {room_id}:{room_type}, {len(result_messages)} messages")
            return result_messages

        except Exception as e:
            logger.error(f"Failed to get or set messages for room {room_id}: {e}")
            return []

    @staticmethod
    async def _update_cache_stats(is_hit: bool) -> None:
        """
        캐시 통계 업데이트

        Args:
            is_hit: 캐시 히트 여부
        """
        try:
            redis = await get_redis()

            if is_hit:
                await redis.incr(CACHE_HIT_COUNTER)
            else:
                await redis.incr(CACHE_MISS_COUNTER)

            # 통계 키 TTL 설정
            await redis.expire(CACHE_HIT_COUNTER, CACHE_STATS_TTL)
            await redis.expire(CACHE_MISS_COUNTER, CACHE_STATS_TTL)

        except Exception as e:
            logger.error(f"Failed to update cache stats: {e}")

    @staticmethod
    async def get_cache_stats() -> Dict:
        """
        캐시 통계 조회

        Returns:
            캐시 통계 딕셔너리
        """
        try:
            redis = await get_redis()

            pipe = redis.pipeline()
            pipe.get(CACHE_HIT_COUNTER)
            pipe.get(CACHE_MISS_COUNTER)
            results = await pipe.execute()

            hits = int(results[0]) if results[0] else 0
            misses = int(results[1]) if results[1] else 0
            total = hits + misses

            hit_rate = (hits / total * 100) if total > 0 else 0

            return {
                "cache_hits": hits,
                "cache_misses": misses,
                "total_requests": total,
                "hit_rate_percent": round(hit_rate, 2),
                "miss_rate_percent": round(100 - hit_rate, 2)
            }

        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {
                "cache_hits": 0,
                "cache_misses": 0,
                "total_requests": 0,
                "hit_rate_percent": 0.0,
                "miss_rate_percent": 0.0
            }

    @staticmethod
    async def warm_up_cache(room_id: int, room_type: str = "private") -> bool:
        """
        캐시 워밍업 (미리 캐시 생성)

        Args:
            room_id: 채팅방 ID
            room_type: 채팅방 타입

        Returns:
            성공 여부
        """
        try:
            # DB에서 최근 메시지 조회
            messages = await message_service.get_room_messages(
                room_id=room_id,
                room_type=room_type,
                limit=DEFAULT_CACHE_SIZE,
                skip=0,
                include_deleted=False
            )

            if messages:
                # 메시지를 딕셔너리로 변환
                messages_dict = []
                for msg in messages:
                    msg_dict = msg.model_dump()
                    msg_dict["id"] = str(msg.id)
                    messages_dict.append(msg_dict)

                # 캐시에 저장
                success = await MessageCacheService.cache_messages(
                    room_id, room_type, messages_dict, DEFAULT_CACHE_SIZE
                )

                if success:
                    logger.info(f"Cache warmed up for room {room_id}:{room_type} with {len(messages_dict)} messages")

                return success

            return True  # 메시지가 없어도 성공으로 처리

        except Exception as e:
            logger.error(f"Failed to warm up cache for room {room_id}: {e}")
            return False

    @staticmethod
    async def cleanup_expired_caches() -> int:
        """
        만료된 캐시 정리

        Returns:
            정리된 캐시 수
        """
        try:
            redis = await get_redis()

            # 메시지 캐시 키 패턴으로 검색
            pattern = ROOM_MESSAGES_CACHE_KEY.format(room_id="*", room_type="*")
            cache_keys = await redis.keys(pattern)

            cleaned_count = 0
            for key in cache_keys:
                # TTL 확인
                ttl = await redis.ttl(key)
                if ttl == -1:  # TTL이 설정되지 않은 키
                    await redis.expire(key, CACHE_TTL)
                elif ttl == -2:  # 이미 만료된 키
                    await redis.delete(key)
                    cleaned_count += 1

            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired message caches")

            return cleaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup expired caches: {e}")
            return 0


# 편의 함수들
async def get_cached_room_messages(
    room_id: int,
    room_type: str = "private",
    limit: int = 50,
    skip: int = 0
) -> List[Dict]:
    """캐시에서 채팅방 메시지 조회 (DB fallback 포함)"""
    return await MessageCacheService.get_or_set_messages(
        room_id, room_type, limit, skip
    )


async def cache_new_message(room_id: int, room_type: str, message: Dict) -> bool:
    """새 메시지 캐시 추가"""
    return await MessageCacheService.add_new_message_to_cache(
        room_id, room_type, message
    )


async def invalidate_cache(room_id: int, room_type: str) -> bool:
    """캐시 무효화"""
    return await MessageCacheService.invalidate_room_cache(room_id, room_type)


async def get_cache_statistics() -> Dict:
    """캐시 통계 조회"""
    return await MessageCacheService.get_cache_stats()