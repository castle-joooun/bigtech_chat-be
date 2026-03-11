"""
User API Endpoints (사용자 조회 API 엔드포인트)
==============================================

사용자 검색 및 조회를 처리하는 API 레이어입니다.

엔드포인트 목록
---------------
| Method | Path             | 설명                     | 인증 |
|--------|------------------|-------------------------|------|
| GET    | /users/search    | 사용자 검색 (이름/닉네임) | O    |
| GET    | /users/{id}      | 특정 사용자 조회         | O    |
| GET    | /users           | 여러 사용자 조회 (batch) | O    |

설계 패턴
---------
1. Query Parameter:
   - 검색: ?query=john&limit=10
   - Batch 조회: ?user_ids=1,2,3

2. Path Parameter:
   - 단일 조회: /users/{id}

사용 사례
---------
1. 친구 추가 시 사용자 검색:
   GET /users/search?query=john&limit=10

2. 채팅방 멤버 정보 조회 (batch):
   GET /users?user_ids=1,2,3,4,5

3. 특정 사용자 프로필 조회:
   GET /users/123

성능 고려사항
-------------
1. 검색 (search):
   - LIKE 검색으로 Full Table Scan 가능
   - limit으로 결과 수 제한 필수

2. Batch 조회:
   - IN 쿼리로 N+1 문제 방지
   - 한 번의 쿼리로 여러 사용자 조회

SOLID 원칙
----------
- SRP: 사용자 조회/검색 기능만 담당
- DIP: auth_service 추상화에 의존

관련 파일
---------
- app/services/auth_service.py: 검색/조회 로직
- app/schemas/user.py: 응답 스키마
"""

from typing import List
from fastapi import APIRouter, Depends, status, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mysql import get_async_session
from app.models.user import User
from app.schemas.user import UserProfile, UserSearchResponse
from app.api.dependencies import get_current_user
from app.services import auth_service
from shared_lib.core import ResourceNotFoundException, Validator
import logging


class UserBatchRequest(BaseModel):
    """Batch 사용자 조회 요청 스키마"""
    user_ids: List[int] = Field(..., min_length=1, max_length=100, description="조회할 사용자 ID 목록 (최대 100개)")


class UserExistsResponse(BaseModel):
    """사용자 존재 여부 응답 스키마"""
    user_id: int = Field(..., description="사용자 ID")
    exists: bool = Field(..., description="존재 여부")

logger = logging.getLogger(__name__)

# =============================================================================
# Router 설정
# =============================================================================
router = APIRouter(prefix="/api/users", tags=["Users"])


# =============================================================================
# Search API
# =============================================================================

@router.get("/search", response_model=UserSearchResponse)
async def search_users(
    query: str = Query(..., min_length=1, max_length=50, description="검색 쿼리"),
    limit: int = Query(default=10, ge=1, le=50, description="결과 개수"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> UserSearchResponse:
    """
    사용자 검색

    사용자명(username) 또는 표시명(display_name)으로 사용자를 검색합니다.
    친구 추가 시 사용자를 찾는 데 사용됩니다.

    Args:
        query: 검색어 (1-50자)
            - 사용자명 또는 표시명에서 부분 일치 검색
            - 대소문자 구분 없음 (ILIKE)
        limit: 최대 결과 수 (1-50, 기본값: 10)
        current_user: 현재 인증된 사용자 (검색 결과에서 제외됨)
        db: 데이터베이스 세션

    Returns:
        UserSearchResponse:
            - users: 검색된 사용자 프로필 목록
            - total_count: 전체 검색 결과 수

    Raises:
        HTTPException 400: query가 비어있거나 너무 김
        HTTPException 500: 검색 실패

    요청 예시:
        GET /users/search?query=john&limit=20

    응답 예시:
        {
            "users": [
                {"id": 1, "username": "john_doe", "display_name": "John"},
                {"id": 2, "username": "johnny", "display_name": "Johnny"}
            ],
            "total_count": 15
        }

    검색 로직:
        - username ILIKE '%query%' OR display_name ILIKE '%query%'
        - is_active = true (활성화된 사용자만)
        - id != current_user.id (자기 자신 제외)

    성능 고려:
        - LIKE 검색은 인덱스를 완전히 활용하지 못함
        - limit으로 결과 수 제한하여 성능 확보
        - 프로덕션에서는 Elasticsearch 고려
    """
    try:
        # 사용자 검색 (자기 자신 제외)
        users = await auth_service.search_users_by_username(
            db=db,
            query=query,
            limit=limit,
            exclude_user_id=current_user.id
        )

        # 전체 검색 결과 수 (페이지네이션용)
        total_count = await auth_service.get_user_count_by_query(
            db=db,
            query=query,
            exclude_user_id=current_user.id
        )

        # Pydantic 스키마로 변환
        user_profiles = [UserProfile.model_validate(user) for user in users]

        return UserSearchResponse(
            users=user_profiles,
            total_count=total_count
        )

    except Exception as e:
        logger.error(f"Error searching users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search users"
        )


# =============================================================================
# Single User API
# =============================================================================

@router.get("/{user_id}", response_model=UserProfile)
async def get_user_by_id(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> UserProfile:
    """
    특정 사용자 조회

    ID로 단일 사용자의 프로필을 조회합니다.
    채팅 상대방 정보, 친구 프로필 조회 등에 사용.

    Args:
        user_id: 조회할 사용자 ID (Path Parameter)
        current_user: 현재 인증된 사용자
        db: 데이터베이스 세션

    Returns:
        UserProfile: 사용자 프로필 정보

    Raises:
        HTTPException 400: user_id가 양수가 아님
        HTTPException 404: 사용자를 찾을 수 없음

    요청 예시:
        GET /users/123

    응답 예시:
        {
            "id": 123,
            "username": "john_doe",
            "display_name": "John Doe",
            "is_online": true,
            "last_seen_at": "2024-01-15T10:30:00"
        }
    """
    # 입력 검증 (양수 정수인지 확인)
    user_id = Validator.validate_positive_integer(user_id, "user_id")

    # 사용자 조회
    user = await auth_service.find_user_by_id(db, user_id)
    if not user:
        raise ResourceNotFoundException("User")

    return UserProfile.model_validate(user)


# =============================================================================
# Batch User API
# =============================================================================

@router.get("", response_model=List[UserProfile])
async def get_users_by_ids(
    user_ids: str = Query(..., description="쉼표로 구분된 사용자 ID 목록"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> List[UserProfile]:
    """
    여러 사용자 조회 (Batch)

    여러 사용자의 정보를 한 번에 조회합니다.
    채팅방 멤버 목록, 친구 목록 등에서 사용.

    Args:
        user_ids: 쉼표로 구분된 사용자 ID 목록
            - 예: "1,2,3,4,5"
            - 최소 1개 이상
        current_user: 현재 인증된 사용자
        db: 데이터베이스 세션

    Returns:
        List[UserProfile]: 사용자 프로필 목록
            - 순서는 보장되지 않음
            - 존재하지 않는 ID는 결과에서 제외됨

    Raises:
        HTTPException 400: ID가 없거나 형식 오류
        HTTPException 500: 조회 실패

    요청 예시:
        GET /users?user_ids=1,2,3,4,5

    응답 예시:
        [
            {"id": 1, "username": "user1", ...},
            {"id": 2, "username": "user2", ...},
            {"id": 3, "username": "user3", ...}
        ]

    N+1 문제 방지:
        - 개별 조회 대신 IN 쿼리로 한 번에 조회
        - SELECT * FROM users WHERE id IN (1, 2, 3, 4, 5)

    사용 사례:
        1. 채팅방 멤버 목록 표시
        2. 친구 목록에서 프로필 표시
        3. 그룹 채팅 참여자 정보 표시
    """
    try:
        # ID 목록 파싱 (문자열 → 정수 리스트)
        # "1,2,3" → [1, 2, 3]
        id_list = [int(uid.strip()) for uid in user_ids.split(",") if uid.strip()]

        if not id_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one user ID is required"
            )

        # Batch 조회 (IN 쿼리)
        users = await auth_service.get_users_by_ids(db, id_list)

        # Pydantic 스키마로 변환
        user_profiles = [UserProfile.model_validate(user) for user in users]

        return user_profiles

    except ValueError:
        # int() 변환 실패 시
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    except Exception as e:
        logger.error(f"Error getting users by IDs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get users"
        )


# =============================================================================
# Batch User API (POST) - 서비스 간 통신용
# =============================================================================

@router.post("/batch", response_model=List[UserProfile])
async def get_users_batch(
    request: UserBatchRequest,
    db: AsyncSession = Depends(get_async_session)
) -> List[UserProfile]:
    """
    여러 사용자 Batch 조회 (서비스 간 통신용)

    다른 마이크로서비스에서 여러 사용자 정보를 한 번에 조회할 때 사용합니다.
    인증 없이 내부 서비스 호출 가능 (서비스 메시 환경 가정).

    Args:
        request: UserBatchRequest (user_ids: List[int])
            - 최대 100개까지 조회 가능

    Returns:
        List[UserProfile]: 사용자 프로필 목록
            - 존재하지 않는 ID는 결과에서 제외됨
            - 순서는 보장되지 않음

    요청 예시:
        POST /api/users/batch
        {
            "user_ids": [1, 2, 3, 4, 5]
        }

    응답 예시:
        [
            {"id": 1, "username": "user1", "display_name": "User One", ...},
            {"id": 2, "username": "user2", "display_name": "User Two", ...}
        ]

    사용 사례:
        - friend-service: 친구 목록 조회 시 사용자 정보
        - chat-service: 채팅방 참여자 정보 조회
    """
    try:
        users = await auth_service.get_users_by_ids(db, request.user_ids)
        return [UserProfile.model_validate(user) for user in users]

    except Exception as e:
        logger.error(f"Error in batch user lookup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get users"
        )


# =============================================================================
# User Exists API - 서비스 간 통신용
# =============================================================================

@router.get("/{user_id}/exists", response_model=UserExistsResponse)
async def check_user_exists(
    user_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> UserExistsResponse:
    """
    사용자 존재 여부 확인 (서비스 간 통신용)

    다른 마이크로서비스에서 사용자 ID의 유효성을 빠르게 확인할 때 사용합니다.
    전체 프로필 정보가 필요 없고 존재 여부만 확인할 때 사용.

    Args:
        user_id: 확인할 사용자 ID

    Returns:
        UserExistsResponse:
            - user_id: 조회한 사용자 ID
            - exists: 존재 여부 (True/False)

    요청 예시:
        GET /api/users/123/exists

    응답 예시:
        {"user_id": 123, "exists": true}

    사용 사례:
        - friend-service: 친구 요청 전 대상 사용자 유효성 검증
        - chat-service: 채팅방 생성 전 상대방 존재 확인
    """
    try:
        exists = await auth_service.is_user_exists(db, user_id)
        return UserExistsResponse(user_id=user_id, exists=exists)

    except Exception as e:
        logger.error(f"Error checking user existence: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check user existence"
        )
