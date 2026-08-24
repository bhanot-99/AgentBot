from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Which provider is active — a config value, never branched on elsewhere (rules.md C10).
    # Anthropic is the fallback for when the Gemini free-tier daily quota runs out mid-project.
    llm_provider: Literal["gemini", "anthropic"] = "gemini"

    gemini_api_key: str = ""
    chat_model: str = "gemini-3.6-flash"
    analytics_model: str = "gemini-3.6-flash"

    anthropic_api_key: str = ""
    anthropic_chat_model: str = "claude-haiku-4-5"
    anthropic_analytics_model: str = "claude-haiku-4-5"

    session_ttl_minutes: int = 120
    force_booking_failure: str = ""
    log_level: str = "INFO"
    allowed_origins: str = ""


@lru_cache
def get_settings() -> Settings:
    # Fail fast at startup with a named variable, not a traceback (phases.md P0 exit gate).
    # Only the active provider's key is required — copying .env.example with LLM_PROVIDER=gemini
    # and an empty ANTHROPIC_API_KEY must still boot cleanly.
    settings = Settings()
    if settings.llm_provider == "gemini" and len(settings.gemini_api_key) < 1:
        raise SystemExit(
            "Missing required environment variable: GEMINI_API_KEY. "
            "Copy .env.example to .env and set it."
        )
    if settings.llm_provider == "anthropic" and len(settings.anthropic_api_key) < 1:
        raise SystemExit(
            "Missing required environment variable: ANTHROPIC_API_KEY. "
            "Copy .env.example to .env and set it."
        )
    return settings
