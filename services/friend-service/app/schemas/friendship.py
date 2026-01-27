from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class FriendshipBase(BaseModel):
    """친구 관계 기본 스키마"""
    user_id_2: int = Field(..., description="친구 요청 대상 사용자 ID")


class FriendshipCreate(FriendshipBase):
    """친구 요청 생성 스키마"""
    message: Optional[str] = Field(None, max_length=500, description="친구 요청 메시지")


class FriendshipResponse(BaseModel):
    """친구 관계 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="친구 관계 ID")
    user_id_1: int = Field(..., description="친구 요청한 사용자 ID")
    user_id_2: int = Field(..., description="친구 요청 받은 사용자 ID")
    status: str = Field(..., description="친구 관계 상태: pending, accepted")
    created_at: datetime = Field(..., description="생성일시")
    updated_at: datetime = Field(..., description="수정일시")
    deleted_at: Optional[datetime] = Field(None, description="삭제일시 (soft delete)")


class FriendshipStatusUpdate(BaseModel):
    """친구 요청 상태 업데이트 스키마"""
    action: str = Field(..., description="수행할 액션: accept, reject")

    def validate_action(self):
        if self.action not in ['accept', 'reject']:
            raise ValueError('action must be either "accept" or "reject"')
        return self.action


class FriendListResponse(BaseModel):
    """친구 목록 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)

    user_id: int = Field(..., description="친구 사용자 ID")
    username: str = Field(..., description="친구 사용자명")
    email: str = Field(..., description="친구 이메일")
    last_seen_at: Optional[datetime] = Field(None, description="마지막 접속 시간")


class FriendRequestListResponse(BaseModel):
    """친구 요청 목록 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)

    friendship_id: int = Field(..., description="친구 요청 ID")
    user_id: int = Field(..., description="요청자/수신자 사용자 ID")
    username: str = Field(..., description="요청자/수신자 사용자명")
    email: str = Field(..., description="요청자/수신자 이메일")
    status: str = Field(..., description="친구 요청 상태")
    created_at: datetime = Field(..., description="요청 생성일")
    request_type: str = Field(..., description="요청 타입: sent, received")
