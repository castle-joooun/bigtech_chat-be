"""
Message Service Layer (메시지 서비스 레이어)
==========================================

MongoDB에 저장되는 메시지 관련 비즈니스 로직을 담당합니다.

아키텍처 개요
-------------
```
┌─────────────────────────────────────────────────────────────────┐
│  API Layer (message.py)                                         │
│  - HTTP 요청/응답 처리                                           │
│  - 인증/인가 확인                                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Service Layer (현재 파일)                                       │
│  - 메시지 생성/조회/삭제                                          │
│  - 읽음 상태 관리                                                 │
│  - 비즈니스 로직                                                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  MongoDB (Beanie ODM)                                           │
│  - messages 컬렉션                                               │
│  - message_read_status 컬렉션                                    │
└─────────────────────────────────────────────────────────────────┘
```

MongoDB vs MySQL 선택 이유
--------------------------
| 특성          | MongoDB         | MySQL          |
|--------------|-----------------|----------------|
| 쓰기 성능     | 높음            | 보통           |
| 스키마        | 유연            | 고정           |
| 확장성        | 수평 확장 용이   | 수직 확장      |
| 트랜잭션      | 제한적          | ACID 완전 지원 |

메시지는:
- 빈번한 쓰기 (초당 수천 건)
- 비정형 데이터 (첨부파일, 반응 등)
- 단순 조회 패턴 (room_id로 조회)
→ MongoDB가 적합

Beanie ODM
----------
Beanie는 MongoDB를 위한 비동기 ODM (Object Document Mapper).

```python
# 문서 생성
message = Message(user_id=1, content="Hello")
await message.insert()

# 문서 조회
messages = await Message.find(Message.room_id == 123).to_list()

# 문서 수정
message.content = "Updated"
await message.save()
```

읽음 상태 처리
--------------
```
┌──────────────────────────────────────────────────────────────┐
│  Message (messages 컬렉션)                                    │
│  - id: ObjectId                                              │
│  - user_id, room_id, content, ...                            │
└───────────────────────────┬──────────────────────────────────┘
                            │ 1:N
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  MessageReadStatus (message_read_status 컬렉션)               │
│  - message_id: str (Message ObjectId 참조)                   │
│  - user_id: int                                              │
│  - read_at: datetime                                         │
└──────────────────────────────────────────────────────────────┘
```

SOLID 원칙
----------
- SRP: 메시지 관련 작업만 담당
- OCP: 새 메시지 타입 추가 시 기존 코드 수정 최소화
- DIP: Beanie Document 추상화에 의존

관련 파일
---------
- app/models/messages.py: Message, MessageReadStatus 모델
- app/api/message.py: API 엔드포인트
- app/kafka/events.py: MessageSent, MessagesRead 이벤트
"""

from datetime import datetime
from typing import List, Optional
from beanie import PydanticObjectId
from pymongo import DESCENDING

from app.models.messages import Message, MessageReadStatus
from app.services.cache_service import get_chat_cache


# =============================================================================
# 메시지 생성
# =============================================================================

async def create_message(
    user_id: int,
    room_id: int,
    room_type: str,
    content: str,
    message_type: str = "text"
) -> Message:
    """
    메시지 생성

    새 메시지를 MongoDB에 저장합니다.

    Args:
        user_id: 메시지 작성자 ID
        room_id: 채팅방 ID
        room_type: 채팅방 타입 ("private", "group")
        content: 메시지 내용
        message_type: 메시지 타입 ("text", "image", "file", "system")

    Returns:
        Message: 생성된 메시지 문서

    MongoDB 작업:
        await message.insert()  # insertOne()

    사용 예시:
        message = await create_message(
            user_id=1,
            room_id=100,
            room_type="private",
            content="안녕하세요!",
            message_type="text"
        )
    """
    # 메시지 문서 생성
    message = Message(
        user_id=user_id,
        room_id=room_id,
        room_type=room_type,
        content=content,
        message_type=message_type,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    # MongoDB에 저장
    await message.insert()

    # 캐시 무효화: 해당 채팅방의 메시지 캐시 삭제
    chat_cache = get_chat_cache()
    if chat_cache:
        await chat_cache.invalidate_room_messages(room_id)
        # 최근 메시지 리스트에 추가
        await chat_cache.push_recent_message(room_id, {
            "id": str(message.id),
            "user_id": user_id,
            "content": content[:100],  # 미리보기용
            "created_at": message.created_at.isoformat()
        })

    return message


# =============================================================================
# 메시지 조회
# =============================================================================

async def find_message_by_id(message_id: str) -> Optional[Message]:
    """
    메시지 ID로 단일 메시지 조회

    Args:
        message_id: MongoDB ObjectId 문자열

    Returns:
        Message 또는 None

    MongoDB 작업:
        Message.get(ObjectId) → findOne({_id: ObjectId})

    예외 처리:
        - 잘못된 ObjectId 형식이면 None 반환
        - 문서가 없으면 None 반환
    """
    try:
        return await Message.get(PydanticObjectId(message_id))
    except Exception:
        return None


async def get_room_messages(
    room_id: int,
    room_type: str = "private",
    limit: int = 50,
    skip: int = 0
) -> List[Message]:
    """
    채팅방 메시지 목록 조회 (캐시 적용)

    페이지네이션을 지원하며, 시간순으로 정렬된 메시지를 반환합니다.

    Args:
        room_id: 채팅방 ID
        room_type: 채팅방 타입 (기본값: "private")
        limit: 조회할 메시지 수 (기본값: 50)
        skip: 건너뛸 메시지 수 (페이지네이션)

    Returns:
        List[Message]: 메시지 목록 (오래된 순)

    캐시 전략:
        - 캐시 키: chat:messages:{room_id}:p{page}
        - TTL: 30초 (메시지는 자주 변경되므로 짧은 TTL)
        - 새 메시지 전송 시 캐시 무효화

    정렬 전략:
        1. DB에서 최신순으로 조회 (DESCENDING)
        2. 결과를 역순으로 변환 (오래된 순)
        → 클라이언트에서 메시지를 위→아래로 표시

    인덱스:
        (room_id, room_type, created_at DESC)

    MongoDB 쿼리:
        db.messages.find({
            room_id: 100,
            room_type: "private",
            is_deleted: false
        }).sort({created_at: -1}).skip(0).limit(50)
    """
    # 페이지 번호 계산
    page = (skip // limit) + 1 if limit > 0 else 1

    # 캐시 조회
    chat_cache = get_chat_cache()
    if chat_cache:
        cached_messages = await chat_cache.get_room_messages(room_id, page)
        if cached_messages is not None:
            # 캐시된 dict를 Message 객체로 변환
            return [Message(**msg) for msg in cached_messages]

    # DB 조회
    messages = await Message.find(
        Message.room_id == room_id,
        Message.room_type == room_type,
        Message.is_deleted == False  # Soft delete된 메시지 제외
    ).sort([("created_at", DESCENDING)]).skip(skip).limit(limit).to_list()

    # 최신순 → 오래된 순으로 변환
    messages = list(reversed(messages))

    # 캐시 저장
    if chat_cache and messages:
        # Message 객체를 dict로 변환하여 캐싱
        messages_dict = [
            {
                "id": str(msg.id),
                "user_id": msg.user_id,
                "room_id": msg.room_id,
                "room_type": msg.room_type,
                "content": msg.content,
                "message_type": msg.message_type,
                "is_deleted": msg.is_deleted,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
                "updated_at": msg.updated_at.isoformat() if msg.updated_at else None,
            }
            for msg in messages
        ]
        await chat_cache.set_room_messages(room_id, page, messages_dict)

    return messages


async def get_room_messages_count(
    room_id: int,
    room_type: str = "private"
) -> int:
    """
    채팅방 메시지 총 개수 조회

    페이지네이션 UI (전체 페이지 수 계산)에 사용.

    Args:
        room_id: 채팅방 ID
        room_type: 채팅방 타입

    Returns:
        int: 메시지 총 개수

    MongoDB 쿼리:
        db.messages.countDocuments({
            room_id: 100,
            room_type: "private",
            is_deleted: false
        })
    """
    return await Message.find(
        Message.room_id == room_id,
        Message.room_type == room_type,
        Message.is_deleted == False
    ).count()


# =============================================================================
# 읽음 상태 관리
# =============================================================================

async def mark_message_as_read(
    message_id: str,
    user_id: int,
    room_id: int
) -> MessageReadStatus:
    """
    단일 메시지 읽음 처리

    중복 처리 방지: 이미 읽은 메시지는 기존 상태 반환.

    Args:
        message_id: 메시지 ID
        user_id: 읽은 사용자 ID
        room_id: 채팅방 ID

    Returns:
        MessageReadStatus: 읽음 상태 문서

    캐시 전략:
        - 읽음 처리 시 unread_count 캐시 무효화

    멱등성:
        - 이미 읽은 경우 기존 문서 반환
        - 새로 읽은 경우 새 문서 생성
    """
    # 기존 읽음 상태 확인 (멱등성)
    existing_read = await MessageReadStatus.find_one(
        MessageReadStatus.message_id == message_id,
        MessageReadStatus.user_id == user_id
    )

    if existing_read:
        return existing_read

    # 새 읽음 상태 생성
    read_status = MessageReadStatus(
        message_id=message_id,
        user_id=user_id,
        room_id=room_id,
        read_at=datetime.utcnow()
    )

    await read_status.insert()

    # 캐시 무효화: unread_count 캐시 삭제
    chat_cache = get_chat_cache()
    if chat_cache:
        await chat_cache.invalidate_unread_count(room_id, user_id)

    return read_status


async def mark_multiple_messages_as_read(
    message_ids: List[str],
    user_id: int,
    room_id: int
) -> int:
    """
    여러 메시지 일괄 읽음 처리

    채팅방 진입 시 모든 안 읽은 메시지를 한 번에 처리.

    Args:
        message_ids: 메시지 ID 목록
        user_id: 읽은 사용자 ID
        room_id: 채팅방 ID

    Returns:
        int: 실제로 읽음 처리된 메시지 수

    성능 고려:
        - 각 메시지별로 중복 확인
        - TODO: 대량 처리 시 bulk_write 사용 고려

    사용 예시:
        count = await mark_multiple_messages_as_read(
            message_ids=["id1", "id2", "id3"],
            user_id=1,
            room_id=100
        )
        print(f"{count}개 메시지 읽음 처리")
    """
    read_count = 0

    for message_id in message_ids:
        # 중복 확인
        existing_read = await MessageReadStatus.find_one(
            MessageReadStatus.message_id == message_id,
            MessageReadStatus.user_id == user_id
        )

        if not existing_read:
            read_status = MessageReadStatus(
                message_id=message_id,
                user_id=user_id,
                room_id=room_id,
                read_at=datetime.utcnow()
            )
            await read_status.insert()
            read_count += 1

    return read_count


async def get_unread_messages_count(room_id: int, user_id: int) -> int:
    """
    읽지 않은 메시지 수 조회 (캐시 적용)

    채팅방 목록에서 안 읽은 메시지 수 표시에 사용.

    Args:
        room_id: 채팅방 ID
        user_id: 사용자 ID

    Returns:
        int: 읽지 않은 메시지 수 (자신이 보낸 메시지 제외)

    캐시 전략:
        - 캐시 키: chat:unread:{room_id}:{user_id}
        - TTL: 60초
        - 메시지 읽음 처리 시 캐시 무효화

    계산 로직:
        1. 채팅방의 모든 메시지 조회
        2. 사용자가 읽은 메시지 ID 조회
        3. (전체 - 읽은 - 자신이 보낸) = 안 읽은 수

    성능 최적화 필요:
        - 현재: 모든 메시지를 메모리에 로드
        - 개선: 집계 파이프라인 사용
        ```
        db.messages.aggregate([
            {$match: {room_id: 100, is_deleted: false}},
            {$lookup: {...}},
            {$count: "unread"}
        ])
        ```
    """
    # 캐시 조회
    chat_cache = get_chat_cache()
    if chat_cache:
        cached_count = await chat_cache.get_unread_count(room_id, user_id)
        if cached_count is not None:
            return cached_count

    # 채팅방의 모든 메시지 조회
    all_messages = await Message.find(
        Message.room_id == room_id,
        Message.is_deleted == False
    ).to_list()

    if not all_messages:
        return 0

    # 읽은 메시지 ID 조회
    read_statuses = await MessageReadStatus.find(
        MessageReadStatus.room_id == room_id,
        MessageReadStatus.user_id == user_id
    ).to_list()

    read_message_ids = set(status.message_id for status in read_statuses)

    # 읽지 않은 메시지 수 계산 (자신이 보낸 메시지 제외)
    unread_count = 0
    for message in all_messages:
        # 자신이 보낸 메시지는 제외
        if message.user_id != user_id and str(message.id) not in read_message_ids:
            unread_count += 1

    # 캐시 저장
    if chat_cache:
        await chat_cache.set_unread_count(room_id, user_id, unread_count)

    return unread_count
