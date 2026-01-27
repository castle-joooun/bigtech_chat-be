# Bounded Context 설계

> **작성일**: 2026-01-27
> **목적**: DDD 패턴 적용을 위한 도메인 경계 정의

## Overview

BigTech Chat Platform을 4개의 Bounded Context로 분리하여 각 도메인의 독립성을 확보하고, 향후 MSA 전환의 기반을 마련합니다.

---

## 1. User Context (사용자 도메인)

### 책임 (Responsibility)
- 사용자 인증 및 권한 관리
- 프로필 관리 (이름, 이미지, 상태 메시지)
- 사용자 검색

### Aggregate Root
- **User Aggregate**
  - User (Entity, Root)
  - Profile (Value Object)

### Domain Events
```python
class UserRegistered(DomainEvent):
    user_id: int
    email: str
    username: str
    timestamp: datetime

class UserProfileUpdated(DomainEvent):
    user_id: int
    display_name: str
    profile_image_url: str
    timestamp: datetime

class UserOnlineStatusChanged(DomainEvent):
    user_id: int
    is_online: bool
    timestamp: datetime
```

### API Endpoints
- `POST /auth/register` - 회원가입
- `POST /auth/login` - 로그인
- `POST /auth/logout` - 로그아웃
- `GET /users/{user_id}` - 사용자 조회
- `GET /users/search` - 사용자 검색
- `PUT /profile/me` - 프로필 수정

### Dependencies
- **Outgoing**: Notification Context (회원가입 알림)
- **Incoming**: Friend Context, Chat Context (사용자 정보 조회)

---

## 2. Friend Context (친구 관계 도메인)

### 책임
- 친구 요청/수락/거절
- 친구 목록 관리
- 사용자 차단 관리

### Aggregate Root
- **Friendship Aggregate**
  - Friendship (Entity, Root)
  - FriendRequest (Entity)
  - BlockUser (Entity)

### Domain Events
```python
class FriendRequestSent(DomainEvent):
    friendship_id: int
    requester_id: int
    addressee_id: int
    timestamp: datetime

class FriendRequestAccepted(DomainEvent):
    friendship_id: int
    requester_id: int
    addressee_id: int
    timestamp: datetime

class FriendRequestRejected(DomainEvent):
    friendship_id: int
    requester_id: int
    addressee_id: int
    timestamp: datetime

class FriendRequestCancelled(DomainEvent):
    friendship_id: int
    requester_id: int
    addressee_id: int
    timestamp: datetime

class UserBlocked(DomainEvent):
    blocker_id: int
    blocked_id: int
    timestamp: datetime
```

### API Endpoints
- `POST /friends/request/{user_id}` - 친구 요청
- `POST /friends/accept/{friendship_id}` - 친구 수락
- `POST /friends/reject/{friendship_id}` - 친구 거절
- `DELETE /friends/cancel/{friendship_id}` - 친구 요청 취소
- `GET /friends` - 친구 목록 조회
- `POST /friends/block/{user_id}` - 사용자 차단

### Dependencies
- **Outgoing**: Notification Context (친구 요청 알림)
- **Incoming**: Chat Context (친구 관계 확인)

---

## 3. Chat Context (채팅 도메인)

### 책임
- 1:1 채팅방 생성 및 관리
- 그룹 채팅방 관리 (향후 확장)
- 채팅방 목록 조회
- 마지막 메시지 및 읽지 않은 메시지 수

### Aggregate Root
- **ChatRoom Aggregate**
  - ChatRoom (Entity, Root)
  - RoomMember (Entity)
  - LastMessageSnapshot (Value Object)

### Domain Events
```python
class ChatRoomCreated(DomainEvent):
    room_id: int
    user_1_id: int
    user_2_id: int
    timestamp: datetime

class ChatRoomUpdated(DomainEvent):
    room_id: int
    updated_at: datetime

class MessageSent(DomainEvent):
    message_id: str
    room_id: int
    user_id: int
    content: str
    message_type: str
    timestamp: datetime

class MessageDeleted(DomainEvent):
    message_id: str
    room_id: int
    deleted_by: int
    timestamp: datetime

class MessagesRead(DomainEvent):
    room_id: int
    user_id: int
    message_ids: List[str]
    timestamp: datetime
```

### API Endpoints
- `GET /chat-rooms` - 채팅방 목록 조회
- `GET /chat-rooms/check/{participant_id}` - 채팅방 조회 또는 생성
- `GET /messages/{room_id}` - 메시지 목록 조회
- `POST /messages/{room_id}` - 메시지 전송
- `POST /messages/read` - 메시지 읽음 처리
- `GET /messages/stream/{room_id}` - 실시간 메시지 스트리밍 (SSE)

### Dependencies
- **Outgoing**: Notification Context (메시지 알림)
- **Incoming**: Friend Context (채팅 가능 여부 확인)

---

## 4. Notification Context (알림 도메인)

### 책임
- 실시간 알림 전송
- 온라인 상태 브로드캐스트
- SSE 연결 관리

### Aggregate Root
- **Notification Aggregate**
  - Notification (Entity, Root)
  - UserSubscription (Entity)

### Domain Events
```python
class NotificationSent(DomainEvent):
    notification_id: str
    user_id: int
    notification_type: str
    content: dict
    timestamp: datetime

class UserSubscribed(DomainEvent):
    user_id: int
    subscription_id: str
    timestamp: datetime

class UserUnsubscribed(DomainEvent):
    user_id: int
    subscription_id: str
    timestamp: datetime
```

### API Endpoints
- `GET /online-status/stream` - 온라인 상태 스트리밍 (SSE)
- `GET /online-status/users` - 특정 사용자들의 온라인 상태 조회
- `POST /online-status/heartbeat` - Heartbeat (온라인 상태 갱신)

### Dependencies
- **Incoming**: User Context, Friend Context, Chat Context

---

## Context Map (도메인 간 관계)

```
┌─────────────────┐
│  User Context   │──┐
└─────────────────┘  │
                     │ UserOnlineStatusChanged
                     ▼
┌─────────────────┐  ┌─────────────────────┐
│ Friend Context  │─▶│ Notification Context│
└─────────────────┘  └─────────────────────┘
         │                      ▲
         │ FriendRequestSent    │ MessageSent
         ▼                      │
┌─────────────────┐             │
│  Chat Context   │─────────────┘
└─────────────────┘
```

### 관계 유형

| From Context | To Context | 관계 유형 | 통신 방식 |
|--------------|------------|-----------|-----------|
| User | Notification | Publisher-Subscriber | Kafka (user.events) |
| Friend | Notification | Publisher-Subscriber | Kafka (friend.events) |
| Chat | Notification | Publisher-Subscriber | Kafka (message.events) |
| Friend | Chat | Conformist | REST API (친구 여부 확인) |

---

## Ubiquitous Language (공통 언어)

### User Context
- **User**: 시스템 사용자
- **Profile**: 사용자의 공개 프로필 정보
- **Authentication**: 인증 과정
- **Online Status**: 온라인/오프라인 상태

### Friend Context
- **Friendship**: 친구 관계
- **Friend Request**: 친구 요청
- **Requester**: 친구 요청을 보낸 사람
- **Addressee**: 친구 요청을 받은 사람
- **Block**: 사용자 차단

### Chat Context
- **Chat Room**: 채팅방 (1:1 or 그룹)
- **Message**: 채팅 메시지
- **Participant**: 채팅방 참여자
- **Unread Count**: 읽지 않은 메시지 수
- **Last Message**: 마지막 메시지

### Notification Context
- **Notification**: 알림
- **Subscription**: SSE 구독
- **Broadcast**: 브로드캐스트 (다수에게 전송)
- **Push**: 푸시 (특정 사용자에게 전송)

---

## Anti-Corruption Layer (ACL)

### Chat Context의 Friend Context 호출
```python
# Anti-Corruption Layer
class FriendshipACL:
    """Chat Context가 Friend Context를 호출할 때 사용하는 변환 레이어"""

    @staticmethod
    async def check_friendship(user_1_id: int, user_2_id: int) -> bool:
        """친구 관계 확인 (Chat 도메인 용어로 변환)"""
        # Friend Context의 API 호출
        response = await friend_service.get_friendship(user_1_id, user_2_id)

        # Chat 도메인의 용어로 변환
        return response is not None and response.status == "accepted"
```

---

## 다음 단계

1. **Aggregate 상세 설계** - 각 Aggregate의 Entity, Value Object 정의
2. **Domain Events 구현** - Kafka Topic 매핑
3. **Repository Interface 정의** - 데이터 접근 추상화
4. **Application Service 설계** - Use Case 구현

---

## References

- [Domain-Driven Design by Eric Evans](https://www.domainlanguage.com/ddd/)
- [Implementing Domain-Driven Design by Vaughn Vernon](https://vaughnvernon.com/)
- [Context Map Patterns](https://github.com/ddd-crew/context-mapping)
