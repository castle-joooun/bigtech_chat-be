# Microservices Architecture

이 디렉토리는 Monolithic 애플리케이션을 MSA로 분리한 마이크로서비스들을 포함합니다.

## 서비스 개요

### 1. User Service (Port: 8001)
**책임**: 사용자 인증, 프로필 관리, 온라인 상태 관리

**API Endpoints**:
- `POST /auth/register` - 회원가입
- `POST /auth/login` - 로그인
- `POST /auth/logout` - 로그아웃
- `GET /users/{user_id}` - 사용자 정보 조회
- `GET /users/search` - 사용자 검색
- `PUT /profile/me` - 프로필 수정
- `POST /profile/upload-image` - 프로필 이미지 업로드
- `GET /online-status/{user_id}` - 온라인 상태 조회
- `GET /online-status/stream` - 친구 온라인 상태 SSE 스트리밍

**데이터베이스**:
- MySQL: users 테이블
- Redis: 온라인 상태, 세션

**발행 이벤트**:
- `UserRegistered` → user.events
- `UserProfileUpdated` → user.events
- `UserOnlineStatusChanged` → user.online_status

---

### 2. Chat Service (Port: 8002)
**책임**: 채팅방 관리, 메시지 CRUD, 실시간 메시지 스트리밍

**API Endpoints**:
- `GET /chat-rooms` - 채팅방 목록 조회
- `GET /chat-rooms/check/{participant_id}` - 1:1 채팅방 존재 확인
- `GET /messages/{room_id}` - 메시지 조회
- `POST /messages/{room_id}` - 메시지 전송
- `POST /messages/read` - 메시지 읽음 처리
- `GET /messages/stream/{room_id}` - 실시간 메시지 SSE 스트리밍

**데이터베이스**:
- MySQL: chat_rooms, room_members 테이블
- MongoDB: messages, message_read_status 컬렉션
- Redis: 메시지 캐싱

**발행 이벤트**:
- `ChatRoomCreated` → chat.events
- `MessageSent` → message.events
- `MessagesRead` → message.events

**구독 이벤트**:
- `FriendRequestAccepted` (친구 승인 시 채팅 가능 여부 확인용)

---

### 3. Friend Service (Port: 8003)
**책임**: 친구 관계 관리, 친구 요청, 차단

**API Endpoints**:
- `GET /friends` - 친구 목록 조회
- `POST /friends/request` - 친구 요청
- `POST /friends/accept` - 친구 요청 수락
- `POST /friends/reject` - 친구 요청 거절
- `DELETE /friends/{friend_id}` - 친구 삭제
- `POST /friends/block` - 사용자 차단
- `DELETE /friends/unblock/{user_id}` - 차단 해제

**데이터베이스**:
- MySQL: friendships, block_users 테이블

**발행 이벤트**:
- `FriendRequestSent` → friend.events
- `FriendRequestAccepted` → friend.events
- `FriendRequestRejected` → friend.events
- `FriendDeleted` → friend.events
- `UserBlocked` → friend.events

---

### 4. Notification Service (Port: 8004)
**책임**: 실시간 알림 전송 (친구 요청, 메시지 등)

**API Endpoints**:
- `GET /notifications` - 알림 목록 조회
- `GET /notifications/stream` - 실시간 알림 SSE 스트리밍
- `POST /notifications/read` - 알림 읽음 처리

**데이터베이스**:
- MongoDB: notifications 컬렉션

**구독 이벤트**:
- `FriendRequestSent`
- `FriendRequestAccepted`
- `MessageSent`

**발행 이벤트**:
- `NotificationSent` → notification.events

---

## 서비스 간 통신

### Event-Driven Architecture (Kafka)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│User Service │     │Chat Service │     │Friend Svc   │     │Notification │
│  (8001)     │     │  (8002)     │     │  (8003)     │     │ Service     │
│             │     │             │     │             │     │  (8004)     │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │                   │
       │  UserRegistered   │  MessageSent      │  FriendRequest    │
       │ ─────────────────▶│◀──────────────────│ ─────────────────▶│
       │                   │                   │ ─────────────────▶│
       │  OnlineStatus     │  ChatRoomCreated  │  FriendAccepted   │
       │ ─────────────────▶│◀──────────────────│ ─────────────────▶│
       │                   │                   │                   │
       └───────────────────┴───────────────────┴───────────────────┘
                          Kafka Event Bus
                    (message.events, friend.events, ...)
```

### Kafka Topics

| Topic | Producer | Consumer | Description |
|-------|----------|----------|-------------|
| `user.events` | User Service | - | 사용자 등록, 프로필 수정 |
| `user.online_status` | User Service | Notification Service | 온라인 상태 변경 |
| `message.events` | Chat Service | Chat Service (SSE), Notification Service | 메시지 전송, 읽음 |
| `chat.events` | Chat Service | - | 채팅방 생성 |
| `friend.events` | Friend Service | Chat Service, Notification Service | 친구 요청, 수락, 거절 |
| `notification.events` | Notification Service | - | 알림 전송 완료 |

---

## 로컬 개발

### 1. 모든 서비스 시작

```bash
# 각 서비스 디렉토리에서 실행
cd services/user-service
python main.py

cd services/chat-service
python main.py

cd services/friend-service
python main.py

cd services/notification-service
python main.py
```

### 2. Docker Compose로 실행

```bash
docker-compose -f infrastructure/docker/docker-compose-services.yml up -d
```

### 3. API 테스트

```bash
# User Service
curl http://localhost:8001/health

# Chat Service
curl http://localhost:8002/health

# Friend Service
curl http://localhost:8003/health

# Notification Service
curl http://localhost:8004/health
```

---

## 다음 단계

- [ ] API Gateway 구성 (Kong)
- [ ] Service Mesh 구성 (Istio)
- [ ] 분산 트레이싱 (Jaeger)
- [ ] 중앙 로깅 (ELK Stack)
- [ ] 모니터링 (Prometheus + Grafana)
- [ ] CI/CD 파이프라인 (GitHub Actions)

---

## 주의사항

**현재 상태**: 디렉토리 구조만 생성된 상태입니다. 실제 API 구현은 아직 진행 중입니다.

**마이그레이션 단계**:
1. ✅ Week 1-2: DDD Lite 적용 (Bounded Context, Aggregate, Domain Events)
2. ✅ Week 3-4: Kafka 통합 (Redis Pub/Sub → Kafka)
3. 🚧 Week 5: MSA 서비스 분리 (진행 중)
4. ⏳ Week 6: API Gateway 구성
5. ⏳ Week 7-8: 모니터링 및 CI/CD
