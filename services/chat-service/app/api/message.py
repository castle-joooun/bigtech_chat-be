"""
Message API - 메시지 관련 API 엔드포인트
"""

import json
import logging
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.database.mysql import get_async_session
from app.models.user import User
from app.schemas.message import (
    MessageCreate, MessageResponse, MessageListResponse,
    MessageReadRequest, MessageReadResponse
)
from app.api.dependencies import get_current_user
from app.core.errors import ResourceNotFoundException, BusinessLogicException, AuthorizationException
from app.core.validators import Validator
from app.core.config import settings
from app.services import message_service, chat_room_service
from app.kafka.producer import get_event_producer
from app.kafka.events import MessageSent, MessagesRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.post("/{room_id}", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    room_id: int,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> MessageResponse:
    """
    메시지 전송

    - **room_id**: 채팅방 ID
    - **content**: 메시지 내용
    - **message_type**: 메시지 타입 (기본값: text)
    - **reply_to**: 답글 대상 메시지 ID (선택사항)
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

    # 답글 메시지 존재 확인 (선택사항)
    if message_data.reply_to:
        reply_message = await message_service.find_message_by_id(message_data.reply_to)
        if not reply_message or reply_message.room_id != room_id:
            raise BusinessLogicException("Reply target message not found in this room")

    if not message_data.content.strip():
        raise BusinessLogicException("Message content cannot be empty")
    if len(message_data.content) > 300:
        raise BusinessLogicException("Message content exceeds maximum length of 300 characters")

    # 메시지 생성
    message = await message_service.create_message(
        user_id=current_user.id,
        room_id=room_id,
        room_type="private",
        content=message_data.content,
        message_type=message_data.message_type,
        reply_to=message_data.reply_to
    )

    # MongoDB ObjectId를 문자열로 변환
    message_dict = message.model_dump()
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
                username=current_user.username,
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
    current_user: User = Depends(get_current_user),
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

    # MongoDB ObjectId를 문자열로 변환
    message_responses = []
    for message in messages:
        message_dict = message.model_dump()
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
    current_user: User = Depends(get_current_user)
) -> MessageReadResponse:
    """
    여러 메시지를 읽음으로 표시

    - **message_ids**: 읽음 처리할 메시지 ID 목록
    """

    if not read_request.message_ids:
        raise BusinessLogicException("Message IDs cannot be empty")

    # 메시지들이 모두 같은 방에 있는지 확인
    room_id = None
    for message_id in read_request.message_ids:
        message = await message_service.find_message_by_id(message_id)
        if not message:
            continue

        if room_id is None:
            room_id = message.room_id
        elif room_id != message.room_id:
            raise BusinessLogicException("All messages must be from the same room")

    if room_id is None:
        raise ResourceNotFoundException("No valid messages found")

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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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

                    # 해당 채팅방의 메시지만 필터링
                    if event_data.get('room_id') == room_id:
                        message_data = {
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
                            "data": json.dumps(message_data)
                        }
                        logger.debug(f"Sent Kafka message {message_data.get('id')} to user {current_user.id}")

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

    return EventSourceResponse(event_generator(), ping=30)
