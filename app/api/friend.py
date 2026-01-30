from typing import List
from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mysql import get_async_session
from app.models.users import User
from app.schemas.friendship import (
    FriendshipCreate,
    FriendshipResponse,
    FriendshipStatusUpdate,
    FriendListResponse,
    FriendRequestListResponse
)
from app.schemas.user import UserProfile
from app.api.auth import get_current_user
from app.services.friendship_service import FriendshipService
from app.services.auth_service import find_user_by_id
from app.utils.time_utils import format_relative_time
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/friends", tags=["Friends"])


@router.post("/request", response_model=FriendshipResponse,
             status_code=status.HTTP_201_CREATED)
async def send_friend_request(
        friend_request: FriendshipCreate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """
    친구 요청을 전송합니다.
    
    Args:
        friend_request: 친구 요청 데이터 (target_user_id)
        current_user: 현재 인증된 사용자
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

    # 대상 사용자 존재 확인
    target_user = await find_user_by_id(db, target_user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user not found"
        )

    try:

        # 친구 요청 전송
        friendship = await FriendshipService.send_friend_request(
            db, current_user.id, target_user_id
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
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """
    친구 요청 상태를 업데이트합니다 (수락/거절).

    Args:
        requester_user_id: 친구 요청을 보낸 사용자 ID
        status_update: 상태 업데이트 정보 (accept/reject)
        current_user: 현재 인증된 사용자
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

            # JSON 응답 반환 (dict가 아닌 JSONResponse 사용하지 않아도 됨)
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
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """
    현재 사용자의 친구 목록을 조회합니다.
    
    Args:
        current_user: 현재 인증된 사용자
        db: 데이터베이스 세션
        
    Returns:
        List[FriendListResponse]: 친구 목록
    """
    try:
        friends = await FriendshipService.get_friends_list(db, current_user.id)

        friend_list = []
        for friend_user, friendship_date in friends:
            # 마지막 접속 시간 상대적 표기
            last_seen_display = format_relative_time(friend_user.last_seen_at)

            friend_list.append(FriendListResponse(
                user_id=friend_user.id,
                username=friend_user.username,
                email=friend_user.email,
                last_seen_at=friend_user.last_seen_at,
                last_seen_display=last_seen_display
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
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """
    현재 사용자의 친구 요청 목록을 조회합니다.
    
    Args:
        current_user: 현재 인증된 사용자
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
                email=requester.email,
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
                email=target_user.email,
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
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """
    자신이 특정 사용자에게 보낸 친구 요청을 취소합니다.

    Args:
        target_user_id: 친구 요청을 받은 대상 사용자 ID
        current_user: 현재 인증된 사용자
        db: 데이터베이스 세션

    Returns:
        dict: 성공 메시지

    Example:
        DELETE /api/friends/request/123
        # 현재 유저가 user_id=123에게 보낸 친구 요청을 취소
    """
    try:
        # 친구 요청 취소
        await FriendshipService.cancel_friend_request_by_target(
            db, current_user.id, target_user_id
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


@router.get("/search", response_model=List[UserProfile])
async def search_users_for_friend(
        query: str = Query(..., min_length=3, max_length=50,
                           description="검색어 (최소 3글자)"),
        limit: int = Query(default=20, ge=1, le=50, description="결과 개수"),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """
    친구 추가를 위한 사용자 검색

    검색 조건:
    - 최소 3글자 이상 입력
    - email 또는 username으로 검색
    - 이미 친구인 사용자 제외
    - 차단한/차단된 사용자 제외
    - 본인 제외

    Args:
        query: 검색어 (email 또는 username)
        limit: 결과 개수 (기본값: 20, 최대: 50)
        current_user: 현재 인증된 사용자
        db: 데이터베이스 세션

    Returns:
        List[UserProfile]: 검색된 사용자 목록
    """
    try:
        # 친구 검색
        users = await FriendshipService.search_users_for_friend(
            db=db,
            current_user_id=current_user.id,
            query=query,
            limit=limit
        )

        # UserProfile로 변환
        user_profiles = [UserProfile.model_validate(user) for user in users]

        return user_profiles

    except Exception as e:
        logger.error(f"Error searching users for friend: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search users"
        )
