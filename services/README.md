# Microservices Architecture

이 디렉토리는 Monolithic 애플리케이션을 MSA로 분리한 마이크로서비스들을 포함합니다.

> **마지막 업데이트**: 2026-01-27

---

## 서비스 구현 현황

| 서비스 | 포트 | 상태 | 완료율 | 비고 |
|--------|------|------|--------|------|
| **User Service** | 8005 | ✅ 완료 | 100% | 기존 API 마이그레이션 |
| **Friend Service** | 8003 | ✅ 완료 | 100% | 기존 API 마이그레이션 |
| **Chat Service** | 8002 | ✅ 완료 | 100% | 기존 API 마이그레이션 |
| Notification Service | 8004 | ⏳ 신규 | - | 신규 기능 (추후 구현) |

---

## ✅ 완료된 서비스

### 1. User Service (Port: 8005)

**상태**: ✅ **완전 구현 완료**

**책임**: 사용자 인증, 프로필 관리, 온라인 상태 관리

#### 구현된 API Endpoints

| Method | Endpoint | 설명 | 상태 |
|--------|----------|------|------|
| `POST` | `/auth/register` | 회원가입 | ✅ |
| `POST` | `/auth/login` | 로그인 (OAuth2 form) | ✅ |
| `POST` | `/auth/login/json` | 로그인 (JSON) | ✅ |
| `POST` | `/auth/logout` | 로그아웃 | ✅ |
| `GET` | `/profile/me` | 내 프로필 조회 | ✅ |
| `GET` | `/profile/{user_id}` | 특정 사용자 프로필 조회 | ✅ |
| `PUT` | `/profile/me` | 내 프로필 수정 | ✅ |
| `POST` | `/profile/me/image` | 프로필 이미지 업로드 | ✅ |
| `DELETE` | `/profile/me/image` | 프로필 이미지 삭제 | ✅ |
| `GET` | `/users/search` | 사용자 검색 | ✅ |
| `GET` | `/users/{user_id}` | 사용자 조회 | ✅ |
| `GET` | `/users` | 복수 사용자 조회 (user_ids) | ✅ |
| `GET` | `/health` | 헬스 체크 | ✅ |

#### 구현된 파일 구조

```
services/user-service/
├── main.py                           # FastAPI 앱 엔트리포인트
├── app/
│   ├── api/
│   │   ├── auth.py                   # 인증 API (register, login, logout)
│   │   ├── profile.py                # 프로필 API (조회, 수정, 이미지)
│   │   └── user.py                   # 사용자 API (검색, 조회)
│   ├── core/
│   │   ├── config.py                 # 설정 관리
│   │   ├── errors.py                 # 에러 정의
│   │   └── validators.py             # 입력 검증
│   ├── database/
│   │   └── mysql.py                  # MySQL 연결
│   ├── domain/entities/
│   │   └── user.py                   # User 도메인 엔티티
│   ├── models/
│   │   └── user.py                   # SQLAlchemy User 모델
│   ├── schemas/
│   │   └── user.py                   # Pydantic 스키마
│   ├── services/
│   │   ├── auth_service.py           # 인증 비즈니스 로직
│   │   ├── file_service.py           # 파일 업로드 서비스
│   │   └── online_status_service.py  # 온라인 상태 관리
│   └── utils/
│       └── auth.py                   # JWT, 비밀번호 해싱
```

#### 데이터베이스
- **MySQL**: `users` 테이블
- **Redis**: 온라인 상태, 세션 관리

#### 발행 이벤트 (예정)
- `UserRegistered` → `user.events`
- `UserProfileUpdated` → `user.events`
- `UserOnlineStatusChanged` → `user.online_status`

---

### 2. Friend Service (Port: 8003)

**상태**: ✅ **완전 구현 완료**

**책임**: 친구 관계 관리, 친구 요청/수락/거절/취소

#### 구현된 API Endpoints

| Method | Endpoint | 설명 | 상태 |
|--------|----------|------|------|
| `POST` | `/friends/request` | 친구 요청 전송 | ✅ |
| `PUT` | `/friends/status/{requester_user_id}` | 친구 요청 수락/거절 | ✅ |
| `GET` | `/friends/list` | 친구 목록 조회 | ✅ |
| `GET` | `/friends/requests` | 받은/보낸 친구 요청 목록 | ✅ |
| `DELETE` | `/friends/request/{target_user_id}` | 친구 요청 취소 | ✅ |
| `GET` | `/friends/search` | 친구 추가용 사용자 검색 | ✅ |
| `GET` | `/health` | 헬스 체크 | ✅ |

#### 구현된 파일 구조

```
services/friend-service/
├── main.py                           # FastAPI 앱 엔트리포인트
├── app/
│   ├── api/
│   │   ├── friend.py                 # 친구 관계 API
│   │   └── dependencies.py           # 의존성 (get_current_user)
│   ├── core/
│   │   ├── config.py                 # 설정 관리
│   │   ├── errors.py                 # 에러 정의
│   │   └── validators.py             # 입력 검증
│   ├── database/
│   │   └── mysql.py                  # MySQL 연결
│   ├── models/
│   │   ├── user.py                   # User 모델 (조회용)
│   │   └── friendship.py             # Friendship, BlockUser 모델
│   ├── schemas/
│   │   ├── user.py                   # User 스키마
│   │   └── friendship.py             # Friendship 스키마
│   ├── services/
│   │   ├── auth_service.py           # 사용자 조회 서비스
│   │   └── friendship_service.py     # 친구 관계 비즈니스 로직
│   └── utils/
│       └── auth.py                   # JWT 토큰 검증
```

#### 데이터베이스
- **MySQL**: `friendships`, `block_users` 테이블

#### 발행 이벤트 (예정)
- `FriendRequestSent` → `friend.events`
- `FriendRequestAccepted` → `friend.events`
- `FriendRequestRejected` → `friend.events`
- `FriendDeleted` → `friend.events`

---

## 🚧 진행 중인 서비스

### 3. Chat Service (Port: 8002)

**상태**: ✅ **완전 구현 완료**

**책임**: 채팅방 관리, 메시지 CRUD, 실시간 메시지 스트리밍

#### 구현된 API Endpoints

| Method | Endpoint | 설명 | 상태 |
|--------|----------|------|------|
| `GET` | `/chat-rooms` | 채팅방 목록 조회 | ✅ |
| `GET` | `/chat-rooms/check/{participant_id}` | 1:1 채팅방 조회/생성 | ✅ |
| `POST` | `/messages/{room_id}` | 메시지 전송 | ✅ |
| `GET` | `/messages/{room_id}` | 메시지 조회 | ✅ |
| `POST` | `/messages/read` | 메시지 읽음 처리 | ✅ |
| `GET` | `/messages/room/{room_id}/unread-count` | 읽지 않은 메시지 수 | ✅ |
| `GET` | `/messages/stream/{room_id}` | 실시간 메시지 SSE | ✅ |
| `GET` | `/health` | 헬스 체크 | ✅ |

#### 구현된 파일 구조

```
services/chat-service/
├── main.py                           # FastAPI 앱 엔트리포인트
├── requirements.txt                  # 의존성
├── .env.example                      # 환경변수 예시
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── dependencies.py           # 의존성 (get_current_user)
│   │   ├── chat_room.py              # 채팅방 API
│   │   └── message.py                # 메시지 API
│   ├── core/
│   │   ├── config.py                 # 설정 관리
│   │   ├── errors.py                 # 에러 정의
│   │   └── validators.py             # 입력 검증
│   ├── database/
│   │   ├── mysql.py                  # MySQL 연결
│   │   ├── mongodb.py                # MongoDB 연결
│   │   └── redis.py                  # Redis 연결
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py                   # User 모델
│   │   ├── chat_rooms.py             # ChatRoom 모델
│   │   ├── messages.py               # Message 모델 (MongoDB)
│   │   └── room_members.py           # RoomMember 모델
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py                   # User 스키마
│   │   ├── chat_room.py              # ChatRoom 스키마
│   │   └── message.py                # Message 스키마
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py           # 사용자 조회 서비스
│   │   ├── chat_room_service.py      # 채팅방 비즈니스 로직
│   │   └── message_service.py        # 메시지 비즈니스 로직
│   └── utils/
│       └── auth.py                   # JWT 토큰 검증
```

#### 데이터베이스
- **MySQL**: `chat_rooms`, `room_members` 테이블
- **MongoDB**: `messages`, `message_read_status`, `message_reactions` 컬렉션
- **Redis**: 메시지 캐싱

#### 발행 이벤트 (예정)
- `ChatRoomCreated` → `chat.events`
- `MessageSent` → `message.events`
- `MessagesRead` → `message.events`

---

## ⏳ 추후 구현 예정 (신규 기능)

### 4. Notification Service (Port: 8004)

**상태**: ⏳ **신규 기능 - 추후 구현**

> 기존 Monolithic 앱에 없던 신규 서비스입니다. MSA 전환 후 추가 기능으로 구현 예정.

**책임**: 실시간 알림 전송 (친구 요청, 메시지 등)

#### 예정 API Endpoints

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/notifications` | 알림 목록 조회 |
| `GET` | `/notifications/stream` | 실시간 알림 SSE |
| `POST` | `/notifications/read` | 알림 읽음 처리 |

---

## 서비스 간 통신

### Event-Driven Architecture (Kafka)

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ User Service │  │ Chat Service │  │Friend Service│  │ Notification │
│   (8005)     │  │   (8002)     │  │   (8003)     │  │   Service    │
│  ✅ 완료      │  │  ✅ 완료      │  │  ✅ 완료      │  │   (8004)     │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │                 │
       │  UserRegistered │  MessageSent    │  FriendRequest  │
       │ ───────────────▶│◀────────────────│ ───────────────▶│
       │                 │                 │ ───────────────▶│
       │  OnlineStatus   │  ChatRoomCreated│  FriendAccepted │
       │ ───────────────▶│◀────────────────│ ───────────────▶│
       │                 │                 │                 │
       └─────────────────┴─────────────────┴─────────────────┘
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

### 1. 완료된 서비스 실행

```bash
# User Service (Port 8005)
cd services/user-service
python -m uvicorn main:app --host 0.0.0.0 --port 8005 --reload

# Friend Service (Port 8003)
cd services/friend-service
python -m uvicorn main:app --host 0.0.0.0 --port 8003 --reload

# Chat Service (Port 8002)
cd services/chat-service
python -m uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

### 2. 헬스 체크

```bash
# User Service
curl http://localhost:8005/health
# {"status":"healthy","service":"User Service"}

# Friend Service
curl http://localhost:8003/health
# {"status":"healthy","service":"Friend Service"}

# Chat Service
curl http://localhost:8002/health
# {"status":"healthy","service":"Chat Service"}
```

### 3. Swagger UI

- **User Service**: http://localhost:8005/docs
- **Friend Service**: http://localhost:8003/docs
- **Chat Service**: http://localhost:8002/docs

### 4. 전체 MSA 스택 실행 (Docker Compose)

```bash
# 전체 MSA 스택 실행 (Kong + 서비스 + 인프라)
docker-compose -f docker-compose.msa.yml up -d

# Kong 라우팅 설정
chmod +x infrastructure/docker/kong/kong-config.sh
./infrastructure/docker/kong/kong-config.sh

# 서비스 중지
docker-compose -f docker-compose.msa.yml down
```

### 5. Kafka 클러스터만 실행 (개발용)

```bash
docker-compose -f infrastructure/docker/docker-compose-kafka.yml up -d
```

---

## 다음 단계

### 1단계: 핵심 API 마이그레이션 (✅ 완료)
- [x] User Service API 완성
- [x] Friend Service API 완성
- [x] Chat Service API 완성
- [ ] Notification Service (신규 기능, 추후 구현)

### 2단계: API Gateway 구성 (✅ 완료)
- [x] Kong API Gateway 설정
- [x] 라우팅 규칙 설정 스크립트
- [x] CORS, Rate Limiting 플러그인

### 3단계: Docker Compose 통합 (✅ 완료)
- [x] 전체 MSA 스택 docker-compose.msa.yml 작성
- [x] 서비스별 Dockerfile 생성
- [x] 서비스 간 네트워크 설정

### 4단계: 모니터링 & CI/CD
- [ ] Prometheus + Grafana 설정
- [ ] 중앙 로깅 (ELK Stack)
- [ ] 분산 트레이싱 (Jaeger)
- [ ] CI/CD 파이프라인 (GitHub Actions)

---

## Port 할당

| 서비스 | Port | 상태 |
|--------|------|------|
| Monolithic API | 8000 | 운영 중 (레거시) |
| **Kong API Gateway** | 80/443 | ✅ 완료 |
| Kong Admin API | 8001 | ✅ 완료 |
| **User Service** | 8005 | ✅ 완료 |
| **Chat Service** | 8002 | ✅ 완료 |
| **Friend Service** | 8003 | ✅ 완료 |
| Notification Service | 8004 | ⏳ 신규 |
| Kafka UI | 8080 | 운영 중 |

---

## 마이그레이션 진행 상황

| Week | 작업 | 상태 |
|------|------|------|
| Week 1-2 | DDD Lite 적용 | ✅ 완료 |
| Week 3-4 | Kafka 통합 | ✅ 완료 |
| Week 5 | MSA 서비스 분리 | ✅ 완료 |
| Week 6 | API Gateway 구성 | ✅ 완료 |
| Week 7-8 | 모니터링 & CI/CD | ⏳ 대기 |
