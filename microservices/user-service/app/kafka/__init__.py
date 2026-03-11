"""Kafka module for User Service"""
from .producer import get_event_producer, KafkaProducer
from .events import UserRegistered, UserProfileUpdated, UserOnlineStatusChanged

__all__ = [
    "get_event_producer",
    "KafkaProducer",
    "UserRegistered",
    "UserProfileUpdated",
    "UserOnlineStatusChanged",
]
