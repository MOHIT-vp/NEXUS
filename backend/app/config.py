"""Application configuration via environment variables."""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Any, List, Optional, Dict
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

    # LLM Global Configuration
    LLM_PROVIDER: str = "google"  # "google", "openai", "groq", "bedrock", "anthropic"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gemini-2.0-flash"
    LLM_API_KEYS: str = ""  # Comma-separated pool of keys auto-distributed to agents

    # Agent-Specific LLM API Keys & Configuration (Prevents shared rate limits across agents)
    # Resume Agent
    RESUME_AGENT_API_KEY: str = ""
    RESUME_AGENT_PROVIDER: str = ""
    RESUME_AGENT_MODEL: str = ""

    # Coding Analytics Agent
    CODING_ANALYTICS_AGENT_API_KEY: str = ""
    CODING_ANALYTICS_AGENT_PROVIDER: str = ""
    CODING_ANALYTICS_AGENT_MODEL: str = ""

    # Skill Gap Agent
    SKILL_GAP_AGENT_API_KEY: str = ""
    SKILL_GAP_AGENT_PROVIDER: str = ""
    SKILL_GAP_AGENT_MODEL: str = ""

    # Job Matching Agent
    JOB_MATCHING_AGENT_API_KEY: str = ""
    JOB_MATCHING_AGENT_PROVIDER: str = ""
    JOB_MATCHING_AGENT_MODEL: str = ""

    # Interview Agent
    INTERVIEW_AGENT_API_KEY: str = ""
    INTERVIEW_AGENT_PROVIDER: str = ""
    INTERVIEW_AGENT_MODEL: str = ""

    # Coordinator / Workflow Planner
    COORDINATOR_AGENT_API_KEY: str = ""
    COORDINATOR_AGENT_PROVIDER: str = ""
    COORDINATOR_AGENT_MODEL: str = ""

    # Mock Interview Evaluator
    MOCK_INTERVIEW_API_KEY: str = ""
    MOCK_INTERVIEW_PROVIDER: str = ""
    MOCK_INTERVIEW_MODEL: str = ""

    # Mock Practice Coach
    MOCK_PRACTICE_API_KEY: str = ""
    MOCK_PRACTICE_PROVIDER: str = ""
    MOCK_PRACTICE_MODEL: str = ""

    # Chat Assistant
    CHAT_AGENT_API_KEY: str = ""
    CHAT_AGENT_PROVIDER: str = ""
    CHAT_AGENT_MODEL: str = ""

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

    @staticmethod
    def _is_valid_key(key: Any) -> bool:
        if not key or not isinstance(key, str):
            return False
        k = key.strip()
        return bool(k) and k.lower() not in ("dummy", "your-api-key-here", "none", "null", "false", "")

    def get_pool_keys(self) -> List[str]:
        """Parse comma or semicolon separated keys from LLM_API_KEYS or os.getenv."""
        raw = (self.LLM_API_KEYS or os.getenv("LLM_API_KEYS", "")).strip()
        if not raw:
            return []
        keys = []
        for part in raw.replace(";", ",").replace("\n", ",").split(","):
            cleaned = part.strip()
            if self._is_valid_key(cleaned):
                keys.append(cleaned)
        return keys

    # Canonical agent configuration mapping
    _AGENT_CONFIG_MAP = {
        "resume_agent": {
            "aliases": ("resume_agent", "resume", "resume_parser"),
            "key_vars": ("RESUME_AGENT_API_KEY", "RESUME_API_KEY", "LLM_API_KEY_RESUME_AGENT", "LLM_API_KEY_RESUME"),
            "provider_vars": ("RESUME_AGENT_PROVIDER", "RESUME_PROVIDER", "LLM_PROVIDER_RESUME_AGENT", "LLM_PROVIDER_RESUME"),
            "model_vars": ("RESUME_AGENT_MODEL", "RESUME_MODEL", "LLM_MODEL_RESUME_AGENT", "LLM_MODEL_RESUME"),
            "pool_index": 0,
        },
        "coding_analytics_agent": {
            "aliases": ("coding_analytics_agent", "coding_analytics", "coding"),
            "key_vars": ("CODING_ANALYTICS_AGENT_API_KEY", "CODING_ANALYTICS_API_KEY", "CODING_API_KEY", "LLM_API_KEY_CODING", "LLM_API_KEY_CODING_ANALYTICS"),
            "provider_vars": ("CODING_ANALYTICS_AGENT_PROVIDER", "CODING_PROVIDER", "LLM_PROVIDER_CODING"),
            "model_vars": ("CODING_ANALYTICS_AGENT_MODEL", "CODING_MODEL", "LLM_MODEL_CODING"),
            "pool_index": 1,
        },
        "skill_gap_agent": {
            "aliases": ("skill_gap_agent", "skill_gap", "skillgap"),
            "key_vars": ("SKILL_GAP_AGENT_API_KEY", "SKILL_GAP_API_KEY", "LLM_API_KEY_SKILL_GAP", "LLM_API_KEY_SKILL_GAP_AGENT"),
            "provider_vars": ("SKILL_GAP_AGENT_PROVIDER", "SKILL_GAP_PROVIDER", "LLM_PROVIDER_SKILL_GAP"),
            "model_vars": ("SKILL_GAP_AGENT_MODEL", "SKILL_GAP_MODEL", "LLM_MODEL_SKILL_GAP"),
            "pool_index": 2,
        },
        "job_matching_agent": {
            "aliases": ("job_matching_agent", "job_matching", "jobmatching", "matching"),
            "key_vars": ("JOB_MATCHING_AGENT_API_KEY", "JOB_MATCHING_API_KEY", "LLM_API_KEY_JOB_MATCHING", "LLM_API_KEY_JOB_MATCHING_AGENT"),
            "provider_vars": ("JOB_MATCHING_AGENT_PROVIDER", "JOB_MATCHING_PROVIDER", "LLM_PROVIDER_JOB_MATCHING"),
            "model_vars": ("JOB_MATCHING_AGENT_MODEL", "JOB_MATCHING_MODEL", "LLM_MODEL_JOB_MATCHING"),
            "pool_index": 3,
        },
        "interview_agent": {
            "aliases": ("interview_agent", "interview", "interview_prep"),
            "key_vars": ("INTERVIEW_AGENT_API_KEY", "INTERVIEW_API_KEY", "LLM_API_KEY_INTERVIEW", "LLM_API_KEY_INTERVIEW_AGENT"),
            "provider_vars": ("INTERVIEW_AGENT_PROVIDER", "INTERVIEW_PROVIDER", "LLM_PROVIDER_INTERVIEW"),
            "model_vars": ("INTERVIEW_AGENT_MODEL", "INTERVIEW_MODEL", "LLM_MODEL_INTERVIEW"),
            "pool_index": 4,
        },
        "coordinator": {
            "aliases": ("coordinator", "coordinator_agent", "planner"),
            "key_vars": ("COORDINATOR_AGENT_API_KEY", "COORDINATOR_API_KEY", "LLM_API_KEY_COORDINATOR", "LLM_API_KEY_COORDINATOR_AGENT"),
            "provider_vars": ("COORDINATOR_AGENT_PROVIDER", "COORDINATOR_PROVIDER", "LLM_PROVIDER_COORDINATOR"),
            "model_vars": ("COORDINATOR_AGENT_MODEL", "COORDINATOR_MODEL", "LLM_MODEL_COORDINATOR"),
            "pool_index": 5,
        },
        "mock_interview": {
            "aliases": ("mock_interview", "mock_interview_agent", "interview_grader"),
            "key_vars": ("MOCK_INTERVIEW_API_KEY", "MOCK_INTERVIEW_AGENT_API_KEY", "LLM_API_KEY_MOCK_INTERVIEW"),
            "provider_vars": ("MOCK_INTERVIEW_PROVIDER", "LLM_PROVIDER_MOCK_INTERVIEW"),
            "model_vars": ("MOCK_INTERVIEW_MODEL", "LLM_MODEL_MOCK_INTERVIEW"),
            "pool_index": 6,
        },
        "mock_practice": {
            "aliases": ("mock_practice", "mock_practice_agent", "practice_coach"),
            "key_vars": ("MOCK_PRACTICE_API_KEY", "MOCK_PRACTICE_AGENT_API_KEY", "LLM_API_KEY_MOCK_PRACTICE"),
            "provider_vars": ("MOCK_PRACTICE_PROVIDER", "LLM_PROVIDER_MOCK_PRACTICE"),
            "model_vars": ("MOCK_PRACTICE_MODEL", "LLM_MODEL_MOCK_PRACTICE"),
            "pool_index": 7,
        },
        "chat": {
            "aliases": ("chat", "chat_agent", "nexus_chat"),
            "key_vars": ("CHAT_AGENT_API_KEY", "CHAT_API_KEY", "LLM_API_KEY_CHAT", "LLM_API_KEY_CHAT_AGENT"),
            "provider_vars": ("CHAT_AGENT_PROVIDER", "CHAT_PROVIDER", "LLM_PROVIDER_CHAT"),
            "model_vars": ("CHAT_AGENT_MODEL", "CHAT_MODEL", "LLM_MODEL_CHAT"),
            "pool_index": 8,
        },
    }

    def get_agent_llm_config(self, agent_name: Optional[str] = None) -> Dict[str, str]:
        """
        Resolves the LLM configuration (provider, model, api_key) for a specific agent.
        
        Resolution order for API key:
        1. Agent-specific environment variable or Setting attribute (e.g. RESUME_AGENT_API_KEY)
        2. Key from LLM_API_KEYS pool (assigned deterministically by agent index)
        3. Global LLM_API_KEY default
        
        Resolution order for provider & model:
        1. Agent-specific environment variable or Setting attribute
        2. Global LLM_PROVIDER / LLM_MODEL default
        """
        raw = (agent_name or "").lower().strip()
        matched_entry = None
        matched_canonical = None

        for canonical, entry in self._AGENT_CONFIG_MAP.items():
            if raw == canonical or raw in entry["aliases"]:
                matched_entry = entry
                matched_canonical = canonical
                break

        api_key = ""
        provider = ""
        model = ""

        if matched_entry:
            for k in matched_entry["key_vars"]:
                val = getattr(self, k, None) or os.getenv(k, "")
                if self._is_valid_key(val):
                    api_key = str(val).strip()
                    break

            for p in matched_entry["provider_vars"]:
                val = getattr(self, p, None) or os.getenv(p, "")
                if val and str(val).strip():
                    provider = str(val).strip()
                    break

            for m in matched_entry["model_vars"]:
                val = getattr(self, m, None) or os.getenv(m, "")
                if val and str(val).strip():
                    model = str(val).strip()
                    break

            if not api_key:
                pool = self.get_pool_keys()
                if pool:
                    idx = matched_entry["pool_index"] % len(pool)
                    api_key = pool[idx]
        elif raw:
            clean = raw.replace("-", "_").upper()
            for cand in (f"{clean}_AGENT_API_KEY", f"{clean}_API_KEY", f"LLM_API_KEY_{clean}"):
                val = getattr(self, cand, None) or os.getenv(cand, "")
                if self._is_valid_key(val):
                    api_key = str(val).strip()
                    break
            pool = self.get_pool_keys()
            if not api_key and pool:
                api_key = pool[abs(hash(raw)) % len(pool)]

        if not api_key:
            api_key = (self.LLM_API_KEY or os.getenv("LLM_API_KEY", "")).strip()

        if not provider:
            provider = (self.LLM_PROVIDER or os.getenv("LLM_PROVIDER", "google")).strip()

        if not model:
            model = (self.LLM_MODEL or os.getenv("LLM_MODEL", "gemini-2.0-flash")).strip()

        return {
            "agent_name": matched_canonical or raw or "default",
            "provider": provider,
            "model": model,
            "api_key": api_key,
        }

    def is_agent_llm_enabled(self, agent_name: Optional[str] = None) -> bool:
        """Check whether LLM is enabled for a given agent."""
        cfg = self.get_agent_llm_config(agent_name)
        if cfg["provider"].lower() == "bedrock":
            return bool(os.getenv("AWS_ACCESS_KEY_ID"))
        return self._is_valid_key(cfg["api_key"])

    @property
    def llm_enabled(self) -> bool:
        """LLM narration runs when any real key is configured (global or per-agent)."""
        if self._is_valid_key(self.LLM_API_KEY):
            return True
        if self.LLM_PROVIDER.lower() == "bedrock" and bool(os.getenv("AWS_ACCESS_KEY_ID")):
            return True
        if any(self._is_valid_key(k) for k in self.get_pool_keys()):
            return True
        for agent in self._AGENT_CONFIG_MAP:
            if self._is_valid_key(self.get_agent_llm_config(agent).get("api_key")):
                return True
        return False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
