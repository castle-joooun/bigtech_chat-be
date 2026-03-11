"""
Chat Room Service - 채팅방 관련 비즈니스 로직
"""

from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_

from app.models.chat_rooms import ChatRoom
from app.models.messages import Message, MessageReadStatus


async def find_chat_room_by_id(db: AsyncSession, room_id: int) -> Optional[ChatRoom]:
    """채팅방 ID로 조회"""
    result = await db.execute(
        select(ChatRoom).where(ChatRoom.id == room_id)
    )
    return result.scalar_one_or_none()


async def find_existing_chat_room(
    db: AsyncSession,
    user1_id: int,
    user2_id: int
) -> Optional[ChatRoom]:
    """두 사용자 간의 기존 채팅방 조회"""
    result = await db.execute(
        select(ChatRoom).where(
            or_(
                and_(ChatRoom.user_1_id == user1_id, ChatRoom.user_2_id == user2_id),
                and_(ChatRoom.user_1_id == user2_id, ChatRoom.user_2_id == user1_id)
            )
        )
    )
    return result.scalar_one_or_none()


async def create_chat_room(
    db: AsyncSession,
    user1_id: int,
    user2_id: int
) -> ChatRoom:
    """새 채팅방 생성 (user_id가 작은 쪽을 user_1로 설정)"""
    user_1_id = min(user1_id, user2_id)
    user_2_id = max(user1_id, user2_id)

    new_room = ChatRoom(
        user_1_id=user_1_id,
        user_2_id=user_2_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db.add(new_room)
    await db.commit()
    await db.refresh(new_room)

    return new_room


async def update_chat_room_timestamp(db: AsyncSession, chat_room: ChatRoom) -> ChatRoom:
    """채팅방 타임스탬프 업데이트"""
    chat_room.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(chat_room)
    return chat_room


async def get_user_chat_rooms(
    db: AsyncSession,
    user_id: int,
    skip: int = 0,
    limit: int = 10
) -> List[ChatRoom]:
    """사용자의 채팅방 목록 조회 (페이지네이션 포함)"""
    query = select(ChatRoom).where(
        or_(ChatRoom.user_1_id == user_id, ChatRoom.user_2_id == user_id)
    ).order_by(ChatRoom.updated_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


def get_other_participant_id(chat_room: ChatRoom, current_user_id: int) -> int:
    """채팅방에서 현재 사용자가 아닌 상대방의 ID를 반환"""
    return chat_room.user_2_id if chat_room.user_1_id == current_user_id else chat_room.user_1_id


def is_user_in_chat_room(user_id: int, chat_room: ChatRoom) -> bool:
    """사용자가 채팅방에 속해있는지 확인"""
    return user_id in [chat_room.user_1_id, chat_room.user_2_id]


async def get_last_message(room_id: int) -> Optional[Dict]:
    """채팅방의 마지막 메시지 조회 (MongoDB)"""
    try:
        last_msg = await Message.find(
            Message.room_id == room_id,
            Message.is_deleted == False
        ).sort(-Message.created_at).limit(1).first_or_none()

        if not last_msg:
            return None

        return {
            "id": str(last_msg.id),
            "user_id": last_msg.user_id,
            "content": last_msg.content,
            "message_type": last_msg.message_type,
            "created_at": last_msg.created_at.isoformat() if last_msg.created_at else None
        }
    except Exception:
        return None


async def get_unread_count(room_id: int, user_id: int) -> int:
    """사용자의 읽지 않은 메시지 수 조회 (MongoDB)"""
    try:
        # 채팅방의 모든 메시지 조회 (자신의 메시지 제외)
        all_messages = await Message.find(
            Message.room_id == room_id,
            Message.user_id != user_id,
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

        # 읽지 않은 메시지 수 계산
        unread_count = 0
        for message in all_messages:
            if str(message.id) not in read_message_ids:
                unread_count += 1

        return unread_count
    except Exception:
        return 0
