"""
Domain Events

모든 Domain Event의 기본 클래스 및 이벤트 정의
"""

from .base import DomainEvent
from .user_events import UserRegistered, UserProfileUpdated, UserOnlineStatusChanged
from .friend_events import (
    FriendRequestSent,
    FriendRequestAccepted,
    FriendRequestRejected,
    FriendRequestCancelled
)
from .message_events import MessageSent, MessagesRead, MessageDeleted
from .chat_events import ChatRoomCreated, ChatRoomUpdated

__all__ = [
    'DomainEvent',
    'UserRegistered',
    'UserProfileUpdated',
    'UserOnlineStatusChanged',
    'FriendRequestSent',
    'FriendRequestAccepted',
    'FriendRequestRejected',
    'FriendRequestCancelled',
    'MessageSent',
    'MessagesRead',
    'MessageDeleted',
    'ChatRoomCreated',
    'ChatRoomUpdated',
]
