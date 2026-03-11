"""
Kafka Module (Kafka 모듈)
========================

Kafka Producer 및 도메인 이벤트 베이스 클래스를 제공합니다.
"""

from .events import DomainEvent

__all__ = ["DomainEvent"]

# Producer는 optional (aiokafka 패키지가 설치된 경우에만)
try:
    from .producer import KafkaProducer, get_kafka_producer
    __all__.extend(["KafkaProducer", "get_kafka_producer"])
except ImportError:
    pass
