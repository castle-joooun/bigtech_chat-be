"""
Friend Domain Events
"""

from dataclasses import dataclass, asdict
from datetime import datetime


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
class FriendRequestSent(DomainEvent):
    """Friend request sent event"""
    friendship_id: int
    requester_id: int
    requester_name: str
    addressee_id: int
    addressee_name: str
    timestamp: datetime


@dataclass
class FriendRequestAccepted(DomainEvent):
    """Friend request accepted event"""
    friendship_id: int
    requester_id: int
    requester_name: str
    addressee_id: int
    addressee_name: str
    timestamp: datetime


@dataclass
class FriendRequestRejected(DomainEvent):
    """Friend request rejected event"""
    friendship_id: int
    requester_id: int
    addressee_id: int
    timestamp: datetime


@dataclass
class FriendRequestCancelled(DomainEvent):
    """Friend request cancelled event"""
    friendship_id: int
    requester_id: int
    addressee_id: int
    timestamp: datetime
