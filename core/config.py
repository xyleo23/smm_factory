"""Configuration management for SMM Factory."""

from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
    )

    # Telegram Bot — accepts both BOT_TOKEN and TELEGRAM_BOT_TOKEN
    telegram_bot_token: str = Field(
        default="",
        validation_alias=AliasChoices("BOT_TOKEN", "TELEGRAM_BOT_TOKEN"),
        description="Telegram bot token",
    )
    telegram_channel_id: str = Field(
        default="",
        description="Telegram channel ID (e.g. @mychannel or -100123456789)",
    )
    admin_chat_id: Optional[str] = Field(
        None,
        description="Telegram user/chat ID of the admin (used for default UserSettings seed)",
    )

    # AI / LLM APIs
    openrouter_api_key: Optional[str] = Field(None, description="OpenRouter API key")
    nano_banana_api_key: Optional[str] = Field(None, description="NanoBanana image API key")

    # VC.ru API
    vc_session_token: Optional[str] = Field(None, description="VC.ru session token (X-Device-Token)")

    # RBC Companies
    rbc_login: Optional[str] = Field(None, description="RBC Companies login email")
    rbc_password: Optional[str] = Field(None, description="RBC Companies password")

    # Redis for Celery
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for Celery broker and backend",
    )

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./smm_factory.db",
        description="SQLAlchemy database URL",
    )

    # Paths
    logs_dir: Path = Field(default=Path("logs"), description="Directory for log files")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    @property
    def DATABASE_URL(self) -> str:
        """Backward-compatible alias for legacy uppercase access."""
        return self.database_url


# Global settings instance
settings = Settings()

# Backward-compatible alias for existing imports
config = settings
