# Kafka Topic 설계

> **작성일**: 2026-01-27
> **목적**: 네카라쿠배 포트폴리오용 Kafka Event Streaming 구현

## Topic 설계 원칙

### 1. Topic Naming Convention
- 형식: `{context}.{entity}.{event-type}`
- 예: `user.profile.updated`, `message.chat.sent`
- 단순화: `{context}.events` (이벤트 통합)

### 2. Partition 전략
- **Key 기반**: 순서 보장이 필요한 경우
- **Round-Robin**: 순서 무관, 처리량 중요

### 3. Retention Policy
- Short-term: 1-7일 (실시간 이벤트)
- Long-term: 30일+ (감사 로그)

---

## Topic List

| Topic Name | Partitions | Replication | Retention | Cleanup | 설명 |
|------------|------------|-------------|-----------|---------|------|
| `user.events` | 3 | 3 | 7 days | delete | 사용자 이벤트 |
| `user.online_status` | 6 | 3 | 1 hour | delete | 온라인 상태 |
| `friend.events` | 3 | 3 | 7 days | delete | 친구 이벤트 |
| `chat.events` | 3 | 3 | 7 days | delete | 채팅방 이벤트 |
| `message.events` | 10 | 3 | 7 days | delete | 메시지 이벤트 |
| `notification.events` | 3 | 3 | 7 days | delete | 알림 이벤트 |
| `*.dlq` | 1 | 3 | 30 days | delete | Dead Letter Queue |

---

## Topic 생성 스크립트

### Docker Compose에서 자동 생성

```yaml
# infrastructure/docker/docker-compose-kafka.yml

services:
  kafka-setup:
    image: confluentinc/cp-kafka:7.6.0
    depends_on:
      - kafka-1
      - kafka-2
      - kafka-3
    command: |
      bash -c '
        echo "Waiting for Kafka..."
        cub kafka-ready -b kafka-1:9092 3 30

        echo "Creating topics..."

        kafka-topics --create --if-not-exists \
          --bootstrap-server kafka-1:9092 \
          --topic user.events \
          --partitions 3 \
          --replication-factor 3 \
          --config retention.ms=604800000

        kafka-topics --create --if-not-exists \
          --bootstrap-server kafka-1:9092 \
          --topic user.online_status \
          --partitions 6 \
          --replication-factor 3 \
          --config retention.ms=3600000

        kafka-topics --create --if-not-exists \
          --bootstrap-server kafka-1:9092 \
          --topic friend.events \
          --partitions 3 \
          --replication-factor 3 \
          --config retention.ms=604800000

        kafka-topics --create --if-not-exists \
          --bootstrap-server kafka-1:9092 \
          --topic chat.events \
          --partitions 3 \
          --replication-factor 3 \
          --config retention.ms=604800000

        kafka-topics --create --if-not-exists \
          --bootstrap-server kafka-1:9092 \
          --topic message.events \
          --partitions 10 \
          --replication-factor 3 \
          --config retention.ms=604800000

        kafka-topics --create --if-not-exists \
          --bootstrap-server kafka-1:9092 \
          --topic notification.events \
          --partitions 3 \
          --replication-factor 3 \
          --config retention.ms=604800000

        echo "Topics created successfully!"
      '
```

### Python 스크립트로 생성

```python
# scripts/create_kafka_topics.py

from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

KAFKA_BOOTSTRAP_SERVERS = 'localhost:9092'

topics = [
    NewTopic(
        name='user.events',
        num_partitions=3,
        replication_factor=3,
        topic_configs={'retention.ms': '604800000'}  # 7 days
    ),
    NewTopic(
        name='user.online_status',
        num_partitions=6,
        replication_factor=3,
        topic_configs={'retention.ms': '3600000'}  # 1 hour
    ),
    NewTopic(
        name='friend.events',
        num_partitions=3,
        replication_factor=3,
        topic_configs={'retention.ms': '604800000'}
    ),
    NewTopic(
        name='chat.events',
        num_partitions=3,
        replication_factor=3,
        topic_configs={'retention.ms': '604800000'}
    ),
    NewTopic(
        name='message.events',
        num_partitions=10,
        replication_factor=3,
        topic_configs={'retention.ms': '604800000'}
    ),
    NewTopic(
        name='notification.events',
        num_partitions=3,
        replication_factor=3,
        topic_configs={'retention.ms': '604800000'}
    ),
]

def create_topics():
    admin_client = KafkaAdminClient(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        client_id='topic-creator'
    )

    try:
        admin_client.create_topics(new_topics=topics, validate_only=False)
        print("✅ All topics created successfully!")

    except TopicAlreadyExistsError:
        print("⚠️ Some topics already exist")

    finally:
        admin_client.close()

if __name__ == '__main__':
    create_topics()
```

---

## Partitioning 전략 상세

### message.events (10 partitions)

**Key**: `room_id`

**이유**:
- 같은 채팅방의 메시지는 순서 보장 필요
- room_id를 Key로 사용 → 같은 파티션에 할당
- High-throughput (초당 수백~수천 건)

**예시**:
```python
await producer.send(
    topic='message.events',
    key=str(room_id),  # room_id = 123
    value=message_data
)
# → Partition = hash(123) % 10 = Partition 3
# → room_id=123의 모든 메시지는 Partition 3으로
```

**효과**:
- 10개 Consumer가 병렬 처리 가능
- 채팅방별 독립적 처리

---

### user.online_status (6 partitions)

**Key**: `user_id`

**이유**:
- High-frequency (로그인/로그아웃, heartbeat)
- 빠른 처리 위해 파티션 수 증가
- 순서는 덜 중요 (최신 상태만 중요)

---

### user.events, friend.events, chat.events (3 partitions)

**Key**: `user_id` 또는 `entity_id`

**이유**:
- Medium-frequency
- 3개 파티션으로 충분한 처리량

---

## Consumer Group 설계

### notification-consumer-group

```python
{
    'group_id': 'notification-consumer-group',
    'topics': [
        'user.events',
        'friend.events',
        'message.events'
    ],
    'num_consumers': 3,
    'purpose': 'SSE 실시간 알림 전송'
}
```

**Partition 할당**:
- Consumer 1: `message.events` Partition 0-3
- Consumer 2: `message.events` Partition 4-7
- Consumer 3: `message.events` Partition 8-9 + other topics

---

### analytics-consumer-group

```python
{
    'group_id': 'analytics-consumer-group',
    'topics': ['*'],  # 모든 토픽
    'num_consumers': 2,
    'purpose': '실시간 통계 및 분석'
}
```

**특징**:
- 모든 이벤트 수신 (별도 Consumer Group)
- notification-consumer-group과 독립적

---

## Offset 관리 전략

### Auto-commit (Default)

```python
consumer = AIOKafkaConsumer(
    'message.events',
    group_id='notification-consumer-group',
    enable_auto_commit=True,  # 자동 커밋
    auto_commit_interval_ms=5000  # 5초마다
)
```

**장점**: 간단함
**단점**: 처리 실패 시 메시지 손실 가능

---

### Manual-commit (Recommended for Production)

```python
consumer = AIOKafkaConsumer(
    'message.events',
    group_id='notification-consumer-group',
    enable_auto_commit=False  # 수동 커밋
)

async for msg in consumer:
    try:
        # 이벤트 처리
        await handle_event(msg.value)

        # 처리 성공 후 수동 커밋
        await consumer.commit()

    except Exception as e:
        # 처리 실패 시 커밋 안함 → 재처리
        logger.error(f"Event processing failed: {e}")
```

**장점**: at-least-once 보장
**단점**: 복잡도 증가

---

## Topic Monitoring

### 주요 메트릭

1. **Producer Metrics**
   - `kafka_producer_record_send_rate`: 초당 전송 메시지 수
   - `kafka_producer_request_latency_avg`: 평균 전송 지연

2. **Consumer Metrics**
   - `kafka_consumer_records_consumed_rate`: 초당 소비 메시지 수
   - `kafka_consumer_lag`: Consumer Lag (처리 지연)

3. **Topic Metrics**
   - `kafka_topic_partition_current_offset`: 현재 Offset
   - `kafka_topic_partition_earliest_offset`: 가장 오래된 Offset

---

## 예상 처리량 (부하 테스트 목표)

| Topic | Events/sec | Data/sec | Description |
|-------|-----------|----------|-------------|
| `message.events` | 1,000 | 1 MB/s | 메시지 전송 (평균 1KB) |
| `user.online_status` | 500 | 50 KB/s | 온라인 상태 변경 |
| `friend.events` | 100 | 10 KB/s | 친구 요청/수락 |
| `user.events` | 50 | 5 KB/s | 회원가입/프로필 |
| **Total** | **1,650** | **1.065 MB/s** | |

---

## Topic 설정 최적화

### High-throughput Topics (message.events)

```bash
kafka-configs --alter --entity-type topics --entity-name message.events \
  --add-config compression.type=snappy \
  --add-config segment.bytes=1073741824 \
  --add-config retention.bytes=10737418240 \
  --bootstrap-server localhost:9092
```

**compression.type=snappy**: 압축으로 처리량 향상
**segment.bytes=1GB**: 세그먼트 크기 증가 (I/O 최적화)
**retention.bytes=10GB**: 크기 기반 retention

---

### Low-latency Topics (user.online_status)

```bash
kafka-configs --alter --entity-type topics --entity-name user.online_status \
  --add-config min.insync.replicas=2 \
  --add-config compression.type=lz4 \
  --add-config retention.ms=3600000 \
  --bootstrap-server localhost:9092
```

**min.insync.replicas=2**: 신뢰성과 속도 균형
**compression.type=lz4**: 빠른 압축
**retention.ms=1hour**: 짧은 보관 (메모리 절약)

---

## 다음 단계

1. **Kafka Docker Compose 작성** - 3 brokers + Zookeeper
2. **Producer/Consumer 구현** - Python aiokafka
3. **Monitoring 설정** - Prometheus + Grafana
4. **부하 테스트** - k6로 처리량 측정

---

## References

- [Kafka Topic Configuration](https://kafka.apache.org/documentation/#topicconfigs)
- [Kafka Partitioning](https://www.confluent.io/blog/how-choose-number-topics-partitions-kafka-cluster/)
- [Consumer Group](https://docs.confluent.io/platform/current/clients/consumer.html)
