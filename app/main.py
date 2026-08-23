import json
import logging
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import httpx2
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from google.genai import errors as genai_errors

from app.api import chat, session
from app.config import get_settings
from app.llm.gemini_client import GeminiLLMClient
from app.models import ErrorDetail, ErrorEnvelope
from app.services.booking import BookingService
from app.services.crm import CrmService
from app.store.memory_store import InMemorySessionStore

logger = logging.getLogger(__name__)

# Masks a trailing phone number in a log message to its last four digits (rules.md A14).
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


# Reading settings at import time is the fail-fast point: a missing GEMINI_API_KEY
# stops the process here with one named-variable message, before uvicorn ever binds a port.
settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.session_store = InMemorySessionStore(ttl_minutes=settings.session_ttl_minutes)
    app.state.llm_client = GeminiLLMClient(
        api_key=settings.gemini_api_key,
        chat_model=settings.chat_model,
        analytics_model=settings.analytics_model,
    )
    app.state.booking_service = BookingService(force_failure=settings.force_booking_failure)
    app.state.crm_service = CrmService()
    yield


app = FastAPI(title="Northstar Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in settings.allowed_origins.split(",") if origin] or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session.router)
app.include_router(chat.router)


def _error_response(
    status_code: int, code: str, message: str, *, request_id: str | None = None
) -> JSONResponse:
    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code=code, message=message, request_id=request_id or f"req_{uuid.uuid4().hex[:16]}"
        )
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump())


# The error envelope (Architecture.md §8) is the only shape the browser ever sees (rules.md
# C8) — every handler below logs whatever detail is useful server-side and returns only that.


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    detail = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
    return _error_response(400, "invalid_request", detail)


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    code_by_status = {404: "session_not_found", 409: "session_ended"}
    code = code_by_status.get(exc.status_code, "invalid_request")
    return _error_response(exc.status_code, code, str(exc.detail))


@app.exception_handler(httpx.TransportError)
async def handle_llm_connection_error_httpx(
    request: Request, exc: httpx.TransportError
) -> JSONResponse:
    logger.error("llm unavailable (connection): %s", exc)
    return _error_response(
        502,
        "llm_unavailable",
        "The assistant is temporarily unavailable. Please try again shortly.",
    )


@app.exception_handler(httpx2.TransportError)
async def handle_llm_connection_error_httpx2(
    request: Request, exc: httpx2.TransportError
) -> JSONResponse:
    logger.error("llm unavailable (connection): %s", exc)
    return _error_response(
        502,
        "llm_unavailable",
        "The assistant is temporarily unavailable. Please try again shortly.",
    )


@app.exception_handler(genai_errors.ClientError)
async def handle_llm_client_error(request: Request, exc: genai_errors.ClientError) -> JSONResponse:
    logger.error("llm unavailable: status=%s message=%s", exc.status, exc.message)
    return _error_response(
        502,
        "llm_unavailable",
        "The assistant is temporarily unavailable. Please try again shortly.",
    )


@app.exception_handler(genai_errors.ServerError)
async def handle_llm_server_error(request: Request, exc: genai_errors.ServerError) -> JSONResponse:
    logger.error("llm unavailable: status=%s message=%s", exc.status, exc.message)
    return _error_response(
        502,
        "llm_unavailable",
        "The assistant is temporarily unavailable. Please try again shortly.",
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled exception", exc_info=True)
    return _error_response(500, "internal_error", "Something went wrong. Please try again.")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
