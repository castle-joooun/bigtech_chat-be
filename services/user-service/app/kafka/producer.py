"""
Kafka Producer for User Service
"""

import json
import logging
from typing import Any, Optional
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError, KafkaTimeoutError

from app.core.config import settings

logger = logging.getLogger(__name__)


class KafkaProducer:
    """Kafka Producer for publishing domain events"""

    def __init__(self):
        self.producer: Optional[AIOKafkaProducer] = None
        self._started = False

    async def start(self):
        """Start the producer"""
        if self._started:
            logger.warning("Producer already started")
            return

        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: str(k).encode('utf-8') if k else None,
                acks='all',
                compression_type='gzip',
            )
            await self.producer.start()
            self._started = True
            logger.info("Kafka Producer started successfully")

        except Exception as e:
            logger.error(f"Failed to start Kafka Producer: {e}")
            self._started = False

    async def stop(self):
        """Stop the producer"""
        if self.producer and self._started:
            await self.producer.stop()
            self._started = False
            logger.info("Kafka Producer stopped")

    async def publish(
        self,
        topic: str,
        event: Any,
        key: Optional[str] = None
    ) -> bool:
        """Publish an event to Kafka"""
        if not self._started or not self.producer:
            logger.warning("Producer not started, skipping publish")
            return False

        try:
            if hasattr(event, 'to_dict'):
                event_data = event.to_dict()
            elif isinstance(event, dict):
                event_data = event
            else:
                raise ValueError(f"Unsupported event type: {type(event)}")

            metadata = await self.producer.send_and_wait(
                topic=topic,
                value=event_data,
                key=key
            )

            logger.info(
                f"[Event Published] Topic: {topic}, "
                f"Partition: {metadata.partition}, "
                f"Offset: {metadata.offset}"
            )
            return True

        except (KafkaTimeoutError, KafkaError) as e:
            logger.error(f"[Kafka Error] Topic: {topic}, Error: {e}")
            return False

        except Exception as e:
            logger.error(f"[Unexpected Error] Topic: {topic}, Error: {e}")
            return False


_producer: Optional[KafkaProducer] = None


def get_event_producer() -> KafkaProducer:
    """Get singleton producer instance"""
    global _producer
    if _producer is None:
        _producer = KafkaProducer()
    return _producer
