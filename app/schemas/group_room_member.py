from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from pydantic import BaseModel, Field, ConfigDict

if TYPE_CHECKING:
    from .user import UserProfile
    from .group_chat_room import GroupChatRoomResponse


class GroupRoomMemberBase(BaseModel):
    """그룹 채팅방 멤버 기본 스키마"""
    user_id: int = Field(..., description="사용자 ID")
    group_room_id: int = Field(..., description="그룹 채팅방 ID")
    role: str = Field(default="member", description="역할: owner, admin, member")


class GroupRoomMemberCreate(BaseModel):
    """그룹 채팅방 멤버 추가 스키마"""
    user_id: int = Field(..., description="추가할 사용자 ID")
    role: str = Field(default="member", description="역할: owner, admin, member")


class GroupRoomMemberUpdate(BaseModel):
    """그룹 채팅방 멤버 정보 수정 스키마"""
    role: Optional[str] = Field(None, description="역할: owner, admin, member")
    is_active: Optional[bool] = Field(None, description="활성화 상태")


class GroupRoomMemberResponse(GroupRoomMemberBase):
    """그룹 채팅방 멤버 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="멤버 관계 ID")
    is_active: bool = Field(..., description="활성화 상태")
    joined_at: datetime = Field(..., description="참여일시")
    left_at: Optional[datetime] = Field(None, description="퇴장일시")
    created_at: datetime = Field(..., description="생성일시")
    updated_at: datetime = Field(..., description="수정일시")


class GroupRoomMemberWithDetails(GroupRoomMemberResponse):
    """상세 정보가 포함된 그룹 채팅방 멤버 스키마"""
    user: Optional["UserProfile"] = Field(None, description="사용자 정보")
    group_room: Optional["GroupChatRoomResponse"] = Field(None, description="그룹 채팅방 정보")
    permissions: List[str] = Field(default_factory=list, description="권한 목록")
    is_online: bool = Field(default=False, description="온라인 상태")
    last_seen: Optional[datetime] = Field(None, description="마지막 접속 시간")


class GroupRoomMemberList(BaseModel):
    """그룹 채팅방 멤버 목록 스키마"""
    members: List[GroupRoomMemberWithDetails] = Field(..., description="멤버 목록")
    total: int = Field(..., description="전체 멤버 수")
    online_count: int = Field(default=0, description="온라인 멤버 수")
    owners: int = Field(default=0, description="관리자 수")
    admins: int = Field(default=0, description="부관리자 수")
    members_count: int = Field(default=0, description="일반 멤버 수")
    page: int = Field(..., description="현재 페이지")
    limit: int = Field(..., description="페이지당 항목 수")


class GroupRoomMemberInvite(BaseModel):
    """그룹 채팅방 멤버 초대 스키마"""
    group_room_id: int = Field(..., description="그룹 채팅방 ID")
    user_ids: List[int] = Field(..., min_length=1, description="초대할 사용자 ID 목록")
    role: str = Field(default="member", description="초대할 사용자들의 역할")
    invite_message: Optional[str] = Field(None, max_length=500, description="초대 메시지")


class GroupRoomMemberKick(BaseModel):
    """그룹 채팅방 멤버 추방 스키마"""
    user_id: int = Field(..., description="추방할 사용자 ID")
    reason: Optional[str] = Field(None, max_length=500, description="추방 이유")


class GroupRoomMemberLeave(BaseModel):
    """그룹 채팅방 멤버 퇴장 스키마"""
    group_room_id: int = Field(..., description="퇴장할 그룹 채팅방 ID")
    leave_message: Optional[str] = Field(None, max_length=500, description="퇴장 메시지")


class GroupRoomMemberRole(BaseModel):
    """그룹 채팅방 멤버 역할 변경 스키마"""
    user_id: int = Field(..., description="역할을 변경할 사용자 ID")
    new_role: str = Field(..., description="새 역할: owner, admin, member")
    reason: Optional[str] = Field(None, max_length=500, description="역할 변경 이유")


class GroupRoomMemberPermissions(BaseModel):
    """그룹 채팅방 멤버 권한 스키마"""
    can_invite: bool = Field(default=False, description="초대 권한")
    can_kick: bool = Field(default=False, description="추방 권한")
    can_delete_messages: bool = Field(default=False, description="메시지 삭제 권한")
    can_pin_messages: bool = Field(default=False, description="메시지 고정 권한")
    can_manage_members: bool = Field(default=False, description="멤버 관리 권한")
    can_edit_room: bool = Field(default=False, description="채팅방 정보 수정 권한")


class GroupRoomMemberActivity(BaseModel):
    """그룹 채팅방 멤버 활동 스키마"""
    user_id: int = Field(..., description="사용자 ID")
    activity_type: str = Field(..., description="활동 타입: joined, left, promoted, demoted, etc")
    details: Optional[dict] = Field(None, description="활동 상세 정보")
    timestamp: datetime = Field(..., description="활동 시간")
