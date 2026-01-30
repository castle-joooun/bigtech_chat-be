# Jaeger Distributed Tracing

## 📋 목차
1. [분산 추적 개요](#분산-추적-개요)
2. [OpenTelemetry 설정](#opentelemetry-설정)
3. [FastAPI Integration](#fastapi-integration)
4. [Kubernetes 배포](#kubernetes-배포)
5. [Trace 분석](#trace-분석)

---

## 분산 추적 개요

### 사용 목적
- **MSA 환경의 요청 추적**: 여러 마이크로서비스를 거치는 요청의 전체 흐름 파악
- **성능 병목 지점 식별**: 각 서비스/구간별 처리 시간 측정
- **에러 디버깅**: 분산 환경에서의 에러 발생 지점 추적
- **서비스 의존성 파악**: 서비스 간 호출 관계 시각화

### 아키텍처
```
┌──────────────┐
│ User Service │──────┐
└──────────────┘      │
                      │   ┌────────────────┐
┌──────────────┐      ├──→│ Jaeger Agent  │
│ Chat Service │──────┤   │ (Sidecar)     │
└──────────────┘      │   └───────┬────────┘
                      │           │
┌──────────────┐      │           ↓
│Friend Service│──────┤   ┌────────────────┐    ┌────────────────┐
└──────────────┘      │   │ Jaeger         │───→│ Jaeger Query   │
                      │   │ Collector      │    │ (UI)           │
┌──────────────┐      │   └───────┬────────┘    └────────────────┘
│ Notif Service│──────┘           │
└──────────────┘                  ↓
                          ┌────────────────┐
                          │ Elasticsearch  │
                          │ (Storage)      │
                          └────────────────┘
```

### Trace 예시: "메시지 전송" 요청
```
POST /rooms/123/messages
│
├─ [User Service] GET /users/me (인증)         ──── 15ms
│
├─ [Chat Service] POST /rooms/123/messages     ──── 120ms
│   │
│   ├─ [MySQL] SELECT room_participants        ──── 8ms
│   ├─ [MongoDB] INSERT message                ──── 25ms
│   ├─ [Kafka] PUBLISH message.events          ──── 12ms
│   └─ [Redis] UPDATE last_message_time        ──── 5ms
│
└─ [Notification Service] (Kafka Consumer)     ──── 45ms
    │
    ├─ [Kafka] CONSUME message.events          ──── 10ms
    └─ [SSE] SEND notification                 ──── 35ms

Total Duration: 180ms
```

---

## OpenTelemetry 설정

### 1. 의존성 설치

`requirements.txt`:
```txt
# OpenTelemetry 핵심 라이브러리
opentelemetry-api==1.21.0
opentelemetry-sdk==1.21.0
opentelemetry-instrumentation==0.42b0

# FastAPI 자동 계측
opentelemetry-instrumentation-fastapi==0.42b0

# HTTP 클라이언트 계측
opentelemetry-instrumentation-httpx==0.42b0
opentelemetry-instrumentation-requests==0.42b0

# 데이터베이스 계측
opentelemetry-instrumentation-sqlalchemy==0.42b0
opentelemetry-instrumentation-pymongo==0.42b0
opentelemetry-instrumentation-redis==0.42b0

# Kafka 계측
opentelemetry-instrumentation-kafka-python==0.42b0

# Jaeger Exporter
opentelemetry-exporter-jaeger==1.21.0

# OTLP Exporter (권장)
opentelemetry-exporter-otlp==1.21.0
```

```bash
pip install -r requirements.txt
```

### 2. Tracer 초기화

`app/infrastructure/tracing/tracer.py`:
```python
"""
OpenTelemetry Tracer 설정
"""
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
import os
import logging

logger = logging.getLogger(__name__)


def setup_tracing(app, service_name: str, service_version: str = "1.0.0"):
    """
    OpenTelemetry Tracing 설정

    Args:
        app: FastAPI 애플리케이션
        service_name: 서비스 이름 (user-service, chat-service, etc.)
        service_version: 서비스 버전
    """

    # Jaeger Collector 엔드포인트
    jaeger_endpoint = os.getenv(
        "JAEGER_ENDPOINT",
        "http://jaeger-collector:4317"
    )

    # Resource 정의 (서비스 메타데이터)
    resource = Resource(attributes={
        SERVICE_NAME: service_name,
        SERVICE_VERSION: service_version,
        "environment": os.getenv("ENVIRONMENT", "development"),
        "deployment.namespace": os.getenv("NAMESPACE", "bigtech-chat")
    })

    # TracerProvider 설정
    provider = TracerProvider(resource=resource)

    # OTLP Exporter 설정 (Jaeger로 전송)
    otlp_exporter = OTLPSpanExporter(
        endpoint=jaeger_endpoint,
        insecure=True  # 개발 환경용 (프로덕션에서는 TLS 사용)
    )

    # BatchSpanProcessor로 성능 최적화
    span_processor = BatchSpanProcessor(otlp_exporter)
    provider.add_span_processor(span_processor)

    # Global TracerProvider 설정
    trace.set_tracer_provider(provider)

    # FastAPI 자동 계측
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="/health,/metrics"  # 헬스체크는 제외
    )

    # HTTP Client 계측
    HTTPXClientInstrumentor().instrument()

    # Redis 계측
    RedisInstrumentor().instrument()

    logger.info(f"✅ OpenTelemetry tracing enabled: {service_name} → {jaeger_endpoint}")

    return provider


def get_tracer(name: str):
    """Tracer 인스턴스 반환"""
    return trace.get_tracer(name)


# ===================================
# Custom Span Helpers
# ===================================

def trace_function(name: str = None):
    """함수 실행을 자동으로 Span으로 추적하는 데코레이터"""
    def decorator(func):
        import functools

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            span_name = name or f"{func.__module__}.{func.__name__}"

            with tracer.start_as_current_span(span_name) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("function.result", str(result)[:100])
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            span_name = name or f"{func.__module__}.{func.__name__}"

            with tracer.start_as_current_span(span_name) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("function.result", str(result)[:100])
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise

        # async 함수인지 sync 함수인지 판별
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def add_span_attributes(**attributes):
    """현재 Span에 속성 추가"""
    current_span = trace.get_current_span()
    if current_span:
        for key, value in attributes.items():
            current_span.set_attribute(key, value)


def add_span_event(name: str, attributes: dict = None):
    """현재 Span에 이벤트 추가"""
    current_span = trace.get_current_span()
    if current_span:
        current_span.add_event(name, attributes or {})
```

---

## FastAPI Integration

### 1. 애플리케이션에 Tracing 적용

`app/main.py`:
```python
from fastapi import FastAPI
from app.infrastructure.tracing.tracer import setup_tracing
import os

# 서비스 이름 환경 변수에서 가져오기
SERVICE_NAME = os.getenv("SERVICE_NAME", "chat-service")

app = FastAPI(title=SERVICE_NAME)

# OpenTelemetry Tracing 설정
setup_tracing(app, service_name=SERVICE_NAME, service_version="1.0.0")

# 기존 라우터 등록
# ...
```

### 2. 수동 Span 생성

`app/api/chat.py`:
```python
from fastapi import APIRouter, Depends
from app.infrastructure.tracing.tracer import (
    get_tracer,
    trace_function,
    add_span_attributes,
    add_span_event
)
from opentelemetry import trace

router = APIRouter()
tracer = get_tracer(__name__)


@router.post("/rooms/{room_id}/messages")
async def send_message(
    room_id: int,
    message: MessageCreate,
    current_user: User = Depends(get_current_user)
):
    """메시지 전송 (분산 추적 적용)"""

    # 부모 Span은 FastAPIInstrumentor가 자동 생성
    # 추가 속성 설정
    add_span_attributes(
        user_id=current_user.id,
        room_id=room_id,
        message_type=message.message_type
    )

    # Child Span 1: 권한 확인
    with tracer.start_as_current_span("check_room_permission") as span:
        span.set_attribute("room_id", room_id)
        has_permission = await check_room_permission(current_user.id, room_id)

        if not has_permission:
            span.set_status(trace.Status(trace.StatusCode.ERROR, "Permission denied"))
            raise HTTPException(status_code=403)

    # Child Span 2: 메시지 저장
    with tracer.start_as_current_span("save_message_to_mongodb") as span:
        span.set_attribute("db.system", "mongodb")
        span.set_attribute("db.operation", "insert")

        msg = await message_repository.save(message)

        span.set_attribute("message_id", str(msg.id))
        add_span_event("message_saved", {"message_id": str(msg.id)})

    # Child Span 3: Kafka 이벤트 발행
    with tracer.start_as_current_span("publish_kafka_event") as span:
        span.set_attribute("messaging.system", "kafka")
        span.set_attribute("messaging.destination", "message.events")
        span.set_attribute("messaging.destination_kind", "topic")

        event = MessageSent(
            message_id=str(msg.id),
            room_id=room_id,
            user_id=current_user.id,
            username=current_user.username,
            content=message.content,
            message_type=message.message_type,
            timestamp=datetime.now(timezone.utc)
        )

        await kafka_producer.publish(
            topic='message.events',
            event=event,
            key=str(room_id)
        )

        add_span_event("kafka_event_published")

    return {"message_id": str(msg.id)}


@trace_function(name="check_room_permission")
async def check_room_permission(user_id: int, room_id: int) -> bool:
    """방 참여 권한 확인 (자동 Span 생성)"""

    # MySQL 쿼리 (SQLAlchemyInstrumentor가 자동으로 Span 생성)
    participant = await db.execute(
        select(ChatRoomParticipant)
        .where(
            ChatRoomParticipant.room_id == room_id,
            ChatRoomParticipant.user_id == user_id
        )
    )

    return participant.scalars().first() is not None
```

### 3. Kafka Producer에 Trace Context 전파

`app/infrastructure/kafka/producer.py`:
```python
from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from typing import Any, Optional

class DomainEventProducer:
    """Domain Events를 Kafka로 발행하는 Producer (with Tracing)"""

    async def publish(
        self,
        topic: str,
        event: Any,
        key: Optional[str] = None
    ):
        if not self._started or not self.producer:
            raise RuntimeError("Producer not started")

        # Span 시작
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(f"kafka.publish.{topic}") as span:
            span.set_attribute("messaging.system", "kafka")
            span.set_attribute("messaging.destination", topic)
            span.set_attribute("messaging.destination_kind", "topic")

            try:
                # Event를 dict로 변환
                if isinstance(event, DomainEvent):
                    event_data = event.to_dict()
                elif isinstance(event, dict):
                    event_data = event
                else:
                    raise ValueError(f"Unsupported event type: {type(event)}")

                # Trace Context를 Kafka Headers에 주입
                headers = {}
                TraceContextTextMapPropagator().inject(headers)

                kafka_headers = [
                    (k, v.encode('utf-8') if isinstance(v, str) else v)
                    for k, v in headers.items()
                ]

                # Kafka로 전송
                metadata = await self.producer.send_and_wait(
                    topic=topic,
                    value=event_data,
                    key=key,
                    headers=kafka_headers  # Trace Context 포함
                )

                span.set_attribute("messaging.kafka.partition", metadata.partition)
                span.set_attribute("messaging.kafka.offset", metadata.offset)

                logger.info(
                    f"[Event Published] Topic: {topic}, "
                    f"Partition: {metadata.partition}, "
                    f"Offset: {metadata.offset}"
                )

            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise
```

### 4. Kafka Consumer에서 Trace Context 추출

`app/infrastructure/kafka/consumer.py`:
```python
from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

class DomainEventConsumer:
    """Domain Events를 Kafka에서 소비하는 Consumer (with Tracing)"""

    async def _handle_message(self, msg):
        """메시지 처리 (Trace Context 복원)"""

        # Kafka Headers에서 Trace Context 추출
        headers_dict = {}
        if msg.headers:
            for key, value in msg.headers:
                if isinstance(value, bytes):
                    headers_dict[key] = value.decode('utf-8')
                else:
                    headers_dict[key] = value

        # Trace Context 복원
        ctx = TraceContextTextMapPropagator().extract(carrier=headers_dict)

        tracer = trace.get_tracer(__name__)

        # 부모 Span을 복원하여 Child Span 생성
        with tracer.start_as_current_span(
            f"kafka.consume.{msg.topic}",
            context=ctx
        ) as span:
            span.set_attribute("messaging.system", "kafka")
            span.set_attribute("messaging.source", msg.topic)
            span.set_attribute("messaging.kafka.partition", msg.partition)
            span.set_attribute("messaging.kafka.offset", msg.offset)
            span.set_attribute("messaging.consumer_group", self.group_id)

            retry_count = 0
            max_retries = 3

            while retry_count < max_retries:
                try:
                    # Handler 호출
                    await self.handler(msg.topic, msg.key, msg.value)

                    span.set_attribute("retry_count", retry_count)
                    span.add_event("message_processed_successfully")
                    break

                except Exception as e:
                    retry_count += 1
                    span.add_event(f"retry_{retry_count}", {"error": str(e)})

                    if retry_count >= max_retries:
                        span.record_exception(e)
                        span.set_status(trace.Status(trace.StatusCode.ERROR))
                        await self._send_to_dlq(msg, str(e))
                        break

                    import asyncio
                    await asyncio.sleep(0.5 * retry_count)
```

### 5. 데이터베이스 쿼리 자동 계측

`app/database/mysql.py`:
```python
from sqlalchemy.ext.asyncio import create_async_engine
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

# MySQL 엔진 생성
engine = create_async_engine(settings.mysql_url, echo=True)

# SQLAlchemy 자동 계측
SQLAlchemyInstrumentor().instrument(
    engine=engine.sync_engine,
    service="chat-service-mysql"
)
```

`app/database/mongodb.py`:
```python
from motor.motor_asyncio import AsyncIOMotorClient
from opentelemetry.instrumentation.pymongo import PymongoInstrumentor

# MongoDB 클라이언트 생성
client = AsyncIOMotorClient(settings.mongo_url)

# PyMongo 자동 계측
PymongoInstrumentor().instrument()
```

---

## Kubernetes 배포

### 1. Jaeger All-in-One (개발 환경)

`infrastructure/k8s/manifests/jaeger-all-in-one.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jaeger
  namespace: bigtech-chat
spec:
  replicas: 1
  selector:
    matchLabels:
      app: jaeger
  template:
    metadata:
      labels:
        app: jaeger
    spec:
      containers:
        - name: jaeger
          image: jaegertracing/all-in-one:1.51
          env:
            - name: COLLECTOR_OTLP_ENABLED
              value: "true"
          ports:
            - containerPort: 16686  # Jaeger UI
              name: ui
            - containerPort: 4317   # OTLP gRPC
              name: otlp-grpc
            - containerPort: 4318   # OTLP HTTP
              name: otlp-http
            - containerPort: 14250  # Jaeger gRPC
              name: jaeger-grpc
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: jaeger-collector
  namespace: bigtech-chat
spec:
  type: ClusterIP
  ports:
    - port: 4317
      targetPort: 4317
      name: otlp-grpc
    - port: 4318
      targetPort: 4318
      name: otlp-http
    - port: 14250
      targetPort: 14250
      name: jaeger-grpc
  selector:
    app: jaeger
---
apiVersion: v1
kind: Service
metadata:
  name: jaeger-query
  namespace: bigtech-chat
spec:
  type: ClusterIP
  ports:
    - port: 16686
      targetPort: 16686
      name: ui
  selector:
    app: jaeger
```

### 2. Jaeger Production (Elasticsearch 백엔드)

`infrastructure/k8s/manifests/jaeger-production.yaml`:
```yaml
# Elasticsearch for Jaeger
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: elasticsearch
  namespace: bigtech-chat
spec:
  serviceName: elasticsearch
  replicas: 3
  selector:
    matchLabels:
      app: elasticsearch
  template:
    metadata:
      labels:
        app: elasticsearch
    spec:
      containers:
        - name: elasticsearch
          image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
          env:
            - name: discovery.type
              value: "zen"
            - name: ES_JAVA_OPTS
              value: "-Xms512m -Xmx512m"
            - name: xpack.security.enabled
              value: "false"
          ports:
            - containerPort: 9200
              name: http
            - containerPort: 9300
              name: transport
          volumeMounts:
            - name: data
              mountPath: /usr/share/elasticsearch/data
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 20Gi
---
apiVersion: v1
kind: Service
metadata:
  name: elasticsearch
  namespace: bigtech-chat
spec:
  clusterIP: None
  ports:
    - port: 9200
      name: http
    - port: 9300
      name: transport
  selector:
    app: elasticsearch
---
# Jaeger Collector
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jaeger-collector
  namespace: bigtech-chat
spec:
  replicas: 3
  selector:
    matchLabels:
      app: jaeger-collector
  template:
    metadata:
      labels:
        app: jaeger-collector
    spec:
      containers:
        - name: jaeger-collector
          image: jaegertracing/jaeger-collector:1.51
          env:
            - name: SPAN_STORAGE_TYPE
              value: "elasticsearch"
            - name: ES_SERVER_URLS
              value: "http://elasticsearch:9200"
            - name: COLLECTOR_OTLP_ENABLED
              value: "true"
          ports:
            - containerPort: 4317
              name: otlp-grpc
            - containerPort: 4318
              name: otlp-http
            - containerPort: 14250
              name: jaeger-grpc
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
---
apiVersion: v1
kind: Service
metadata:
  name: jaeger-collector
  namespace: bigtech-chat
spec:
  type: ClusterIP
  ports:
    - port: 4317
      targetPort: 4317
      name: otlp-grpc
    - port: 4318
      targetPort: 4318
      name: otlp-http
  selector:
    app: jaeger-collector
---
# Jaeger Query (UI)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jaeger-query
  namespace: bigtech-chat
spec:
  replicas: 2
  selector:
    matchLabels:
      app: jaeger-query
  template:
    metadata:
      labels:
        app: jaeger-query
    spec:
      containers:
        - name: jaeger-query
          image: jaegertracing/jaeger-query:1.51
          env:
            - name: SPAN_STORAGE_TYPE
              value: "elasticsearch"
            - name: ES_SERVER_URLS
              value: "http://elasticsearch:9200"
          ports:
            - containerPort: 16686
              name: ui
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: jaeger-query
  namespace: bigtech-chat
spec:
  type: ClusterIP
  ports:
    - port: 16686
      targetPort: 16686
      name: ui
  selector:
    app: jaeger-query
```

### 3. FastAPI 서비스에 환경 변수 추가

`infrastructure/k8s/manifests/user-service-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-service
  namespace: bigtech-chat
spec:
  template:
    spec:
      containers:
        - name: user-service
          env:
            # ... 기존 환경 변수

            # Jaeger 설정
            - name: SERVICE_NAME
              value: "user-service"
            - name: JAEGER_ENDPOINT
              value: "http://jaeger-collector:4317"
            - name: ENVIRONMENT
              value: "production"
            - name: NAMESPACE
              valueFrom:
                fieldRef:
                  fieldPath: metadata.namespace
```

---

## Trace 분석

### 1. Jaeger UI 접속

```bash
# Port Forward
kubectl port-forward -n bigtech-chat svc/jaeger-query 16686:16686

# 브라우저에서 접속
# http://localhost:16686
```

### 2. Trace 검색

Jaeger UI에서:
1. **Service 선택**: `chat-service`, `user-service`, 등
2. **Operation 선택**: `POST /rooms/{room_id}/messages`, 등
3. **Tags 필터**:
   - `user_id=123`
   - `room_id=456`
   - `error=true` (에러만 검색)
4. **Duration 필터**: 느린 요청만 검색 (예: > 500ms)

### 3. Trace 상세 분석

**Trace Timeline 예시**:
```
POST /rooms/123/messages                           [180ms]
│
├─ check_room_permission                           [15ms]
│  └─ SELECT room_participants (MySQL)            [8ms]
│
├─ save_message_to_mongodb                         [25ms]
│  └─ mongodb.insert (messages)                    [20ms]
│
├─ publish_kafka_event                             [12ms]
│  └─ kafka.send (message.events)                  [10ms]
│
└─ consume_message_event (Notification Service)    [45ms]
   ├─ kafka.consume                                [10ms]
   └─ send_sse_notification                        [35ms]
```

**Span 속성 확인**:
```json
{
  "traceID": "abc123def456",
  "spanID": "span-001",
  "operationName": "POST /rooms/{room_id}/messages",
  "startTime": 1700000000000,
  "duration": 180000,
  "tags": {
    "service.name": "chat-service",
    "http.method": "POST",
    "http.url": "/rooms/123/messages",
    "http.status_code": 200,
    "user_id": 456,
    "room_id": 123,
    "message_type": "text"
  },
  "logs": [
    {
      "timestamp": 1700000001000,
      "fields": {
        "event": "message_saved",
        "message_id": "msg-789"
      }
    }
  ]
}
```

### 4. 서비스 의존성 그래프

Jaeger UI → **Dependencies** 탭에서:
```
        ┌───────────────┐
        │  User Service │
        └───────┬───────┘
                │ (Auth)
                ↓
        ┌───────────────┐
        │  Chat Service │
        └───┬───────┬───┘
            │       │
    (MySQL) │       │ (Kafka)
            ↓       ↓
        ┌───────┐ ┌──────────────────┐
        │ MySQL │ │ Notification Svc │
        └───────┘ └──────────────────┘
```

### 5. 성능 병목 지점 식별

**Slow Query 찾기**:
1. Jaeger UI → Search
2. Min Duration: 500ms 설정
3. 결과 확인:
   ```
   Trace ID: xyz789
   Duration: 1.2s ⚠️

   └─ save_message_to_mongodb [1.1s] ← 병목!
      └─ mongodb.insert [1.0s]
   ```

**해결 방법**:
- MongoDB 인덱스 추가
- Batch Insert 적용
- Connection Pool 크기 조정

---

## 배포 순서

### 개발 환경 (All-in-One)
```bash
# Jaeger All-in-One 배포
kubectl apply -f infrastructure/k8s/manifests/jaeger-all-in-one.yaml

# 확인
kubectl get pods -n bigtech-chat -l app=jaeger

# UI 접속
kubectl port-forward -n bigtech-chat svc/jaeger-query 16686:16686
```

### 프로덕션 환경 (Elasticsearch)
```bash
# Elasticsearch 배포
kubectl apply -f infrastructure/k8s/manifests/jaeger-production.yaml

# Elasticsearch 상태 확인
kubectl get pods -n bigtech-chat -l app=elasticsearch

# Jaeger Collector/Query 배포
# (위 yaml에 포함됨)

# UI 접속
kubectl port-forward -n bigtech-chat svc/jaeger-query 16686:16686
```

---

## 다음 단계

1. **ELK Stack 로그 수집**: `elk-logging.md` 참고
2. **Trace + Log 통합**: Correlation ID로 연결

---

## 참고 자료
- [Jaeger 공식 문서](https://www.jaegertracing.io/docs/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/instrumentation/python/)
- [Distributed Tracing Best Practices](https://opentelemetry.io/docs/concepts/signals/traces/)
