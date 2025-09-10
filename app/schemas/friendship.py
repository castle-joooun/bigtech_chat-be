from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from pydantic import BaseModel, Field, ConfigDict

if TYPE_CHECKING:
    from .user import UserProfile


class FriendshipBase(BaseModel):
    """친구 관계 기본 스키마"""
    user_id_2: int = Field(..., description="친구 요청 대상 사용자 ID")


class FriendshipCreate(FriendshipBase):
    """친구 요청 생성 스키마"""
    message: Optional[str] = Field(None, max_length=500, description="친구 요청 메시지")


class FriendshipUpdate(BaseModel):
    """친구 관계 수정 스키마"""
    status: str = Field(..., description="친구 관계 상태: pending, accepted, rejected")


class FriendshipResponse(BaseModel):
    """친구 관계 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="친구 관계 ID")
    user_id_1: int = Field(..., description="친구 요청한 사용자 ID")
    user_id_2: int = Field(..., description="친구 요청 받은 사용자 ID")
    status: str = Field(..., description="친구 관계 상태: pending, accepted, rejected")
    created_at: datetime = Field(..., description="생성일시")
    updated_at: datetime = Field(..., description="수정일시")


class FriendshipWithUser(FriendshipResponse):
    """사용자 정보가 포함된 친구 관계 스키마"""
    requester: Optional["UserProfile"] = Field(None, description="친구 요청한 사용자 정보")
    target: Optional["UserProfile"] = Field(None, description="친구 요청 받은 사용자 정보")
    is_online: bool = Field(default=False, description="친구의 온라인 상태")
    last_seen: Optional[datetime] = Field(None, description="마지막 접속 시간")


class FriendList(BaseModel):
    """친구 목록 스키마"""
    friends: List[FriendshipWithUser] = Field(..., description="친구 목록")
    total: int = Field(..., description="전체 친구 수")
    online_count: int = Field(default=0, description="온라인 친구 수")
    page: int = Field(..., description="현재 페이지")
    limit: int = Field(..., description="페이지당 항목 수")


class FriendRequestList(BaseModel):
    """친구 요청 목록 스키마"""
    requests: List[FriendshipWithUser] = Field(..., description="친구 요청 목록")
    sent_requests: List[FriendshipWithUser] = Field(..., description="보낸 친구 요청 목록")
    total_received: int = Field(..., description="받은 친구 요청 수")
    total_sent: int = Field(..., description="보낸 친구 요청 수")


class FriendSearch(BaseModel):
    """친구 검색 스키마"""
    query: str = Field(..., min_length=1, description="검색 쿼리 (사용자명, 이메일 등)")
    limit: int = Field(default=20, ge=1, le=50, description="검색 결과 수")


class FriendSuggestion(BaseModel):
    """친구 추천 스키마"""
    user: dict = Field(..., description="추천 사용자 정보")
    reason: str = Field(..., description="추천 이유")
    mutual_friends: int = Field(default=0, description="공통 친구 수")


class FriendActivity(BaseModel):
    """친구 활동 스키마"""
    user_id: int = Field(..., description="사용자 ID")
    activity_type: str = Field(..., description="활동 타입: online, offline, typing, etc")
    room_id: Optional[int] = Field(None, description="관련 채팅방 ID")
    timestamp: datetime = Field(..., description="활동 시간")


class BlockFriend(BaseModel):
    """친구 차단 스키마"""
    friend_id: int = Field(..., description="차단할 친구의 사용자 ID")
    reason: Optional[str] = Field(None, max_length=500, description="차단 이유")
