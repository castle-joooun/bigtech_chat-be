"""
Kafka Consumer

Domain Events를 Kafka에서 소비하는 Consumer
"""

import json
import logging
import asyncio
from typing import List, Callable, Optional, Dict, Any
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

from .config import kafka_config
from .producer import get_event_producer

logger = logging.getLogger(__name__)


class DomainEventConsumer:
    """Domain Events를 Kafka에서 소비하는 Consumer"""

    def __init__(
        self,
        topics: List[str],
        group_id: str,
        handler: Callable[[str, Optional[str], Dict], Any]
    ):
        """
        Args:
            topics: 구독할 Kafka topics
            group_id: Consumer group ID
            handler: 이벤트 처리 함수 (topic, key, event_data)
        """
        self.topics = topics
        self.group_id = group_id
        self.handler = handler
        self.consumer: Optional[AIOKafkaConsumer] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Consumer 시작"""
        if self._running:
            logger.warning(f"Consumer {self.group_id} already running")
            return

        try:
            self.consumer = AIOKafkaConsumer(
                *self.topics,
                bootstrap_servers=kafka_config.bootstrap_servers,
                group_id=self.group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                auto_offset_reset=kafka_config.consumer_auto_offset_reset,
                enable_auto_commit=kafka_config.consumer_enable_auto_commit,
                auto_commit_interval_ms=kafka_config.consumer_auto_commit_interval_ms,
                max_poll_records=kafka_config.consumer_max_poll_records,
                session_timeout_ms=kafka_config.consumer_session_timeout_ms
            )

            await self.consumer.start()
            self._running = True

            # 백그라운드 태스크로 이벤트 소비
            self._task = asyncio.create_task(self._consume_loop())

            logger.info(
                f"✅ Kafka Consumer started: "
                f"group_id={self.group_id}, "
                f"topics={self.topics}"
            )

        except Exception as e:
            logger.error(f"❌ Failed to start Consumer {self.group_id}: {e}")
            raise

    async def stop(self):
        """Consumer 중지"""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self.consumer:
            await self.consumer.stop()
            logger.info(f"Kafka Consumer stopped: {self.group_id}")

    async def _consume_loop(self):
        """이벤트 소비 루프"""
        try:
            async for msg in self.consumer:
                try:
                    # 이벤트 처리
                    await self._handle_message(msg)

                except Exception as e:
                    logger.error(
                        f"[Event Processing Error] "
                        f"Group: {self.group_id}, "
                        f"Topic: {msg.topic}, "
                        f"Partition: {msg.partition}, "
                        f"Offset: {msg.offset}, "
                        f"Error: {e}"
                    )
                    # TODO: Dead Letter Queue로 전송

        except asyncio.CancelledError:
            logger.info(f"Consumer loop cancelled: {self.group_id}")
            raise

        except Exception as e:
            logger.error(f"[Consumer Loop Error] {self.group_id}: {e}")

    async def _handle_message(self, msg):
        """메시지 처리 (재시도 로직 포함)"""
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                # Handler 호출
                await self.handler(msg.topic, msg.key, msg.value)

                logger.debug(
                    f"[Event Consumed] "
                    f"Topic: {msg.topic}, "
                    f"Partition: {msg.partition}, "
                    f"Offset: {msg.offset}, "
                    f"Event: {msg.value.get('__event_type__', 'Unknown')}"
                )

                # 성공 시 루프 탈출
                break

            except Exception as e:
                retry_count += 1
                logger.warning(
                    f"[Retry {retry_count}/{max_retries}] "
                    f"Topic: {msg.topic}, "
                    f"Offset: {msg.offset}, "
                    f"Error: {e}"
                )

                if retry_count >= max_retries:
                    # 최대 재시도 초과 → DLQ로 전송
                    await self._send_to_dlq(msg, str(e))
                    break

                # Exponential backoff
                await asyncio.sleep(0.5 * retry_count)

    async def _send_to_dlq(self, msg, error: str):
        """Dead Letter Queue로 전송"""
        try:
            dlq_topic = f"{msg.topic}.dlq"
            dlq_message = {
                'original_topic': msg.topic,
                'original_partition': msg.partition,
                'original_offset': msg.offset,
                'original_key': msg.key,
                'original_value': msg.value,
                'error': error,
                'consumer_group': self.group_id,
                'failed_at': asyncio.get_event_loop().time()
            }

            producer = get_event_producer()
            if producer._started:
                await producer.publish(
                    topic=dlq_topic,
                    event=dlq_message,
                    key=msg.key
                )

                logger.warning(
                    f"[DLQ] Message sent to {dlq_topic}: "
                    f"original_offset={msg.offset}"
                )

        except Exception as e:
            logger.error(f"[DLQ Error] Failed to send to DLQ: {e}")


class NotificationEventHandler:
    """알림 서비스의 이벤트 핸들러 예시"""

    async def handle(self, topic: str, key: Optional[str], event_data: Dict):
        """이벤트 라우팅"""
        event_type = event_data.get('__event_type__')

        if topic == kafka_config.topic_user_events:
            await self._handle_user_event(event_type, event_data)
        elif topic == kafka_config.topic_friend_events:
            await self._handle_friend_event(event_type, event_data)
        elif topic == kafka_config.topic_message_events:
            await self._handle_message_event(event_type, event_data)
        else:
            logger.warning(f"Unknown topic: {topic}")

    async def _handle_user_event(self, event_type: str, event_data: Dict):
        """사용자 이벤트 처리"""
        if event_type == 'UserRegistered':
            await self._send_welcome_notification(event_data)
        elif event_type == 'UserOnlineStatusChanged':
            await self._broadcast_online_status(event_data)

    async def _handle_friend_event(self, event_type: str, event_data: Dict):
        """친구 이벤트 처리"""
        if event_type == 'FriendRequestSent':
            await self._send_friend_request_notification(event_data)
        elif event_type == 'FriendRequestAccepted':
            await self._send_friend_accepted_notification(event_data)

    async def _handle_message_event(self, event_type: str, event_data: Dict):
        """메시지 이벤트 처리"""
        if event_type == 'MessageSent':
            await self._send_new_message_notification(event_data)

    async def _send_welcome_notification(self, event_data: Dict):
        """환영 알림 전송"""
        logger.info(f"Welcome notification: user_id={event_data['user_id']}")
        # TODO: 실제 알림 전송 로직

    async def _broadcast_online_status(self, event_data: Dict):
        """온라인 상태 브로드캐스트"""
        logger.info(
            f"Online status broadcast: "
            f"user_id={event_data['user_id']}, "
            f"is_online={event_data['is_online']}"
        )
        # TODO: Redis Pub/Sub로 SSE 연결된 클라이언트에게 전송

    async def _send_friend_request_notification(self, event_data: Dict):
        """친구 요청 알림 전송"""
        logger.info(
            f"Friend request notification: "
            f"from={event_data['requester_name']} "
            f"to={event_data['addressee_id']}"
        )
        # TODO: SSE로 실시간 전송

    async def _send_friend_accepted_notification(self, event_data: Dict):
        """친구 수락 알림 전송"""
        logger.info(
            f"Friend accepted notification: "
            f"to={event_data['requester_id']}"
        )

    async def _send_new_message_notification(self, event_data: Dict):
        """새 메시지 알림 전송"""
        logger.info(
            f"New message notification: "
            f"room_id={event_data['room_id']}, "
            f"from={event_data['username']}"
        )
        # TODO: SSE로 실시간 전송
