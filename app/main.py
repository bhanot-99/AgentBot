import json
import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings

# Masks a trailing phone number in a log message to its last four digits (rules.md A15).
_PHONE_RE = re.compile(r"(?<!\d)(\d{6,})(\d{4})(?!\d)")


class PhoneMaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Mask the fully-interpolated message, not the raw %-template — record.msg alone
        # never contains the digits when callers pass args lazily (the recommended pattern).
        record.msg = _PHONE_RE.sub(
            lambda m: "*" * len(m.group(1)) + m.group(2), record.getMessage()
        )
        record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {"level": record.levelname, "logger": record.name, "message": record.getMessage()}
        )


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(PhoneMaskingFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


# Reading settings at import time is the fail-fast point: a missing ANTHROPIC_API_KEY
# stops the process here with one named-variable message, before uvicorn ever binds a port.
settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO(P2): construct the LLMClient and SessionStore singletons here.
    yield


app = FastAPI(title="Northstar Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in settings.allowed_origins.split(",") if origin] or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
