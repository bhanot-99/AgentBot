import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, TypeVar

import anthropic
from anthropic.types import Message, TextBlockParam
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_CHAT_TIMEOUT_SECONDS = 30
_ANALYTICS_TIMEOUT_SECONDS = 60
_CHAT_MAX_TOKENS = 1024
_ANALYTICS_MAX_TOKENS = 4096


class AnthropicLLMClient:
    def __init__(self, *, api_key: str, chat_model: str, analytics_model: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._chat_model = chat_model
        self._analytics_model = analytics_model

    async def complete(
        self,
        *,
        system: list[TextBlockParam],
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> Message:
        async with _log_anthropic_errors():
            response = await self._client.with_options(
                timeout=_CHAT_TIMEOUT_SECONDS
            ).messages.create(
                model=self._chat_model,
                system=system,
                messages=messages,
                tools=tools or [],
                max_tokens=_CHAT_MAX_TOKENS,
                output_config={"effort": "low"},
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
        async with _log_anthropic_errors():
            response = await self._client.with_options(
                timeout=_ANALYTICS_TIMEOUT_SECONDS
            ).messages.parse(
                model=self._analytics_model,
                system=system,
                messages=messages,
                output_format=output_format,
                max_tokens=_ANALYTICS_MAX_TOKENS,
                output_config={"effort": "medium"},
            )
        _log_usage(response)
        return response.parsed_output


def _log_usage(response: Message) -> None:
    usage = response.usage
    logger.info(
        "llm usage: input=%s cache_read=%s output=%s request_id=%s",
        usage.input_tokens,
        usage.cache_read_input_tokens,
        usage.output_tokens,
        response._request_id,  # noqa: SLF001 — the SDK's documented way to read it (rules.md A14)
    )


@asynccontextmanager
async def _log_anthropic_errors() -> AsyncIterator[None]:
    # Specific-first (rules.md A14): a single broad `except APIStatusError` would erase the
    # retryable/non-retryable distinction the caller needs. Logged here, re-raised for the
    # API layer's global exception handlers (Phase 2 task 7) to map onto the error envelope.
    try:
        yield
    except anthropic.AuthenticationError:
        logger.error("anthropic authentication failed", exc_info=True)
        raise
    except anthropic.NotFoundError:
        logger.error("anthropic resource not found", exc_info=True)
        raise
    except anthropic.RateLimitError as exc:
        logger.warning("anthropic rate limited request_id=%s", exc.request_id)
        raise
    except anthropic.APIStatusError as exc:
        logger.error(
            "anthropic api status error status=%s request_id=%s", exc.status_code, exc.request_id
        )
        raise
    except (anthropic.APIConnectionError, anthropic.APITimeoutError) as exc:
        logger.error("anthropic connection error: %s", exc)
        raise
