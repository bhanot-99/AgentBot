from functools import lru_cache

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str
    chat_model: str = "claude-opus-5"
    analytics_model: str = "claude-opus-5"
    session_ttl_minutes: int = 120
    force_booking_failure: str = ""
    log_level: str = "INFO"
    allowed_origins: str = ""


@lru_cache
def get_settings() -> Settings:
    # Fail fast at startup with a named variable, not a traceback (phases.md P0 exit gate).
    try:
        return Settings()
    except ValidationError as exc:
        missing = ", ".join(
            str(err["loc"][0]).upper() for err in exc.errors() if err["type"] == "missing"
        )
        raise SystemExit(
            f"Missing required environment variable: {missing or 'ANTHROPIC_API_KEY'}. "
            "Copy .env.example to .env and set it."
        ) from exc
