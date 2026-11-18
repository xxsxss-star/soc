from functools import lru_cache

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration currently consumed by deterministic domain services."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["demo", "test", "development", "production"] = Field(
        default="demo", validation_alias="APP_ENV"
    )
    ai_mode: Literal["mock", "live"] = Field(default="mock", validation_alias="AI_MODE")
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="", validation_alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="", validation_alias="OPENAI_MODEL")
    ai_timeout_seconds: float = Field(
        default=15, gt=0, validation_alias="AI_TIMEOUT_SECONDS"
    )
    ai_max_retries: int = Field(default=1, ge=0, le=1, validation_alias="AI_MAX_RETRIES")
    ai_false_positive_threshold: int = Field(
        default=85,
        ge=0,
        le=100,
        validation_alias="AI_FALSE_POSITIVE_THRESHOLD",
    )
    demo_node_delay_ms: int = Field(default=300, ge=0, validation_alias="DEMO_NODE_DELAY_MS")
    data_dir: Path = Field(default=Path("data"), validation_alias="DATA_DIR")


@lru_cache
def get_settings() -> Settings:
    return Settings()
