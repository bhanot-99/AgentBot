import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel

from app.llm.base import LLMResponse, ToolCallRequest, ToolSpec
from app.models import Usage

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_CHAT_TIMEOUT_S = 30.0
_ANALYTICS_TIMEOUT_S = 60.0
_CHAT_MAX_TOKENS = 1024
_ANALYTICS_MAX_TOKENS = 4096
_RETRY_ATTEMPTS = 2


class AnthropicLLMClient:
    """Fallback LLMClient for when the Gemini free-tier quota is exhausted mid-project — the
    same `LLMClient` Protocol, so the orchestrator, tools.py, and session storage are unaware
    of which provider is active (Architecture.md §2, extended for dual-provider support)."""

    def __init__(self, *, api_key: str, chat_model: str, analytics_model: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key, max_retries=_RETRY_ATTEMPTS)
        self._chat_model = chat_model
        self._analytics_model = analytics_model

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        async with _log_anthropic_errors():
            response = await self._client.with_options(timeout=_CHAT_TIMEOUT_S).messages.create(
                model=self._chat_model,
                max_tokens=_CHAT_MAX_TOKENS,
                system=system,
                messages=_to_anthropic_messages(messages),
                tools=[_to_anthropic_tool(spec) for spec in tools] if tools else [],
            )
        _log_usage(response)
        return _to_llm_response(response)

    async def parse(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        output_format: type[T],
    ) -> T:
        async with _log_anthropic_errors():
            response = await self._client.with_options(timeout=_ANALYTICS_TIMEOUT_S).messages.parse(
                model=self._analytics_model,
                max_tokens=_ANALYTICS_MAX_TOKENS,
                system=system,
                messages=_to_anthropic_messages(messages),
                output_format=output_format,
            )
        _log_usage(response)
        return response.parsed


def _to_anthropic_tool(spec: ToolSpec) -> dict[str, Any]:
    # strict:true + additionalProperties:false is Anthropic's closed-schema guard (rules.md
    # A5) — the exact opposite of Gemini, whose live API rejects additionalProperties outright.
    return {
        "name": spec.name,
        "description": spec.description,
        "input_schema": {
            "type": "object",
            "properties": spec.properties,
            "required": spec.required,
            "additionalProperties": False,
        },
        "strict": True,
    }


def _to_anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    anthropic_messages = []
    for message in messages:
        role = message["role"]
        if role == "user":
            anthropic_messages.append({"role": "user", "content": message["text"]})
        elif role == "assistant":
            content: list[dict[str, Any]] = []
            if message.get("text"):
                content.append({"type": "text", "text": message["text"]})
            for call in message.get("tool_calls", []):
                content.append(
                    {
                        "type": "tool_use",
                        "id": call["id"],
                        "name": call["name"],
                        "input": call["args"],
                    }
                )
            anthropic_messages.append({"role": "assistant", "content": content})
        elif role == "tool_result":
            content = [
                {
                    "type": "tool_result",
                    "tool_use_id": result["id"],
                    "content": json.dumps(result["output"]),
                    "is_error": not bool(result["output"].get("ok", True)),
                }
                for result in message["results"]
            ]
            anthropic_messages.append({"role": "user", "content": content})
    return anthropic_messages


def _to_llm_response(response: anthropic.types.Message) -> LLMResponse:
    text_blocks = [block.text for block in response.content if block.type == "text"]
    tool_calls = [
        ToolCallRequest(id=block.id, name=block.name, args=dict(block.input))
        for block in response.content
        if block.type == "tool_use"
    ]
    usage = Usage(
        input_tokens=response.usage.input_tokens,
        cache_read_input_tokens=response.usage.cache_read_input_tokens or 0,
        output_tokens=response.usage.output_tokens,
    )
    text = "\n".join(text_blocks).strip() or None
    return LLMResponse(text=text, tool_calls=tool_calls, usage=usage)


def _log_usage(response: Any) -> None:
    usage = getattr(response, "usage", None)
    logger.info(
        "llm usage: input=%s cached=%s output=%s",
        usage.input_tokens if usage else None,
        usage.cache_read_input_tokens if usage else None,
        usage.output_tokens if usage else None,
    )


@asynccontextmanager
async def _log_anthropic_errors() -> AsyncIterator[None]:
    # Specific-first (rules.md A13): most-specific exception first so retryable (429, 5xx,
    # connection) and non-retryable (400/401/403/404) failures stay distinguishable.
    try:
        yield
    except anthropic.AuthenticationError as exc:
        logger.error(
            "anthropic authentication failed status=%s request_id=%s",
            exc.status_code,
            exc.request_id,
        )
        raise
    except anthropic.PermissionDeniedError as exc:
        logger.error(
            "anthropic permission denied status=%s request_id=%s", exc.status_code, exc.request_id
        )
        raise
    except anthropic.NotFoundError as exc:
        logger.error(
            "anthropic resource not found status=%s request_id=%s",
            exc.status_code,
            exc.request_id,
        )
        raise
    except anthropic.RateLimitError as exc:
        logger.warning(
            "anthropic rate limited status=%s request_id=%s", exc.status_code, exc.request_id
        )
        raise
    except anthropic.APIStatusError as exc:
        logger.error(
            "anthropic api error status=%s request_id=%s message=%s",
            exc.status_code,
            exc.request_id,
            exc.message,
        )
        raise
    except anthropic.APIConnectionError as exc:
        logger.error("anthropic connection error: %s", exc)
        raise
