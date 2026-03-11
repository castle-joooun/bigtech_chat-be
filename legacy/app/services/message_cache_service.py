"""
메시지 캐싱 서비스 (Message Cache Service)

================================================================================
아키텍처 개요 (Architecture Overview)
================================================================================

이 모듈은 Redis를 사용하여 채팅방별 최근 메시지를 캐싱하는 서비스입니다.
Cache-Aside (Lazy Loading) 패턴을 구현하여 데이터베이스 부하를 줄이고
응답 속도를 향상시킵니다.

핵심 캐싱 전략:
- Cache-Aside Pattern: 캐시 미스 시 DB에서 조회 후 캐시에 저장
- Write-Through Pattern: 새 메시지 생성 시 캐시에도 즉시 반영
- TTL (Time-To-Live): 24시간 후 자동 만료로 메모리 관리

================================================================================
적용된 디자인 패턴 (Design Patterns Applied)
================================================================================

1. Cache-Aside Pattern (캐시 어사이드 패턴)
   - 읽기: 캐시 조회 → 미스 시 DB 조회 → 캐시 저장 → 반환
   - 장점: 캐시 실패 시에도 서비스 지속, 유연한 캐시 갱신
   - 단점: 첫 요청은 항상 느림 (Cold Start)

   구현 예시:
   ```python
   # get_or_set_messages() 메서드
   cached = await cache.get(key)
   if cached:
       return cached  # Cache Hit
   data = await db.query()  # Cache Miss → DB 조회
   await cache.set(key, data)  # 캐시 저장
   return data
   ```

2. Write-Through Pattern (쓰기 관통 패턴)
   - 새 데이터 생성 시 캐시에도 동시 반영
   - add_new_message_to_cache()로 구현
   - 캐시와 DB 간 일관성 유지

3. Pipeline Pattern (파이프라인 패턴)
   - Redis 파이프라인으로 여러 명령을 하나의 네트워크 라운드트립으로 처리
   - 네트워크 지연 최소화, 처리량 향상

   성능 비교:
   ```
   개별 명령어: N번의 네트워크 라운드트립 → O(N) 지연
   파이프라인:  1번의 네트워크 라운드트립 → O(1) 지연
   ```

4. Graceful Degradation Pattern (우아한 성능 저하 패턴)
   - 캐시 실패 시에도 DB fallback으로 서비스 지속
   - 통계 업데이트 실패는 warning으로만 처리 (비치명적)

================================================================================
SOLID 원칙 적용 (SOLID Principles)
================================================================================

1. Single Responsibility Principle (단일 책임 원칙)
   - MessageCacheService: 메시지 캐싱에만 집중
   - 캐시 저장/조회/무효화/통계 각각 별도 메서드

2. Open/Closed Principle (개방-폐쇄 원칙)
   - 새로운 캐시 전략 추가 시 기존 코드 수정 없이 확장 가능
   - cache_size, TTL 등 설정값 외부화

3. Liskov Substitution Principle (리스코프 치환 원칙)
   - 편의 함수들이 서비스 메서드와 동일한 인터페이스 제공
   - get_cached_room_messages() == MessageCacheService.get_or_set_messages()

4. Interface Segregation Principle (인터페이스 분리 원칙)
   - 읽기(get), 쓰기(cache), 삭제(invalidate), 통계(stats) 분리
   - 클라이언트는 필요한 기능만 사용

5. Dependency Inversion Principle (의존성 역전 원칙)
   - get_redis() 함수로 Redis 의존성 주입
   - message_service 모듈 참조로 느슨한 결합

================================================================================
Redis 자료구조 선택 (Redis Data Structure)
================================================================================

List 자료구조 선택 이유:
- 시간순 정렬된 메시지에 적합 (LPUSH/LRANGE)
- O(1) 삽입, O(N) 범위 조회
- LTRIM으로 자동 크기 제한

대안 비교:
- Sorted Set: 점수 기반 정렬 필요 시 (timestamp)
- Stream: 메시지 큐, 컨슈머 그룹 필요 시

키 네이밍 컨벤션:
- 패턴: "room:messages:{room_id}:{room_type}"
- 예시: "room:messages:123:private"
- 장점: 명확한 계층 구조, 패턴 매칭 가능

================================================================================
성능 최적화 기법 (Performance Optimizations)
================================================================================

1. Redis Pipeline 사용
   - 여러 명령을 단일 네트워크 요청으로 처리
   - cache_messages(), _update_cache_stats() 등에서 사용

2. SCAN vs KEYS
   - KEYS: O(N) 블로킹 - 프로덕션 금지!
   - SCAN: 커서 기반 점진적 스캔 - 서버 블로킹 방지

   cleanup_expired_caches()에서 SCAN 사용:
   ```python
   cursor = 0
   while True:
       cursor, keys = await redis.scan(cursor, match=pattern, count=100)
       # 키 처리...
       if cursor == 0:
           break
   ```

3. 캐시 크기 제한 (LTRIM)
   - 메모리 사용량 제한
   - 오래된 메시지 자동 제거

4. 성능 메트릭 수집
   - log_performance_metric()으로 응답 시간 추적
   - 캐시 히트율 모니터링

================================================================================
"""

import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from legacy.app.database.redis import get_redis
from legacy.app.core.logging import get_logger, log_performance_metric
from legacy.app.services import message_service

logger = get_logger(__name__)


# =============================================================================
# Redis 키 패턴 정의 (Key Patterns)
# =============================================================================
#
# 키 네이밍 컨벤션: "domain:entity:identifier"
# - 명확한 계층 구조로 관리 용이
# - 패턴 매칭으로 일괄 작업 가능 (SCAN match)
#
# =============================================================================

ROOM_MESSAGES_CACHE_KEY = "room:messages:{room_id}:{room_type}"
"""
채팅방 메시지 캐시 키 패턴

형식: room:messages:{room_id}:{room_type}
예시: room:messages:123:private, room:messages:456:group
자료구조: Redis List (최신 메시지가 앞에 위치)
"""

CACHE_STATS_KEY = "cache:stats:messages"
"""캐시 통계 키 (현재 미사용, 향후 확장용)"""

CACHE_HIT_COUNTER = "cache:hit:messages"
"""캐시 히트 카운터 - 캐시에서 데이터를 찾은 횟수"""

CACHE_MISS_COUNTER = "cache:miss:messages"
"""캐시 미스 카운터 - DB fallback이 발생한 횟수"""


# =============================================================================
# 캐시 설정값 (Cache Configuration)
# =============================================================================
#
# 설정값 결정 기준:
# - DEFAULT_CACHE_SIZE: 일반적인 채팅방에서 스크롤 없이 볼 수 있는 메시지 수
# - CACHE_TTL: 자주 사용되지 않는 채팅방의 메모리 회수
# - CACHE_STATS_TTL: 통계는 단기간만 유지 (모니터링 용도)
#
# =============================================================================

DEFAULT_CACHE_SIZE = 50
"""
채팅방별 캐시할 메시지 수

근거:
- 일반적인 채팅 UI에서 첫 화면에 표시되는 메시지 수
- 메모리 효율성과 캐시 히트율 간의 균형점
- 50개 이상은 스크롤 필요 → 추가 로딩 시 DB 조회
"""

CACHE_TTL = 86400  # 24시간
"""
캐시 만료 시간 (초)

근거:
- 24시간 이상 비활성 채팅방은 캐시에서 제거
- 활성 채팅방은 새 메시지 추가 시 TTL 자동 갱신
- 메모리 누수 방지
"""

CACHE_STATS_TTL = 3600  # 1시간
"""
통계 데이터 만료 시간 (초)

근거:
- 시간당 캐시 히트율 모니터링
- 장기 통계는 별도 시계열 DB 사용 권장
"""


class MessageCacheService:
    """
    메시지 캐싱 서비스 클래스

    =========================================================================
    클래스 설계 철학
    =========================================================================

    1. Stateless 설계
       - 모든 메서드가 @staticmethod
       - 인스턴스 생성 없이 사용 가능
       - 수평 확장에 유리

    2. 비동기 우선 (Async-First)
       - 모든 메서드가 async
       - I/O 바운드 작업(Redis, DB)에 최적화
       - 동시성 처리 지원

    3. 장애 격리 (Fault Isolation)
       - 캐시 실패 시에도 서비스 지속
       - 모든 메서드에 try-except 적용
       - 적절한 기본값 반환

    =========================================================================
    사용 예시
    =========================================================================

    # 캐시에서 메시지 조회 (DB fallback 포함)
    messages = await MessageCacheService.get_or_set_messages(
        room_id=123,
        room_type="private",
        limit=50
    )

    # 새 메시지 캐시에 추가
    await MessageCacheService.add_new_message_to_cache(
        room_id=123,
        room_type="private",
        message={"content": "Hello", "sender_id": 1}
    )

    # 캐시 무효화 (메시지 삭제 시)
    await MessageCacheService.invalidate_room_cache(123, "private")
    """

    @staticmethod
    async def get_cached_messages(
        room_id: int,
        room_type: str = "private",
        limit: int = 50,
        skip: int = 0
    ) -> Tuple[Optional[List[Dict]], bool]:
        """
        캐시에서 메시지 조회

        =====================================================================
        동작 방식
        =====================================================================

        1. Redis List에서 LRANGE로 범위 조회
        2. 캐시 히트/미스 통계 업데이트
        3. 성능 메트릭 로깅

        시간 복잡도: O(skip + limit)

        =====================================================================
        Redis 명령어 분석
        =====================================================================

        LRANGE key start stop
        - List의 특정 범위 요소 반환
        - start=0, stop=-1: 전체 조회
        - 음수 인덱스 지원 (-1은 마지막 요소)

        예시:
        - LRANGE room:messages:123:private 0 49
        - 첫 50개 메시지 조회 (최신순)

        =====================================================================
        SOLID 적용: Single Responsibility
        =====================================================================

        - 오직 캐시 조회만 담당
        - DB fallback은 get_or_set_messages()에서 처리
        - 통계 업데이트는 별도 메서드 호출

        Args:
            room_id: 채팅방 ID
            room_type: 채팅방 타입 ("private" | "group")
            limit: 조회할 메시지 수 (기본값: 50)
            skip: 건너뛸 메시지 수 (페이지네이션용)

        Returns:
            Tuple[Optional[List[Dict]], bool]:
                - 첫 번째 값: 메시지 리스트 (없으면 None)
                - 두 번째 값: 캐시 히트 여부 (True/False)

        Example:
            >>> messages, is_hit = await MessageCacheService.get_cached_messages(
            ...     room_id=123,
            ...     room_type="private",
            ...     limit=20
            ... )
            >>> if is_hit:
            ...     print(f"캐시에서 {len(messages)}개 메시지 조회")
            ... else:
            ...     print("캐시 미스 - DB 조회 필요")
        """
        try:
            redis = await get_redis()
            cache_key = ROOM_MESSAGES_CACHE_KEY.format(room_id=room_id, room_type=room_type)

            start_time = time.time()

            # ---------------------------------------------------------------------
            # Redis List에서 메시지 조회 (최신순)
            #
            # LRANGE는 0-indexed
            # skip=0, limit=50 → LRANGE key 0 49 (첫 50개)
            # skip=50, limit=50 → LRANGE key 50 99 (다음 50개)
            # ---------------------------------------------------------------------
            cached_data = await redis.lrange(cache_key, skip, skip + limit - 1)

            if cached_data:
                # -----------------------------------------------------------------
                # 캐시 히트 (Cache Hit)
                #
                # JSON 문자열을 Python 딕셔너리로 역직렬화
                # List Comprehension으로 간결하게 처리
                # -----------------------------------------------------------------
                messages = [json.loads(msg_str) for msg_str in cached_data]

                # 캐시 히트 통계 업데이트 (비동기, 실패해도 계속 진행)
                await MessageCacheService._update_cache_stats(True)

                # 성능 메트릭 로깅 (모니터링/알림용)
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
                # -----------------------------------------------------------------
                # 캐시 미스 (Cache Miss)
                #
                # 빈 리스트 반환 시 캐시 미스로 처리
                # 호출자가 DB fallback 결정
                # -----------------------------------------------------------------
                await MessageCacheService._update_cache_stats(False)

                logger.debug(f"Cache miss for room {room_id}:{room_type}")
                return None, False

        except Exception as e:
            # ---------------------------------------------------------------------
            # 장애 격리 (Fault Isolation)
            #
            # Redis 연결 실패, 직렬화 오류 등 모든 예외 처리
            # 캐시 미스로 처리하여 DB fallback 유도
            # 서비스 중단 방지
            # ---------------------------------------------------------------------
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
        메시지를 캐시에 저장 (전체 교체 방식)

        =====================================================================
        동작 방식
        =====================================================================

        1. 기존 캐시 삭제 (DELETE)
        2. 새 메시지들 순차 추가 (LPUSH)
        3. 크기 제한 (LTRIM)
        4. TTL 설정 (EXPIRE)

        모든 작업을 Pipeline으로 원자적 실행

        =====================================================================
        Pipeline 사용 이유
        =====================================================================

        개별 명령 실행 시:
        - 50개 메시지 = 50번 네트워크 라운드트립
        - 평균 1ms/명령 = 50ms 총 지연

        Pipeline 사용 시:
        - 50개 명령 = 1번 네트워크 라운드트립
        - 1ms 총 지연 (50배 성능 향상)

        =====================================================================
        원자성 보장
        =====================================================================

        Pipeline의 모든 명령이 순차 실행되지만,
        다른 클라이언트의 명령이 중간에 끼어들 수 있음

        완전한 원자성이 필요하면 MULTI/EXEC (트랜잭션) 사용
        하지만 캐시 데이터는 일시적 불일치 허용 가능

        =====================================================================
        SOLID 적용: Open/Closed Principle
        =====================================================================

        - cache_size 파라미터로 캐시 크기 조절
        - 호출자가 필요에 따라 크기 변경 가능
        - 기존 코드 수정 없이 확장

        Args:
            room_id: 채팅방 ID
            room_type: 채팅방 타입
            messages: 캐시할 메시지 리스트 (시간순 정렬)
            cache_size: 캐시 크기 (기본값: 50)

        Returns:
            bool: 성공 여부

        Example:
            >>> messages = [{"id": "1", "content": "Hello"}, ...]
            >>> success = await MessageCacheService.cache_messages(
            ...     room_id=123,
            ...     room_type="private",
            ...     messages=messages,
            ...     cache_size=100  # 더 많이 캐시
            ... )
        """
        try:
            if not messages:
                return True  # 빈 리스트는 성공으로 처리

            redis = await get_redis()
            cache_key = ROOM_MESSAGES_CACHE_KEY.format(room_id=room_id, room_type=room_type)

            start_time = time.time()

            # -----------------------------------------------------------------
            # Redis Pipeline 생성
            #
            # 여러 명령을 버퍼에 쌓아두고 한 번에 전송
            # 네트워크 오버헤드 최소화
            # -----------------------------------------------------------------
            pipe = redis.pipeline()

            # Step 1: 기존 캐시 삭제 (새로운 데이터로 완전 교체)
            pipe.delete(cache_key)

            # -----------------------------------------------------------------
            # Step 2: 메시지를 JSON 문자열로 변환하여 List에 추가
            #
            # reversed(): 최신 메시지를 List 앞에 배치
            # [-cache_size:]: 최신 N개만 사용 (메모리 절약)
            #
            # LPUSH: List의 왼쪽(앞)에 추가 → O(1)
            # 결과: [최신] → [이전] → [더 이전] → ...
            # -----------------------------------------------------------------
            for message in reversed(messages[-cache_size:]):
                # default=str: datetime, ObjectId 등 직렬화 불가 타입 처리
                # ensure_ascii=False: 한글 등 유니코드 그대로 저장
                message_str = json.dumps(message, default=str, ensure_ascii=False)
                pipe.lpush(cache_key, message_str)

            # -----------------------------------------------------------------
            # Step 3: 캐시 크기 제한 (메모리 관리)
            #
            # LTRIM key 0 (cache_size-1)
            # 0번째부터 (cache_size-1)번째까지만 유지
            # 나머지는 삭제
            # -----------------------------------------------------------------
            pipe.ltrim(cache_key, 0, cache_size - 1)

            # Step 4: TTL 설정 (자동 만료)
            pipe.expire(cache_key, CACHE_TTL)

            # -----------------------------------------------------------------
            # Pipeline 실행
            #
            # 모든 명령이 한 번에 Redis 서버로 전송
            # 응답도 한 번에 수신
            # -----------------------------------------------------------------
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
        새 메시지를 캐시에 추가 (Incremental Update)

        =====================================================================
        Write-Through 패턴 구현
        =====================================================================

        메시지 생성 시 DB와 캐시 모두 업데이트
        - DB: MessageService.create_message()
        - 캐시: 이 메서드

        장점:
        - 캐시 일관성 유지
        - 다음 조회 시 캐시 히트 보장

        =====================================================================
        동작 방식
        =====================================================================

        1. 캐시 존재 확인 (EXISTS)
        2. 새 메시지를 List 앞에 추가 (LPUSH)
        3. 크기 제한 (LTRIM)
        4. TTL 갱신 (EXPIRE)

        =====================================================================
        캐시 미존재 시 처리
        =====================================================================

        캐시가 없으면 False 반환
        → 다음 조회 시 get_or_set_messages()가 전체 캐시 생성

        이유:
        - 단일 메시지만 캐시하면 불완전한 캐시
        - 조회 시 잘못된 결과 반환 가능성
        - 전체 캐시 갱신이 더 안전

        Args:
            room_id: 채팅방 ID
            room_type: 채팅방 타입
            message: 새 메시지 딕셔너리
            cache_size: 캐시 크기

        Returns:
            bool: 성공 여부 (캐시 미존재 시 False)

        Example:
            >>> new_message = {
            ...     "id": "abc123",
            ...     "content": "새 메시지",
            ...     "sender_id": 1,
            ...     "created_at": datetime.utcnow()
            ... }
            >>> success = await MessageCacheService.add_new_message_to_cache(
            ...     room_id=123,
            ...     room_type="private",
            ...     message=new_message
            ... )
            >>> if not success:
            ...     # 캐시가 없었음 → 다음 조회 시 자동 생성됨
            ...     pass
        """
        try:
            redis = await get_redis()
            cache_key = ROOM_MESSAGES_CACHE_KEY.format(room_id=room_id, room_type=room_type)

            # -----------------------------------------------------------------
            # 캐시 존재 확인
            #
            # EXISTS key: 키 존재 여부 반환 (1 또는 0)
            # 캐시가 없으면 새 메시지만 추가하는 것이 무의미
            # -----------------------------------------------------------------
            cache_exists = await redis.exists(cache_key)
            if not cache_exists:
                # 캐시가 없으면 전체 캐시 갱신 필요
                # get_or_set_messages() 호출 시 자동 생성됨
                return False

            # -----------------------------------------------------------------
            # Pipeline을 사용한 원자적 업데이트
            #
            # LPUSH → LTRIM → EXPIRE를 하나의 요청으로
            # -----------------------------------------------------------------
            pipe = redis.pipeline()

            # Step 1: 새 메시지를 List 앞에 추가 (최신순 유지)
            message_str = json.dumps(message, default=str, ensure_ascii=False)
            pipe.lpush(cache_key, message_str)

            # Step 2: 캐시 크기 제한 (오래된 메시지 자동 제거)
            pipe.ltrim(cache_key, 0, cache_size - 1)

            # Step 3: TTL 갱신 (활성 채팅방은 캐시 유지)
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
        채팅방 캐시 무효화 (Cache Invalidation)

        =====================================================================
        캐시 무효화가 필요한 경우
        =====================================================================

        1. 메시지 삭제
           - 캐시에 삭제된 메시지가 남아있으면 안 됨

        2. 메시지 수정
           - 캐시와 DB 불일치 방지

        3. 채팅방 삭제/나가기
           - 불필요한 캐시 정리

        4. 강제 새로고침
           - 관리자 기능 또는 디버깅

        =====================================================================
        Cache Invalidation 전략
        =====================================================================

        방법 1: 즉시 삭제 (현재 구현)
        - 단순하고 확실함
        - 다음 조회 시 캐시 재생성

        방법 2: 만료 시간 단축
        - 점진적 무효화
        - 서버 부하 분산

        방법 3: 캐시 갱신 (Update)
        - 수정된 데이터로 교체
        - 캐시 히트율 유지

        =====================================================================
        SOLID 적용: Single Responsibility
        =====================================================================

        - 오직 캐시 삭제만 담당
        - DB 정리는 별도 서비스에서 처리
        - 호출자가 무효화 타이밍 결정

        Args:
            room_id: 채팅방 ID
            room_type: 채팅방 타입

        Returns:
            bool: 성공 여부

        Example:
            >>> # 메시지 삭제 후 캐시 무효화
            >>> await MessageService.delete_message(message_id)
            >>> await MessageCacheService.invalidate_room_cache(
            ...     room_id=123,
            ...     room_type="private"
            ... )
        """
        try:
            redis = await get_redis()
            cache_key = ROOM_MESSAGES_CACHE_KEY.format(room_id=room_id, room_type=room_type)

            # -----------------------------------------------------------------
            # DEL 명령어
            #
            # 키가 존재하면 삭제하고 1 반환
            # 키가 없으면 0 반환
            # -----------------------------------------------------------------
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
        캐시에서 메시지 조회, 없으면 DB에서 조회 후 캐시 (Cache-Aside Pattern)

        =====================================================================
        Cache-Aside Pattern 상세
        =====================================================================

        ```
        +--------+     1. Check      +-------+
        | Client | ----------------> | Cache |
        +--------+                   +-------+
             |                           |
             | 2a. Cache Hit             | 2b. Cache Miss
             v (return data)             v
        +--------+     3. Query     +----+
        | Client | <--------------- | DB |
        +--------+                  +----+
             |
             | 4. Store
             v
        +-------+
        | Cache |
        +-------+
        ```

        장점:
        - 캐시 실패 시에도 서비스 지속
        - 필요한 데이터만 캐시 (Lazy Loading)

        단점:
        - 첫 요청은 항상 DB 조회 (Cold Start)
        - 캐시 만료 시 일시적 지연

        =====================================================================
        캐시 예열 (Cache Warming) 전략
        =====================================================================

        Cold Start 문제 해결 방안:
        1. warm_up_cache(): 서버 시작 시 인기 채팅방 캐시
        2. 백그라운드 작업으로 주기적 갱신
        3. 사용자 로그인 시 관련 채팅방 캐시

        =====================================================================
        최적화: 초과 조회 (Over-fetch)
        =====================================================================

        limit=20 요청 시에도 50개를 조회하여 캐시
        → 다음 스크롤 요청 시 캐시 히트 확률 증가

        Args:
            room_id: 채팅방 ID
            room_type: 채팅방 타입
            limit: 조회할 메시지 수
            skip: 건너뛸 메시지 수
            include_deleted: 삭제된 메시지 포함 여부

        Returns:
            List[Dict]: 메시지 리스트 (에러 시 빈 리스트)

        Example:
            >>> # 첫 페이지 조회
            >>> messages = await MessageCacheService.get_or_set_messages(
            ...     room_id=123,
            ...     room_type="private",
            ...     limit=50,
            ...     skip=0
            ... )
            >>>
            >>> # 다음 페이지 조회 (스크롤)
            >>> more_messages = await MessageCacheService.get_or_set_messages(
            ...     room_id=123,
            ...     room_type="private",
            ...     limit=50,
            ...     skip=50
            ... )
        """
        try:
            # =================================================================
            # Step 1: 캐시에서 먼저 조회 (Cache Lookup)
            # =================================================================
            cached_messages, cache_hit = await MessageCacheService.get_cached_messages(
                room_id, room_type, limit, skip
            )

            if cache_hit and cached_messages:
                # 캐시 히트 → 즉시 반환 (빠른 경로)
                return cached_messages

            # =================================================================
            # Step 2: 캐시 미스 → DB 조회 (Slow Path)
            # =================================================================
            start_time = time.time()

            # -----------------------------------------------------------------
            # Over-fetch 전략
            #
            # 요청된 limit보다 더 많이 조회하여 캐시
            # max(limit, DEFAULT_CACHE_SIZE) = max(20, 50) = 50
            #
            # skip=0으로 조회하는 이유:
            # 캐시는 항상 최신 N개 메시지를 저장
            # skip이 있는 요청도 캐시에서 처리하기 위함
            # -----------------------------------------------------------------
            db_messages = await message_service.get_room_messages(
                room_id=room_id,
                room_type=room_type,
                limit=max(limit, DEFAULT_CACHE_SIZE),  # 캐시용으로 더 많이 조회
                skip=0,  # 캐시용이므로 skip=0
                include_deleted=include_deleted
            )

            # -----------------------------------------------------------------
            # Beanie Document → Dict 변환
            #
            # ObjectId는 JSON 직렬화 불가
            # → 문자열로 변환하여 저장
            # -----------------------------------------------------------------
            messages_dict = []
            for msg in db_messages:
                msg_dict = msg.model_dump()
                msg_dict["id"] = str(msg.id)  # ObjectId → str
                messages_dict.append(msg_dict)

            # =================================================================
            # Step 3: DB 조회 결과를 캐시에 저장
            # =================================================================
            if messages_dict:
                await MessageCacheService.cache_messages(
                    room_id, room_type, messages_dict, DEFAULT_CACHE_SIZE
                )

            # =================================================================
            # Step 4: 요청된 범위의 메시지 반환
            # =================================================================
            # 슬라이싱으로 요청된 범위만 추출
            end_index = skip + limit
            result_messages = messages_dict[skip:end_index]

            # 성능 메트릭 로깅 (DB fallback은 모니터링 대상)
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
            # -----------------------------------------------------------------
            # Graceful Degradation
            #
            # 캐시/DB 모두 실패해도 빈 리스트 반환
            # 서비스 중단 방지 (에러는 로깅)
            # -----------------------------------------------------------------
            logger.error(f"Failed to get or set messages for room {room_id}: {e}")
            return []

    @staticmethod
    async def _update_cache_stats(is_hit: bool) -> None:
        """
        캐시 통계 업데이트 (내부 메서드)

        =====================================================================
        최적화: Pipeline 사용
        =====================================================================

        기존 (비최적화):
        ```python
        await redis.incr(counter_key)  # 1번째 라운드트립
        await redis.expire(counter_key, ttl)  # 2번째 라운드트립
        ```

        개선 (Pipeline):
        ```python
        pipe = redis.pipeline()
        pipe.incr(counter_key)
        pipe.expire(counter_key, ttl)
        await pipe.execute()  # 1번의 라운드트립
        ```

        =====================================================================
        비치명적 작업 처리
        =====================================================================

        통계 업데이트 실패는 서비스에 영향 없음
        - error → warning 레벨로 로깅
        - 예외를 던지지 않음 (호출자에게 전파 안 함)

        Args:
            is_hit: 캐시 히트 여부 (True=히트, False=미스)
        """
        try:
            redis = await get_redis()

            # -----------------------------------------------------------------
            # Pipeline을 사용하여 네트워크 라운드트립 최소화
            #
            # INCR + EXPIRE 2개의 명령을 1번의 요청으로
            # -----------------------------------------------------------------
            pipe = redis.pipeline()

            if is_hit:
                pipe.incr(CACHE_HIT_COUNTER)
            else:
                pipe.incr(CACHE_MISS_COUNTER)

            # 통계 키 TTL 설정 (매번 갱신하여 활성 유지)
            pipe.expire(CACHE_HIT_COUNTER, CACHE_STATS_TTL)
            pipe.expire(CACHE_MISS_COUNTER, CACHE_STATS_TTL)

            await pipe.execute()

        except Exception as e:
            # 통계 실패는 치명적이지 않으므로 warning으로 로깅
            # 메인 로직에 영향 주지 않음
            logger.warning(f"Failed to update cache stats: {e}")

    @staticmethod
    async def get_cache_stats() -> Dict:
        """
        캐시 통계 조회 (모니터링용)

        =====================================================================
        캐시 히트율 계산
        =====================================================================

        Hit Rate = (Hits / Total) * 100

        목표 히트율:
        - 80% 이상: 우수
        - 60-80%: 양호
        - 60% 미만: 개선 필요

        낮은 히트율 원인:
        - 캐시 크기 부족
        - TTL이 너무 짧음
        - 캐시 예열(warming) 필요
        - 접근 패턴이 캐시에 부적합

        =====================================================================
        사용 예시
        =====================================================================

        모니터링 대시보드에서 정기적으로 조회:
        - Prometheus + Grafana 연동
        - 알림 설정 (히트율 60% 미만 시)

        Returns:
            Dict: 캐시 통계
                - cache_hits: 캐시 히트 횟수
                - cache_misses: 캐시 미스 횟수
                - total_requests: 총 요청 수
                - hit_rate_percent: 히트율 (%)
                - miss_rate_percent: 미스율 (%)

        Example:
            >>> stats = await MessageCacheService.get_cache_stats()
            >>> print(f"캐시 히트율: {stats['hit_rate_percent']}%")
            >>> if stats['hit_rate_percent'] < 60:
            ...     print("캐시 성능 점검 필요!")
        """
        try:
            redis = await get_redis()

            # Pipeline으로 두 값을 한 번에 조회
            pipe = redis.pipeline()
            pipe.get(CACHE_HIT_COUNTER)
            pipe.get(CACHE_MISS_COUNTER)
            results = await pipe.execute()

            # 문자열 → 정수 변환 (없으면 0)
            hits = int(results[0]) if results[0] else 0
            misses = int(results[1]) if results[1] else 0
            total = hits + misses

            # 0으로 나누기 방지
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
            # 에러 시 기본값 반환 (모니터링 중단 방지)
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
        캐시 워밍업 (Cache Warming / Pre-heating)

        =====================================================================
        Cache Warming 전략
        =====================================================================

        Cold Start 문제:
        - 서버 재시작 후 모든 캐시가 비어있음
        - 첫 요청마다 DB 조회 발생
        - 일시적 성능 저하

        해결책:
        1. 서버 시작 시 인기 채팅방 캐시 예열
        2. 사용자 로그인 시 관련 채팅방 캐시
        3. 백그라운드 작업으로 주기적 갱신

        =====================================================================
        워밍업 대상 선정 기준
        =====================================================================

        우선순위:
        1. 최근 활동이 있는 채팅방
        2. 멤버 수가 많은 그룹 채팅방
        3. VIP 사용자의 채팅방

        =====================================================================
        사용 예시
        =====================================================================

        1. 서버 시작 시:
        ```python
        async def on_startup():
            active_rooms = await get_active_room_ids()
            for room_id, room_type in active_rooms:
                await MessageCacheService.warm_up_cache(room_id, room_type)
        ```

        2. 사용자 로그인 시:
        ```python
        async def on_user_login(user_id: int):
            rooms = await get_user_rooms(user_id)
            for room in rooms:
                await MessageCacheService.warm_up_cache(room.id, room.type)
        ```

        Args:
            room_id: 채팅방 ID
            room_type: 채팅방 타입

        Returns:
            bool: 성공 여부
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
                # Beanie Document → Dict 변환
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
        만료된 캐시 정리 (Maintenance Task)

        =====================================================================
        SCAN vs KEYS 명령어 비교
        =====================================================================

        KEYS 명령어 (사용 금지!):
        - O(N) 시간 복잡도
        - 전체 키를 한 번에 스캔
        - 서버 블로킹 발생 → 다른 요청 처리 불가
        - 프로덕션에서 절대 사용 금지!

        SCAN 명령어 (권장):
        - 커서 기반 점진적 스캔
        - COUNT로 배치 크기 조절
        - 서버 블로킹 없음
        - 중간에 다른 요청 처리 가능

        =====================================================================
        TTL 상태 해석
        =====================================================================

        TTL 반환값:
        - 양수: 남은 만료 시간 (초)
        - -1: TTL이 설정되지 않음 (영구 키)
        - -2: 키가 존재하지 않음 (이미 만료)

        처리 방법:
        - TTL = -1: TTL 설정 (메모리 누수 방지)
        - TTL = -2: 삭제 목록에 추가

        =====================================================================
        배치 처리 최적화
        =====================================================================

        1. SCAN으로 키 수집
        2. 처리할 키 목록 생성
        3. Pipeline으로 일괄 처리

        이 방식의 장점:
        - 네트워크 라운드트립 최소화
        - 서버 부하 분산
        - 대량 키 처리 가능

        Returns:
            int: 정리된 캐시 수

        Example:
            >>> # 주기적 정리 작업 (Celery, APScheduler 등에서 호출)
            >>> cleaned = await MessageCacheService.cleanup_expired_caches()
            >>> print(f"정리된 캐시: {cleaned}개")
        """
        try:
            redis = await get_redis()

            # -----------------------------------------------------------------
            # SCAN을 사용하여 서버 블로킹 방지
            #
            # 패턴: room:messages:*:*
            # count=100: 한 번에 최대 100개 키 스캔 (근사값)
            # -----------------------------------------------------------------
            pattern = ROOM_MESSAGES_CACHE_KEY.format(room_id="*", room_type="*")
            cleaned_count = 0
            keys_to_delete = []
            keys_to_set_ttl = []

            # -----------------------------------------------------------------
            # SCAN 반복자 사용
            #
            # cursor=0으로 시작
            # cursor=0이 반환되면 스캔 완료
            # -----------------------------------------------------------------
            cursor = 0
            while True:
                cursor, keys = await redis.scan(cursor, match=pattern, count=100)

                for key in keys:
                    ttl = await redis.ttl(key)
                    if ttl == -1:  # TTL이 설정되지 않은 키
                        # 메모리 누수 방지를 위해 TTL 설정
                        keys_to_set_ttl.append(key)
                    elif ttl == -2:  # 이미 만료된 키 (존재하지 않음)
                        # 삭제 목록에 추가
                        keys_to_delete.append(key)

                if cursor == 0:
                    break  # 스캔 완료

            # -----------------------------------------------------------------
            # Pipeline으로 일괄 처리
            #
            # 모든 삭제/TTL 설정을 하나의 요청으로
            # -----------------------------------------------------------------
            if keys_to_delete or keys_to_set_ttl:
                pipe = redis.pipeline()

                for key in keys_to_delete:
                    pipe.delete(key)
                    cleaned_count += 1

                for key in keys_to_set_ttl:
                    pipe.expire(key, CACHE_TTL)

                await pipe.execute()

            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired message caches")

            return cleaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup expired caches: {e}")
            return 0


# =============================================================================
# 편의 함수 (Convenience Functions)
# =============================================================================
#
# Facade Pattern 적용:
# - 복잡한 클래스 메서드를 단순한 함수로 제공
# - 호출자 코드 간소화
# - 이전 버전 API와 호환성 유지
#
# 사용 예시:
# ```python
# # 클래스 메서드 직접 호출
# await MessageCacheService.get_or_set_messages(room_id, room_type, limit, skip)
#
# # 편의 함수 사용 (더 간단)
# await get_cached_room_messages(room_id, room_type, limit, skip)
# ```
#
# =============================================================================

async def get_cached_room_messages(
    room_id: int,
    room_type: str = "private",
    limit: int = 50,
    skip: int = 0
) -> List[Dict]:
    """
    캐시에서 채팅방 메시지 조회 (DB fallback 포함)

    MessageCacheService.get_or_set_messages()의 간편 래퍼 함수

    Args:
        room_id: 채팅방 ID
        room_type: 채팅방 타입 (기본값: "private")
        limit: 조회할 메시지 수 (기본값: 50)
        skip: 건너뛸 메시지 수 (기본값: 0)

    Returns:
        List[Dict]: 메시지 리스트
    """
    return await MessageCacheService.get_or_set_messages(
        room_id, room_type, limit, skip
    )


async def cache_new_message(room_id: int, room_type: str, message: Dict) -> bool:
    """
    새 메시지 캐시 추가

    MessageCacheService.add_new_message_to_cache()의 간편 래퍼 함수

    Args:
        room_id: 채팅방 ID
        room_type: 채팅방 타입
        message: 새 메시지 딕셔너리

    Returns:
        bool: 성공 여부
    """
    return await MessageCacheService.add_new_message_to_cache(
        room_id, room_type, message
    )


async def invalidate_cache(room_id: int, room_type: str) -> bool:
    """
    캐시 무효화

    MessageCacheService.invalidate_room_cache()의 간편 래퍼 함수

    Args:
        room_id: 채팅방 ID
        room_type: 채팅방 타입

    Returns:
        bool: 성공 여부
    """
    return await MessageCacheService.invalidate_room_cache(room_id, room_type)


async def get_cache_statistics() -> Dict:
    """
    캐시 통계 조회

    MessageCacheService.get_cache_stats()의 간편 래퍼 함수

    Returns:
        Dict: 캐시 통계
    """
    return await MessageCacheService.get_cache_stats()
