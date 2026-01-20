from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mysql import get_async_session
from app.models.users import User
from app.schemas.chat_room import ChatRoomCreate, ChatRoomResponse
from app.schemas.user import UserProfile
from app.api.auth import get_current_user
from app.core.errors import user_not_found_error, ResourceNotFoundException, BusinessLogicException, AuthorizationException
from app.core.validators import Validator
from app.services import chat_room_service, auth_service

router = APIRouter(prefix="/chat-rooms", tags=["Chat Rooms"])


@router.post("", response_model=ChatRoomResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_room(
    room_data: ChatRoomCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> ChatRoomResponse:
    """
    1:1 채팅방 생성 (단순화된 MVP 버전)
    
    - **participant_id**: 상대방 사용자 ID
    
    두 사용자 간에 기존 채팅방이 있으면 기존 채팅방을 반환합니다.
    """
    
    # 입력 검증
    participant_id = Validator.validate_positive_integer(room_data.participant_id, "participant_id")
    
    # 비즈니스 로직: 자기 자신과는 채팅방 생성 불가
    if current_user.id == participant_id:
        raise BusinessLogicException("Cannot create chat room with yourself")
    
    # 비즈니스 로직: 상대방 존재 확인
    participant = await auth_service.find_user_by_id(db, participant_id)
    if not participant:
        raise user_not_found_error(participant_id)
    
    # 기존 채팅방 확인 및 처리
    existing_room = await chat_room_service.find_existing_chat_room(db, current_user.id, participant_id)
    if existing_room:
        # 기존 채팅방이 있으면 타임스탬프 업데이트하고 반환
        room = await chat_room_service.update_chat_room_timestamp(db, existing_room)
    else:
        # 새 채팅방 생성 (1:1 채팅방은 별도 멤버십 불필요)
        room = await chat_room_service.create_chat_room(db, current_user.id, participant_id)
    
    # 응답 데이터 구성
    return ChatRoomResponse(
        id=room.id,
        user_1_id=room.user_1_id,
        user_2_id=room.user_2_id,
        room_type="direct",
        created_at=room.created_at,
        updated_at=room.updated_at,
        participants=[
            {"id": current_user.id, "username": current_user.username},
            {"id": participant.id, "username": participant.username}
        ],
        last_message=None
    )


@router.get("", response_model=List[ChatRoomResponse])
async def get_chat_rooms(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> List[ChatRoomResponse]:
    """
    사용자의 채팅방 목록 조회 (단순화된 MVP 버전)
    """
    
    # 사용자의 채팅방 목록 조회 (단순화된 MVP 버전)
    chat_rooms = await chat_room_service.get_user_chat_rooms(db, current_user.id)
    
    return chat_rooms


@router.get("/{room_id}", response_model=ChatRoomResponse)
async def get_chat_room(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> ChatRoomResponse:
    """
    채팅방 상세 정보 조회 (단순화된 MVP 버전)
    """
    
    # 채팅방 존재 확인
    chat_room = await chat_room_service.find_chat_room_by_id(db, room_id)
    if not chat_room:
        raise ResourceNotFoundException("Chat room")
    
    # 비즈니스 로직: 권한 확인 (채팅방 참여자인지)
    if not chat_room_service.is_user_in_chat_room(current_user.id, chat_room):
        raise AuthorizationException("Access denied to this chat room")
    
    return chat_room
