"""
Kafka Producer

Domain Events를 Kafka로 발행하는 Producer
"""

import json
import logging
from typing import Any, Optional
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError, KafkaTimeoutError

from app.domain.events.base import DomainEvent
from .config import kafka_config

logger = logging.getLogger(__name__)


class DomainEventProducer:
    """Domain Events를 Kafka로 발행하는 Producer"""

    def __init__(self):
        self.producer: Optional[AIOKafkaProducer] = None
        self._started = False

    async def start(self):
        """Producer 시작"""
        if self._started:
            logger.warning("Producer already started")
            return

        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=kafka_config.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: str(k).encode('utf-8') if k else None,
                acks=kafka_config.producer_acks,
                compression_type=kafka_config.producer_compression_type,
                max_batch_size=16384,  # 16KB (aiokafka 기본값)
                request_timeout_ms=kafka_config.producer_request_timeout_ms
            )
            await self.producer.start()
            self._started = True
            logger.info("✅ Kafka Producer started successfully")

        except Exception as e:
            logger.error(f"❌ Failed to start Kafka Producer: {e}")
            raise

    async def stop(self):
        """Producer 중지"""
        if self.producer and self._started:
            await self.producer.stop()
            self._started = False
            logger.info("Kafka Producer stopped")

    async def publish(
        self,
        topic: str,
        event: Any,
        key: Optional[str] = None
    ):
        """
        Domain Event 발행

        Args:
            topic: Kafka topic
            event: Domain Event (DomainEvent 인스턴스 또는 dict)
            key: Partition key (user_id, room_id 등)
        """
        if not self._started or not self.producer:
            raise RuntimeError("Producer not started. Call start() first.")

        try:
            # Event를 dict로 변환
            if isinstance(event, DomainEvent):
                event_data = event.to_dict()
            elif isinstance(event, dict):
                event_data = event
            else:
                raise ValueError(f"Unsupported event type: {type(event)}")

            # Kafka로 전송
            metadata = await self.producer.send_and_wait(
                topic=topic,
                value=event_data,
                key=key
            )

            logger.info(
                f"[Event Published] "
                f"Topic: {topic}, "
                f"Partition: {metadata.partition}, "
                f"Offset: {metadata.offset}, "
                f"Event: {event_data.get('__event_type__', 'Unknown')}"
            )

        except KafkaTimeoutError as e:
            logger.error(f"[Kafka Timeout] Topic: {topic}, Error: {e}")
            # TODO: Dead Letter Queue로 전송
            raise

        except KafkaError as e:
            logger.error(f"[Kafka Error] Topic: {topic}, Error: {e}")
            raise

        except Exception as e:
            logger.error(f"[Unexpected Error] Topic: {topic}, Error: {e}")
            raise

    async def publish_with_retry(
        self,
        topic: str,
        event: Any,
        key: Optional[str] = None,
        max_retries: int = 3
    ) -> bool:
        """
        재시도 로직이 포함된 발행

        Args:
            topic: Kafka topic
            event: Domain Event
            key: Partition key
            max_retries: 최대 재시도 횟수

        Returns:
            bool: 성공 여부
        """
        for attempt in range(max_retries):
            try:
                await self.publish(topic, event, key)
                return True

            except KafkaTimeoutError:
                if attempt < max_retries - 1:
                    logger.warning(f"Retry {attempt + 1}/{max_retries} for topic: {topic}")
                    import asyncio
                    await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"Failed after {max_retries} retries: {topic}")
                    # TODO: Dead Letter Queue로 전송
                    return False

            except Exception as e:
                logger.error(f"Unrecoverable error: {e}")
                return False

        return False


# Singleton instance
_event_producer: Optional[DomainEventProducer] = None


def get_event_producer() -> DomainEventProducer:
    """Singleton Producer 인스턴스 반환"""
    global _event_producer
    if _event_producer is None:
        _event_producer = DomainEventProducer()
    return _event_producer
