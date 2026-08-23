import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, TypeVar

import httpx
import httpx2
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_CHAT_TIMEOUT_MS = 30_000
_ANALYTICS_TIMEOUT_MS = 60_000
_CHAT_MAX_OUTPUT_TOKENS = 1024
_ANALYTICS_MAX_OUTPUT_TOKENS = 4096
# google-genai does not retry by default, unlike the Anthropic SDK this project used before
# (rules.md A12) — omitting this means one transient failure surfaces immediately.
_RETRY_ATTEMPTS = 3

# The SDK vendors two httpx major versions internally; a connection/timeout failure can
# surface as either, so both must be caught (rules.md A13).
_CONNECTION_ERRORS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx2.TimeoutException,
    httpx2.ConnectError,
)


class GeminiLLMClient:
    def __init__(self, *, api_key: str, chat_model: str, analytics_model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._chat_model = chat_model
        self._analytics_model = analytics_model

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[types.Tool] | None = None,
    ) -> types.GenerateContentResponse:
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=_CHAT_MAX_OUTPUT_TOKENS,
            thinking_config=types.ThinkingConfig(thinking_level="LOW"),
            http_options=_http_options(_CHAT_TIMEOUT_MS),
            tools=tools,
        )
        async with _log_gemini_errors():
            response = await self._client.aio.models.generate_content(
                model=self._chat_model, contents=messages, config=config
            )
        _log_usage(response)
        return response

    async def parse(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        output_format: type[T],
    ) -> T:
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=_ANALYTICS_MAX_OUTPUT_TOKENS,
            thinking_config=types.ThinkingConfig(thinking_level="MEDIUM"),
            response_mime_type="application/json",
            response_schema=output_format,
            http_options=_http_options(_ANALYTICS_TIMEOUT_MS),
        )
        async with _log_gemini_errors():
            response = await self._client.aio.models.generate_content(
                model=self._analytics_model, contents=messages, config=config
            )
        _log_usage(response)
        return response.parsed


def _http_options(timeout_ms: int) -> types.HttpOptions:
    return types.HttpOptions(
        timeout=timeout_ms, retry_options=types.HttpRetryOptions(attempts=_RETRY_ATTEMPTS)
    )


def _log_usage(response: types.GenerateContentResponse) -> None:
    usage = response.usage_metadata
    logger.info(
        "llm usage: input=%s cached=%s output=%s",
        usage.prompt_token_count if usage else None,
        usage.cached_content_token_count if usage else None,
        usage.candidates_token_count if usage else None,
    )


@asynccontextmanager
async def _log_gemini_errors() -> AsyncIterator[None]:
    # Specific-first (rules.md A13): `.status` is Google's canonical status string
    # ("UNAUTHENTICATED", "RESOURCE_EXHAUSTED", ...) — NOT the HTTP int (that's `.code`).
    # Verified against a live call with a bad key: an invalid key returns code=400,
    # status="INVALID_ARGUMENT", not the 401 a naive int-based branch would expect.
    try:
        yield
    except errors.ClientError as exc:
        if exc.status in ("UNAUTHENTICATED", "PERMISSION_DENIED"):
            logger.error("gemini authentication failed code=%s status=%s", exc.code, exc.status)
        elif exc.status == "NOT_FOUND":
            logger.error("gemini resource not found code=%s status=%s", exc.code, exc.status)
        elif exc.status == "RESOURCE_EXHAUSTED":
            logger.warning("gemini rate limited code=%s status=%s", exc.code, exc.status)
        else:
            logger.error(
                "gemini client error code=%s status=%s message=%s",
                exc.code,
                exc.status,
                exc.message,
            )
        raise
    except errors.ServerError as exc:
        logger.error(
            "gemini server error code=%s status=%s message=%s", exc.code, exc.status, exc.message
        )
        raise
    except _CONNECTION_ERRORS as exc:
        logger.error("gemini connection error: %s", exc)
        raise
