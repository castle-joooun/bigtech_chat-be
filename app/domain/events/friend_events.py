"""
Friend Context Domain Events
"""

from dataclasses import dataclass
from datetime import datetime
from .base import DomainEvent


@dataclass
class FriendRequestSent(DomainEvent):
    """친구 요청 전송 이벤트"""
    friendship_id: int
    requester_id: int
    requester_name: str
    addressee_id: int
    addressee_name: str
    timestamp: datetime


@dataclass
class FriendRequestAccepted(DomainEvent):
    """친구 요청 수락 이벤트"""
    friendship_id: int
    requester_id: int
    requester_name: str
    addressee_id: int
    addressee_name: str
    timestamp: datetime


@dataclass
class FriendRequestRejected(DomainEvent):
    """친구 요청 거절 이벤트"""
    friendship_id: int
    requester_id: int
    addressee_id: int
    timestamp: datetime


@dataclass
class FriendRequestCancelled(DomainEvent):
    """친구 요청 취소 이벤트"""
    friendship_id: int
    requester_id: int
    addressee_id: int
    timestamp: datetime
