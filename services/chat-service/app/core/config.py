"""
Chat Service Configuration

환경 변수를 통한 설정 관리
"""

from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    """Chat Service 설정"""

    # Application
    app_name: str = "Chat Service"
    version: str = "1.0.0"
    debug: bool = True

    # Server
    host: str = "0.0.0.0"
    port: int = 8002

    # Database - MySQL
    mysql_url: str = "mysql+aiomysql://root:password@localhost:3306/chatdb"

    # Database - MongoDB
    mongo_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "chatdb"

    # Database - Redis
    redis_url: str = "redis://localhost:6379"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:19092,localhost:19093,localhost:19094"
    kafka_topic_message_events: str = "message.events"

    # JWT
    secret_key: str = "your-secret-key-here"
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
        extra = "ignore"  # 추가 환경변수 무시


settings = Settings()
