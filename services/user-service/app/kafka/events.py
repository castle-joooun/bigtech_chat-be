"""
User Domain Events
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional


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
class UserRegistered(DomainEvent):
    """User registration event"""
    user_id: int
    email: str
    username: str
    display_name: str
    timestamp: datetime


@dataclass
class UserProfileUpdated(DomainEvent):
    """User profile update event"""
    user_id: int
    display_name: str
    profile_image_url: Optional[str]
    status_message: Optional[str]
    timestamp: datetime


@dataclass
class UserOnlineStatusChanged(DomainEvent):
    """Online status change event"""
    user_id: int
    is_online: bool
    timestamp: datetime
