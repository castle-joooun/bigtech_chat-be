from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()  # .env 파일 로드


class Settings(BaseSettings):
    # Database URLs
    mongo_url: str
    mysql_url: str
    redis_url: str = "redis://localhost:6379/0"

    # JWT Settings
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_hours: int = 2

    # App Settings
    debug: bool = False
    app_name: str = "BigTech Chat Backend"
    version: str = "1.0.0"

    # Redis Settings
    redis_max_connections: int = 20
    redis_retry_on_timeout: bool = True
    redis_socket_keepalive: bool = True
    redis_socket_keepalive_options: dict = {}

    # Rate Limiting Settings
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60
    rate_limit_burst: int = 10

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
