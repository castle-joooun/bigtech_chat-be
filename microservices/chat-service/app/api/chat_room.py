"""
Chat Room API (채팅방 API)
=========================

채팅방 관리를 위한 RESTful API를 정의합니다.

API 엔드포인트 목록
-------------------
| Method | Path                          | 설명                    |
|--------|-------------------------------|------------------------|
| GET    | /chat-rooms                   | 채팅방 목록 조회         |
| GET    | /chat-rooms/check/{user_id}   | 채팅방 조회/생성         |
| GET    | /chat-rooms/{room_id}         | 채팅방 상세 조회         |

MSA 원칙
--------
- User 정보는 user-service API를 통해 조회
- JWT에서 추출한 CurrentUserInfo로 인증 처리
- ChatRoom 테이블만 직접 DB 접근

관련 파일
---------
- app/services/chat_room_service.py: 비즈니스 로직
- app/models/chat_rooms.py: SQLAlchemy 모델
- app/schemas/chat_room.py: 요청/응답 스키마
"""

from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mysql import get_async_session
from app.schemas.chat_room import ChatRoomResponse
from app.api.dependencies import get_current_user, CurrentUserInfo
from shared_lib.core import ResourceNotFoundException, BusinessLogicException, AuthorizationException, Validator
from app.services import chat_room_service, auth_service

router = APIRouter(prefix="/api/chat-rooms", tags=["Chat Rooms"])


@router.get("", response_model=List[ChatRoomResponse])
async def get_chat_rooms(
    current_user: CurrentUserInfo = Depends(get_current_user),
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

    # 모든 상대방 ID 수집
    other_user_ids = []
    for room in chat_rooms:
        other_user_id = chat_room_service.get_other_participant_id(room, current_user.id)
        other_user_ids.append(other_user_id)

    # user-service API로 Batch 조회
    other_users = await auth_service.get_users_by_ids(other_user_ids)
    user_map = {u.id: u for u in other_users}

    # 각 채팅방에 last_message와 unread_count 추가
    result = []
    for room in chat_rooms:
        # 상대방 정보 조회
        other_user_id = chat_room_service.get_other_participant_id(room, current_user.id)
        other_user = user_map.get(other_user_id)

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
                {"id": current_user.id, "username": current_user.username or "Unknown"},
                {"id": other_user.id, "username": other_user.username} if other_user else {"id": other_user_id, "username": "Unknown"}
            ],
            last_message=last_message,
            unread_count=unread_count
        ))

    return result


@router.get("/check/{participant_id}", response_model=ChatRoomResponse)
async def get_or_create_chat_room(
    participant_id: int,
    current_user: CurrentUserInfo = Depends(get_current_user),
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
        raise BusinessLogicException(
            "Cannot create chat room with yourself",
            error_code="CANNOT_CHAT_SELF",
            status_code=422
        )

    # 비즈니스 로직: 상대방 존재 확인 (user-service API 호출)
    participant_exists = await auth_service.user_exists(participant_id)
    if not participant_exists:
        raise ResourceNotFoundException("User")

    # 상대방 정보 조회
    participant = await auth_service.get_user_by_id(participant_id)

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
            {"id": current_user.id, "username": current_user.username or "Unknown"},
            {"id": participant.id, "username": participant.username} if participant else {"id": participant_id, "username": "Unknown"}
        ],
        last_message=last_message,
        unread_count=unread_count
    )


@router.get("/{room_id}", response_model=ChatRoomResponse)
async def get_chat_room_detail(
    room_id: int,
    current_user: CurrentUserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> ChatRoomResponse:
    """
    채팅방 상세 조회

    Spring Boot의 GET /api/chat-rooms/{roomId}와 동일한 엔드포인트.

    - **room_id**: 채팅방 ID (경로 파라미터)
    """

    # 입력 검증
    room_id = Validator.validate_positive_integer(room_id, "room_id")

    # 채팅방 조회
    chat_room = await chat_room_service.find_chat_room_by_id(db, room_id)
    if not chat_room:
        raise ResourceNotFoundException("Chat room")

    # 권한 확인 (채팅방 참여자인지)
    if not chat_room_service.is_user_in_chat_room(current_user.id, chat_room):
        raise AuthorizationException("Access denied to this chat room")

    # 상대방 정보 조회
    other_user_id = chat_room_service.get_other_participant_id(chat_room, current_user.id)
    other_user = await auth_service.get_user_by_id(other_user_id)

    # 마지막 메시지 조회
    last_message = await chat_room_service.get_last_message(chat_room.id)

    # 읽지 않은 메시지 수 조회
    unread_count = await chat_room_service.get_unread_count(chat_room.id, current_user.id)

    return ChatRoomResponse(
        id=chat_room.id,
        user_1_id=chat_room.user_1_id,
        user_2_id=chat_room.user_2_id,
        room_type="direct",
        created_at=chat_room.created_at,
        updated_at=chat_room.updated_at,
        participants=[
            {"id": current_user.id, "username": current_user.username or "Unknown"},
            {"id": other_user.id, "username": other_user.username} if other_user else {"id": other_user_id, "username": "Unknown"}
        ],
        last_message=last_message,
        unread_count=unread_count
    )
