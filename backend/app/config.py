from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tg_content_engine"

    @property
    def async_database_url(self) -> str:
        """Convert database URL to async format for asyncpg."""
        url = self.database_url
        # Handle Railway/Supabase URLs that don't have +asyncpg
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        """Get sync database URL for alembic migrations."""
        url = self.database_url
        # Remove +asyncpg if present for sync operations
        if "+asyncpg" in url:
            return url.replace("+asyncpg", "", 1)
        return url

    # Redis - Railway may use REDIS_URL or REDIS_PRIVATE_URL
    redis_url: str = "redis://localhost:6379/0"
    redis_private_url: Optional[str] = None

    @property
    def effective_redis_url(self) -> str:
        """Get the effective Redis URL, preferring private URL if available."""
        if self.redis_private_url:
            return self.redis_private_url
        return self.redis_url

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
    backend_url: str = "http://localhost:8000"  # Set to your Railway backend URL in production

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
