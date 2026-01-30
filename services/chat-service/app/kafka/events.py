"""
Chat/Message Domain Events
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List


@dataclass
class DomainEvent:
    """Base class for domain events"""
    timestamp: datetime

    def to_dict(self) -> dict:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['__event_type__'] = self.__class__.__name__
        return data


@dataclass
class MessageSent(DomainEvent):
    """Message sent event"""
    message_id: str
    room_id: int
    user_id: int
    username: str
    content: str
    message_type: str  # "text", "image", "file"
    timestamp: datetime


@dataclass
class MessagesRead(DomainEvent):
    """Messages read event"""
    room_id: int
    user_id: int
    message_ids: List[str]
    timestamp: datetime


@dataclass
class MessageDeleted(DomainEvent):
    """Message deleted event"""
    message_id: str
    room_id: int
    deleted_by: int
    timestamp: datetime


@dataclass
class ChatRoomCreated(DomainEvent):
    """Chat room created event"""
    room_id: int
    room_type: str  # "direct", "group"
    creator_id: int
    participant_ids: List[int]
    timestamp: datetime
