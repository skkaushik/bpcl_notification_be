"""
Application configuration using pydantic-settings.
Reads from .env file and environment variables.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # AI Provider
    AI_PROVIDER: str = "gemini"  # "gemini" or "openai"
    AI_MODEL: str = "gemini-2.5-flash"

    # API Keys (server-side defaults; client can override per-request)
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Upload limits
    MAX_UPLOAD_SIZE_MB: int = 50

    # Session TTL in hours
    SESSION_TTL_HOURS: int = 24

    MONGODB_URL: str
    DATABASE_NAME: str = "notification_ai"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
