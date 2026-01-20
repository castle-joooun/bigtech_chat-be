"""
Message service layer for MongoDB operations.

Handles all database queries and data operations related to messages, reactions, and read status.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from beanie import PydanticObjectId
from pymongo import DESCENDING, TEXT

from app.models.messages import Message, MessageReaction, MessageReadStatus


# =============================================================================
# Message CRUD Operations
# =============================================================================

async def create_message(
    user_id: int,
    room_id: int,
    room_type: str,
    content: str,
    message_type: str = "text",
    reply_to: Optional[str] = None,
    file_url: Optional[str] = None,
    file_name: Optional[str] = None,
    file_size: Optional[int] = None,
    file_type: Optional[str] = None
) -> Message:
    """메시지 생성 (확장된 버전)"""

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
        file_url=file_url,
        file_name=file_name,
        file_size=file_size,
        file_type=file_type,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    await message.insert()
    return message


async def find_message_by_id(message_id: str) -> Optional[Message]:
    """메시지 ID로 조회"""
    try:
        return await Message.get(PydanticObjectId(message_id))
    except:
        return None


async def get_room_messages(
    room_id: int,
    room_type: str = "private",
    limit: int = 50,
    skip: int = 0,
    include_deleted: bool = False
) -> List[Message]:
    """채팅방 메시지 목록 조회 (확장된 버전)"""
    conditions = [
        Message.room_id == room_id,
        Message.room_type == room_type
    ]

    # 삭제된 메시지 제외 옵션
    if not include_deleted:
        conditions.append(Message.is_deleted == False)

    messages = await Message.find(*conditions).sort([("created_at", DESCENDING)]).skip(skip).limit(limit).to_list()

    # 최신순으로 정렬된 것을 역순으로 변경 (오래된 것부터)
    return list(reversed(messages))


async def get_room_messages_count(
    room_id: int,
    room_type: str = "private",
    include_deleted: bool = False
) -> int:
    """채팅방 메시지 총 개수 조회"""
    conditions = [
        Message.room_id == room_id,
        Message.room_type == room_type
    ]

    if not include_deleted:
        conditions.append(Message.is_deleted == False)

    return await Message.find(*conditions).count()


# =============================================================================
# Message Operations (Delete, Edit, etc.)
# =============================================================================

async def soft_delete_message(message_id: str, deleted_by_user_id: int) -> Optional[Message]:
    """메시지 소프트 삭제"""
    message = await find_message_by_id(message_id)
    if not message:
        return None

    message.soft_delete(deleted_by_user_id)
    await message.save()
    return message


async def update_message_content(message_id: str, new_content: str) -> Optional[Message]:
    """메시지 내용 수정"""
    message = await find_message_by_id(message_id)
    if not message or message.is_deleted:
        return None

    message.edit_content(new_content)
    await message.save()
    return message


async def restore_deleted_message(message_id: str) -> Optional[Message]:
    """삭제된 메시지 복원"""
    message = await find_message_by_id(message_id)
    if not message or not message.is_deleted:
        return None

    message.is_deleted = False
    message.deleted_at = None
    message.deleted_by = None
    message.updated_at = datetime.utcnow()
    await message.save()
    return message


# =============================================================================
# Message Reactions
# =============================================================================

async def add_reaction(message_id: str, user_id: int, emoji: str) -> Optional[MessageReaction]:
    """메시지에 반응 추가"""
    # 기존 반응 확인
    existing_reaction = await MessageReaction.find_one(
        MessageReaction.message_id == message_id,
        MessageReaction.user_id == user_id,
        MessageReaction.emoji == emoji
    )

    if existing_reaction:
        return existing_reaction

    reaction = MessageReaction(
        message_id=message_id,
        user_id=user_id,
        emoji=emoji,
        created_at=datetime.utcnow()
    )

    await reaction.insert()
    return reaction


async def remove_reaction(message_id: str, user_id: int, emoji: str) -> bool:
    """메시지 반응 제거"""
    reaction = await MessageReaction.find_one(
        MessageReaction.message_id == message_id,
        MessageReaction.user_id == user_id,
        MessageReaction.emoji == emoji
    )

    if reaction:
        await reaction.delete()
        return True
    return False


async def get_message_reactions(message_id: str) -> List[MessageReaction]:
    """메시지의 모든 반응 조회"""
    return await MessageReaction.find(MessageReaction.message_id == message_id).to_list()


async def get_reaction_summary(message_id: str) -> Dict[str, Any]:
    """메시지 반응 요약"""
    reactions = await get_message_reactions(message_id)
    summary = {}

    for reaction in reactions:
        emoji = reaction.emoji
        if emoji not in summary:
            summary[emoji] = {"count": 0, "users": []}
        summary[emoji]["count"] += 1
        summary[emoji]["users"].append(reaction.user_id)

    return summary


# =============================================================================
# Message Read Status
# =============================================================================

async def mark_message_as_read(message_id: str, user_id: int, room_id: int) -> MessageReadStatus:
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


async def mark_multiple_messages_as_read(message_ids: List[str], user_id: int, room_id: int) -> int:
    """여러 메시지를 읽음으로 표시"""
    read_count = 0

    for message_id in message_ids:
        # 기존 읽음 상태 확인
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


async def get_message_read_status(message_id: str) -> List[MessageReadStatus]:
    """메시지 읽음 상태 조회"""
    return await MessageReadStatus.find(MessageReadStatus.message_id == message_id).to_list()


# =============================================================================
# Message Search
# =============================================================================

async def search_messages(
    query: str,
    user_id: Optional[int] = None,
    room_id: Optional[int] = None,
    message_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 20,
    skip: int = 0
) -> List[Message]:
    """메시지 텍스트 검색"""
    conditions = [
        Message.is_deleted == False
    ]

    # 텍스트 검색 조건
    if query:
        # MongoDB 텍스트 검색 또는 정규 표현식 사용
        conditions.append({"$text": {"$search": query}})

    # 추가 필터 조건
    if user_id:
        conditions.append(Message.user_id == user_id)

    if room_id:
        conditions.append(Message.room_id == room_id)

    if message_type:
        conditions.append(Message.message_type == message_type)

    if start_date:
        conditions.append(Message.created_at >= start_date)

    if end_date:
        conditions.append(Message.created_at <= end_date)

    # 검색 실행
    if len(conditions) == 1:  # is_deleted == False만 있는 경우
        query_filter = conditions[0]
    else:
        query_filter = {"$and": conditions}

    messages = await Message.find(query_filter).sort([("created_at", DESCENDING)]).skip(skip).limit(limit).to_list()

    return messages


async def get_search_results_count(
    query: str,
    user_id: Optional[int] = None,
    room_id: Optional[int] = None,
    message_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> int:
    """메시지 검색 결과 수 조회"""
    conditions = [
        Message.is_deleted == False
    ]

    if query:
        conditions.append({"$text": {"$search": query}})

    if user_id:
        conditions.append(Message.user_id == user_id)

    if room_id:
        conditions.append(Message.room_id == room_id)

    if message_type:
        conditions.append(Message.message_type == message_type)

    if start_date:
        conditions.append(Message.created_at >= start_date)

    if end_date:
        conditions.append(Message.created_at <= end_date)

    if len(conditions) == 1:
        query_filter = conditions[0]
    else:
        query_filter = {"$and": conditions}

    return await Message.find(query_filter).count()


# =============================================================================
# Message Statistics
# =============================================================================

async def get_message_stats(user_id: Optional[int] = None, room_id: Optional[int] = None) -> Dict[str, int]:
    """메시지 통계 조회"""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)

    conditions = [Message.is_deleted == False]

    if user_id:
        conditions.append(Message.user_id == user_id)

    if room_id:
        conditions.append(Message.room_id == room_id)

    # 전체 메시지 수
    total_messages = await Message.find(*conditions).count()

    # 오늘 메시지 수
    today_conditions = conditions + [Message.created_at >= today]
    today_messages = await Message.find(*today_conditions).count()

    # 이번 주 메시지 수
    week_conditions = conditions + [Message.created_at >= week_ago]
    this_week_messages = await Message.find(*week_conditions).count()

    return {
        "total_messages": total_messages,
        "today_messages": today_messages,
        "this_week_messages": this_week_messages
    }


# =============================================================================
# Helper Functions
# =============================================================================

async def get_latest_message_in_room(
    room_id: int,
    room_type: str = "private",
    include_deleted: bool = False
) -> Optional[Message]:
    """채팅방의 최신 메시지 조회"""
    conditions = [
        Message.room_id == room_id,
        Message.room_type == room_type
    ]

    if not include_deleted:
        conditions.append(Message.is_deleted == False)

    messages = await Message.find(*conditions).sort([("created_at", DESCENDING)]).limit(1).to_list()

    return messages[0] if messages else None


async def get_replies_to_message(message_id: str) -> List[Message]:
    """특정 메시지에 대한 답장들 조회"""
    return await Message.find(
        Message.reply_to == message_id,
        Message.is_deleted == False
    ).sort([("created_at", 1)]).to_list()


async def cleanup_old_deleted_messages(days_old: int = 30) -> int:
    """오래된 삭제 메시지 정리 (실제 삭제)"""
    cutoff_date = datetime.utcnow() - timedelta(days=days_old)

    old_deleted_messages = await Message.find(
        Message.is_deleted == True,
        Message.deleted_at < cutoff_date
    ).to_list()

    count = len(old_deleted_messages)

    for message in old_deleted_messages:
        # 관련 반응들도 삭제
        reactions = await MessageReaction.find(MessageReaction.message_id == str(message.id)).to_list()
        for reaction in reactions:
            await reaction.delete()

        # 관련 읽음 상태들도 삭제
        read_statuses = await MessageReadStatus.find(MessageReadStatus.message_id == str(message.id)).to_list()
        for read_status in read_statuses:
            await read_status.delete()

        # 메시지 삭제
        await message.delete()

    return count