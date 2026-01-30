# Domain Events 설계

> **작성일**: 2026-01-27
> **목적**: Kafka를 활용한 Event-Driven Architecture 구현

## Domain Events 개요

### Event란?
- 과거에 발생한 **사실(Fact)**
- 불변(Immutable)
- 시간 정보 포함

### 왜 Domain Events를 사용하는가?
1. **느슨한 결합**: Bounded Context 간 독립성 유지
2. **확장성**: 새로운 이벤트 구독자 추가 용이
3. **감사 추적**: 모든 이벤트 기록
4. **Eventual Consistency**: 결과적 일관성 구현

---

## Event Naming Convention

### 형식
`{Aggregate}{과거형Verb}` (예: `UserRegistered`, `MessageSent`)

### 규칙
- 과거형 사용 (이미 발생한 사실)
- 명확하고 비즈니스 언어로 표현
- Context 이름 포함 (선택사항)

---

## 1. User Context Events

### UserRegistered

```python
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict
import json

@dataclass
class UserRegistered:
    """사용자 등록 이벤트"""
    user_id: int
    email: str
    username: str
    display_name: str
    timestamp: datetime

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict())
```

**발행 시점**: 회원가입 성공 시

**구독자**:
- Notification Service → 환영 알림 전송
- Analytics Service → 신규 가입자 통계

**Kafka Topic**: `user.events`

---

### UserProfileUpdated

```python
@dataclass
class UserProfileUpdated:
    """사용자 프로필 업데이트 이벤트"""
    user_id: int
    display_name: str
    profile_image_url: str
    status_message: str
    timestamp: datetime

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
```

**발행 시점**: 프로필 수정 시

**구독자**:
- Friend Service → 친구 목록의 프로필 정보 업데이트 (캐시)
- Chat Service → 채팅방 목록의 프로필 정보 업데이트

**Kafka Topic**: `user.events`

---

### UserOnlineStatusChanged

```python
@dataclass
class UserOnlineStatusChanged:
    """온라인 상태 변경 이벤트"""
    user_id: int
    is_online: bool
    timestamp: datetime

    def to_dict(self) -> Dict:
        return {
            'user_id': self.user_id,
            'is_online': self.is_online,
            'timestamp': self.timestamp.isoformat()
        }
```

**발행 시점**: 로그인/로그아웃 시, 비활성 타임아웃 시

**구독자**:
- Notification Service → 친구들에게 온라인 상태 브로드캐스트

**Kafka Topic**: `user.online_status`

**특징**: High-frequency event (초당 수백~수천 건)

---

## 2. Friend Context Events

### FriendRequestSent

```python
@dataclass
class FriendRequestSent:
    """친구 요청 전송 이벤트"""
    friendship_id: int
    requester_id: int
    requester_name: str
    addressee_id: int
    addressee_name: str
    timestamp: datetime

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
```

**발행 시점**: 친구 요청 전송 시

**구독자**:
- Notification Service → 수신자에게 알림 전송

**Kafka Topic**: `friend.events`

---

### FriendRequestAccepted

```python
@dataclass
class FriendRequestAccepted:
    """친구 요청 수락 이벤트"""
    friendship_id: int
    requester_id: int
    requester_name: str
    addressee_id: int
    addressee_name: str
    timestamp: datetime

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
```

**발행 시점**: 친구 요청 수락 시

**구독자**:
- Notification Service → 요청자에게 수락 알림
- Analytics Service → 친구 관계 형성 통계

**Kafka Topic**: `friend.events`

---

### FriendRequestRejected / FriendRequestCancelled

동일한 구조 (생략)

**Kafka Topic**: `friend.events`

---

## 3. Chat Context Events

### ChatRoomCreated

```python
@dataclass
class ChatRoomCreated:
    """채팅방 생성 이벤트"""
    room_id: int
    user_1_id: int
    user_2_id: int
    room_type: str  # "direct" or "group"
    timestamp: datetime

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
```

**발행 시점**: 채팅방 생성 시

**구독자**:
- Analytics Service → 채팅방 생성 통계

**Kafka Topic**: `chat.events`

---

### MessageSent

```python
@dataclass
class MessageSent:
    """메시지 전송 이벤트"""
    message_id: str
    room_id: int
    user_id: int
    username: str
    content: str
    message_type: str  # "text", "image", "file"
    created_at: datetime

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        return data
```

**발행 시점**: 메시지 전송 시

**구독자**:
- Notification Service → 상대방에게 SSE로 실시간 전송
- Analytics Service → 메시지 전송 통계
- Search Service → 메시지 검색 인덱싱 (향후)

**Kafka Topic**: `message.events`

**특징**: High-throughput event (초당 수백~수천 건)

---

### MessagesRead

```python
@dataclass
class MessagesRead:
    """메시지 읽음 이벤트"""
    room_id: int
    user_id: int
    message_ids: List[str]
    timestamp: datetime

    def to_dict(self) -> Dict:
        return {
            'room_id': self.room_id,
            'user_id': self.user_id,
            'message_ids': self.message_ids,
            'timestamp': self.timestamp.isoformat()
        }
```

**발행 시점**: 메시지 읽음 처리 시

**구독자**:
- Notification Service → 발신자에게 읽음 상태 업데이트 (선택)

**Kafka Topic**: `message.events`

---

## 4. Notification Context Events

### NotificationSent

```python
@dataclass
class NotificationSent:
    """알림 전송 이벤트"""
    notification_id: str
    user_id: int
    notification_type: str
    title: str
    content: Dict
    timestamp: datetime

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
```

**발행 시점**: 알림 전송 시

**구독자**:
- Analytics Service → 알림 전송 통계

**Kafka Topic**: `notification.events`

---

## Kafka Topic 설계

### Topic List

| Topic Name | Partitions | Replication Factor | Retention | 설명 |
|------------|------------|--------------------|-----------| -----|
| `user.events` | 3 | 3 | 7 days | 사용자 이벤트 |
| `user.online_status` | 6 | 3 | 1 hour | 온라인 상태 (high-frequency) |
| `friend.events` | 3 | 3 | 7 days | 친구 관계 이벤트 |
| `chat.events` | 3 | 3 | 7 days | 채팅방 이벤트 |
| `message.events` | 10 | 3 | 7 days | 메시지 이벤트 (high-throughput) |
| `notification.events` | 3 | 3 | 7 days | 알림 이벤트 |

### Partitioning 전략

**user.events, friend.events, chat.events**
- Partition Key: `user_id`
- 같은 사용자의 이벤트는 순서 보장

**message.events**
- Partition Key: `room_id`
- 같은 채팅방의 메시지는 순서 보장

**user.online_status**
- Partition Key: `user_id`
- High-frequency이므로 파티션 수 증가 (6개)

---

## Consumer Group 설계

### notification-consumer-group
**구독 Topic**: 모든 Topic
**목적**: 실시간 알림 전송 (SSE)
**Instance 수**: 3개 (로드 밸런싱)

### analytics-consumer-group
**구독 Topic**: 모든 Topic
**목적**: 실시간 분석 및 통계
**Instance 수**: 1개

### search-indexer-group (향후)
**구독 Topic**: `message.events`
**목적**: 메시지 검색 인덱싱
**Instance 수**: 2개

---

## Event Producer 구현

### KafkaProducer 래퍼

```python
from aiokafka import AIOKafkaProducer
import json
from typing import Any
from app.core.config import settings

class DomainEventProducer:
    """Domain Events를 Kafka로 발행하는 Producer"""

    def __init__(self):
        self.producer: AIOKafkaProducer = None

    async def start(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: str(k).encode('utf-8') if k else None,
            acks='all',  # 모든 replica가 확인해야 성공
            compression_type='snappy',
            max_in_flight_requests_per_connection=5,
            retries=3,
            request_timeout_ms=30000
        )
        await self.producer.start()

    async def stop(self):
        if self.producer:
            await self.producer.stop()

    async def publish(self, topic: str, event: Any, key: str = None):
        """Domain Event 발행"""
        try:
            # Event를 dict로 변환
            if hasattr(event, 'to_dict'):
                event_data = event.to_dict()
            else:
                event_data = event

            # Kafka로 전송
            await self.producer.send_and_wait(
                topic=topic,
                value=event_data,
                key=key
            )

            print(f"[Event Published] Topic: {topic}, Key: {key}, Event: {event.__class__.__name__}")

        except Exception as e:
            print(f"[Event Publish Failed] Topic: {topic}, Error: {e}")
            # 에러 처리: Dead Letter Queue로 전송 or 로깅
            raise

# 싱글톤 인스턴스
event_producer = DomainEventProducer()
```

### Application Service에서 사용

```python
from app.infrastructure.kafka.producer import event_producer

class UserApplicationService:
    """User Use Cases"""

    async def register_user(self, email: str, username: str, password: str):
        # 1. User Aggregate 생성
        password_hash = get_password_hash(password)
        user = User(
            id=None,  # Repository에서 할당
            email=email,
            username=username,
            password_hash=password_hash,
            display_name=username,
            profile=Profile(),
            is_online=False,
            last_seen_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # 2. Repository에 저장
        saved_user = await user_repository.save(user)

        # 3. Domain Event 발행
        event = UserRegistered(
            user_id=saved_user.id,
            email=saved_user.email,
            username=saved_user.username,
            display_name=saved_user.display_name,
            timestamp=saved_user.created_at
        )

        await event_producer.publish(
            topic='user.events',
            event=event,
            key=str(saved_user.id)  # Partition Key
        )

        return saved_user
```

---

## Event Consumer 구현

### KafkaConsumer 래퍼

```python
from aiokafka import AIOKafkaConsumer
import json
import asyncio

class DomainEventConsumer:
    """Domain Events를 Kafka에서 소비하는 Consumer"""

    def __init__(self, topics: List[str], group_id: str, handler):
        self.topics = topics
        self.group_id = group_id
        self.handler = handler  # 이벤트 처리 함수
        self.consumer: AIOKafkaConsumer = None
        self.running = False

    async def start(self):
        self.consumer = AIOKafkaConsumer(
            *self.topics,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=self.group_id,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',  # 최초 실행 시 처음부터 읽기
            enable_auto_commit=True,
            max_poll_records=100
        )
        await self.consumer.start()
        self.running = True

        # 백그라운드 태스크로 이벤트 소비
        asyncio.create_task(self._consume_loop())

    async def stop(self):
        self.running = False
        if self.consumer:
            await self.consumer.stop()

    async def _consume_loop(self):
        """이벤트 소비 루프"""
        try:
            async for msg in self.consumer:
                try:
                    # 이벤트 처리
                    await self.handler(msg.topic, msg.key, msg.value)

                except Exception as e:
                    print(f"[Event Consume Error] Topic: {msg.topic}, Offset: {msg.offset}, Error: {e}")
                    # Dead Letter Queue로 전송 (향후 구현)

        except Exception as e:
            print(f"[Consumer Loop Error]: {e}")
```

### Notification Service의 Consumer

```python
from app.infrastructure.kafka.consumer import DomainEventConsumer

class NotificationEventHandler:
    """알림 서비스의 이벤트 핸들러"""

    async def handle_event(self, topic: str, key: str, event_data: dict):
        """이벤트 라우팅"""
        if topic == 'user.events':
            await self._handle_user_event(event_data)
        elif topic == 'friend.events':
            await self._handle_friend_event(event_data)
        elif topic == 'message.events':
            await self._handle_message_event(event_data)

    async def _handle_friend_event(self, event_data: dict):
        """친구 이벤트 처리"""
        event_type = event_data.get('__type__')  # 이벤트 타입 (향후 추가)

        if 'requester_id' in event_data and 'addressee_id' in event_data:
            # FriendRequestSent 이벤트
            await self._send_friend_request_notification(
                requester_id=event_data['requester_id'],
                requester_name=event_data['requester_name'],
                addressee_id=event_data['addressee_id']
            )

    async def _send_friend_request_notification(self, requester_id, requester_name, addressee_id):
        """친구 요청 알림 전송"""
        # SSE를 통해 실시간 전송
        notification = {
            'type': 'friend_request',
            'title': f'{requester_name}님이 친구 요청을 보냈습니다',
            'data': {
                'requester_id': requester_id,
                'requester_name': requester_name
            }
        }

        # Redis Pub/Sub로 SSE 연결된 클라이언트에게 전송
        redis = await get_redis()
        await redis.publish(
            f'user:notifications:{addressee_id}',
            json.dumps(notification)
        )

# Consumer 시작
notification_consumer = DomainEventConsumer(
    topics=['user.events', 'friend.events', 'message.events'],
    group_id='notification-consumer-group',
    handler=NotificationEventHandler().handle_event
)

# FastAPI 시작 시
@app.on_event("startup")
async def startup():
    await notification_consumer.start()

@app.on_event("shutdown")
async def shutdown():
    await notification_consumer.stop()
```

---

## Dead Letter Queue (DLQ) 구현

### DLQ Topic
- `user.events.dlq`
- `friend.events.dlq`
- `message.events.dlq`

### DLQ 전송 조건
- 처리 실패 3회 이상
- Deserialization 실패
- 비즈니스 로직 예외

```python
class DomainEventConsumer:
    async def _consume_loop(self):
        async for msg in self.consumer:
            retry_count = 0
            max_retries = 3

            while retry_count < max_retries:
                try:
                    await self.handler(msg.topic, msg.key, msg.value)
                    break  # 성공 시 루프 탈출

                except Exception as e:
                    retry_count += 1
                    print(f"[Retry {retry_count}/{max_retries}] Topic: {msg.topic}, Error: {e}")

                    if retry_count >= max_retries:
                        # DLQ로 전송
                        await self._send_to_dlq(msg.topic, msg.key, msg.value, str(e))

    async def _send_to_dlq(self, topic: str, key: str, value: dict, error: str):
        """Dead Letter Queue로 전송"""
        dlq_topic = f"{topic}.dlq"
        dlq_message = {
            'original_topic': topic,
            'original_key': key,
            'original_value': value,
            'error': error,
            'timestamp': datetime.utcnow().isoformat()
        }

        await event_producer.publish(
            topic=dlq_topic,
            event=dlq_message,
            key=key
        )
        print(f"[DLQ] Message sent to {dlq_topic}")
```

---

## 다음 단계

1. **Kafka Docker 설정** - docker-compose에 Kafka 추가
2. **Producer/Consumer 구현** - 실제 코드 작성
3. **Topic 생성 스크립트** - 자동화
4. **모니터링** - Kafka Lag, Throughput

---

## References

- [Kafka Documentation](https://kafka.apache.org/documentation/)
- [Event-Driven Microservices](https://www.oreilly.com/library/view/building-event-driven-microservices/9781492057888/)
- [Domain Events Pattern](https://martinfowler.com/eaaDev/DomainEvent.html)
