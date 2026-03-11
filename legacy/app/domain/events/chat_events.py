"""
Chat Context Domain Events
"""

from dataclasses import dataclass
from datetime import datetime
from .base import DomainEvent


@dataclass
class ChatRoomCreated(DomainEvent):
    """채팅방 생성 이벤트"""
    room_id: int
    user_1_id: int
    user_2_id: int
    room_type: str  # "direct" or "group"
    timestamp: datetime


@dataclass
class ChatRoomUpdated(DomainEvent):
    """채팅방 업데이트 이벤트 (타임스탬프 갱신)"""
    room_id: int
    timestamp: datetime
