"""Kafka module for Friend Service"""
from .producer import get_event_producer, KafkaProducer
from .events import (
    FriendRequestSent,
    FriendRequestAccepted,
    FriendRequestRejected,
    FriendRequestCancelled,
)

__all__ = [
    "get_event_producer",
    "KafkaProducer",
    "FriendRequestSent",
    "FriendRequestAccepted",
    "FriendRequestRejected",
    "FriendRequestCancelled",
]
