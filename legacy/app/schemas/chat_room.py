from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from pydantic import BaseModel, Field, ConfigDict

if TYPE_CHECKING:
    from .user import UserProfile


class ChatRoomCreate(BaseModel):
    """1:1 채팅방 생성 스키마"""
    participant_id: int = Field(..., description="상대방 사용자 ID")


# ChatRoomUpdate 스키마는 MVP에서 제거됨 (복잡한 개인 설정 기능 제거)


class ChatRoomResponse(BaseModel):
    """1:1 채팅방 응답 스키마 (개선된 버전)"""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="채팅방 ID")
    user_1_id: int = Field(..., description="사용자 1 ID")
    user_2_id: int = Field(..., description="사용자 2 ID")
    room_type: str = Field(default="direct", description="채팅방 타입")
    created_at: datetime = Field(..., description="생성일시")
    updated_at: datetime = Field(..., description="수정일시")

    # 추가 정보
    participants: Optional[List[dict]] = Field(default=None, description="참여자 정보")
    last_message: Optional[dict] = Field(default=None, description="마지막 메시지 정보")
    unread_count: int = Field(default=0, description="읽지 않은 메시지 수")


# ChatRoomListItem 스키마는 MVP에서 제거됨 (복잡한 개인화 기능 제거)


# ChatRoomListResponse 스키마는 MVP에서 제거됨 (복잡한 목록 기능 제거)


# ChatRoomDetail 스키마는 MVP에서 제거됨 (복잡한 상세 정보 기능 제거)


# ChatRoomSettingsResponse 스키마는 MVP에서 제거됨 (개인 설정 기능 제거)
