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

    # Coding-platform connectors (public APIs; GITHUB_TOKEN only raises the rate limit)
    GITHUB_API_URL: str = "https://api.github.com"
    GITHUB_TOKEN: str = ""
    LEETCODE_GRAPHQL_URL: str = "https://leetcode.com/graphql"
    CONNECTOR_TIMEOUT_SECONDS: float = 10.0
    CODING_DATA_STALE_HOURS: int = 24

    # Knowledge base backend: "postgres_fts" (default, no extensions) or "pgvector"
    KB_BACKEND: str = "postgres_fts"

    # Run checkpoints (Lab 6): "sqlite" keeps each run's progress on disk so an
    # interrupted run resumes from its last completed step; "memory" does not survive a restart.
    CHECKPOINT_BACKEND: str = "sqlite"
    CHECKPOINT_DB_PATH: str = "./data/checkpoints.sqlite"
    RESUME_INTERRUPTED_RUNS_ON_STARTUP: bool = True

    # Similarity search: "model" = local sentence-embedding model (fastembed, downloaded once),
    # "hashed" = lexical hashed vectors (no download). Falls back to "hashed" if the model can't load.
    EMBEDDING_BACKEND: str = "model"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_CACHE_DIR: str = "./data/models"

    @property
    def llm_enabled(self) -> bool:
        """LLM narration runs only when a real key is configured; otherwise agents stay deterministic."""
        key = (self.LLM_API_KEY or "").strip()
        return bool(key) and key not in ("dummy", "your-api-key-here")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
