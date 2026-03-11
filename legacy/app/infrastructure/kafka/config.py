"""
Kafka Configuration
"""

from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings


class KafkaConfig(BaseSettings):
    """Kafka 설정"""

    # Kafka 브로커 주소
    bootstrap_servers: List[str] = Field(
        default=["localhost:19092", "localhost:19093", "localhost:19094"],
        description="Kafka bootstrap servers"
    )

    # Producer 설정
    producer_acks: str = Field(
        default="all",
        description="Producer acks: 'all', '1', '0'"
    )
    producer_compression_type: str = Field(
        default="snappy",
        description="Compression type: 'none', 'gzip', 'snappy', 'lz4'"
    )
    producer_max_in_flight: int = Field(
        default=5,
        description="Max in-flight requests per connection"
    )
    producer_retries: int = Field(
        default=3,
        description="Number of retries"
    )
    producer_request_timeout_ms: int = Field(
        default=30000,
        description="Request timeout in milliseconds"
    )

    # Consumer 설정
    consumer_auto_offset_reset: str = Field(
        default="earliest",
        description="Auto offset reset: 'earliest', 'latest'"
    )
    consumer_enable_auto_commit: bool = Field(
        default=True,
        description="Enable auto commit"
    )
    consumer_auto_commit_interval_ms: int = Field(
        default=5000,
        description="Auto commit interval in milliseconds"
    )
    consumer_max_poll_records: int = Field(
        default=100,
        description="Max poll records"
    )
    consumer_session_timeout_ms: int = Field(
        default=30000,
        description="Session timeout in milliseconds"
    )

    # Topic 설정
    topic_user_events: str = "user.events"
    topic_user_online_status: str = "user.online_status"
    topic_friend_events: str = "friend.events"
    topic_chat_events: str = "chat.events"
    topic_message_events: str = "message.events"
    topic_notification_events: str = "notification.events"

    class Config:
        env_prefix = "KAFKA_"
        case_sensitive = False


# Singleton instance
kafka_config = KafkaConfig()
