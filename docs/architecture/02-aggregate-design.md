# Aggregate 설계

> **작성일**: 2026-01-27
> **목적**: 각 Bounded Context의 Aggregate Root 및 Entity, Value Object 정의

## DDD Aggregate 개요

### Aggregate란?
- **트랜잭션 일관성 경계**: 하나의 단위로 변경되어야 하는 객체들의 묶음
- **Aggregate Root**: 외부에서 접근 가능한 유일한 진입점
- **Entity**: 식별자를 가진 객체 (생명주기 추적)
- **Value Object**: 식별자가 없는 불변 객체 (값 자체로 비교)

---

## 1. User Aggregate

### Aggregate Root: User

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class User:
    """User Aggregate Root"""
    id: int
    email: str
    username: str
    password_hash: str
    display_name: str
    profile: Profile  # Value Object
    is_online: bool
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime

    def update_profile(self, display_name: str, status_message: Optional[str], profile_image_url: Optional[str]):
        """프로필 업데이트 (비즈니스 규칙 적용)"""
        if not display_name or len(display_name) < 2:
            raise ValueError("Display name must be at least 2 characters")

        self.display_name = display_name
        self.profile = Profile(
            status_message=status_message,
            profile_image_url=profile_image_url
        )
        self.updated_at = datetime.utcnow()

        # Domain Event 발행
        return UserProfileUpdated(
            user_id=self.id,
            display_name=self.display_name,
            profile_image_url=profile_image_url,
            timestamp=self.updated_at
        )

    def go_online(self):
        """온라인 상태로 전환"""
        if not self.is_online:
            self.is_online = True
            self.last_seen_at = datetime.utcnow()

            return UserOnlineStatusChanged(
                user_id=self.id,
                is_online=True,
                timestamp=datetime.utcnow()
            )

    def go_offline(self):
        """오프라인 상태로 전환"""
        if self.is_online:
            self.is_online = False
            self.last_seen_at = datetime.utcnow()

            return UserOnlineStatusChanged(
                user_id=self.id,
                is_online=False,
                timestamp=datetime.utcnow()
            )
```

### Value Object: Profile

```python
@dataclass(frozen=True)
class Profile:
    """프로필 Value Object (불변)"""
    status_message: Optional[str] = None
    profile_image_url: Optional[str] = None

    def __post_init__(self):
        """Validation"""
        if self.status_message and len(self.status_message) > 100:
            raise ValueError("Status message must be less than 100 characters")
```

---

## 2. Friendship Aggregate

### Aggregate Root: Friendship

```python
from enum import Enum

class FriendshipStatus(Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

@dataclass
class Friendship:
    """Friendship Aggregate Root"""
    id: int
    requester_id: int
    addressee_id: int
    status: FriendshipStatus
    requested_at: datetime
    responded_at: Optional[datetime] = None

    def accept(self):
        """친구 요청 수락"""
        if self.status != FriendshipStatus.PENDING:
            raise ValueError(f"Cannot accept friendship in status: {self.status}")

        self.status = FriendshipStatus.ACCEPTED
        self.responded_at = datetime.utcnow()

        return FriendRequestAccepted(
            friendship_id=self.id,
            requester_id=self.requester_id,
            addressee_id=self.addressee_id,
            timestamp=self.responded_at
        )

    def reject(self):
        """친구 요청 거절"""
        if self.status != FriendshipStatus.PENDING:
            raise ValueError(f"Cannot reject friendship in status: {self.status}")

        self.status = FriendshipStatus.REJECTED
        self.responded_at = datetime.utcnow()

        return FriendRequestRejected(
            friendship_id=self.id,
            requester_id=self.requester_id,
            addressee_id=self.addressee_id,
            timestamp=self.responded_at
        )

    def cancel(self):
        """친구 요청 취소 (요청자만 가능)"""
        if self.status != FriendshipStatus.PENDING:
            raise ValueError(f"Cannot cancel friendship in status: {self.status}")

        self.status = FriendshipStatus.CANCELLED
        self.responded_at = datetime.utcnow()

        return FriendRequestCancelled(
            friendship_id=self.id,
            requester_id=self.requester_id,
            addressee_id=self.addressee_id,
            timestamp=self.responded_at
        )

    def is_friends_with(self, user_id: int) -> bool:
        """특정 사용자와 친구인지 확인"""
        return (
            self.status == FriendshipStatus.ACCEPTED and
            (self.requester_id == user_id or self.addressee_id == user_id)
        )
```

### Entity: BlockUser

```python
@dataclass
class BlockUser:
    """사용자 차단 Entity"""
    id: int
    blocker_id: int  # 차단한 사용자
    blocked_id: int  # 차단된 사용자
    created_at: datetime

    @staticmethod
    def create(blocker_id: int, blocked_id: int):
        """차단 생성"""
        if blocker_id == blocked_id:
            raise ValueError("Cannot block yourself")

        block = BlockUser(
            id=None,  # Repository에서 할당
            blocker_id=blocker_id,
            blocked_id=blocked_id,
            created_at=datetime.utcnow()
        )

        return block, UserBlocked(
            blocker_id=blocker_id,
            blocked_id=blocked_id,
            timestamp=datetime.utcnow()
        )
```

---

## 3. ChatRoom Aggregate

### Aggregate Root: ChatRoom

```python
@dataclass
class ChatRoom:
    """ChatRoom Aggregate Root"""
    id: int
    user_1_id: int
    user_2_id: int
    room_type: str  # "direct" or "group"
    created_at: datetime
    updated_at: datetime

    def update_timestamp(self):
        """채팅방 타임스탬프 업데이트 (새 메시지 발생 시)"""
        self.updated_at = datetime.utcnow()

        return ChatRoomUpdated(
            room_id=self.id,
            updated_at=self.updated_at
        )

    def is_participant(self, user_id: int) -> bool:
        """사용자가 참여자인지 확인"""
        return user_id in [self.user_1_id, self.user_2_id]

    def get_other_participant(self, user_id: int) -> int:
        """상대방 ID 반환"""
        if not self.is_participant(user_id):
            raise ValueError("User is not a participant")

        return self.user_2_id if user_id == self.user_1_id else self.user_1_id
```

### Entity: Message (MongoDB)

```python
@dataclass
class Message:
    """메시지 Entity (MongoDB)"""
    id: str  # ObjectId
    room_id: int
    user_id: int
    content: str
    message_type: str  # "text", "image", "file"
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[int] = None
    reply_to: Optional[str] = None  # 답장 대상 메시지 ID

    def soft_delete(self, deleted_by_user_id: int):
        """메시지 소프트 삭제"""
        if self.is_deleted:
            raise ValueError("Message is already deleted")

        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by = deleted_by_user_id

        return MessageDeleted(
            message_id=self.id,
            room_id=self.room_id,
            deleted_by=deleted_by_user_id,
            timestamp=self.deleted_at
        )

    def edit_content(self, new_content: str):
        """메시지 내용 수정"""
        if self.is_deleted:
            raise ValueError("Cannot edit deleted message")

        if not new_content.strip():
            raise ValueError("Message content cannot be empty")

        self.content = new_content
        self.updated_at = datetime.utcnow()

        return MessageEdited(
            message_id=self.id,
            room_id=self.room_id,
            new_content=new_content,
            timestamp=self.updated_at
        )
```

### Value Object: MessageReadStatus (MongoDB)

```python
@dataclass(frozen=True)
class MessageReadStatus:
    """메시지 읽음 상태 Value Object"""
    message_id: str
    user_id: int
    room_id: int
    read_at: datetime
```

---

## 4. Notification Aggregate

### Aggregate Root: Notification

```python
from enum import Enum

class NotificationType(Enum):
    FRIEND_REQUEST = "friend_request"
    FRIEND_ACCEPTED = "friend_accepted"
    NEW_MESSAGE = "new_message"
    SYSTEM = "system"

@dataclass
class Notification:
    """Notification Aggregate Root"""
    id: str  # UUID
    user_id: int
    notification_type: NotificationType
    title: str
    content: dict  # JSON 데이터
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime] = None

    @staticmethod
    def create_friend_request_notification(
        requester_id: int,
        requester_name: str,
        addressee_id: int
    ):
        """친구 요청 알림 생성"""
        return Notification(
            id=str(uuid.uuid4()),
            user_id=addressee_id,
            notification_type=NotificationType.FRIEND_REQUEST,
            title=f"{requester_name}님이 친구 요청을 보냈습니다",
            content={
                "requester_id": requester_id,
                "requester_name": requester_name
            },
            is_read=False,
            created_at=datetime.utcnow()
        )

    @staticmethod
    def create_new_message_notification(
        sender_id: int,
        sender_name: str,
        recipient_id: int,
        message_preview: str,
        room_id: int
    ):
        """새 메시지 알림 생성"""
        return Notification(
            id=str(uuid.uuid4()),
            user_id=recipient_id,
            notification_type=NotificationType.NEW_MESSAGE,
            title=f"{sender_name}님의 새 메시지",
            content={
                "sender_id": sender_id,
                "sender_name": sender_name,
                "message_preview": message_preview[:50],
                "room_id": room_id
            },
            is_read=False,
            created_at=datetime.utcnow()
        )

    def mark_as_read(self):
        """알림 읽음 처리"""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
```

---

## Aggregate 설계 원칙

### 1. 작은 Aggregate
- Aggregate는 가능한 작게 유지
- 트랜잭션 일관성이 필요한 최소 범위만 포함

### 2. ID로 다른 Aggregate 참조
- Aggregate 간 참조는 ID로만 수행
- 객체 참조 금지 (결합도 증가 방지)

```python
# ❌ Bad: 객체 참조
class ChatRoom:
    participants: List[User]  # User Aggregate 직접 참조

# ✅ Good: ID 참조
class ChatRoom:
    user_1_id: int  # User ID만 참조
    user_2_id: int
```

### 3. Invariant (불변식) 보호
- Aggregate 내부의 비즈니스 규칙 강제

```python
class Friendship:
    def accept(self):
        # Invariant: PENDING 상태에서만 수락 가능
        if self.status != FriendshipStatus.PENDING:
            raise ValueError(f"Cannot accept in status: {self.status}")
        # ...
```

### 4. Eventual Consistency (결과적 일관성)
- Aggregate 간 일관성은 Domain Events로 처리

```python
# User가 오프라인 될 때 → Notification Context에 이벤트 발행
user.go_offline()  # UserOnlineStatusChanged 이벤트 발행
# → Kafka를 통해 Notification Service가 이벤트 수신
# → 친구들에게 오프라인 상태 브로드캐스트
```

---

## Repository 인터페이스 정의

### UserRepository

```python
from abc import ABC, abstractmethod

class UserRepository(ABC):
    @abstractmethod
    async def find_by_id(self, user_id: int) -> Optional[User]:
        pass

    @abstractmethod
    async def find_by_email(self, email: str) -> Optional[User]:
        pass

    @abstractmethod
    async def save(self, user: User) -> User:
        pass

    @abstractmethod
    async def update(self, user: User) -> User:
        pass
```

### FriendshipRepository

```python
class FriendshipRepository(ABC):
    @abstractmethod
    async def find_by_id(self, friendship_id: int) -> Optional[Friendship]:
        pass

    @abstractmethod
    async def find_by_users(self, user_1_id: int, user_2_id: int) -> Optional[Friendship]:
        pass

    @abstractmethod
    async def find_friends_of(self, user_id: int) -> List[Friendship]:
        pass

    @abstractmethod
    async def save(self, friendship: Friendship) -> Friendship:
        pass

    @abstractmethod
    async def update(self, friendship: Friendship) -> Friendship:
        pass
```

### ChatRoomRepository

```python
class ChatRoomRepository(ABC):
    @abstractmethod
    async def find_by_id(self, room_id: int) -> Optional[ChatRoom]:
        pass

    @abstractmethod
    async def find_by_participants(self, user_1_id: int, user_2_id: int) -> Optional[ChatRoom]:
        pass

    @abstractmethod
    async def find_rooms_of_user(self, user_id: int, skip: int, limit: int) -> List[ChatRoom]:
        pass

    @abstractmethod
    async def save(self, chat_room: ChatRoom) -> ChatRoom:
        pass

    @abstractmethod
    async def update(self, chat_room: ChatRoom) -> ChatRoom:
        pass
```

### MessageRepository (MongoDB)

```python
class MessageRepository(ABC):
    @abstractmethod
    async def find_by_id(self, message_id: str) -> Optional[Message]:
        pass

    @abstractmethod
    async def find_by_room(self, room_id: int, skip: int, limit: int) -> List[Message]:
        pass

    @abstractmethod
    async def save(self, message: Message) -> Message:
        pass

    @abstractmethod
    async def soft_delete(self, message_id: str, deleted_by: int) -> bool:
        pass
```

---

## 다음 단계

1. **Domain Events 구현** - Kafka Topic 매핑 및 Producer/Consumer 작성
2. **Repository 구현** - MySQL/MongoDB 기반 구현체 작성
3. **Application Service 작성** - Use Case 구현 (트랜잭션 관리)
4. **디렉토리 구조 리팩토링** - domain/application/infrastructure 레이어 분리

---

## References

- [Effective Aggregate Design by Vaughn Vernon](https://www.dddcommunity.org/library/vernon_2011/)
- [Domain-Driven Design Distilled](https://www.amazon.com/Domain-Driven-Design-Distilled-Vaughn-Vernon/dp/0134434420)
