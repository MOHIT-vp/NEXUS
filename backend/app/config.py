"""Application configuration via environment variables."""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Any, List, Union
import os


class Settings(BaseSettings):
    """Central configuration loaded from environment variables."""

    # App
    APP_NAME: str = "Placement Readiness & Career Intelligence Portal"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v: Any) -> bool:
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "debug", "dev")
        return bool(v)

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://placement_user:placement_pass@localhost:5432/placement_portal"

    # Security
    SECRET_KEY: str = "change-this-to-a-64-character-random-secret-key-for-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM
    LLM_PROVIDER: str = "google"  # "google" or "openai"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gemini-2.0-flash"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS
    CORS_ORIGINS: str = "*"

    @property
    def cors_origins_list(self) -> List[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    # File Uploads
    MAX_UPLOAD_SIZE_MB: int = 5
    UPLOAD_DIR: str = "./uploads"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # Agent Config
    MAX_RETRIES: int = 3
    TOKEN_BUDGET: int = 100000
    RUN_TIMEOUT_SECONDS: int = 300

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
