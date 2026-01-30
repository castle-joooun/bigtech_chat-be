"""
Chat Room API - 채팅방 관련 API 엔드포인트
"""

from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mysql import get_async_session
from app.models.user import User
from app.schemas.chat_room import ChatRoomResponse
from app.api.dependencies import get_current_user
from app.core.errors import ResourceNotFoundException, BusinessLogicException
from app.core.validators import Validator
from app.services import chat_room_service, auth_service

router = APIRouter(prefix="/chat-rooms", tags=["Chat Rooms"])


@router.get("", response_model=List[ChatRoomResponse])
async def get_chat_rooms(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
    skip: int = Query(0, ge=0, description="건너뛸 채팅방 수"),
    limit: int = Query(10, ge=1, le=100, description="조회할 채팅방 수 (최대 100)")
) -> List[ChatRoomResponse]:
    """
    사용자의 채팅방 목록 조회 (페이지네이션 포함)

    - **skip**: 건너뛸 채팅방 수 (기본: 0)
    - **limit**: 조회할 채팅방 수 (기본: 10, 최대: 100)
    """

    # 사용자의 채팅방 목록 조회
    chat_rooms = await chat_room_service.get_user_chat_rooms(
        db, current_user.id, skip=skip, limit=limit
    )

    # 각 채팅방에 last_message와 unread_count 추가
    result = []
    for room in chat_rooms:
        # 상대방 정보 조회
        other_user_id = chat_room_service.get_other_participant_id(room, current_user.id)
        other_user = await auth_service.find_user_by_id(db, other_user_id)

        # 마지막 메시지 조회
        last_message = await chat_room_service.get_last_message(room.id)

        # 읽지 않은 메시지 수 조회
        unread_count = await chat_room_service.get_unread_count(room.id, current_user.id)

        result.append(ChatRoomResponse(
            id=room.id,
            user_1_id=room.user_1_id,
            user_2_id=room.user_2_id,
            room_type="direct",
            created_at=room.created_at,
            updated_at=room.updated_at,
            participants=[
                {"id": current_user.id, "username": current_user.username},
                {"id": other_user.id, "username": other_user.username} if other_user else {"id": other_user_id, "username": "Unknown"}
            ],
            last_message=last_message,
            unread_count=unread_count
        ))

    return result


@router.get("/check/{participant_id}", response_model=ChatRoomResponse)
async def get_or_create_chat_room(
    participant_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> ChatRoomResponse:
    """
    1:1 채팅방 조회 또는 생성 (통합 엔드포인트)

    현재 사용자와 상대방 사용자 간의 채팅방을 조회하거나 생성합니다.
    - 기존 채팅방이 있으면 해당 채팅방 정보를 반환
    - 없으면 새로운 채팅방을 생성하고 정보를 반환

    - **participant_id**: 상대방 사용자 ID (경로 파라미터)
    """

    # 입력 검증
    participant_id = Validator.validate_positive_integer(participant_id, "participant_id")

    # 비즈니스 로직: 자기 자신과는 채팅방 생성 불가
    if current_user.id == participant_id:
        raise BusinessLogicException("Cannot create chat room with yourself")

    # 비즈니스 로직: 상대방 존재 확인
    participant = await auth_service.find_user_by_id(db, participant_id)
    if not participant:
        raise ResourceNotFoundException("User")

    # 기존 채팅방 확인 및 처리
    existing_room = await chat_room_service.find_existing_chat_room(db, current_user.id, participant_id)
    if existing_room:
        # 기존 채팅방이 있으면 타임스탬프 업데이트하고 반환
        room = await chat_room_service.update_chat_room_timestamp(db, existing_room)
    else:
        # 새 채팅방 생성
        room = await chat_room_service.create_chat_room(db, current_user.id, participant_id)

    # 마지막 메시지 조회 (MongoDB)
    last_message = await chat_room_service.get_last_message(room.id)

    # 읽지 않은 메시지 수 조회
    unread_count = await chat_room_service.get_unread_count(room.id, current_user.id)

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
        last_message=last_message,
        unread_count=unread_count
    )
