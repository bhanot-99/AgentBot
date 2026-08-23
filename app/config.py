from functools import lru_cache

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # min_length=1 matters: `.env.example` copied straight to `.env` produces
    # `GEMINI_API_KEY=` (present but empty), which a bare `str` field accepts silently —
    # defeating the whole point of the fail-fast check below. Caught live, not by inspection.
    gemini_api_key: str = Field(min_length=1)
    chat_model: str = "gemini-2.5-flash"
    analytics_model: str = "gemini-2.5-pro"
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
            str(err["loc"][0]).upper()
            for err in exc.errors()
            if err["type"] in ("missing", "string_too_short")
        )
        raise SystemExit(
            f"Missing required environment variable: {missing or 'GEMINI_API_KEY'}. "
            "Copy .env.example to .env and set it."
        ) from exc
