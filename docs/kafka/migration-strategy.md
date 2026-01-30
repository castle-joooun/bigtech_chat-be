# Redis Pub/Sub → Kafka 마이그레이션 전략

> **작성일**: 2026-01-27
> **목적**: 점진적 마이그레이션 전략 및 실행 계획

## 마이그레이션 개요

### 왜 Kafka로 전환하는가?

| 항목 | Redis Pub/Sub | Kafka |
|------|---------------|-------|
| **메시지 보존** | 없음 (휘발성) | 7일 (설정 가능) |
| **재처리** | 불가능 | Offset 기반 재처리 |
| **처리량** | ~100K msg/s | ~1M+ msg/s |
| **확장성** | 제한적 | 수평 확장 (파티션) |
| **순서 보장** | 채널별 | 파티션별 |
| **포트폴리오 가치** | 낮음 | **높음** ⭐ |

---

## 마이그레이션 단계

### Phase 1: 하이브리드 운영 (1-2주)

**전략**: Redis와 Kafka를 동시에 운영하며 점진적 전환

```
현재 (Redis만 사용)
    ↓
Phase 1 (Redis + Kafka 동시 운영)
    ↓
Phase 2 (Kafka만 사용)
```

#### Step 1.1: Kafka 인프라 구축

```bash
# Kafka 클러스터 시작
cd infrastructure/docker
docker-compose -f docker-compose-kafka.yml up -d

# Topic 생성 확인
docker exec bigtech-kafka-1 kafka-topics --list --bootstrap-server localhost:9092
```

**체크리스트**:
- [ ] Zookeeper 정상 작동
- [ ] 3개 Kafka 브로커 정상 작동
- [ ] 모든 Topic 생성 완료
- [ ] Kafka UI 접속 확인 (http://localhost:8080)

---

#### Step 1.2: Dual Publish (Redis + Kafka)

**현재 코드 (Redis만)**:
```python
# app/api/message.py (기존)

@router.post("/{room_id}", response_model=MessageResponse)
async def send_message(...):
    # 메시지 저장
    message = await message_service.create_message(...)

    # Redis Pub/Sub으로 브로드캐스트
    redis = await get_redis()
    await redis.publish(
        f"room:messages:{room_id}",
        json.dumps(broadcast_data)
    )

    return MessageResponse(**message_dict)
```

**마이그레이션 코드 (Redis + Kafka 동시)**:
```python
# app/api/message.py (수정)

from app.infrastructure.kafka import get_event_producer
from app.domain.events import MessageSent

@router.post("/{room_id}", response_model=MessageResponse)
async def send_message(...):
    # 메시지 저장
    message = await message_service.create_message(...)

    # 1. Redis Pub/Sub (기존 유지 - 안정성)
    redis = await get_redis()
    await redis.publish(
        f"room:messages:{room_id}",
        json.dumps(broadcast_data)
    )

    # 2. Kafka 발행 (신규 추가 - 테스트)
    try:
        event = MessageSent(
            message_id=str(message.id),
            room_id=room_id,
            user_id=current_user.id,
            username=current_user.username,
            content=message_data.content,
            message_type=message_data.message_type,
            timestamp=message.created_at
        )

        producer = get_event_producer()
        await producer.publish(
            topic='message.events',
            event=event,
            key=str(room_id)  # 같은 방의 메시지는 같은 파티션
        )

    except Exception as kafka_error:
        # Kafka 실패 시 로깅만 (Redis는 동작 중)
        logger.error(f"Kafka publish failed (fallback to Redis): {kafka_error}")

    return MessageResponse(**message_dict)
```

**효과**:
- Redis 장애 → Kafka가 백업
- Kafka 장애 → Redis가 백업
- **안전한 전환**

---

#### Step 1.3: Dual Consume (Redis + Kafka)

**SSE 스트리밍 엔드포인트 수정**:

```python
# app/api/message.py

@router.get("/stream/{room_id}")
async def stream_room_messages(...):
    """SSE 스트리밍 (Redis + Kafka 동시 소비)"""

    async def event_generator():
        redis_pubsub = None
        kafka_consumer = None

        try:
            # 1. Redis Pub/Sub 구독 (기존)
            redis = await get_redis()
            redis_pubsub = redis.pubsub()
            await redis_pubsub.subscribe(f"room:messages:{room_id}")

            # 2. Kafka Consumer 시작 (신규)
            from aiokafka import AIOKafkaConsumer
            kafka_consumer = AIOKafkaConsumer(
                'message.events',
                bootstrap_servers=['localhost:19092'],
                group_id=f'sse_room_{room_id}_user_{current_user.id}',
                auto_offset_reset='latest'
            )
            await kafka_consumer.start()

            # 연결 성공 알림
            yield {
                "event": "connected",
                "data": json.dumps({"message": f"Connected to room {room_id}"})
            }

            # 3. Redis와 Kafka를 동시에 listen
            while True:
                # Redis 메시지 확인 (non-blocking)
                redis_msg = await redis_pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
                if redis_msg and redis_msg["type"] == "message":
                    message_data = json.loads(redis_msg["data"])
                    yield {
                        "event": "new_message",
                        "data": json.dumps({**message_data, "source": "redis"})
                    }

                # Kafka 메시지 확인 (non-blocking)
                try:
                    msg = await asyncio.wait_for(
                        kafka_consumer.getone(),
                        timeout=0.1
                    )
                    if msg.value.get('room_id') == room_id:
                        yield {
                            "event": "new_message",
                            "data": json.dumps({**msg.value, "source": "kafka"})
                        }
                except asyncio.TimeoutError:
                    pass

                await asyncio.sleep(0.01)  # CPU 점유율 방지

        finally:
            if redis_pubsub:
                await redis_pubsub.unsubscribe()
            if kafka_consumer:
                await kafka_consumer.stop()

    return EventSourceResponse(event_generator(), ping=30)
```

**테스트**:
- 클라이언트에서 `source: "redis"` 또는 `source: "kafka"` 확인
- 둘 다 정상 작동하는지 검증

---

### Phase 2: Kafka로 완전 전환 (1주)

#### Step 2.1: Redis 제거 (Publish)

```python
# app/api/message.py (최종)

@router.post("/{room_id}", response_model=MessageResponse)
async def send_message(...):
    # 메시지 저장
    message = await message_service.create_message(...)

    # Kafka만 사용 (Redis 제거)
    event = MessageSent(
        message_id=str(message.id),
        room_id=room_id,
        user_id=current_user.id,
        username=current_user.username,
        content=message_data.content,
        message_type=message_data.message_type,
        timestamp=message.created_at
    )

    producer = get_event_producer()
    await producer.publish(
        topic='message.events',
        event=event,
        key=str(room_id)
    )

    return MessageResponse(**message_dict)
```

---

#### Step 2.2: Redis 제거 (Consume)

```python
# app/api/message.py (최종)

@router.get("/stream/{room_id}")
async def stream_room_messages(...):
    """SSE 스트리밍 (Kafka만 사용)"""

    async def event_generator():
        from aiokafka import AIOKafkaConsumer
        consumer = None

        try:
            consumer = AIOKafkaConsumer(
                'message.events',
                bootstrap_servers=['localhost:19092', 'localhost:19093', 'localhost:19094'],
                group_id=f'sse_room_{room_id}_user_{current_user.id}',
                auto_offset_reset='latest'
            )
            await consumer.start()

            # 특정 파티션 할당 (최적화)
            from aiokafka import TopicPartition
            partition = room_id % 10  # message.events는 10 파티션
            tp = TopicPartition('message.events', partition)
            consumer.assign([tp])
            await consumer.seek_to_end(tp)

            yield {
                "event": "connected",
                "data": json.dumps({"message": f"Connected to room {room_id}"})
            }

            # Kafka 메시지 수신
            async for msg in consumer:
                if msg.value.get('room_id') == room_id:
                    yield {
                        "event": "new_message",
                        "data": json.dumps(msg.value)
                    }

        finally:
            if consumer:
                await consumer.stop()

    return EventSourceResponse(event_generator(), ping=30)
```

---

## 온라인 상태 마이그레이션

### 현재 (Redis Pub/Sub)

```python
# app/services/online_status_service.py (기존)

async def update_user_activity(user_id: int) -> bool:
    redis = await get_redis()
    # ... 상태 업데이트

    # Redis Pub/Sub으로 브로드캐스트
    await redis.publish(
        f"user:status:{user_id}",
        json.dumps({"user_id": user_id, "is_online": True, ...})
    )
```

### 마이그레이션 후 (Kafka)

```python
# app/services/online_status_service.py (수정)

from app.infrastructure.kafka import get_event_producer
from app.domain.events import UserOnlineStatusChanged

async def update_user_activity(user_id: int) -> bool:
    redis = await get_redis()
    # ... 상태 업데이트 (Redis는 캐시로만 사용)

    # Kafka로 상태 변경 이벤트 발행
    event = UserOnlineStatusChanged(
        user_id=user_id,
        is_online=True,
        timestamp=datetime.utcnow()
    )

    producer = get_event_producer()
    await producer.publish(
        topic='user.online_status',
        event=event,
        key=str(user_id)
    )
```

---

## 친구 요청 마이그레이션

### 현재 (직접 호출)

```python
# app/api/friend.py (기존)

@router.post("/request/{user_id}")
async def send_friend_request(...):
    friendship = await friendship_service.send_friend_request(...)

    # 알림 로직이 여기에 포함되어 결합도 높음
    # TODO: 알림 전송

    return FriendshipResponse(...)
```

### 마이그레이션 후 (Event-Driven)

```python
# app/api/friend.py (수정)

from app.infrastructure.kafka import get_event_producer
from app.domain.events import FriendRequestSent

@router.post("/request/{user_id}")
async def send_friend_request(...):
    # 1. 친구 요청 생성
    friendship = await friendship_service.send_friend_request(...)

    # 2. Domain Event 발행
    event = FriendRequestSent(
        friendship_id=friendship.id,
        requester_id=current_user.id,
        requester_name=current_user.username,
        addressee_id=user_id,
        addressee_name=participant.username,
        timestamp=friendship.created_at
    )

    producer = get_event_producer()
    await producer.publish(
        topic='friend.events',
        event=event,
        key=str(friendship.id)
    )

    # 3. Notification Service가 이벤트를 소비하여 알림 전송
    # (결합도 낮아짐)

    return FriendshipResponse(...)
```

---

## Notification Service 구현

### 별도 Consumer 프로세스

```python
# app/consumers/notification_consumer.py (신규 파일)

import asyncio
from app.infrastructure.kafka import DomainEventConsumer, get_event_producer
from app.infrastructure.kafka.consumer import NotificationEventHandler
from app.infrastructure.kafka.config import kafka_config

async def main():
    """Notification Consumer 실행"""

    # Producer 시작
    producer = get_event_producer()
    await producer.start()

    # Consumer 시작
    handler = NotificationEventHandler()
    consumer = DomainEventConsumer(
        topics=[
            kafka_config.topic_user_events,
            kafka_config.topic_friend_events,
            kafka_config.topic_message_events
        ],
        group_id='notification-consumer-group',
        handler=handler.handle
    )

    await consumer.start()

    try:
        # 무한 실행
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("Shutting down...")

    finally:
        await consumer.stop()
        await producer.stop()

if __name__ == '__main__':
    asyncio.run(main())
```

**실행 방법**:
```bash
# 별도 터미널에서
python -m app.consumers.notification_consumer
```

---

## FastAPI 앱 시작 시 Producer 초기화

```python
# app/main.py (수정)

from app.infrastructure.kafka import get_event_producer

@app.on_event("startup")
async def startup():
    await init_databases()

    # Kafka Producer 시작
    producer = get_event_producer()
    await producer.start()
    logger.info("Kafka Producer started")

    # Heartbeat 모니터 시작
    heartbeat_monitor = get_heartbeat_monitor()
    await heartbeat_monitor.start()
    logger.info("Heartbeat monitor started")

@app.on_event("shutdown")
async def shutdown():
    # Kafka Producer 중지
    producer = get_event_producer()
    await producer.stop()
    logger.info("Kafka Producer stopped")

    # Heartbeat 모니터 중지
    await heartbeat_monitor.stop()

    await close_databases()
    logger.info("Application shutdown completed")
```

---

## 롤백 계획

### Kafka 장애 시 Redis로 즉시 복귀

```python
# app/infrastructure/kafka/producer.py

class DomainEventProducer:
    async def publish_with_fallback(self, topic: str, event: Any, key: str):
        """Kafka 실패 시 Redis로 폴백"""
        try:
            await self.publish(topic, event, key)

        except Exception as kafka_error:
            logger.error(f"Kafka failed, falling back to Redis: {kafka_error}")

            # Redis Pub/Sub로 폴백
            redis = await get_redis()
            await redis.publish(
                f"fallback:{topic}:{key}",
                json.dumps(event.to_dict())
            )
```

---

## 모니터링

### Kafka Lag 확인

```bash
# Consumer Lag 확인
docker exec bigtech-kafka-1 kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe \
  --group notification-consumer-group
```

### Kafka UI로 확인

- URL: http://localhost:8080
- Topics → message.events
- Consumers → notification-consumer-group

---

## 마이그레이션 체크리스트

### Week 3: Phase 1 (하이브리드)
- [ ] Kafka 클러스터 구축
- [ ] Topic 생성 확인
- [ ] Dual Publish 구현 (Redis + Kafka)
- [ ] Dual Consume 구현
- [ ] 테스트: 두 소스 모두 메시지 수신

### Week 4: Phase 2 (완전 전환)
- [ ] Redis Publish 제거
- [ ] Redis Subscribe 제거
- [ ] Notification Consumer 별도 프로세스 실행
- [ ] 부하 테스트 (k6)
- [ ] 모니터링 대시보드 확인

---

## 예상 문제 및 해결

### 문제 1: Kafka 연결 실패
**증상**: `KafkaConnectionError`
**해결**:
```bash
# Kafka 브로커 상태 확인
docker ps | grep kafka
docker logs bigtech-kafka-1
```

### 문제 2: Topic 없음
**증상**: `UnknownTopicOrPartitionError`
**해결**:
```bash
# Topic 재생성
docker exec bigtech-kafka-1 kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic message.events \
  --partitions 10 \
  --replication-factor 3
```

### 문제 3: Consumer Lag 증가
**증상**: 메시지 처리 지연
**해결**:
- Consumer 인스턴스 증가 (3개 → 6개)
- `max_poll_records` 증가
- 처리 로직 최적화

---

## 다음 단계

1. **Week 5**: MSA 분리 (User, Chat, Friend, Notification Service)
2. **Week 6-7**: Kubernetes 배포
3. **Week 8**: Observability (Prometheus + Grafana + Jaeger)

---

## References

- [Kafka Migration Best Practices](https://www.confluent.io/blog/apache-kafka-migration-guide/)
- [Zero-Downtime Migration](https://engineering.linkedin.com/kafka/running-kafka-scale)
