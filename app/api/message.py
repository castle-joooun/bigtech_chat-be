import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, status, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.database.mysql import get_async_session
from app.database.redis import get_redis
from app.models.users import User
from app.schemas.message import (
    MessageCreate, MessageResponse, MessageListResponse, MessageUpdate,
    MessageDeleteRequest, MessageImageUpload, MessageReactionCreate,
    MessageReactionResponse, MessageReadRequest, MessageReadResponse,
    MessageSearchRequest, MessageSearchResponse, MessageStatsResponse
)
from app.api.auth import get_current_user
from app.core.errors import ResourceNotFoundException, BusinessLogicException, AuthorizationException
from app.core.validators import Validator
from app.services import message_service, chat_room_service, file_service

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
    메시지 전송 (단순화된 MVP 버전)
    
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
    # TODO: 답급 메시지 활용 안하는것 같음. 확인 필요.
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
        room_type="private",  # MVP에서는 1:1 채팅만 지원
        content=message_data.content,
        message_type=message_data.message_type,
        reply_to=message_data.reply_to
    )

    # MongoDB ObjectId를 문자열로 변환
    message_dict = message.model_dump()
    message_dict["id"] = str(message.id)

    # 새 메시지를 Redis 캐시에 추가
    try:
        from app.services.message_cache_service import cache_new_message
        cache_dict = {
            "id": str(message.id),
            "room_id": room_id,
            "sender_id": current_user.id,
            "content": message_data.content,
            "message_type": message_data.message_type,
            "created_at": message.created_at.isoformat(),
            "is_deleted": False,
            "reply_to": message_data.reply_to
        }
        await cache_new_message(room_id, "private", cache_dict)
    except Exception as cache_error:
        logger.warning(f"Failed to cache new message: {cache_error}")

    # Kafka로 실시간 브로드캐스트 (Event-Driven Architecture)
    try:
        from app.infrastructure.kafka.producer import get_event_producer
        from app.domain.events.message_events import MessageSent
        from datetime import datetime, timezone

        producer = get_event_producer()

        # MessageSent Domain Event 생성
        event = MessageSent(
            message_id=str(message.id),
            room_id=room_id,
            user_id=current_user.id,
            username=current_user.username,
            content=message_data.content,
            message_type=message_data.message_type,
            timestamp=datetime.now(timezone.utc)
        )

        # Kafka로 이벤트 발행 (room_id를 key로 사용하여 순서 보장)
        await producer.publish(
            topic='message.events',
            event=event,
            key=str(room_id)
        )
        logger.info(f"Published MessageSent event to Kafka: message_id={message.id}, room_id={room_id}")
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
    채팅방 메시지 조회 (Redis 캐시 우선 조회)

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

    # Redis 캐시에서 메시지 조회 (캐시 미스 시 MongoDB 조회)
    try:
        from app.services.message_cache_service import get_cached_room_messages

        cached_messages = await get_cached_room_messages(
            room_id=room_id,
            room_type="private",
            limit=limit,
            skip=skip
        )

        # 캐시된 메시지들을 MessageResponse로 변환
        message_responses = []
        for msg_dict in cached_messages:
            message_responses.append(MessageResponse(**msg_dict))

        # 전체 메시지 수 조회 (캐시에서 가져올 수 없는 경우 DB에서 조회)
        total_count = await message_service.get_room_messages_count(room_id, "private")

        has_more = (skip + len(message_responses)) < total_count

        return MessageListResponse(
            messages=message_responses,
            total_count=total_count,
            has_more=has_more
        )

    except Exception as cache_error:
        # 캐시 오류 시 기존 MongoDB 조회로 폴백
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Cache error, falling back to DB: {cache_error}")

        # 메시지 목록 조회 (기존 방식)
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


# ============================================================================
# MVP에서 제외: 메시지 수정/삭제 기능
# ============================================================================

# @router.put("/{message_id}", response_model=MessageResponse)
# async def update_message(
#     message_id: str,
#     message_data: MessageUpdate,
#     current_user: User = Depends(get_current_user)
# ) -> MessageResponse:
#     """
#     메시지 내용 수정
#
#     - **message_id**: 수정할 메시지 ID
#     - **content**: 새로운 메시지 내용
#     """
#
#     # 메시지 존재 확인
#     message = await message_service.find_message_by_id(message_id)
#     if not message:
#         raise ResourceNotFoundException("Message")
#
#     # 권한 확인 (본인이 작성한 메시지만 수정 가능)
#     if message.user_id != current_user.id:
#         raise AuthorizationException("You can only edit your own messages")
#
#     # 삭제된 메시지는 수정 불가
#     if message.is_deleted:
#         raise BusinessLogicException("Cannot edit deleted message")
#
#     # 메시지 수정
#     updated_message = await message_service.update_message_content(message_id, message_data.content)
#     if not updated_message:
#         raise BusinessLogicException("Failed to update message")
#
#     # MongoDB ObjectId를 문자열로 변환
#     message_dict = updated_message.model_dump()
#     message_dict["id"] = str(updated_message.id)
#
#     return MessageResponse(**message_dict)
#
#
# @router.delete("/{message_id}", response_model=MessageResponse)
# async def delete_message(
#     message_id: str,
#     delete_request: MessageDeleteRequest,
#     current_user: User = Depends(get_current_user)
# ) -> MessageResponse:
#     """
#     메시지 삭제 (소프트 삭제)
#
#     - **message_id**: 삭제할 메시지 ID
#     - **delete_for_everyone**: 모든 사용자에게서 삭제할지 여부
#     """
#
#     # 메시지 존재 확인
#     message = await message_service.find_message_by_id(message_id)
#     if not message:
#         raise ResourceNotFoundException("Message")
#
#     # 권한 확인 (본인이 작성한 메시지만 삭제 가능)
#     if message.user_id != current_user.id:
#         raise AuthorizationException("You can only delete your own messages")
#
#     # 이미 삭제된 메시지 확인
#     if message.is_deleted:
#         raise BusinessLogicException("Message is already deleted")
#
#     # 메시지 삭제
#     deleted_message = await message_service.soft_delete_message(message_id, current_user.id)
#     if not deleted_message:
#         raise BusinessLogicException("Failed to delete message")
#
#     # MongoDB ObjectId를 문자열로 변환
#     message_dict = deleted_message.model_dump()
#     message_dict["id"] = str(deleted_message.id)
#
#     return MessageResponse(**message_dict)


# ============================================================================
# MVP에서 제외: 이모지 반응 기능
# ============================================================================

# @router.post("/{message_id}/reactions", response_model=MessageReactionResponse, status_code=status.HTTP_201_CREATED)
# async def add_reaction(
#     message_id: str,
#     reaction_data: MessageReactionCreate,
#     current_user: User = Depends(get_current_user)
# ) -> MessageReactionResponse:
#     """
#     메시지에 이모지 반응 추가
#
#     - **message_id**: 반응을 추가할 메시지 ID
#     - **emoji**: 이모지
#     """
#
#     # 메시지 존재 확인
#     message = await message_service.find_message_by_id(message_id)
#     if not message:
#         raise ResourceNotFoundException("Message")
#
#     # 삭제된 메시지에는 반응 불가
#     if message.is_deleted:
#         raise BusinessLogicException("Cannot react to deleted message")
#
#     # 반응 추가
#     reaction = await message_service.add_reaction(message_id, current_user.id, reaction_data.emoji)
#     if not reaction:
#         raise BusinessLogicException("Failed to add reaction")
#
#     # MongoDB ObjectId를 문자열로 변환
#     reaction_dict = reaction.model_dump()
#     reaction_dict["id"] = str(reaction.id)
#
#     return MessageReactionResponse(**reaction_dict)
#
#
# @router.delete("/{message_id}/reactions/{emoji}")
# async def remove_reaction(
#     message_id: str,
#     emoji: str,
#     current_user: User = Depends(get_current_user)
# ) -> dict:
#     """
#     메시지 이모지 반응 제거
#
#     - **message_id**: 반응을 제거할 메시지 ID
#     - **emoji**: 제거할 이모지
#     """
#
#     # 메시지 존재 확인
#     message = await message_service.find_message_by_id(message_id)
#     if not message:
#         raise ResourceNotFoundException("Message")
#
#     # 반응 제거
#     success = await message_service.remove_reaction(message_id, current_user.id, emoji)
#     if not success:
#         raise ResourceNotFoundException("Reaction not found")
#
#     return {"success": True, "message": "Reaction removed successfully"}
#
#
# @router.get("/{message_id}/reactions", response_model=dict)
# async def get_message_reactions(
#     message_id: str,
#     current_user: User = Depends(get_current_user)
# ) -> dict:
#     """
#     메시지의 모든 반응 조회
#
#     - **message_id**: 메시지 ID
#     """
#
#     # 메시지 존재 확인
#     message = await message_service.find_message_by_id(message_id)
#     if not message:
#         raise ResourceNotFoundException("Message")
#
#     # 반응 요약 조회
#     reactions_summary = await message_service.get_reaction_summary(message_id)
#
#     return reactions_summary


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
            continue  # 존재하지 않는 메시지는 건너뛰기

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
            # Kafka Consumer 생성
            from aiokafka import AIOKafkaConsumer
            from app.infrastructure.kafka.config import kafka_config
            import asyncio

            consumer = AIOKafkaConsumer(
                kafka_config.topic_message_events,
                bootstrap_servers=kafka_config.bootstrap_servers,
                group_id=f"message-stream-user-{current_user.id}",  # 각 사용자별 독립적인 Consumer Group
                auto_offset_reset='latest',  # 연결 시점 이후의 메시지만 수신
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
                        # MessageSent 이벤트를 클라이언트 형식으로 변환
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

                        # SSE 이벤트로 전송
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
            # Kafka Consumer 정리
            if consumer:
                try:
                    await consumer.stop()
                    logger.info(f"Kafka consumer stopped for user {current_user.id}, room {room_id}")
                except Exception as e:
                    logger.error(f"Error stopping Kafka consumer: {e}")

    return EventSourceResponse(event_generator(), ping=30)


# ============================================================================
# MVP에서 제외: 고급 기능 (검색, 이미지 업로드, 통계)
# ============================================================================

# @router.post("/search", response_model=MessageSearchResponse)
# async def search_messages(
#     search_request: MessageSearchRequest,
#     current_user: User = Depends(get_current_user)
# ) -> MessageSearchResponse:
#     """
#     메시지 검색
#
#     - **query**: 검색 키워드
#     - **room_id**: 특정 채팅방에서만 검색 (선택사항)
#     - **message_type**: 메시지 타입 필터 (선택사항)
#     - **start_date**: 시작 날짜 (선택사항)
#     - **end_date**: 종료 날짜 (선택사항)
#     - **limit**: 검색 결과 개수 (기본값: 20)
#     - **skip**: 건너뛸 결과 수 (기본값: 0)
#     """
#
#     # 메시지 검색 실행
#     messages = await message_service.search_messages(
#         query=search_request.query,
#         user_id=current_user.id,  # 현재 사용자와 관련된 메시지만 검색
#         room_id=search_request.room_id,
#         message_type=search_request.message_type,
#         start_date=search_request.start_date,
#         end_date=search_request.end_date,
#         limit=search_request.limit,
#         skip=search_request.skip
#     )
#
#     # 전체 검색 결과 수 조회
#     total_count = await message_service.get_search_results_count(
#         query=search_request.query,
#         user_id=current_user.id,
#         room_id=search_request.room_id,
#         message_type=search_request.message_type,
#         start_date=search_request.start_date,
#         end_date=search_request.end_date
#     )
#
#     # MongoDB ObjectId를 문자열로 변환
#     message_responses = []
#     for message in messages:
#         message_dict = message.model_dump()
#         message_dict["id"] = str(message.id)
#         message_responses.append(MessageResponse(**message_dict))
#
#     has_more = (search_request.skip + len(messages)) < total_count
#
#     return MessageSearchResponse(
#         messages=message_responses,
#         total_count=total_count,
#         has_more=has_more,
#         search_query=search_request.query
#     )
#
#
# @router.post("/upload-image/{room_id}", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
# async def upload_image_message(
#     room_id: int,
#     image_data: MessageImageUpload = Depends(),
#     file: UploadFile = File(...),
#     current_user: User = Depends(get_current_user),
#     db: AsyncSession = Depends(get_async_session)
# ) -> MessageResponse:
#     """
#     이미지 메시지 업로드
#
#     - **room_id**: 채팅방 ID
#     - **file**: 업로드할 이미지 파일 (최대 5MB)
#     - **caption**: 이미지 설명 (선택사항)
#     - **reply_to**: 답글 대상 메시지 ID (선택사항)
#     """
#
#     # 입력 검증
#     room_id = Validator.validate_positive_integer(room_id, "room_id")
#
#     # 비즈니스 로직: 채팅방 존재 확인
#     chat_room = await chat_room_service.find_chat_room_by_id(db, room_id)
#     if not chat_room:
#         raise ResourceNotFoundException("Chat room")
#
#     # 비즈니스 로직: 권한 확인 (채팅방 참여자인지)
#     if not chat_room_service.is_user_in_chat_room(current_user.id, chat_room):
#         raise AuthorizationException("Access denied to this chat room")
#
#     # 파일 검증 및 업로드
#     try:
#         await file_service.validate_uploaded_file(file)
#         file_url = await file_service.save_message_image(file, current_user.id)
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))
#
#     # 답글 메시지 존재 확인 (선택사항)
#     if image_data.reply_to:
#         reply_message = await message_service.find_message_by_id(image_data.reply_to)
#         if not reply_message or reply_message.room_id != room_id:
#             raise BusinessLogicException("Reply target message not found in this room")
#
#     # 이미지 메시지 생성
#     message = await message_service.create_message(
#         user_id=current_user.id,
#         room_id=room_id,
#         room_type="private",  # MVP에서는 1:1 채팅만 지원
#         content=image_data.caption or "Image",
#         message_type="image",
#         reply_to=image_data.reply_to,
#         file_url=file_url,
#         file_name=file.filename,
#         file_size=file.size,
#         file_type=file.content_type
#     )
#
#     # MongoDB ObjectId를 문자열로 변환
#     message_dict = message.model_dump()
#     message_dict["id"] = str(message.id)
#
#     return MessageResponse(**message_dict)
#
#
# @router.get("/stats", response_model=MessageStatsResponse)
# async def get_message_stats(
#     current_user: User = Depends(get_current_user),
#     room_id: Optional[int] = Query(None, description="특정 채팅방 통계 (선택사항)")
# ) -> MessageStatsResponse:
#     """
#     메시지 통계 조회
#
#     - **room_id**: 특정 채팅방 통계 조회 (선택사항)
#     """
#
#     # 메시지 통계 조회
#     stats = await message_service.get_message_stats(
#         user_id=current_user.id,
#         room_id=room_id
#     )
#
#     # 읽지 않은 메시지 수 조회 (room_id가 지정된 경우만)
#     unread_messages = 0
#     if room_id:
#         unread_messages = await message_service.get_unread_messages_count(room_id, current_user.id)
#
#     return MessageStatsResponse(
#         total_messages=stats["total_messages"],
#         unread_messages=unread_messages,
#         today_messages=stats["today_messages"],
#         this_week_messages=stats["this_week_messages"]
#     )