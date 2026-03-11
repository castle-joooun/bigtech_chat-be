"""
Friendship Schemas (친구 관계 스키마)
====================================

친구 관계 API의 요청/응답 스키마를 정의합니다.

스키마 구조
-----------
```
┌─────────────────────────────────────────────────────────────┐
│                     Request Schemas                          │
├─────────────────────────────────────────────────────────────┤
│  FriendshipCreate     → POST /friends/request               │
│  FriendshipStatusUpdate → PUT /friends/status/{id}          │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     Response Schemas                         │
├─────────────────────────────────────────────────────────────┤
│  FriendshipResponse   → 친구 관계 상세 정보                  │
│  FriendListResponse   → 친구 목록 아이템                     │
│  FriendRequestListResponse → 요청 목록 아이템               │
└─────────────────────────────────────────────────────────────┘
```

친구 관계 상태
--------------
| 상태      | 설명                              |
|----------|----------------------------------|
| pending  | 친구 요청 대기 중                  |
| accepted | 친구 요청 수락됨                   |
| (삭제됨)  | Soft Delete (deleted_at 설정)    |

관련 파일
---------
- app/models/friendship.py: SQLAlchemy 모델
- app/api/friend.py: API 엔드포인트
- app/services/friendship_service.py: 비즈니스 로직
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# Request Schemas (요청 스키마)
# =============================================================================

class FriendshipBase(BaseModel):
    """
    친구 관계 기본 스키마

    다른 친구 관계 스키마의 부모 클래스입니다.

    Attributes:
        user_id_2: 친구 요청 대상 사용자 ID
    """
    user_id_2: int = Field(..., description="친구 요청 대상 사용자 ID")


class FriendshipCreate(FriendshipBase):
    """
    친구 요청 생성 스키마

    POST /friends/request 요청 바디에 사용됩니다.

    Attributes:
        user_id_2: 요청 대상 사용자 ID (상속)
        message: 친구 요청 메시지 (선택, 최대 500자)

    사용 예시:
        POST /friends/request
        {
            "user_id_2": 123,
            "message": "친구 추가 부탁드립니다!"
        }
    """
    message: Optional[str] = Field(None, max_length=500, description="친구 요청 메시지")


class FriendshipStatusUpdate(BaseModel):
    """
    친구 요청 상태 업데이트 스키마

    PUT /friends/status/{requester_user_id} 요청 바디에 사용됩니다.

    Attributes:
        action: 수행할 액션 ("accept" 또는 "reject")

    사용 예시:
        PUT /friends/status/123
        {"action": "accept"}  # 친구 요청 수락
    """
    action: str = Field(..., description="수행할 액션: accept, reject")

    def validate_action(self):
        """
        액션 값 검증

        Returns:
            str: 유효한 액션 값

        Raises:
            ValueError: 유효하지 않은 액션
        """
        if self.action not in ['accept', 'reject']:
            raise ValueError('action must be either "accept" or "reject"')
        return self.action


# =============================================================================
# Response Schemas (응답 스키마)
# =============================================================================

class FriendshipResponse(BaseModel):
    """
    친구 관계 응답 스키마

    친구 관계의 상세 정보를 반환합니다.

    Attributes:
        id: 친구 관계 고유 ID
        user_id_1: 요청자 ID
        user_id_2: 수신자 ID
        status: 관계 상태 (pending/accepted)
        created_at: 요청 생성 시각
        updated_at: 마지막 수정 시각
        deleted_at: 삭제 시각 (Soft Delete)
    """
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="친구 관계 ID")
    user_id_1: int = Field(..., description="친구 요청한 사용자 ID")
    user_id_2: int = Field(..., description="친구 요청 받은 사용자 ID")
    status: str = Field(..., description="친구 관계 상태: pending, accepted")
    created_at: datetime = Field(..., description="생성일시")
    updated_at: datetime = Field(..., description="수정일시")
    deleted_at: Optional[datetime] = Field(None, description="삭제일시 (soft delete)")


class FriendListResponse(BaseModel):
    """
    친구 목록 응답 스키마

    GET /friends/list 응답의 각 친구 정보입니다.

    Attributes:
        user_id: 친구의 사용자 ID
        username: 친구의 사용자명
        email: 친구의 이메일
        last_seen_at: 마지막 접속 시간 (온라인 상태 표시용)
    """
    model_config = ConfigDict(from_attributes=True)

    user_id: int = Field(..., description="친구 사용자 ID")
    username: str = Field(..., description="친구 사용자명")
    email: str = Field(..., description="친구 이메일")
    last_seen_at: Optional[datetime] = Field(None, description="마지막 접속 시간")


class FriendRequestListResponse(BaseModel):
    """
    친구 요청 목록 응답 스키마

    GET /friends/requests 응답의 각 요청 정보입니다.

    Attributes:
        friendship_id: 친구 관계 ID
        user_id: 상대방 사용자 ID
        username: 상대방 사용자명
        email: 상대방 이메일
        status: 요청 상태
        created_at: 요청 생성 시각
        request_type: "sent" (보낸 요청) 또는 "received" (받은 요청)
    """
    model_config = ConfigDict(from_attributes=True)

    friendship_id: int = Field(..., description="친구 요청 ID")
    user_id: int = Field(..., description="요청자/수신자 사용자 ID")
    username: str = Field(..., description="요청자/수신자 사용자명")
    email: str = Field(..., description="요청자/수신자 이메일")
    status: str = Field(..., description="친구 요청 상태")
    created_at: datetime = Field(..., description="요청 생성일")
    request_type: str = Field(..., description="요청 타입: sent, received")
