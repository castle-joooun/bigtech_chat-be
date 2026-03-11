"""
User Schemas (공유 사용자 스키마)
================================

다른 서비스에서 user-service의 데이터를 사용할 때 필요한 스키마입니다.
user-service의 스키마와 동일하게 유지해야 합니다.

설계 원칙:
    - 최소한의 필드만 포함 (필요한 정보만)
    - user-service의 UserProfile과 호환
    - 민감한 정보 (password_hash, email 등) 제외
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class UserProfile(BaseModel):
    """
    사용자 프로필 스키마 (전체 정보)

    user-service의 UserProfile 응답과 호환됩니다.
    친구 목록, 채팅방 참여자 정보 표시에 사용합니다.

    Attributes:
        id: 사용자 고유 식별자
        username: 사용자명 (고유)
        display_name: 표시명 (선택)
        status_message: 상태 메시지 (선택)
        is_online: 온라인 상태
        last_seen_at: 마지막 접속 시간
    """
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="사용자 ID")
    username: str = Field(..., description="사용자명")
    display_name: Optional[str] = Field(None, description="표시명")
    status_message: Optional[str] = Field(None, description="상태 메시지")
    is_online: bool = Field(default=False, description="온라인 상태")
    last_seen_at: Optional[datetime] = Field(None, description="마지막 접속 시간")


class UserProfileMinimal(BaseModel):
    """
    최소 사용자 정보 스키마

    채팅방 참여자 목록 등 최소 정보만 필요한 경우 사용합니다.

    Attributes:
        id: 사용자 고유 식별자
        username: 사용자명
    """
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="사용자 ID")
    username: str = Field(..., description="사용자명")
