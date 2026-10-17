"""
Configuration module — loads settings from environment / .env file.

Uses Pydantic BaseSettings for type-safe, validated configuration.
In production, values are injected by ECS task definition from Secrets Manager.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    # --- API ---
    api_key: str = "changeme"
    app_port: int = 8000

    # --- Redis ---
    redis_url: str = "redis://localhost:6379"
    rate_limit_max: int = 10
    rate_limit_window: int = 60

    # --- PostgreSQL ---
    database_url: str = "postgresql://postgres:localdev@localhost:5432/research_platform"

    # --- AWS Bedrock Guardrails ---
    guardrail_id: str = ""
    guardrail_version: str = "DRAFT"
    aws_region: str = "us-east-1"

    # --- TensorZero Gateway ---
    tensorzero_url: str = "http://localhost:3000"

    # --- Embeddings ---
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # --- Cache / LTM similarity thresholds ---
    cache_similarity_threshold: float = 0.85
    ltm_exact_threshold: float = 0.88
    ltm_related_threshold: float = 0.50

    # --- LangSmith ---
    langsmith_api_key: str = ""
    langsmith_project: str = "multi-agent-research"

    # --- LLM keys (used by TensorZero sidecar, not the app directly) ---
    openai_api_key: str = ""
    groq_api_key: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Singleton factory cached for the lifetime of the process."""
    return Settings()
