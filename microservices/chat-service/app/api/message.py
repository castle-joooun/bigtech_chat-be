"""
Message API (메시지 API)
=======================

메시지 관리를 위한 RESTful API를 정의합니다.

API 엔드포인트 목록
-------------------
| Method | Path                              | 설명                |
|--------|-----------------------------------|---------------------|
| POST   | /messages/{room_id}               | 메시지 전송          |
| GET    | /messages/{room_id}               | 메시지 조회          |
| POST   | /messages/read                    | 읽음 처리           |
| GET    | /messages/room/{room_id}/unread-count | 안읽은 수 조회   |
| DELETE | /messages/{message_id}            | 메시지 삭제          |
| PUT    | /messages/{message_id}            | 메시지 수정          |
| GET    | /messages/stream/{room_id}        | SSE 실시간 스트림    |

실시간 메시지 플로우
--------------------
```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   Client A  │────▶│ POST /msg   │────▶│    MongoDB      │
│  (Sender)   │     │             │     │  (메시지 저장)   │
└─────────────┘     └──────┬──────┘     └─────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    Kafka    │
                    │ message.events
                    └──────┬──────┘
                           │
                           ▼
┌─────────────┐     ┌─────────────┐
│   Client B  │◀────│ SSE Stream  │
│  (Receiver) │     │             │
└─────────────┘     └─────────────┘
```

SSE (Server-Sent Events)
------------------------
클라이언트에서 EventSource로 연결하여 실시간 메시지 수신:

```javascript
const eventSource = new EventSource('/messages/stream/123');
eventSource.addEventListener('new_message', (event) => {
    const message = JSON.parse(event.data);
    displayMessage(message);
});
```

메시지 저장소
-------------
| 데이터       | 저장소   | 이유                       |
|-------------|---------|---------------------------|
| Message     | MongoDB | 고성능 쓰기, 비정형 데이터    |
| ReadStatus  | MongoDB | 메시지와 함께 조회           |

관련 파일
---------
- app/services/message_service.py: 비즈니스 로직
- app/models/messages.py: Beanie Document 모델
- app/kafka/events.py: MessageSent 이벤트
"""

import json
import logging
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.database.mysql import get_async_session
from app.schemas.message import (
    MessageCreate, MessageResponse, MessageListResponse,
    MessageReadRequest, MessageReadResponse, MessageUpdateRequest
)
from app.api.dependencies import get_current_user, CurrentUserInfo
from shared_lib.core import ResourceNotFoundException, BusinessLogicException, AuthorizationException, Validator
from app.core.config import settings
from app.services import message_service, chat_room_service
from app.kafka.producer import get_event_producer
from app.kafka.events import MessageSent, MessagesRead, MessageDeleted

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/messages", tags=["Messages"])


@router.post("/{room_id}", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    room_id: int,
    message_data: MessageCreate,
    current_user: CurrentUserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> MessageResponse:
    """
    메시지 전송

    - **room_id**: 채팅방 ID
    - **content**: 메시지 내용
    - **message_type**: 메시지 타입 (기본값: text)
    """

    # 입력 검증
    room_id = Validator.validate_positive_integer(room_id, "room_id")

    # 비즈니스 로직: 채팅방 존재 확인
    chat_room = await chat_room_service.find_chat_room_by_id(db, room_id)
    if not chat_room:
        raise ResourceNotFoundException("Chat room")

    # 비즈니스 로직: 권한 확인 (채팅방 참여자인지)
    if not chat_room_service.is_user_in_chat_room(current_user.id, chat_room):
        raise AuthorizationException("Access denied to this chat room")

    if not message_data.content.strip():
        raise BusinessLogicException("Message content cannot be empty", error_code="INVALID_INPUT")
    if len(message_data.content) > 300:
        raise BusinessLogicException("Message content exceeds maximum length of 300 characters", error_code="MESSAGE_CONTENT_TOO_LONG")

    # 메시지 생성
    message = await message_service.create_message(
        user_id=current_user.id,
        room_id=room_id,
        room_type="private",
        content=message_data.content,
        message_type=message_data.message_type
    )

    # 채팅방 타임스탬프 갱신 (채팅방 목록 정렬 정확도 향상)
    await chat_room_service.update_chat_room_timestamp(db, chat_room)

    # MongoDB ObjectId를 문자열로 변환 (mode="json"으로 datetime 직렬화)
    message_dict = message.model_dump(mode="json")
    message_dict["id"] = str(message.id)

    # Kafka로 실시간 브로드캐스트
    try:
        producer = get_event_producer()
        await producer.publish(
            topic=settings.kafka_topic_message_events,
            event=MessageSent(
                message_id=str(message.id),
                room_id=room_id,
                user_id=current_user.id,
                username=current_user.username or "Unknown",
                content=message_data.content,
                message_type=message_data.message_type,
                timestamp=datetime.utcnow()
            ),
            key=str(room_id)
        )
    except Exception as pub_error:
        logger.error(f"Failed to publish message to Kafka: {pub_error}")

    return MessageResponse(**message_dict)


@router.get("/{room_id}", response_model=MessageListResponse)
async def get_messages(
    room_id: int,
    current_user: CurrentUserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
    limit: int = Query(default=50, ge=1, le=100, description="메시지 개수"),
    skip: int = Query(default=0, ge=0, description="건너뛸 메시지 개수")
) -> MessageListResponse:
    """
    채팅방 메시지 조회

    - **room_id**: 채팅방 ID
    - **limit**: 조회할 메시지 개수 (기본값: 50, 최대: 100)
    - **skip**: 건너뛸 메시지 개수 (페이징용)
    """

    # 입력 검증
    room_id = Validator.validate_positive_integer(room_id, "room_id")

    # 비즈니스 로직: 채팅방 존재 확인
    chat_room = await chat_room_service.find_chat_room_by_id(db, room_id)
    if not chat_room:
        raise ResourceNotFoundException("Chat room")

    # 비즈니스 로직: 권한 확인 (채팅방 참여자인지)
    if not chat_room_service.is_user_in_chat_room(current_user.id, chat_room):
        raise AuthorizationException("Access denied to this chat room")

    # 메시지 목록 조회
    messages = await message_service.get_room_messages(
        room_id=room_id,
        room_type="private",
        limit=limit,
        skip=skip
    )

    # 전체 메시지 수 조회
    total_count = await message_service.get_room_messages_count(room_id, "private")

    # MongoDB ObjectId를 문자열로 변환 (mode="json"으로 datetime 직렬화)
    message_responses = []
    for message in messages:
        message_dict = message.model_dump(mode="json")
        message_dict["id"] = str(message.id)
        message_responses.append(MessageResponse(**message_dict))

    has_more = (skip + len(messages)) < total_count

    return MessageListResponse(
        messages=message_responses,
        total_count=total_count,
        has_more=has_more
    )


@router.post("/read", response_model=MessageReadResponse)
async def mark_messages_as_read(
    read_request: MessageReadRequest,
    current_user: CurrentUserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> MessageReadResponse:
    """
    여러 메시지를 읽음으로 표시

    - **room_id**: 채팅방 ID
    - **message_ids**: 읽음 처리할 메시지 ID 목록
    """

    if not read_request.message_ids:
        raise BusinessLogicException("Message IDs cannot be empty", error_code="INVALID_INPUT")

    room_id = read_request.room_id

    # 채팅방 존재 확인 및 권한 검증
    chat_room = await chat_room_service.find_chat_room_by_id(db, room_id)
    if not chat_room:
        raise ResourceNotFoundException("Chat room")

    if not chat_room_service.is_user_in_chat_room(current_user.id, chat_room):
        raise AuthorizationException("Access denied to this chat room")

    # 메시지들이 해당 채팅방에 속하는지 검증
    for message_id in read_request.message_ids:
        message = await message_service.find_message_by_id(message_id)
        if message and message.room_id != room_id:
            raise BusinessLogicException("All messages must be from the same room", error_code="INVALID_INPUT")

    # 메시지들을 읽음으로 표시
    read_count = await message_service.mark_multiple_messages_as_read(
        read_request.message_ids, current_user.id, room_id
    )

    # Kafka 이벤트 발행
    try:
        producer = get_event_producer()
        await producer.publish(
            topic=settings.kafka_topic_message_events,
            event=MessagesRead(
                room_id=room_id,
                user_id=current_user.id,
                message_ids=read_request.message_ids,
                timestamp=datetime.utcnow()
            ),
            key=str(room_id)
        )
    except Exception as pub_error:
        logger.error(f"Failed to publish read event to Kafka: {pub_error}")

    return MessageReadResponse(
        success=True,
        read_count=read_count,
        message=f"{read_count} messages marked as read"
    )


@router.get("/room/{room_id}/unread-count", response_model=dict)
async def get_unread_count(
    room_id: int,
    current_user: CurrentUserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> dict:
    """
    채팅방의 읽지 않은 메시지 수 조회

    - **room_id**: 채팅방 ID
    """

    # 입력 검증
    room_id = Validator.validate_positive_integer(room_id, "room_id")

    # 비즈니스 로직: 채팅방 존재 확인
    chat_room = await chat_room_service.find_chat_room_by_id(db, room_id)
    if not chat_room:
        raise ResourceNotFoundException("Chat room")

    # 비즈니스 로직: 권한 확인 (채팅방 참여자인지)
    if not chat_room_service.is_user_in_chat_room(current_user.id, chat_room):
        raise AuthorizationException("Access denied to this chat room")

    # 읽지 않은 메시지 수 조회
    unread_count = await message_service.get_unread_messages_count(room_id, current_user.id)

    return {"unread_count": unread_count}


@router.get("/stream/{room_id}")
async def stream_room_messages(
    room_id: int,
    current_user: CurrentUserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    채팅방 메시지 실시간 스트리밍 (SSE + Kafka Consumer)

    클라이언트는 이 엔드포인트로 연결하여 새 메시지를 실시간으로 받습니다.

    - **room_id**: 채팅방 ID

    Returns:
        SSE 스트림 (new_message 이벤트)
    """
    # 입력 검증
    room_id = Validator.validate_positive_integer(room_id, "room_id")

    # 비즈니스 로직: 채팅방 존재 확인
    chat_room = await chat_room_service.find_chat_room_by_id(db, room_id)
    if not chat_room:
        raise ResourceNotFoundException("Chat room")

    # 비즈니스 로직: 권한 확인 (채팅방 참여자인지)
    if not chat_room_service.is_user_in_chat_room(current_user.id, chat_room):
        raise AuthorizationException("Access denied to this chat room")

    async def event_generator():
        consumer = None

        try:
            from aiokafka import AIOKafkaConsumer
            from app.core.config import settings
            import asyncio

            consumer = AIOKafkaConsumer(
                settings.kafka_topic_message_events,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id=f"message-stream-user-{current_user.id}",
                auto_offset_reset='latest',
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )

            await consumer.start()

            # 연결 성공 알림
            yield {
                "event": "connected",
                "data": json.dumps({
                    "message": f"Connected to room {room_id}",
                    "room_id": room_id,
                    "user_id": current_user.id
                })
            }
            logger.info(f"User {current_user.id} connected to Kafka message stream for room {room_id}")

            # Kafka에서 메시지 수신 및 필터링
            async for msg in consumer:
                try:
                    event_data = msg.value

                    # 해당 채팅방의 이벤트만 필터링
                    if event_data.get('room_id') == room_id:
                        event_type = event_data.get('__event_type__', 'MessageSent')

                        if event_type == 'MessageSent':
                            # 새 메시지 이벤트
                            sse_data = {
                                "id": event_data.get('message_id'),
                                "user_id": event_data.get('user_id'),
                                "username": event_data.get('username'),
                                "room_id": event_data.get('room_id'),
                                "content": event_data.get('content'),
                                "message_type": event_data.get('message_type'),
                                "created_at": event_data.get('timestamp'),
                                "is_deleted": False
                            }
                            yield {
                                "event": "new_message",
                                "data": json.dumps(sse_data)
                            }
                            logger.debug(f"SSE new_message {sse_data.get('id')} to user {current_user.id}")

                        elif event_type == 'MessagesRead':
                            # 읽음 처리 이벤트
                            sse_data = {
                                "room_id": event_data.get('room_id'),
                                "user_id": event_data.get('user_id'),
                                "message_ids": event_data.get('message_ids', []),
                                "timestamp": event_data.get('timestamp')
                            }
                            yield {
                                "event": "messages_read",
                                "data": json.dumps(sse_data)
                            }
                            logger.debug(f"SSE messages_read to user {current_user.id}")

                        elif event_type == 'MessageDeleted':
                            # 메시지 삭제 이벤트
                            sse_data = {
                                "message_id": event_data.get('message_id'),
                                "room_id": event_data.get('room_id'),
                                "deleted_by": event_data.get('deleted_by'),
                                "timestamp": event_data.get('timestamp')
                            }
                            yield {
                                "event": "message_deleted",
                                "data": json.dumps(sse_data)
                            }
                            logger.debug(f"SSE message_deleted {sse_data.get('message_id')} to user {current_user.id}")

                        elif event_type == 'ChatRoomCreated':
                            # 채팅방 생성 이벤트
                            sse_data = {
                                "room_id": event_data.get('room_id'),
                                "room_type": event_data.get('room_type'),
                                "creator_id": event_data.get('creator_id'),
                                "participant_ids": event_data.get('participant_ids', []),
                                "timestamp": event_data.get('timestamp')
                            }
                            yield {
                                "event": "chat_room_created",
                                "data": json.dumps(sse_data)
                            }
                            logger.debug(f"SSE chat_room_created {sse_data.get('room_id')} to user {current_user.id}")

                except Exception as e:
                    logger.error(f"Failed to process Kafka message: {e}")
                    continue

        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for user {current_user.id}, room {room_id}")
            raise

        except Exception as e:
            logger.error(f"Error in Kafka SSE stream for user {current_user.id}, room {room_id}: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"message": "Stream error occurred"})
            }

        finally:
            if consumer:
                try:
                    await consumer.stop()
                    logger.info(f"Kafka consumer stopped for user {current_user.id}, room {room_id}")
                except Exception as e:
                    logger.error(f"Error stopping Kafka consumer: {e}")

    # ping=30: 30초마다 keepalive ping (Spring Boot의 @Scheduled ping과 동일)
    # media_type: SSE 표준 MIME 타입
    return EventSourceResponse(
        event_generator(),
        ping=30,
        media_type="text/event-stream"
    )


@router.delete("/{message_id}", status_code=status.HTTP_200_OK)
async def delete_message(
    message_id: str,
    current_user: CurrentUserInfo = Depends(get_current_user)
) -> dict:
    """
    메시지 삭제 (Soft Delete)

    - **message_id**: 메시지 ID (MongoDB ObjectId)
    - 본인이 작성한 메시지만 삭제 가능
    """

    # 메시지 조회
    message = await message_service.find_message_by_id(message_id)
    if not message:
        raise ResourceNotFoundException("Message")

    # 본인 메시지만 삭제 가능
    if message.user_id != current_user.id:
        raise AuthorizationException("You can only delete your own messages")

    # 이미 삭제된 메시지 확인
    if message.is_deleted:
        raise BusinessLogicException("Message is already deleted", error_code="MESSAGE_ALREADY_DELETED")

    # Soft Delete 처리
    message.soft_delete(current_user.id)
    await message.save()

    # 캐시 무효화
    chat_cache = None
    try:
        from app.services.cache_service import get_chat_cache
        chat_cache = get_chat_cache()
        if chat_cache:
            await chat_cache.invalidate_room_messages(message.room_id)
    except Exception:
        pass

    # Kafka 이벤트 발행
    try:
        producer = get_event_producer()
        await producer.publish(
            topic=settings.kafka_topic_message_events,
            event=MessageDeleted(
                message_id=str(message.id),
                room_id=message.room_id,
                deleted_by=current_user.id,
                timestamp=datetime.utcnow()
            ),
            key=str(message.room_id)
        )
    except Exception as pub_error:
        logger.error(f"Failed to publish delete event to Kafka: {pub_error}")

    return {"message": "Message deleted"}


@router.put("/{message_id}", response_model=MessageResponse)
async def update_message(
    message_id: str,
    update_data: MessageUpdateRequest,
    current_user: CurrentUserInfo = Depends(get_current_user)
) -> MessageResponse:
    """
    메시지 수정

    - **message_id**: 메시지 ID (MongoDB ObjectId)
    - **content**: 수정할 메시지 내용 (1-300자)
    - 본인이 작성한 메시지만 수정 가능
    - 삭제된 메시지는 수정 불가
    """

    # 메시지 조회
    message = await message_service.find_message_by_id(message_id)
    if not message:
        raise ResourceNotFoundException("Message")

    # 본인 메시지만 수정 가능
    if message.user_id != current_user.id:
        raise AuthorizationException("You can only edit your own messages")

    # 삭제된 메시지는 수정 불가
    if message.is_deleted:
        raise BusinessLogicException("Cannot edit a deleted message", error_code="MESSAGE_ALREADY_DELETED")

    # 메시지 내용 검증
    if not update_data.content.strip():
        raise BusinessLogicException("Message content cannot be empty", error_code="INVALID_INPUT")
    if len(update_data.content) > 300:
        raise BusinessLogicException("Message content exceeds maximum length of 300 characters", error_code="MESSAGE_CONTENT_TOO_LONG")

    # 메시지 수정
    message.edit_content(update_data.content)
    await message.save()

    # 캐시 무효화
    try:
        from app.services.cache_service import get_chat_cache
        chat_cache = get_chat_cache()
        if chat_cache:
            await chat_cache.invalidate_room_messages(message.room_id)
    except Exception:
        pass

    # 응답 변환
    message_dict = message.model_dump(mode="json")
    message_dict["id"] = str(message.id)

    return MessageResponse(**message_dict)
