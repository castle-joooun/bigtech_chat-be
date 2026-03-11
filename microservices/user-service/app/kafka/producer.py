"""
Kafka Producer for User Service
================================

도메인 이벤트를 Kafka 토픽으로 발행하는 프로듀서입니다.

Event-Driven Architecture (이벤트 기반 아키텍처)
-----------------------------------------------
```
┌─────────────────┐     Kafka      ┌─────────────────┐
│  User Service   │ ──────────────▶│  Friend Service │
│  (Producer)     │   user.events  │  (Consumer)     │
└─────────────────┘                └─────────────────┘
        │                                   │
        │  UserRegistered                   │  친구 추천
        │  UserOnlineStatusChanged          │  온라인 상태 알림
        ▼                                   ▼
┌─────────────────────────────────────────────────────┐
│                    Kafka Cluster                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ Partition 0 │  │ Partition 1 │  │ Partition 2 │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────┘
```

설계 패턴
---------
1. Singleton Pattern:
   - 전역 _producer 인스턴스로 단일 프로듀서 보장
   - 연결 풀 재사용으로 리소스 효율화

2. Event Sourcing:
   - 모든 상태 변경을 이벤트로 발행
   - 다른 서비스가 구독하여 상태 동기화

Kafka 설정
----------
| 설정                | 값         | 설명                          |
|--------------------|------------|-------------------------------|
| acks               | 'all'      | 모든 replica 확인 (최고 내구성) |
| compression_type   | 'gzip'     | 메시지 압축 (네트워크 절약)      |
| value_serializer   | JSON       | 메시지 직렬화                   |
| key_serializer     | UTF-8      | 파티션 키 직렬화                |

토픽 설계
---------
| 토픽                    | 이벤트                      | 파티션 키 |
|------------------------|----------------------------|-----------|
| user.events            | UserRegistered             | user_id   |
| user.online_status     | UserOnlineStatusChanged    | user_id   |
| user.profile_updated   | UserProfileUpdated         | user_id   |

에러 핸들링
-----------
- KafkaTimeoutError: 브로커 응답 타임아웃
- KafkaError: 일반 Kafka 에러
- 실패 시 False 반환 (예외 발생하지 않음)

SOLID 원칙
----------
- SRP: Kafka 발행만 담당
- OCP: 새 이벤트 타입 추가 시 코드 수정 없음 (to_dict 인터페이스)
- DIP: 추상화된 이벤트 인터페이스에 의존

사용 예시
---------
```python
from app.kafka.producer import get_event_producer
from app.kafka.events import UserRegistered

producer = get_event_producer()
await producer.start()

await producer.publish(
    topic="user.events",
    event=UserRegistered(
        user_id=123,
        email="test@example.com",
        username="testuser",
        display_name="Test User",
        timestamp=datetime.utcnow()
    ),
    key="123"  # 파티션 키
)

await producer.stop()
```

관련 파일
---------
- app/kafka/events.py: 이벤트 클래스 정의
- main.py: 프로듀서 시작/종료 (lifespan)
- docs/kafka/topic-design.md: 토픽 설계 문서
"""

import json
import logging
from typing import Any, Optional
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError, KafkaTimeoutError

from app.core.config import settings

logger = logging.getLogger(__name__)


class KafkaProducer:
    """
    Kafka Producer for publishing domain events

    이벤트 발행을 담당하는 클래스.
    비동기 Kafka 프로듀서를 래핑하여 도메인 이벤트 발행을 간소화.

    Lifecycle:
        1. __init__(): 인스턴스 생성 (연결 안 함)
        2. start(): Kafka 브로커에 연결
        3. publish(): 이벤트 발행 (반복)
        4. stop(): 연결 종료

    Thread Safety:
        - AIOKafkaProducer는 thread-safe
        - 여러 코루틴에서 동시 publish 가능

    Attributes:
        producer: AIOKafkaProducer 인스턴스
        _started: 시작 여부 플래그
    """

    def __init__(self):
        """
        프로듀서 인스턴스 생성

        실제 Kafka 연결은 start()에서 수행.
        Lazy Initialization 패턴.
        """
        self.producer: Optional[AIOKafkaProducer] = None
        self._started = False

    async def start(self):
        """
        Kafka 프로듀서 시작

        Kafka 브로커에 연결하고 프로듀서를 초기화합니다.
        이미 시작된 경우 경고 로그만 출력.

        설정:
            - bootstrap_servers: 브로커 주소 목록
            - value_serializer: dict → JSON bytes
            - key_serializer: str → bytes
            - acks='all': 모든 replica 확인 (최고 내구성)
            - compression_type='gzip': 메시지 압축

        Raises:
            Exception: Kafka 연결 실패 시 (로그만 출력, 예외 전파 안 함)
        """
        if self._started:
            logger.warning("Producer already started")
            return

        try:
            self.producer = AIOKafkaProducer(
                # 브로커 주소 목록 (쉼표로 구분)
                bootstrap_servers=settings.kafka_bootstrap_servers.split(","),

                # 직렬화 설정
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: str(k).encode('utf-8') if k else None,

                # 내구성 설정
                # 'all': 리더 + 모든 ISR replica 확인 (데이터 손실 방지)
                # '1': 리더만 확인 (성능 우선)
                # '0': 확인 안 함 (최고 성능, 손실 가능)
                acks='all',

                # 압축 (네트워크 대역폭 절약)
                compression_type='gzip',
            )
            await self.producer.start()
            self._started = True
            logger.info("Kafka Producer started successfully")

        except Exception as e:
            logger.error(f"Failed to start Kafka Producer: {e}")
            self._started = False

    async def stop(self):
        """
        Kafka 프로듀서 종료

        버퍼에 남은 메시지를 전송하고 연결을 종료합니다.
        애플리케이션 종료 시 (lifespan shutdown) 호출.

        Graceful Shutdown:
            - 전송 중인 메시지 완료 대기
            - 연결 정리
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
        이벤트를 Kafka 토픽에 발행

        이벤트 객체를 JSON으로 직렬화하여 Kafka에 전송합니다.

        Args:
            topic: Kafka 토픽 이름
            event: 발행할 이벤트 객체 (to_dict() 메서드 필요)
            key: 파티션 키 (같은 키는 같은 파티션 → 순서 보장)

        Returns:
            bool: 발행 성공 여부

        이벤트 인터페이스:
            - to_dict() 메서드가 있으면 호출
            - dict 타입이면 그대로 사용
            - 그 외: ValueError 발생

        파티션 키 사용 이유:
            - 같은 user_id의 이벤트는 같은 파티션에 저장
            - 해당 사용자의 이벤트 순서 보장

        사용 예시:
            success = await producer.publish(
                topic="user.events",
                event=UserRegistered(...),
                key=str(user.id)
            )
        """
        if not self._started or not self.producer:
            logger.warning("Producer not started, skipping publish")
            return False

        try:
            # 이벤트 직렬화
            # - to_dict() 메서드가 있으면 호출 (DomainEvent 클래스)
            # - dict 타입이면 그대로 사용
            if hasattr(event, 'to_dict'):
                event_data = event.to_dict()
            elif isinstance(event, dict):
                event_data = event
            else:
                raise ValueError(f"Unsupported event type: {type(event)}")

            # Kafka에 전송 (동기식 대기)
            # send_and_wait(): 브로커 확인까지 대기
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


# =============================================================================
# Singleton Instance
# =============================================================================

# 모듈 레벨 전역 변수 (Singleton)
_producer: Optional[KafkaProducer] = None


def get_event_producer() -> KafkaProducer:
    """
    싱글톤 프로듀서 인스턴스 획득

    Design Pattern: Singleton
        - 애플리케이션 전체에서 하나의 프로듀서 인스턴스 공유
        - 연결 풀 재사용으로 리소스 효율화

    Returns:
        KafkaProducer: 싱글톤 프로듀서 인스턴스

    사용 예시:
        producer = get_event_producer()
        await producer.publish(...)
    """
    global _producer
    if _producer is None:
        _producer = KafkaProducer()
    return _producer
