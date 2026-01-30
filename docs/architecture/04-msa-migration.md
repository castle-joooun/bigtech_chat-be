# MSA 마이그레이션 전략

> **작성일**: 2026-01-27
> **목적**: Monolithic → MSA 전환 상세 계획 (Week 5)

## 마이그레이션 개요

### 목표
현재 Monolithic FastAPI 애플리케이션을 4개의 독립적인 마이크로서비스로 분리

### 서비스 분리 기준
- Bounded Context 기반 분리
- 독립적인 데이터베이스
- Kafka를 통한 이벤트 기반 통신

---

## 서비스 구조

### 최종 아키텍처

```
                    ┌──────────────┐
                    │ API Gateway  │
                    │  (Kong)      │
                    └──────┬───────┘
                           │
         ┌─────────────────┼─────────────────┬──────────────┐
         ▼                 ▼                 ▼              ▼
    ┌─────────┐      ┌─────────┐      ┌─────────┐   ┌─────────────┐
    │  User   │      │  Chat   │      │ Friend  │   │Notification │
    │ Service │      │ Service │      │ Service │   │  Service    │
    └────┬────┘      └────┬────┘      └────┬────┘   └──────┬──────┘
         │                │                │               │
         │                │                │               │
         └────────────────┴────────────────┴───────────────┘
                              Kafka Event Bus
                          (message.events, friend.events, ...)
```

---

## 1. User Service

### 책임
- 사용자 인증 (회원가입, 로그인, 로그아웃)
- 프로필 관리
- 사용자 검색
- 온라인 상태 관리 (Redis)

### 데이터베이스
- **MySQL**: users 테이블
- **Redis**: 온라인 상태, 세션

### API Endpoints
```
POST   /auth/register
POST   /auth/login
POST   /auth/logout
GET    /users/{user_id}
GET    /users/search
PUT    /profile/me
POST   /profile/upload-image
```

### 발행하는 Events
- `UserRegistered` → user.events
- `UserProfileUpdated` → user.events
- `UserOnlineStatusChanged` → user.online_status

### 디렉토리 구조
```
services/user-service/
├── main.py
├── requirements.txt
├── Dockerfile
├── app/
│   ├── api/
│   │   ├── auth.py
│   │   ├── user.py
│   │   └── profile.py
│   ├── domain/
│   │   ├── entities/
│   │   │   └── user.py
│   │   └── events/
│   │       └── user_events.py
│   ├── application/
│   │   └── user_service.py
│   ├── infrastructure/
│   │   ├── mysql/
│   │   │   └── user_repository.py
│   │   ├── redis/
│   │   │   └── online_status_service.py
│   │   └── kafka/
│   │       └── producer.py
│   └── core/
│       ├── config.py
│       └── errors.py
└── tests/
```

---

## 2. Chat Service

### 책임
- 채팅방 생성 및 관리
- 메시지 CRUD
- 메시지 읽음 상태 관리
- 실시간 메시지 스트리밍 (SSE + Kafka)

### 데이터베이스
- **MySQL**: chat_rooms 테이블
- **MongoDB**: messages, message_read_status 컬렉션
- **Redis**: 메시지 캐싱 (최근 50개)

### API Endpoints
```
GET    /chat-rooms
GET    /chat-rooms/check/{participant_id}
GET    /messages/{room_id}
POST   /messages/{room_id}
POST   /messages/read
GET    /messages/stream/{room_id}    # SSE
```

### 발행하는 Events
- `ChatRoomCreated` → chat.events
- `MessageSent` → message.events
- `MessagesRead` → message.events

### 구독하는 Events
- `FriendRequestAccepted` (친구 승인 시 채팅 가능 여부 확인용)

### 디렉토리 구조
```
services/chat-service/
├── main.py
├── requirements.txt
├── Dockerfile
├── app/
│   ├── api/
│   │   ├── chat_room.py
│   │   └── message.py
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── chat_room.py
│   │   │   └── message.py
│   │   └── events/
│   │       ├── chat_events.py
│   │       └── message_events.py
│   ├── application/
│   │   ├── chat_room_service.py
│   │   └── message_service.py
│   ├── infrastructure/
│   │   ├── mysql/
│   │   │   └── chat_room_repository.py
│   │   ├── mongodb/
│   │   │   └── message_repository.py
│   │   ├── redis/
│   │   │   └── message_cache_service.py
│   │   └── kafka/
│   │       ├── producer.py
│   │       └── consumer.py
│   └── core/
└── tests/
```

---

## 3. Friend Service

### 책임
- 친구 요청/수락/거절/취소
- 친구 목록 관리
- 사용자 차단 관리
- 친구 검색

### 데이터베이스
- **MySQL**: friendships, block_users 테이블

### API Endpoints
```
POST   /friends/request/{user_id}
POST   /friends/accept/{friendship_id}
POST   /friends/reject/{friendship_id}
DELETE /friends/cancel/{friendship_id}
GET    /friends
POST   /friends/block/{user_id}
GET    /friends/search
```

### 발행하는 Events
- `FriendRequestSent` → friend.events
- `FriendRequestAccepted` → friend.events
- `FriendRequestRejected` → friend.events
- `FriendRequestCancelled` → friend.events

### 구독하는 Events
- `UserRegistered` (새 사용자 캐시 갱신)

### 디렉토리 구조
```
services/friend-service/
├── main.py
├── requirements.txt
├── Dockerfile
├── app/
│   ├── api/
│   │   └── friend.py
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── friendship.py
│   │   │   └── block_user.py
│   │   └── events/
│   │       └── friend_events.py
│   ├── application/
│   │   └── friendship_service.py
│   ├── infrastructure/
│   │   ├── mysql/
│   │   │   ├── friendship_repository.py
│   │   │   └── block_user_repository.py
│   │   └── kafka/
│   │       ├── producer.py
│   │       └── consumer.py
│   └── core/
└── tests/
```

---

## 4. Notification Service

### 책임
- 실시간 알림 전송 (SSE)
- 온라인 상태 브로드캐스트
- Kafka 이벤트 소비 및 알림 변환

### 데이터베이스
- **Redis**: SSE 연결 관리, 온라인 상태

### API Endpoints
```
GET    /online-status/stream          # SSE
GET    /online-status/users
POST   /online-status/heartbeat
```

### 구독하는 Events (모든 이벤트)
- `UserOnlineStatusChanged` → 온라인 상태 브로드캐스트
- `FriendRequestSent` → 친구 요청 알림
- `FriendRequestAccepted` → 친구 수락 알림
- `MessageSent` → 새 메시지 알림

### 디렉토리 구조
```
services/notification-service/
├── main.py
├── requirements.txt
├── Dockerfile
├── app/
│   ├── api/
│   │   └── online_status.py
│   ├── application/
│   │   └── notification_service.py
│   ├── infrastructure/
│   │   ├── redis/
│   │   │   └── sse_manager.py
│   │   └── kafka/
│   │       └── consumer.py
│   └── core/
└── tests/
```

---

## 서비스 간 통신

### 1. 동기 통신 (REST API)

**최소화 원칙**: 가능한 한 Kafka 이벤트로 처리

**예외 케이스**:
- Chat Service → User Service: 사용자 정보 조회 (읽기 전용)
- Friend Service → User Service: 사용자 검색 (읽기 전용)

```python
# Chat Service에서 User Service 호출 (Anti-Corruption Layer)
class UserServiceClient:
    """User Service 호출을 위한 클라이언트"""

    def __init__(self):
        self.base_url = settings.user_service_url

    async def get_user(self, user_id: int) -> Optional[Dict]:
        """사용자 정보 조회"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/users/{user_id}",
                    timeout=5.0
                )
                if response.status_code == 200:
                    return response.json()
                return None

            except httpx.TimeoutException:
                logger.error(f"User service timeout: user_id={user_id}")
                return None
```

---

### 2. 비동기 통신 (Kafka Events)

**기본 원칙**: 모든 상태 변경은 이벤트로 발행

```python
# Friend Service: 친구 요청 수락 시
@router.post("/accept/{friendship_id}")
async def accept_friend_request(...):
    # 1. 친구 관계 업데이트
    friendship = await friendship_service.accept_friend_request(friendship_id)

    # 2. Domain Event 발행
    event = FriendRequestAccepted(
        friendship_id=friendship.id,
        requester_id=friendship.requester_id,
        requester_name=requester.username,
        addressee_id=friendship.addressee_id,
        addressee_name=addressee.username,
        timestamp=datetime.utcnow()
    )

    await kafka_producer.publish(
        topic='friend.events',
        event=event,
        key=str(friendship.id)
    )

    # 3. Notification Service가 이벤트를 소비하여 알림 전송
    return FriendshipResponse(...)
```

---

## API Gateway 설정

### Kong API Gateway 사용

```yaml
# infrastructure/kong/kong.yml

_format_version: "3.0"

services:
  - name: user-service
    url: http://user-service:8000
    routes:
      - name: auth-routes
        paths:
          - /auth
      - name: user-routes
        paths:
          - /users
      - name: profile-routes
        paths:
          - /profile

  - name: chat-service
    url: http://chat-service:8001
    routes:
      - name: chat-room-routes
        paths:
          - /chat-rooms
      - name: message-routes
        paths:
          - /messages

  - name: friend-service
    url: http://friend-service:8002
    routes:
      - name: friend-routes
        paths:
          - /friends

  - name: notification-service
    url: http://notification-service:8003
    routes:
      - name: notification-routes
        paths:
          - /online-status

plugins:
  - name: rate-limiting
    config:
      minute: 100
      policy: local

  - name: cors
    config:
      origins:
        - http://localhost:3000
      credentials: true

  - name: request-id
    config:
      header_name: X-Request-ID
```

---

## Docker Compose 설정

### MSA 전체 구성

```yaml
# infrastructure/docker/docker-compose-microservices.yml

version: '3.8'

services:
  # API Gateway
  kong:
    image: kong:3.5
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /kong/kong.yml
      KONG_PROXY_ACCESS_LOG: /dev/stdout
      KONG_ADMIN_ACCESS_LOG: /dev/stdout
      KONG_PROXY_ERROR_LOG: /dev/stderr
      KONG_ADMIN_ERROR_LOG: /dev/stderr
    volumes:
      - ../kong/kong.yml:/kong/kong.yml
    ports:
      - "8000:8000"
      - "8001:8001"
      - "8443:8443"
      - "8444:8444"
    networks:
      - bigtech-network

  # User Service
  user-service:
    build:
      context: ../../services/user-service
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: mysql+aiomysql://chatuser:chatpassword@mysql:3306/bigtech_chat
      REDIS_URL: redis://redis:6379
      KAFKA_BOOTSTRAP_SERVERS: kafka-1:9092,kafka-2:9093,kafka-3:9094
    ports:
      - "8000:8000"
    depends_on:
      - mysql
      - redis
      - kafka-1
    networks:
      - bigtech-network

  # Chat Service
  chat-service:
    build:
      context: ../../services/chat-service
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: mysql+aiomysql://chatuser:chatpassword@mysql:3306/bigtech_chat
      MONGODB_URL: mongodb://admin:adminpassword@mongodb:27017/bigtech_chat?authSource=admin
      REDIS_URL: redis://redis:6379
      KAFKA_BOOTSTRAP_SERVERS: kafka-1:9092,kafka-2:9093,kafka-3:9094
    ports:
      - "8001:8000"
    depends_on:
      - mysql
      - mongodb
      - redis
      - kafka-1
    networks:
      - bigtech-network

  # Friend Service
  friend-service:
    build:
      context: ../../services/friend-service
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: mysql+aiomysql://chatuser:chatpassword@mysql:3306/bigtech_chat
      KAFKA_BOOTSTRAP_SERVERS: kafka-1:9092,kafka-2:9093,kafka-3:9094
    ports:
      - "8002:8000"
    depends_on:
      - mysql
      - kafka-1
    networks:
      - bigtech-network

  # Notification Service
  notification-service:
    build:
      context: ../../services/notification-service
      dockerfile: Dockerfile
    environment:
      REDIS_URL: redis://redis:6379
      KAFKA_BOOTSTRAP_SERVERS: kafka-1:9092,kafka-2:9093,kafka-3:9094
    ports:
      - "8003:8000"
    depends_on:
      - redis
      - kafka-1
    networks:
      - bigtech-network

  # 기존 인프라 (Kafka, MySQL, MongoDB, Redis)는 docker-compose-kafka.yml 참조
```

---

## 데이터베이스 분리 전략

### Database per Service 원칙

```
User Service      → MySQL: users 테이블
Friend Service    → MySQL: friendships, block_users 테이블
Chat Service      → MySQL: chat_rooms 테이블
                  → MongoDB: messages, message_read_status 컬렉션
```

### 공유 데이터 문제 해결

**문제**: Chat Service에서 User 정보가 필요한 경우?

**해결 1: API 호출** (읽기 전용)
```python
user = await user_service_client.get_user(user_id)
```

**해결 2: Event Sourcing** (캐싱)
```python
# Chat Service가 UserRegistered 이벤트를 소비하여 로컬 캐시 유지
@kafka_consumer.subscribe('user.events')
async def handle_user_event(event):
    if event.type == 'UserRegistered':
        await redis.setex(
            f"user:{event.user_id}",
            86400,  # 24시간
            json.dumps({"username": event.username, ...})
        )
```

**해결 3: CQRS** (향후 확장)
- Command: 각 서비스의 DB
- Query: 통합 Read Model (Elasticsearch)

---

## 트랜잭션 관리

### Saga Pattern (Choreography 방식)

**시나리오**: 친구 요청 수락 시
1. Friend Service: 친구 관계 업데이트
2. Notification Service: 알림 전송
3. Chat Service: 채팅방 생성 (선택사항)

```
Friend Service
    ↓ FriendRequestAccepted Event
Kafka (friend.events)
    ↓
    ├─→ Notification Service (알림 전송)
    └─→ Chat Service (채팅방 자동 생성)
```

**보상 트랜잭션** (Rollback):
- Friend Service에서 실패 시 → `FriendRequestFailed` 이벤트 발행
- Notification Service가 이벤트를 소비하여 이미 전송한 알림 취소

---

## 마이그레이션 단계

### Step 1: 코드 분리 (1-2일)

```bash
# Monolithic 코드를 4개 서비스로 복사
cp -r app/ services/user-service/app/
cp -r app/ services/chat-service/app/
cp -r app/ services/friend-service/app/
cp -r app/ services/notification-service/app/

# 각 서비스에서 불필요한 코드 제거
# User Service: chat, friend 관련 API 제거
# Chat Service: auth, friend 관련 API 제거
# ...
```

### Step 2: 독립 실행 확인 (1일)

```bash
# 각 서비스 독립 실행 테스트
cd services/user-service
uvicorn app.main:app --port 8000

cd services/chat-service
uvicorn app.main:app --port 8001
```

### Step 3: API Gateway 설정 (1일)

```bash
# Kong 시작
docker-compose -f docker-compose-microservices.yml up kong

# 라우팅 테스트
curl http://localhost:8000/auth/login
curl http://localhost:8000/chat-rooms
```

### Step 4: 통합 테스트 (1-2일)

- 전체 플로우 테스트 (회원가입 → 친구 요청 → 메시지 전송)
- Kafka 이벤트 흐름 확인
- 부하 테스트

---

## 모니터링

### Service Health Check

```python
# 각 서비스의 /health 엔드포인트
@app.get("/health")
async def health_check():
    return {
        "service": "user-service",
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }
```

### Distributed Tracing (Jaeger)

```python
# OpenTelemetry 통합
from opentelemetry import trace
from opentelemetry.exporter.jaeger import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider

tracer = trace.get_tracer(__name__)

@router.post("/friends/request/{user_id}")
async def send_friend_request(...):
    with tracer.start_as_current_span("send_friend_request"):
        # 비즈니스 로직
        friendship = await friendship_service.send_friend_request(...)

        with tracer.start_as_current_span("publish_kafka_event"):
            await kafka_producer.publish(...)

        return FriendshipResponse(...)
```

---

## 다음 단계

1. **Week 6-7**: Kubernetes 배포
2. **Week 8**: Observability (Prometheus, Grafana, Jaeger)
3. **Week 9-10**: Spring Boot로 User Service 재구현

---

## References

- [Microservices Patterns by Chris Richardson](https://microservices.io/patterns/microservices.html)
- [Building Microservices by Sam Newman](https://samnewman.io/books/building_microservices/)
- [Saga Pattern](https://microservices.io/patterns/data/saga.html)
