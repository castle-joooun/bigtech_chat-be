"""
Base Service Settings (기본 서비스 설정)
======================================

모든 MSA 서비스가 상속받는 기본 설정 클래스입니다.
서비스별로 이 클래스를 상속하여 추가 설정을 정의합니다.

사용 예시
---------
```python
from shared_lib.core import BaseServiceSettings

class Settings(BaseServiceSettings):
    app_name: str = "my-service"
    port: int = 8001
    kafka_topic_my_events: str = "my.events"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )
```
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """MSA 서비스 공통 설정"""

    # ==========================================================================
    # Application
    # ==========================================================================
    app_name: str = "bigtech-service"
    version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # ==========================================================================
    # Authentication (JWT)
    # ==========================================================================
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_hours: int = 2

    # ==========================================================================
    # CORS
    # ==========================================================================
    cors_origins: str = "*"

    # ==========================================================================
    # Database - MySQL
    # ==========================================================================
    mysql_url: str = "mysql+aiomysql://user:password@localhost:3306/dbname"

    # ==========================================================================
    # Database - Redis (Optional)
    # ==========================================================================
    redis_url: Optional[str] = None

    # ==========================================================================
    # Kafka
    # ==========================================================================
    kafka_bootstrap_servers: str = "localhost:9092"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
