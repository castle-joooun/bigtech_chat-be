from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserBase(BaseModel):
    """사용자 기본 스키마"""
    email: EmailStr = Field(..., description="사용자 이메일")
    username: str = Field(..., min_length=3, max_length=50, description="사용자명")
    display_name: Optional[str] = Field(None, max_length=100, description="표시명")


class UserCreate(UserBase):
    """사용자 생성 스키마"""
    password: str = Field(..., min_length=8, max_length=16, description="비밀번호 (8-16자, 영문+숫자+특수문자)")


class UserUpdate(BaseModel):
    """사용자 정보 수정 스키마"""
    email: Optional[EmailStr] = Field(None, description="이메일")
    username: Optional[str] = Field(None, min_length=3, max_length=50, description="사용자명")
    display_name: Optional[str] = Field(None, max_length=100, description="표시명")
    is_active: Optional[bool] = Field(None, description="활성화 상태")


class UserLogin(BaseModel):
    """사용자 로그인 스키마"""
    email: EmailStr = Field(..., description="이메일")
    password: str = Field(..., description="비밀번호")


class UserResponse(UserBase):
    """사용자 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="사용자 ID")
    is_active: bool = Field(..., description="활성화 상태")
    created_at: datetime = Field(..., description="생성일시")
    updated_at: datetime = Field(..., description="수정일시")


class UserProfile(BaseModel):
    """사용자 프로필 스키마 (민감한 정보 제외)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="사용자 ID")
    username: str = Field(..., description="사용자명")
    display_name: Optional[str] = Field(None, description="표시명")
    is_active: bool = Field(..., description="활성화 상태")


class Token(BaseModel):
    """토큰 스키마"""
    access_token: str = Field(..., description="액세스 토큰")
    token_type: str = Field(default="bearer", description="토큰 타입")
    expires_in: int = Field(..., description="만료 시간(초)")


class TokenData(BaseModel):
    """토큰 데이터 스키마"""
    user_id: Optional[int] = Field(None, description="사용자 ID")
    email: Optional[str] = Field(None, description="이메일")


class UserWithRelations(UserResponse):
    """관계 데이터가 포함된 사용자 스키마"""
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from .chat_room import ChatRoomResponse
        from .friendship import FriendshipResponse
        from .group_chat_room import GroupChatRoomResponse
        from .group_room_member import GroupRoomMemberResponse
        from .block_user import BlockUserResponse
    
    # 1:1 채팅방 관계
    chat_rooms_as_user_1: Optional[List["ChatRoomResponse"]] = Field(default=None, description="사용자1로 참여한 채팅방")
    chat_rooms_as_user_2: Optional[List["ChatRoomResponse"]] = Field(default=None, description="사용자2로 참여한 채팅방")
    
    # 친구 관계
    friendship_requests: Optional[List["FriendshipResponse"]] = Field(default=None, description="보낸 친구 요청")
    friendship_receives: Optional[List["FriendshipResponse"]] = Field(default=None, description="받은 친구 요청")
    
    # 그룹 채팅방 관계
    created_groups: Optional[List["GroupChatRoomResponse"]] = Field(default=None, description="생성한 그룹")
    group_memberships: Optional[List["GroupRoomMemberResponse"]] = Field(default=None, description="참여한 그룹")
    
    # 차단 관계
    blocking: Optional[List["BlockUserResponse"]] = Field(default=None, description="차단한 사용자")
    blocked_by: Optional[List["BlockUserResponse"]] = Field(default=None, description="차단당한 관계")
