"""
Heartbeat 모니터링 서비스 (Heartbeat Monitor Service)

================================================================================
아키텍처 개요 (Architecture Overview)
================================================================================
Redis Keyspace Notification을 사용하여 사용자 온라인 상태 TTL 만료를 감지하고,
자동으로 오프라인 처리를 수행합니다.

동작 원리:
    1. Redis에서 user:online:{user_id} 키의 만료 이벤트 구독
    2. 만료 감지 시 MySQL의 last_seen_at 업데이트
    3. Redis Pub/Sub으로 오프라인 상태 브로드캐스트

이벤트 흐름:
    user:online:{user_id} TTL 만료
           ↓
    Redis Keyspace Notification
           ↓
    _monitor_expirations() 이벤트 수신
           ↓
    _handle_user_offline() 호출
           ↓
    ├── Redis: online_users Set에서 제거
    ├── Redis: last_seen 업데이트
    ├── MySQL: is_online=False, last_seen_at 업데이트
    └── Redis Pub/Sub: 상태 변경 브로드캐스트

================================================================================
Redis 설정 요구사항 (Redis Configuration)
================================================================================
Redis에서 Keyspace Notification이 활성화되어야 합니다:
    CONFIG SET notify-keyspace-events Ex

서비스 시작 시 자동으로 설정을 시도합니다.

================================================================================
사용 예시 (Usage Examples)
================================================================================
>>> from legacy.app.services.heartbeat_monitor import get_heartbeat_monitor
>>>
>>> # 모니터 시작 (애플리케이션 시작 시)
>>> monitor = get_heartbeat_monitor()
>>> await monitor.start()
>>>
>>> # 모니터 중지 (애플리케이션 종료 시)
>>> await monitor.stop()
"""

import asyncio
import json
import re
from datetime import datetime
from legacy.app.database.redis import get_redis
from legacy.app.database.mysql import AsyncSessionLocal
from legacy.app.services import auth_service
from legacy.app.core.logging import get_logger

logger = get_logger(__name__)


class HeartbeatMonitor:
    """
    Heartbeat 만료 감지 및 처리 클래스

    Redis Keyspace Notification을 구독하여 온라인 상태 TTL 만료를 감지합니다.
    싱글톤 패턴으로 구현되어 get_heartbeat_monitor()로 인스턴스를 얻습니다.

    Attributes:
        running (bool): 모니터링 실행 상태
        task (asyncio.Task): 모니터링 비동기 태스크

    Methods:
        start(): 모니터링 시작
        stop(): 모니터링 중지
    """

    def __init__(self):
        """HeartbeatMonitor 초기화"""
        self.running = False
        self.task = None

    async def start(self):
        """
        모니터링 시작

        Redis Keyspace Notification 구독을 시작하고
        백그라운드 태스크로 이벤트를 처리합니다.

        Note:
            이미 실행 중이면 무시됩니다.
        """
        if self.running:
            logger.warning("Heartbeat monitor is already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._monitor_expirations())
        logger.info("Heartbeat monitor started")

    async def stop(self):
        """
        모니터링 중지

        실행 중인 모니터링 태스크를 취소하고 정리합니다.
        애플리케이션 종료 시 호출됩니다.
        """
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Heartbeat monitor stopped")

    async def _monitor_expirations(self):
        """Redis keyspace notification을 통한 TTL 만료 감지"""
        redis = None
        pubsub = None

        try:
            redis = await get_redis()

            # Redis keyspace notifications 활성화 (만료 이벤트)
            # Ex: expired events
            await redis.config_set('notify-keyspace-events', 'Ex')

            pubsub = redis.pubsub()

            # user:online:* 키의 만료 이벤트 구독
            await pubsub.psubscribe('__keyevent@0__:expired')

            logger.info("Subscribed to Redis expiration events")

            # 이벤트 수신
            async for message in pubsub.listen():
                if not self.running:
                    break

                if message['type'] == 'pmessage':
                    # Redis 버전에 따라 bytes 또는 str로 반환될 수 있음
                    expired_key = message['data']
                    if isinstance(expired_key, bytes):
                        expired_key = expired_key.decode('utf-8')

                    # user:online:{user_id} 패턴 확인
                    match = re.match(r'user:online:(\d+)', expired_key)
                    if match:
                        user_id = int(match.group(1))
                        await self._handle_user_offline(user_id)

        except asyncio.CancelledError:
            logger.info("Heartbeat monitor cancelled")
            raise

        except Exception as e:
            logger.error(f"Error in heartbeat monitor: {e}")

        finally:
            if pubsub:
                try:
                    await pubsub.punsubscribe()
                    await pubsub.close()
                except Exception as e:
                    logger.error(f"Error closing pubsub: {e}")

    async def _handle_user_offline(self, user_id: int):
        """
        사용자 오프라인 처리

        Args:
            user_id: 오프라인 처리할 사용자 ID
        """
        try:
            redis = await get_redis()

            # 1. Redis 온라인 집합에서 제거
            await redis.srem("online_users", user_id)

            # 2. 마지막 접속 시간 Redis에 업데이트
            current_time = datetime.utcnow().isoformat()
            await redis.setex(
                f"user:last_seen:{user_id}",
                86400 * 7,  # 7일 보관
                current_time
            )

            # 3. MySQL DB에 last_seen_at 업데이트
            async with AsyncSessionLocal() as db:
                await auth_service.update_online_status(
                    db=db,
                    user_id=user_id,
                    is_online=False
                )
                await db.commit()

            # 4. Redis Pub/Sub으로 오프라인 상태 브로드캐스트
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

            logger.info(f"User {user_id} marked as offline due to heartbeat timeout", extra={
                "user_id": user_id,
                "event_type": "heartbeat_timeout"
            })

        except Exception as e:
            logger.error(f"Failed to handle user {user_id} offline: {e}")


# =============================================================================
# 싱글톤 인스턴스 (Singleton Instance)
# =============================================================================
# 애플리케이션 전체에서 하나의 HeartbeatMonitor만 사용합니다.
# =============================================================================
_heartbeat_monitor = None


def get_heartbeat_monitor() -> HeartbeatMonitor:
    """
    HeartbeatMonitor 싱글톤 인스턴스 반환

    처음 호출 시 인스턴스를 생성하고, 이후에는 동일 인스턴스를 반환합니다.

    Returns:
        HeartbeatMonitor: 싱글톤 인스턴스
    """
    global _heartbeat_monitor
    if _heartbeat_monitor is None:
        _heartbeat_monitor = HeartbeatMonitor()
    return _heartbeat_monitor
