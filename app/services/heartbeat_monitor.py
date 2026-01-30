"""
Heartbeat 모니터링 서비스

Redis TTL 만료를 감지하여 사용자 오프라인 처리 및 last_seen_at 업데이트
"""

import asyncio
import json
import re
from datetime import datetime
from app.database.redis import get_redis
from app.database.mysql import AsyncSessionLocal
from app.services import auth_service
from app.core.logging import get_logger

logger = get_logger(__name__)


class HeartbeatMonitor:
    """Heartbeat 만료 감지 및 처리"""

    def __init__(self):
        self.running = False
        self.task = None

    async def start(self):
        """모니터링 시작"""
        if self.running:
            logger.warning("Heartbeat monitor is already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._monitor_expirations())
        logger.info("Heartbeat monitor started")

    async def stop(self):
        """모니터링 중지"""
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


# 싱글톤 인스턴스
_heartbeat_monitor = None


def get_heartbeat_monitor() -> HeartbeatMonitor:
    """HeartbeatMonitor 싱글톤 인스턴스 반환"""
    global _heartbeat_monitor
    if _heartbeat_monitor is None:
        _heartbeat_monitor = HeartbeatMonitor()
    return _heartbeat_monitor
