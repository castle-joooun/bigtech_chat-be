"""
Friend API Endpoints (친구 API 엔드포인트)
=========================================

친구 관계 관리를 위한 RESTful API를 정의합니다.

API 엔드포인트 목록
-------------------
| Method | Path                          | 설명                |
|--------|-------------------------------|---------------------|
| POST   | /friends/request              | 친구 요청 전송       |
| PUT    | /friends/status/{user_id}     | 요청 수락/거절       |
| GET    | /friends/list                 | 친구 목록 조회       |
| GET    | /friends/requests             | 요청 목록 조회       |
| DELETE | /friends/request/{user_id}    | 요청 취소           |

Note: 사용자 검색은 user-service의 /users/search 사용

MSA 원칙
--------
- User 정보는 user-service API를 통해 조회
- JWT에서 추출한 CurrentUserInfo로 인증 처리
- Friendship 테이블만 직접 DB 접근

관련 파일
---------
- app/services/friendship_service.py: 비즈니스 로직
- app/kafka/events.py: 도메인 이벤트
- app/schemas/friendship.py: 요청/응답 스키마
"""

from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mysql import get_async_session
from app.schemas.friendship import (
    FriendshipCreate,
    FriendshipResponse,
    FriendshipStatusUpdate,
    FriendListResponse,
    FriendRequestListResponse
)
from app.api.dependencies import get_current_user, CurrentUserInfo
from app.services.friendship_service import FriendshipService
from app.services import auth_service
from app.core.config import settings
from app.kafka.producer import get_event_producer
from app.kafka.events import (
    FriendRequestSent,
    FriendRequestAccepted,
    FriendRequestRejected,
    FriendRequestCancelled
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/friends", tags=["Friends"])


@router.post("/request", response_model=FriendshipResponse,
             status_code=status.HTTP_201_CREATED)
async def send_friend_request(
        friend_request: FriendshipCreate,
        current_user: CurrentUserInfo = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """
    친구 요청을 전송합니다.

    Args:
        friend_request: 친구 요청 데이터 (target_user_id)
        current_user: 현재 인증된 사용자 정보
        db: 데이터베이스 세션

    Returns:
        FriendshipResponse: 생성된 친구 요청 정보
    """
    target_user_id = friend_request.user_id_2

    # 자기 자신에게 친구 요청 불가
    if current_user.id == target_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send friend request to yourself"
        )

    # 대상 사용자 존재 확인 (user-service API 호출)
    target_exists = await auth_service.user_exists(target_user_id)
    if not target_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user not found"
        )

    # 대상 사용자 정보 조회 (Kafka 이벤트용)
    target_user = await auth_service.get_user_by_id(target_user_id)

    try:
        # 친구 요청 전송
        friendship = await FriendshipService.send_friend_request(
            db, current_user.id, target_user_id
        )

        # Kafka 이벤트 발행
        producer = get_event_producer()
        await producer.publish(
            topic=settings.kafka_topic_friend_events,
            event=FriendRequestSent(
                friendship_id=friendship.id,
                requester_id=current_user.id,
                requester_name=current_user.username or "Unknown",
                addressee_id=target_user_id,
                addressee_name=target_user.username if target_user else "Unknown",
                timestamp=datetime.utcnow()
            ),
            key=str(friendship.id)
        )

        return FriendshipResponse(
            id=friendship.id,
            user_id_1=friendship.user_id_1,
            user_id_2=friendship.user_id_2,
            status=friendship.status,
            created_at=friendship.created_at,
            updated_at=friendship.updated_at,
            deleted_at=friendship.deleted_at
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error sending friend request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send friend request"
        )


@router.put("/status/{requester_user_id}", response_model=FriendshipResponse)
async def update_friend_request_status(
        requester_user_id: int,
        status_update: FriendshipStatusUpdate,
        current_user: CurrentUserInfo = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """
    친구 요청 상태를 업데이트합니다 (수락/거절).

    Args:
        requester_user_id: 친구 요청을 보낸 사용자 ID
        status_update: 상태 업데이트 정보 (accept/reject)
        current_user: 현재 인증된 사용자 정보
        db: 데이터베이스 세션

    Returns:
        FriendshipResponse: 업데이트된 친구 관계 정보
    """
    try:
        # 액션 검증
        status_update.validate_action()

        if status_update.action == "accept":
            friendship = await FriendshipService.accept_friend_request_by_requester(
                db, requester_user_id, current_user.id
            )

            # 요청자 정보 조회 (Kafka 이벤트용)
            requester = await auth_service.get_user_by_id(requester_user_id)

            # Kafka 이벤트 발행
            producer = get_event_producer()
            await producer.publish(
                topic=settings.kafka_topic_friend_events,
                event=FriendRequestAccepted(
                    friendship_id=friendship.id,
                    requester_id=requester_user_id,
                    requester_name=requester.username if requester else "Unknown",
                    addressee_id=current_user.id,
                    addressee_name=current_user.username or "Unknown",
                    timestamp=datetime.utcnow()
                ),
                key=str(friendship.id)
            )

            return FriendshipResponse(
                id=friendship.id,
                user_id_1=friendship.user_id_1,
                user_id_2=friendship.user_id_2,
                status=friendship.status,
                created_at=friendship.created_at,
                updated_at=friendship.updated_at,
                deleted_at=friendship.deleted_at
            )

        elif status_update.action == "reject":
            await FriendshipService.reject_friend_request_by_requester(
                db, requester_user_id, current_user.id
            )

            # Kafka 이벤트 발행
            producer = get_event_producer()
            await producer.publish(
                topic=settings.kafka_topic_friend_events,
                event=FriendRequestRejected(
                    friendship_id=0,  # Already deleted
                    requester_id=requester_user_id,
                    addressee_id=current_user.id,
                    timestamp=datetime.utcnow()
                ),
                key=str(requester_user_id)
            )

            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=200,
                content={"message": "Friend request rejected successfully"}
            )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating friend request status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update friend request status"
        )


@router.get("/list", response_model=List[FriendListResponse])
async def get_friends_list(
        current_user: CurrentUserInfo = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """
    현재 사용자의 친구 목록을 조회합니다.

    Args:
        current_user: 현재 인증된 사용자 정보
        db: 데이터베이스 세션

    Returns:
        List[FriendListResponse]: 친구 목록
    """
    try:
        friends = await FriendshipService.get_friends_list(db, current_user.id)

        friend_list = []
        for friend_user, friendship_date in friends:
            friend_list.append(FriendListResponse(
                user_id=friend_user.id,
                username=friend_user.username,
                email="",  # 이메일은 UserProfile에서 제공하지 않음
                last_seen_at=friend_user.last_seen_at
            ))

        return friend_list

    except Exception as e:
        logger.error(f"Error getting friends list: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get friends list"
        )


@router.get("/requests", response_model=dict)
async def get_friend_requests(
        current_user: CurrentUserInfo = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """
    현재 사용자의 친구 요청 목록을 조회합니다.

    Args:
        current_user: 현재 인증된 사용자 정보
        db: 데이터베이스 세션

    Returns:
        dict: 받은 요청과 보낸 요청 목록
    """
    try:
        received_requests, sent_requests = await FriendshipService.get_friend_requests(
            db, current_user.id
        )

        received_list = []
        for friendship, requester in received_requests:
            received_list.append(FriendRequestListResponse(
                friendship_id=friendship.id,
                user_id=requester.id,
                username=requester.username,
                email="",  # 이메일은 UserProfile에서 제공하지 않음
                status=friendship.status,
                created_at=friendship.created_at,
                request_type="received"
            ))

        sent_list = []
        for friendship, target_user in sent_requests:
            sent_list.append(FriendRequestListResponse(
                friendship_id=friendship.id,
                user_id=target_user.id,
                username=target_user.username,
                email="",  # 이메일은 UserProfile에서 제공하지 않음
                status=friendship.status,
                created_at=friendship.created_at,
                request_type="sent"
            ))

        return {
            "received_requests": received_list,
            "sent_requests": sent_list
        }

    except Exception as e:
        logger.error(f"Error getting friend requests: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get friend requests"
        )


@router.delete("/request/{target_user_id}")
async def cancel_friend_request(
        target_user_id: int,
        current_user: CurrentUserInfo = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """
    자신이 특정 사용자에게 보낸 친구 요청을 취소합니다.

    Args:
        target_user_id: 친구 요청을 받은 대상 사용자 ID
        current_user: 현재 인증된 사용자 정보
        db: 데이터베이스 세션

    Returns:
        dict: 성공 메시지
    """
    try:
        # 친구 요청 취소
        await FriendshipService.cancel_friend_request_by_target(
            db, current_user.id, target_user_id
        )

        # Kafka 이벤트 발행
        producer = get_event_producer()
        await producer.publish(
            topic=settings.kafka_topic_friend_events,
            event=FriendRequestCancelled(
                friendship_id=0,  # Already deleted
                requester_id=current_user.id,
                addressee_id=target_user_id,
                timestamp=datetime.utcnow()
            ),
            key=str(current_user.id)
        )

        return {
            "message": "Friend request cancelled successfully",
            "target_user_id": target_user_id
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error cancelling friend request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel friend request"
        )
