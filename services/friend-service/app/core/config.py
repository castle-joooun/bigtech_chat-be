"""
Friend Service Configuration

환경 변수를 통한 설정 관리
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Friend Service 설정"""

    # Application
    app_name: str = "Friend Service"
    version: str = "1.0.0"
    debug: bool = True

    # Server
    host: str = "0.0.0.0"
    port: int = 8003

    # Database - MySQL
    mysql_url: str

    # Database - Redis
    redis_url: str = "redis://localhost:6379"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:19092,localhost:19093,localhost:19094"
    kafka_topic_friend_events: str = "friend.events"

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_hours: int = 2

    # CORS
    cors_origins: List[str] = ["http://localhost:3000"]

    # File Upload
    upload_dir: str = "uploads"
    max_upload_size: int = 5 * 1024 * 1024  # 5MB

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
