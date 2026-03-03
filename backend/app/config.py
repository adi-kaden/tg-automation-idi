from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tg_content_engine"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Authentication
    jwt_secret_key: str = "your-super-secret-jwt-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # Encryption
    encryption_key: Optional[str] = None

    # External APIs (stubbed)
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_channel_id: Optional[str] = None
    telegram_smm_chat_id: Optional[str] = None

    # Timezone
    app_timezone: str = "Asia/Dubai"

    # Scraping
    scrape_user_agent: str = "Mozilla/5.0 (compatible; TGContentBot/1.0)"
    scrape_request_delay_sec: int = 2

    # App Settings
    debug: bool = True
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
