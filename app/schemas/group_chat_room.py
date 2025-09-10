from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from pydantic import BaseModel, Field, ConfigDict

if TYPE_CHECKING:
    from .user import UserProfile
    from .group_room_member import GroupRoomMemberResponse


class GroupChatRoomBase(BaseModel):
    """그룹 채팅방 기본 스키마"""
    name: str = Field(..., min_length=1, max_length=255, description="그룹 채팅방 이름")
    description: Optional[str] = Field(None, description="그룹 채팅방 설명")
    is_private: bool = Field(default=False, description="비공개 그룹 여부")
    max_members: int = Field(default=100, ge=2, le=1000, description="최대 멤버 수")


class GroupChatRoomCreate(GroupChatRoomBase):
    """그룹 채팅방 생성 스키마"""
    pass


class GroupChatRoomUpdate(BaseModel):
    """그룹 채팅방 수정 스키마"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="그룹 채팅방 이름")
    description: Optional[str] = Field(None, description="그룹 채팅방 설명")
    is_private: Optional[bool] = Field(None, description="비공개 그룹 여부")
    max_members: Optional[int] = Field(None, ge=2, le=1000, description="최대 멤버 수")
    is_active: Optional[bool] = Field(None, description="활성화 상태")


class GroupChatRoomResponse(GroupChatRoomBase):
    """그룹 채팅방 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="그룹 채팅방 ID")
    created_by: int = Field(..., description="그룹 생성자 ID")
    is_active: bool = Field(..., description="활성화 상태")
    created_at: datetime = Field(..., description="생성일시")
    updated_at: datetime = Field(..., description="수정일시")


class GroupChatRoomWithDetails(GroupChatRoomResponse):
    """상세 정보가 포함된 그룹 채팅방 스키마"""
    creator: Optional["UserProfile"] = Field(None, description="그룹 생성자 정보")
    members: Optional[List["GroupRoomMemberResponse"]] = Field(None, description="그룹 멤버 목록")
    member_count: int = Field(default=0, description="현재 멤버 수")
    last_message: Optional[dict] = Field(None, description="마지막 메시지")
    unread_count: int = Field(default=0, description="읽지 않은 메시지 수")
    my_role: Optional[str] = Field(None, description="내 역할 (owner, admin, member)")


class GroupChatRoomList(BaseModel):
    """그룹 채팅방 목록 스키마"""
    rooms: List[GroupChatRoomWithDetails] = Field(..., description="그룹 채팅방 목록")
    total: int = Field(..., description="전체 그룹 채팅방 수")
    page: int = Field(..., description="현재 페이지")
    limit: int = Field(..., description="페이지당 항목 수")


class GroupChatRoomJoin(BaseModel):
    """그룹 채팅방 참여 스키마"""
    room_id: int = Field(..., description="참여할 그룹 채팅방 ID")
    join_message: Optional[str] = Field(None, max_length=500, description="참여 메시지")


class GroupChatRoomInvite(BaseModel):
    """그룹 채팅방 초대 스키마"""
    user_ids: List[int] = Field(..., min_length=1, description="초대할 사용자 ID 목록")
    invite_message: Optional[str] = Field(None, max_length=500, description="초대 메시지")
