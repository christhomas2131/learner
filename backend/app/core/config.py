"""Application settings with startup validation.

Loaded once as a module-level singleton (`settings`). Required variables are
validated by Pydantic; demo/no-model mode requires no Anthropic key.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.enums import ModelProviderKind

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "local"
    APP_NAME: str = "Learner"
    APP_DEBUG: bool = True
    SECRET_KEY: str = "dev-insecure-change-me"

    # sqlite for local/tests; postgresql+asyncpg://... for production.
    DATABASE_URL: str = f"sqlite+aiosqlite:///{BACKEND_DIR / 'learner.db'}"

    # Model provider. Default is the no-model deterministic path so the app
    # runs with zero external dependencies. "claude_code" enables the worker.
    MODEL_PROVIDER: ModelProviderKind = ModelProviderKind.NONE
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-sonnet-5"

    MAX_MODEL_RETRIES: int = 2
    MAX_PIPELINE_ATTEMPTS: int = 2
    MODEL_TIMEOUT_SECONDS: int = 60

    UPLOAD_DIRECTORY: Path = BACKEND_DIR / "uploads"
    KNOWLEDGE_DIRECTORY: Path = BACKEND_DIR / "knowledge"
    MAX_UPLOAD_SIZE_MB: int = 25

    RETRIEVAL_LIMIT: int = 8
    RETRIEVAL_MIN_SCORE: float = 0.0  # FTS bm25 rank; 0 = accept any match

    # Semantic retrieval: local keyless embeddings (fastembed/ONNX) fused with
    # FTS via reciprocal rank fusion. Degrades to FTS-only if the model can't load.
    RETRIEVAL_USE_EMBEDDINGS: bool = True
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    RRF_K: int = 60

    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    LOG_LEVEL: str = "INFO"

    DEMO_USER_ID: str = "00000000-0000-0000-0000-000000000001"

    # Premium worker presence: the worker writes a heartbeat file; the API
    # reports "online" if it was touched within this many seconds.
    WORKER_HEARTBEAT_TTL: int = 45

    # When true (and the `claude` CLI is installed), the API auto-drains premium
    # questions in-process via `claude -p` — hands-off, no terminal, no API key.
    PREMIUM_AUTODRAIN: bool = True
    PREMIUM_DRAIN_INTERVAL: int = 3

    @property
    def heartbeat_path(self) -> Path:
        return BACKEND_DIR / ".worker_heartbeat"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    def validate_runtime(self) -> None:
        """Fail fast on incoherent configuration at startup."""
        if self.MODEL_PROVIDER == ModelProviderKind.ANTHROPIC and not self.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "MODEL_PROVIDER=anthropic requires ANTHROPIC_API_KEY. "
                "Use MODEL_PROVIDER=none or claude_code for keyless operation."
            )
        self.UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
        self.KNOWLEDGE_DIRECTORY.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
