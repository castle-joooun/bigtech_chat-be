"""
=============================================================================
Kafka Producer (Kafka 프로듀서) - 공통 이벤트 발행 유틸
=============================================================================

📌 이 파일이 하는 일:
    도메인 이벤트를 Kafka 토픽으로 발행하는 프로듀서입니다.
    모든 서비스에서 공통으로 사용할 수 있는 Kafka 프로듀서를 제공합니다.

💡 왜 Kafka를 사용하나요?
    마이크로서비스 간 비동기 통신을 위해 사용합니다.

    예시:
    1. User Service: 사용자 가입 → UserRegistered 이벤트 발행
    2. Kafka: 이벤트 저장
    3. Friend Service: 이벤트 구독 → 환영 메시지 발송

🔄 이벤트 기반 아키텍처:
    ┌─────────────┐     Kafka      ┌─────────────┐
    │ User Service│ ──────────────▶│Friend Service│
    │ (Producer)  │  user.events   │ (Consumer)   │
    └─────────────┘                └─────────────┘

📊 Kafka 설정 옵션:
    - acks="all": 모든 replica 확인 (가장 안전)
    - acks="1": 리더만 확인 (적당한 성능)
    - acks="0": 확인 안 함 (가장 빠름, 손실 가능)

    - compression_type="gzip": 메시지 압축 (네트워크 절약)

사용 예시
---------
```python
from shared_lib.kafka import KafkaProducer, get_kafka_producer

# 1. 초기화 (앱 시작 시)
producer = get_kafka_producer()
await producer.start(bootstrap_servers="localhost:9092")

# 2. 이벤트 발행
await producer.publish(
    topic="user.events",
    event=UserRegistered(user_id=1, email="test@example.com"),
    key="1"  # 파티션 키 (같은 키는 같은 파티션 → 순서 보장)
)

# 3. 종료 (앱 종료 시)
await producer.stop()
```

관련 파일
---------
- user-service/app/kafka/producer.py: 서비스별 프로듀서 (이 모듈 참조)
- user-service/app/kafka/events.py: 이벤트 클래스 정의
"""

import json
import logging
from typing import Any, Optional, Union
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError, KafkaTimeoutError

logger = logging.getLogger(__name__)


# =============================================================================
# Kafka Producer 클래스
# =============================================================================

class KafkaProducer:
    """
    📌 Kafka Producer for publishing domain events

    도메인 이벤트를 Kafka 토픽으로 발행하는 비동기 프로듀서입니다.

    생명주기:
        1. __init__(): 인스턴스 생성 (연결 안 함)
        2. start(): Kafka 브로커에 연결
        3. publish(): 이벤트 발행 (반복)
        4. stop(): 연결 종료

    Thread Safety:
        AIOKafkaProducer는 thread-safe
        여러 코루틴에서 동시 publish 가능
    """

    def __init__(self):
        """
        프로듀서 인스턴스 생성

        실제 Kafka 연결은 start()에서 수행합니다.
        (Lazy Initialization 패턴)
        """
        self.producer: Optional[AIOKafkaProducer] = None
        self._started = False

    async def start(
        self,
        bootstrap_servers: Union[str, list],
        acks: str = "all",
        compression_type: str = "gzip"
    ):
        """
        📌 프로듀서 시작 (Kafka 연결)

        애플리케이션 시작 시 (lifespan startup) 호출합니다.

        Args:
            bootstrap_servers: Kafka 브로커 주소
                - 문자열: "localhost:9092"
                - 쉼표 구분: "broker1:9092,broker2:9092"
                - 리스트: ["broker1:9092", "broker2:9092"]
            acks: 확인 레벨
                - "all": 모든 replica 확인 (가장 안전, 권장)
                - "1": 리더만 확인
                - "0": 확인 안 함 (손실 가능)
            compression_type: 메시지 압축 방식
                - "gzip": 압축률 높음 (권장)
                - "snappy": 빠른 압축/해제
                - "lz4": 균형 잡힌 성능
                - "none": 압축 안 함

        사용 예시:
            producer = KafkaProducer()
            await producer.start("localhost:9092")
        """
        if self._started:
            logger.warning("Producer already started")
            return

        try:
            # 문자열이면 리스트로 변환
            if isinstance(bootstrap_servers, str):
                bootstrap_servers = bootstrap_servers.split(",")

            self.producer = AIOKafkaProducer(
                bootstrap_servers=bootstrap_servers,
                # JSON 직렬화
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: str(k).encode('utf-8') if k else None,
                acks=acks,
                compression_type=compression_type,
            )
            await self.producer.start()
            self._started = True
            logger.info("Kafka Producer started successfully")

        except Exception as e:
            logger.error(f"Failed to start Kafka Producer: {e}")
            self._started = False

    async def stop(self):
        """
        📌 프로듀서 종료

        애플리케이션 종료 시 (lifespan shutdown) 호출합니다.
        버퍼에 남은 메시지를 전송하고 연결을 정리합니다.
        """
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
        """
        📌 이벤트를 Kafka 토픽에 발행

        도메인 이벤트를 JSON으로 직렬화하여 Kafka에 전송합니다.

        Args:
            topic: Kafka 토픽 이름
                   예: "user.events", "friend.events"
            event: 발행할 이벤트 객체
                   - to_dict() 메서드가 있는 객체
                   - 또는 dict 타입
            key: 파티션 키 (선택)
                 같은 키는 같은 파티션에 저장됨
                 → 해당 키의 이벤트 순서 보장

        Returns:
            bool: 발행 성공 여부 (True/False)

        파티션 키 사용 이유:
            같은 user_id의 이벤트는 같은 파티션에 저장
            → 해당 사용자의 이벤트 순서가 보장됨

        사용 예시:
            success = await producer.publish(
                topic="user.events",
                event=UserRegistered(user_id=123, email="test@test.com"),
                key="123"  # user_id를 파티션 키로 사용
            )
        """
        if not self._started or not self.producer:
            logger.warning("Producer not started, skipping publish")
            return False

        try:
            # 이벤트 데이터 변환
            # - to_dict() 메서드가 있으면 호출
            # - dict 타입이면 그대로 사용
            if hasattr(event, 'to_dict'):
                event_data = event.to_dict()
            elif isinstance(event, dict):
                event_data = event
            else:
                raise ValueError(f"Unsupported event type: {type(event)}")

            # Kafka에 발행 (브로커 확인까지 대기)
            metadata = await self.producer.send_and_wait(
                topic=topic,
                value=event_data,
                key=key
            )

            # 발행 성공 로그
            logger.info(
                f"[Event Published] Topic: {topic}, "
                f"Partition: {metadata.partition}, "
                f"Offset: {metadata.offset}"
            )
            return True

        except (KafkaTimeoutError, KafkaError) as e:
            # Kafka 관련 에러 (재시도 가능)
            logger.error(f"[Kafka Error] Topic: {topic}, Error: {e}")
            return False

        except Exception as e:
            # 예상치 못한 에러
            logger.error(f"[Unexpected Error] Topic: {topic}, Error: {e}")
            return False

    @property
    def is_started(self) -> bool:
        """프로듀서 시작 상태 확인"""
        return self._started


# =============================================================================
# 싱글톤 패턴
# =============================================================================
# 애플리케이션 전체에서 하나의 프로듀서 인스턴스 공유
# 연결 풀 재사용으로 리소스 효율화

_producer: Optional[KafkaProducer] = None


def get_kafka_producer() -> KafkaProducer:
    """
    📌 Kafka 프로듀서 싱글톤 반환

    처음 호출 시 프로듀서를 생성하고,
    이후에는 같은 인스턴스를 반환합니다.

    Returns:
        KafkaProducer: 싱글톤 프로듀서 인스턴스

    사용 예시:
        producer = get_kafka_producer()
        await producer.start("localhost:9092")
        await producer.publish("topic", event)
    """
    global _producer
    if _producer is None:
        _producer = KafkaProducer()
    return _producer
