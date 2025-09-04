from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()  # .env 파일 로드


class Settings(BaseSettings):
    mongo_url: str
    mysql_url: str
    secret_key: str
    algorithm: str
    debug: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
