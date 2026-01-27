"""
Message Service - 메시지 관련 비즈니스 로직 (MongoDB)
"""

from datetime import datetime
from typing import List, Optional
from beanie import PydanticObjectId
from pymongo import DESCENDING

from app.models.messages import Message, MessageReadStatus


async def create_message(
    user_id: int,
    room_id: int,
    room_type: str,
    content: str,
    message_type: str = "text",
    reply_to: Optional[str] = None
) -> Message:
    """메시지 생성"""

    # 답장 메시지 정보 가져오기
    reply_content = None
    reply_sender_id = None
    if reply_to:
        reply_message = await find_message_by_id(reply_to)
        if reply_message:
            reply_content = reply_message.content[:100] + "..." if len(reply_message.content) > 100 else reply_message.content
            reply_sender_id = reply_message.user_id

    message = Message(
        user_id=user_id,
        room_id=room_id,
        room_type=room_type,
        content=content,
        message_type=message_type,
        reply_to=reply_to,
        reply_content=reply_content,
        reply_sender_id=reply_sender_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    await message.insert()
    return message


async def find_message_by_id(message_id: str) -> Optional[Message]:
    """메시지 ID로 조회"""
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
    """채팅방 메시지 목록 조회"""
    messages = await Message.find(
        Message.room_id == room_id,
        Message.room_type == room_type,
        Message.is_deleted == False
    ).sort([("created_at", DESCENDING)]).skip(skip).limit(limit).to_list()

    # 최신순으로 정렬된 것을 역순으로 변경 (오래된 것부터)
    return list(reversed(messages))


async def get_room_messages_count(
    room_id: int,
    room_type: str = "private"
) -> int:
    """채팅방 메시지 총 개수 조회"""
    return await Message.find(
        Message.room_id == room_id,
        Message.room_type == room_type,
        Message.is_deleted == False
    ).count()


async def mark_message_as_read(
    message_id: str,
    user_id: int,
    room_id: int
) -> MessageReadStatus:
    """메시지를 읽음으로 표시"""
    # 기존 읽음 상태 확인
    existing_read = await MessageReadStatus.find_one(
        MessageReadStatus.message_id == message_id,
        MessageReadStatus.user_id == user_id
    )

    if existing_read:
        return existing_read

    read_status = MessageReadStatus(
        message_id=message_id,
        user_id=user_id,
        room_id=room_id,
        read_at=datetime.utcnow()
    )

    await read_status.insert()
    return read_status


async def mark_multiple_messages_as_read(
    message_ids: List[str],
    user_id: int,
    room_id: int
) -> int:
    """여러 메시지를 읽음으로 표시"""
    read_count = 0

    for message_id in message_ids:
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
    """사용자의 읽지 않은 메시지 수 조회"""
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
        if message.user_id != user_id and str(message.id) not in read_message_ids:
            unread_count += 1

    return unread_count
