"""
온라인 상태 관리 서비스

Redis를 사용하여 사용자의 온라인 상태를 실시간으로 관리합니다.
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from app.database.redis import get_redis
from app.core.logging import get_logger

logger = get_logger(__name__)

# Redis 키 패턴
USER_ONLINE_KEY = "user:online:{user_id}"
USER_LAST_SEEN_KEY = "user:last_seen:{user_id}"
ONLINE_USERS_SET = "online_users"
USER_WEBSOCKET_KEY = "user:websocket:{user_id}"

# TTL 설정 (초)
ONLINE_STATUS_TTL = 60  # 1분 (테스트용 - 원래는 300초/5분)
LAST_SEEN_TTL = 86400 * 7  # 7일 (마지막 접속 시간 보관)


class OnlineStatusService:
    """온라인 상태 관리 서비스"""

    @staticmethod
    async def set_user_online(user_id: int, session_id: str = None) -> bool:
        """
        사용자를 온라인 상태로 설정

        Args:
            user_id: 사용자 ID
            session_id: 세션 ID (WebSocket 연결 등)

        Returns:
            성공 여부
        """
        try:
            redis = await get_redis()
            current_time = datetime.utcnow().isoformat()

            # 파이프라인을 사용한 원자적 연산
            pipe = redis.pipeline()

            # 1. 사용자 온라인 상태 설정
            online_data = {
                "user_id": user_id,
                "status": "online",
                "last_activity": current_time,
                "session_id": session_id
            }
            pipe.setex(
                USER_ONLINE_KEY.format(user_id=user_id),
                ONLINE_STATUS_TTL,
                json.dumps(online_data)
            )

            # 2. 온라인 사용자 집합에 추가
            pipe.sadd(ONLINE_USERS_SET, user_id)
            pipe.expire(ONLINE_USERS_SET, ONLINE_STATUS_TTL)

            # 3. 마지막 접속 시간 업데이트
            pipe.setex(
                USER_LAST_SEEN_KEY.format(user_id=user_id),
                LAST_SEEN_TTL,
                current_time
            )

            # 4. WebSocket 세션 매핑 (세션 ID가 있는 경우)
            if session_id:
                pipe.setex(
                    USER_WEBSOCKET_KEY.format(user_id=user_id),
                    ONLINE_STATUS_TTL,
                    session_id
                )

            await pipe.execute()

            # 5. Redis Pub/Sub으로 상태 변화 브로드캐스트
            status_change_message = {
                "user_id": user_id,
                "is_online": True,
                "last_activity": current_time,
                "session_id": session_id,
                "timestamp": current_time
            }
            await redis.publish(
                f"user:status:{user_id}",
                json.dumps(status_change_message)
            )

            logger.info(f"User {user_id} set to online status", extra={
                "user_id": user_id,
                "session_id": session_id,
                "event_type": "user_online"
            })

            return True

        except Exception as e:
            logger.error(f"Failed to set user {user_id} online: {e}")
            return False

    @staticmethod
    async def set_user_offline(user_id: int) -> bool:
        """
        사용자를 오프라인 상태로 설정

        Args:
            user_id: 사용자 ID

        Returns:
            성공 여부
        """
        try:
            redis = await get_redis()
            current_time = datetime.utcnow().isoformat()

            # 파이프라인을 사용한 원자적 연산
            pipe = redis.pipeline()

            # 1. 온라인 상태 데이터 삭제
            pipe.delete(USER_ONLINE_KEY.format(user_id=user_id))

            # 2. 온라인 사용자 집합에서 제거
            pipe.srem(ONLINE_USERS_SET, user_id)

            # 3. 마지막 접속 시간 업데이트
            pipe.setex(
                USER_LAST_SEEN_KEY.format(user_id=user_id),
                LAST_SEEN_TTL,
                current_time
            )

            # 4. WebSocket 세션 매핑 삭제
            pipe.delete(USER_WEBSOCKET_KEY.format(user_id=user_id))

            await pipe.execute()

            # 5. Redis Pub/Sub으로 상태 변화 브로드캐스트
            status_change_message = {
                "user_id": user_id,
                "is_online": False,
                "last_seen": current_time,
                "timestamp": current_time
            }
            await redis.publish(
                f"user:status:{user_id}",
                json.dumps(status_change_message)
            )

            logger.info(f"User {user_id} set to offline status", extra={
                "user_id": user_id,
                "event_type": "user_offline"
            })

            return True

        except Exception as e:
            logger.error(f"Failed to set user {user_id} offline: {e}")
            return False

    @staticmethod
    async def is_user_online(user_id: int) -> bool:
        """
        사용자 온라인 상태 확인

        Args:
            user_id: 사용자 ID

        Returns:
            온라인 여부
        """
        try:
            redis = await get_redis()
            result = await redis.get(USER_ONLINE_KEY.format(user_id=user_id))
            return result is not None

        except Exception as e:
            logger.error(f"Failed to check online status for user {user_id}: {e}")
            return False

    @staticmethod
    async def get_user_status(user_id: int) -> Optional[Dict]:
        """
        사용자 상태 정보 조회

        Args:
            user_id: 사용자 ID

        Returns:
            상태 정보 딕셔너리 또는 None
        """
        try:
            redis = await get_redis()

            # 온라인 상태 정보 조회
            online_data = await redis.get(USER_ONLINE_KEY.format(user_id=user_id))
            last_seen = await redis.get(USER_LAST_SEEN_KEY.format(user_id=user_id))

            if online_data:
                # 온라인 상태
                status_data = json.loads(online_data)
                status_data["is_online"] = True
                return status_data
            elif last_seen:
                # 오프라인 상태 (마지막 접속 시간 있음)
                return {
                    "user_id": user_id,
                    "status": "offline",
                    "is_online": False,
                    "last_seen": last_seen
                }
            else:
                # 접속 기록 없음
                return {
                    "user_id": user_id,
                    "status": "unknown",
                    "is_online": False,
                    "last_seen": None
                }

        except Exception as e:
            logger.error(f"Failed to get status for user {user_id}: {e}")
            return None

    @staticmethod
    async def get_online_users() -> List[int]:
        """
        현재 온라인 사용자 목록 조회

        Returns:
            온라인 사용자 ID 리스트
        """
        try:
            redis = await get_redis()
            online_user_ids = await redis.smembers(ONLINE_USERS_SET)

            # bytes를 int로 변환
            return [int(user_id) for user_id in online_user_ids if user_id]

        except Exception as e:
            logger.error(f"Failed to get online users: {e}")
            return []

    @staticmethod
    async def get_online_count() -> int:
        """
        온라인 사용자 수 조회

        Returns:
            온라인 사용자 수
        """
        try:
            redis = await get_redis()
            return await redis.scard(ONLINE_USERS_SET)

        except Exception as e:
            logger.error(f"Failed to get online user count: {e}")
            return 0

    @staticmethod
    async def update_user_activity(user_id: int) -> bool:
        """
        사용자 활동 시간 업데이트 (heartbeat)

        온라인 상태가 없으면 (TTL 만료) 자동으로 다시 온라인 상태로 설정합니다.

        Args:
            user_id: 사용자 ID

        Returns:
            성공 여부
        """
        try:
            redis = await get_redis()
            online_key = USER_ONLINE_KEY.format(user_id=user_id)
            current_time = datetime.utcnow().isoformat()

            # 온라인 상태 확인
            online_data = await redis.get(online_key)

            if not online_data:
                # 오프라인 상태 (TTL 만료) → 다시 온라인으로 설정
                logger.info(f"User {user_id} was offline, setting back to online via activity")

                # 파이프라인으로 원자적 연산
                pipe = redis.pipeline()

                # 1. 온라인 상태 설정
                status_data = {
                    "user_id": user_id,
                    "status": "online",
                    "last_activity": current_time,
                    "connected_at": current_time
                }
                pipe.setex(online_key, ONLINE_STATUS_TTL, json.dumps(status_data))

                # 2. 온라인 사용자 집합에 추가
                pipe.sadd(ONLINE_USERS_SET, user_id)

                await pipe.execute()

                # 3. Redis Pub/Sub으로 온라인 상태 브로드캐스트
                await redis.publish(
                    f"user:status:{user_id}",
                    json.dumps({
                        "user_id": user_id,
                        "is_online": True,
                        "timestamp": current_time
                    })
                )

                return True

            # 이미 온라인 상태 → 활동 시간만 업데이트
            status_data = json.loads(online_data)
            old_activity = status_data.get("last_activity", "")
            status_data["last_activity"] = current_time

            # TTL 연장
            await redis.setex(online_key, ONLINE_STATUS_TTL, json.dumps(status_data))

            # 주기적 브로드캐스트 (마지막 활동으로부터 10초 이상 지난 경우)
            # 친구들에게 "아직 온라인이다"라는 신호를 보냄
            should_broadcast = True
            if old_activity:
                try:
                    old_time = datetime.fromisoformat(old_activity)
                    current_dt = datetime.fromisoformat(current_time)
                    time_diff = (current_dt - old_time).total_seconds()

                    # 10초 이내에 이미 업데이트된 경우 브로드캐스트 생략
                    if time_diff < 10:
                        should_broadcast = False
                except:
                    pass

            if should_broadcast:
                # Redis Pub/Sub으로 활동 상태 브로드캐스트
                await redis.publish(
                    f"user:status:{user_id}",
                    json.dumps({
                        "user_id": user_id,
                        "is_online": True,
                        "timestamp": current_time
                    })
                )
                logger.debug(f"Broadcasted activity update for user {user_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to update activity for user {user_id}: {e}")
            return False

    @staticmethod
    async def get_users_status(user_ids: List[int]) -> Dict[int, Dict]:
        """
        여러 사용자의 상태 정보 일괄 조회

        Args:
            user_ids: 사용자 ID 리스트

        Returns:
            사용자 ID별 상태 정보 딕셔너리
        """
        try:
            if not user_ids:
                return {}

            redis = await get_redis()
            pipe = redis.pipeline()

            # 온라인 상태 정보 일괄 조회
            for user_id in user_ids:
                pipe.get(USER_ONLINE_KEY.format(user_id=user_id))
                pipe.get(USER_LAST_SEEN_KEY.format(user_id=user_id))

            results = await pipe.execute()

            # 결과 파싱
            status_map = {}
            for i, user_id in enumerate(user_ids):
                online_data = results[i * 2]
                last_seen = results[i * 2 + 1]

                if online_data:
                    # 온라인 상태
                    status_data = json.loads(online_data)
                    status_data["is_online"] = True
                    status_map[user_id] = status_data
                elif last_seen:
                    # 오프라인 상태
                    status_map[user_id] = {
                        "user_id": user_id,
                        "status": "offline",
                        "is_online": False,
                        "last_seen": last_seen
                    }
                else:
                    # 접속 기록 없음
                    status_map[user_id] = {
                        "user_id": user_id,
                        "status": "unknown",
                        "is_online": False,
                        "last_seen": None
                    }

            return status_map

        except Exception as e:
            logger.error(f"Failed to get users status: {e}")
            return {}

    @staticmethod
    async def cleanup_expired_users() -> int:
        """
        만료된 온라인 사용자 정리

        Returns:
            정리된 사용자 수
        """
        try:
            redis = await get_redis()

            # 온라인 사용자 목록 조회
            online_user_ids = await redis.smembers(ONLINE_USERS_SET)
            cleaned_count = 0

            for user_id_bytes in online_user_ids:
                user_id = int(user_id_bytes)
                online_key = USER_ONLINE_KEY.format(user_id=user_id)

                # 개별 사용자 온라인 상태 확인
                exists = await redis.exists(online_key)
                if not exists:
                    # 만료된 사용자 집합에서 제거
                    await redis.srem(ONLINE_USERS_SET, user_id)
                    cleaned_count += 1

            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired online users")

            return cleaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup expired users: {e}")
            return 0

    @staticmethod
    async def get_user_websocket_session(user_id: int) -> Optional[str]:
        """
        사용자의 WebSocket 세션 ID 조회

        Args:
            user_id: 사용자 ID

        Returns:
            세션 ID 또는 None
        """
        try:
            redis = await get_redis()
            return await redis.get(USER_WEBSOCKET_KEY.format(user_id=user_id))

        except Exception as e:
            logger.error(f"Failed to get WebSocket session for user {user_id}: {e}")
            return None

    @staticmethod
    async def set_user_websocket_session(user_id: int, session_id: str) -> bool:
        """
        사용자의 WebSocket 세션 ID 설정

        Args:
            user_id: 사용자 ID
            session_id: 세션 ID

        Returns:
            성공 여부
        """
        try:
            redis = await get_redis()
            await redis.setex(
                USER_WEBSOCKET_KEY.format(user_id=user_id),
                ONLINE_STATUS_TTL,
                session_id
            )
            return True

        except Exception as e:
            logger.error(f"Failed to set WebSocket session for user {user_id}: {e}")
            return False

    @staticmethod
    async def remove_user_websocket_session(user_id: int) -> bool:
        """
        사용자의 WebSocket 세션 제거

        Args:
            user_id: 사용자 ID

        Returns:
            성공 여부
        """
        try:
            redis = await get_redis()
            await redis.delete(USER_WEBSOCKET_KEY.format(user_id=user_id))
            return True

        except Exception as e:
            logger.error(f"Failed to remove WebSocket session for user {user_id}: {e}")
            return False


# 편의 함수들
async def set_online(user_id: int, session_id: str = None) -> bool:
    """사용자 온라인 설정"""
    return await OnlineStatusService.set_user_online(user_id, session_id)


async def set_offline(user_id: int) -> bool:
    """사용자 오프라인 설정"""
    return await OnlineStatusService.set_user_offline(user_id)


async def is_online(user_id: int) -> bool:
    """온라인 상태 확인"""
    return await OnlineStatusService.is_user_online(user_id)


async def get_online_users() -> List[int]:
    """온라인 사용자 목록 조회"""
    return await OnlineStatusService.get_online_users()


async def update_activity(user_id: int) -> bool:
    """활동 시간 업데이트"""
    return await OnlineStatusService.update_user_activity(user_id)