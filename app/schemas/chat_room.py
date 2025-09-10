from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from pydantic import BaseModel, Field, ConfigDict

if TYPE_CHECKING:
    from .user import UserProfile


class ChatRoomBase(BaseModel):
    """1:1 채팅방 기본 스키마"""
    user_id_1: int = Field(..., description="첫 번째 사용자 ID")
    user_id_2: int = Field(..., description="두 번째 사용자 ID")


class ChatRoomCreate(ChatRoomBase):
    """1:1 채팅방 생성 스키마"""
    pass


class ChatRoomUpdate(BaseModel):
    """1:1 채팅방 수정 스키마"""
    is_active: Optional[bool] = Field(None, description="활성화 상태")


class ChatRoomResponse(ChatRoomBase):
    """1:1 채팅방 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="채팅방 ID")
    is_active: bool = Field(..., description="활성화 상태")
    created_at: datetime = Field(..., description="생성일시")
    updated_at: datetime = Field(..., description="수정일시")


class ChatRoomWithUsers(ChatRoomResponse):
    """사용자 정보가 포함된 1:1 채팅방 스키마"""
    user_1: Optional["UserProfile"] = Field(None, description="첫 번째 사용자 정보")
    user_2: Optional["UserProfile"] = Field(None, description="두 번째 사용자 정보")
    last_message: Optional[dict] = Field(None, description="마지막 메시지")
    unread_count: int = Field(default=0, description="읽지 않은 메시지 수")


class ChatRoomList(BaseModel):
    """채팅방 목록 스키마"""
    rooms: List[ChatRoomWithUsers] = Field(..., description="채팅방 목록")
    total: int = Field(..., description="전체 채팅방 수")
    page: int = Field(..., description="현재 페이지")
    limit: int = Field(..., description="페이지당 항목 수")
