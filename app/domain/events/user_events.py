"""
User Context Domain Events
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from .base import DomainEvent


@dataclass
class UserRegistered(DomainEvent):
    """사용자 등록 이벤트"""
    user_id: int
    email: str
    username: str
    display_name: str
    timestamp: datetime


@dataclass
class UserProfileUpdated(DomainEvent):
    """사용자 프로필 업데이트 이벤트"""
    user_id: int
    display_name: str
    profile_image_url: Optional[str]
    status_message: Optional[str]
    timestamp: datetime


@dataclass
class UserOnlineStatusChanged(DomainEvent):
    """온라인 상태 변경 이벤트"""
    user_id: int
    is_online: bool
    timestamp: datetime
