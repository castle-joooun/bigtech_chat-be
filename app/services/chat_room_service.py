"""
Chat room service layer for database operations.

Handles all database queries and data operations related to chat rooms.
"""

from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from app.models.chat_rooms import ChatRoom
from app.models.room_members import RoomMember
from app.models.users import User


# =============================================================================
# Chat Room CRUD Operations
# =============================================================================

async def find_chat_room_by_id(db: AsyncSession, room_id: int) -> Optional[ChatRoom]:
    """채팅방 ID로 조회"""
    result = await db.execute(
        select(ChatRoom).where(ChatRoom.id == room_id)
    )
    return result.scalar_one_or_none()


async def find_existing_chat_room(db: AsyncSession, user1_id: int, user2_id: int) -> Optional[ChatRoom]:
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


async def create_chat_room(db: AsyncSession, user1_id: int, user2_id: int) -> ChatRoom:
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


async def get_user_chat_rooms(db: AsyncSession, user_id: int) -> List[ChatRoom]:
    """사용자의 채팅방 목록 조회 (단순화된 MVP 버전)"""
    query = select(ChatRoom).where(
        or_(ChatRoom.user_1_id == user_id, ChatRoom.user_2_id == user_id)
    ).order_by(ChatRoom.updated_at.desc())
    
    result = await db.execute(query)
    return result.scalars().all()


# 레거시 함수 - 1:1 채팅에서는 더 이상 사용하지 않음 (그룹 채팅에서만 필요시 사용)
async def get_user_chat_rooms_with_settings(
    db: AsyncSession, 
    user_id: int
) -> List[Tuple[ChatRoom, RoomMember]]:
    """사용자의 채팅방 목록과 개인 설정을 함께 조회 (레거시 함수 - 그룹 채팅용)"""
    query = select(ChatRoom, RoomMember).join(
        RoomMember, 
        and_(
            RoomMember.chat_room_id == ChatRoom.id,
            RoomMember.user_id == user_id
        )
    ).where(
        or_(ChatRoom.user_1_id == user_id, ChatRoom.user_2_id == user_id)
    )
    
    # updated_at 기준 내림차순 정렬 (최근 활동순)
    query = query.order_by(ChatRoom.updated_at.desc())
    
    result = await db.execute(query)
    return result.all()


# =============================================================================
# Room Member Operations (현재 1:1 채팅에서는 미사용, 그룹 채팅용으로 보존)
# =============================================================================

# 1:1 채팅방에서는 더 이상 사용하지 않지만, 향후 그룹 채팅에서 필요할 수 있어 보존

async def find_room_member(db: AsyncSession, user_id: int, chat_room_id: int) -> Optional[RoomMember]:
    """채팅방 개인 설정 조회 (그룹 채팅용)"""
    result = await db.execute(
        select(RoomMember).where(
            and_(
                RoomMember.user_id == user_id,
                RoomMember.chat_room_id == chat_room_id
            )
        )
    )
    return result.scalar_one_or_none()


async def create_room_member(db: AsyncSession, user_id: int, chat_room_id: int) -> RoomMember:
    """새로운 채팅방 멤버십 생성 (그룹 채팅용)"""
    room_member = RoomMember(
        user_id=user_id,
        chat_room_id=chat_room_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(room_member)
    await db.commit()
    await db.refresh(room_member)
    return room_member


async def get_or_create_room_member(db: AsyncSession, user_id: int, chat_room_id: int) -> RoomMember:
    """채팅방 개인 설정 조회 또는 생성 (그룹 채팅용)"""
    room_member = await find_room_member(db, user_id, chat_room_id)
    
    if not room_member:
        room_member = await create_room_member(db, user_id, chat_room_id)
    
    return room_member


async def update_room_member_timestamp(db: AsyncSession, room_member: RoomMember) -> RoomMember:
    """채팅방 멤버십 타임스탬프 업데이트 (그룹 채팅용)"""
    room_member.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(room_member)
    return room_member


# =============================================================================
# Helper Functions
# =============================================================================

def get_other_participant_id(chat_room: ChatRoom, current_user_id: int) -> int:
    """채팅방에서 현재 사용자가 아닌 상대방의 ID를 반환"""
    return chat_room.user_2_id if chat_room.user_1_id == current_user_id else chat_room.user_1_id


def is_user_in_chat_room(user_id: int, chat_room: ChatRoom) -> bool:
    """사용자가 채팅방에 속해있는지 확인"""
    return user_id in [chat_room.user_1_id, chat_room.user_2_id]