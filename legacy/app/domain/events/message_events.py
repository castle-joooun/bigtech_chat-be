"""
Message Context Domain Events
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List
from .base import DomainEvent


@dataclass
class MessageSent(DomainEvent):
    """메시지 전송 이벤트"""
    message_id: str
    room_id: int
    user_id: int
    username: str
    content: str
    message_type: str  # "text", "image", "file"
    timestamp: datetime


@dataclass
class MessagesRead(DomainEvent):
    """메시지 읽음 이벤트"""
    room_id: int
    user_id: int
    message_ids: List[str]
    timestamp: datetime


@dataclass
class MessageDeleted(DomainEvent):
    """메시지 삭제 이벤트"""
    message_id: str
    room_id: int
    deleted_by: int
    timestamp: datetime
