import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, TypeVar

import httpx
import httpx2
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from app.llm.base import LLMResponse, ToolCallRequest, ToolSpec
from app.models import Usage

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_CHAT_TIMEOUT_MS = 30_000
_ANALYTICS_TIMEOUT_MS = 60_000
_CHAT_MAX_OUTPUT_TOKENS = 1024
_ANALYTICS_MAX_OUTPUT_TOKENS = 4096
# google-genai does not retry by default, unlike the Anthropic SDK this project also uses
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

# Provider-neutral ToolSpec.properties use lowercase JSON Schema type names; Gemini's
# types.Schema wants its own uppercase Type enum names.
_JSON_SCHEMA_TO_GEMINI_TYPE = {
    "string": "STRING",
    "integer": "INTEGER",
    "number": "NUMBER",
    "boolean": "BOOLEAN",
    "array": "ARRAY",
    "object": "OBJECT",
}


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
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=_CHAT_MAX_OUTPUT_TOKENS,
            thinking_config=types.ThinkingConfig(thinking_level="LOW"),
            http_options=_http_options(_CHAT_TIMEOUT_MS),
            tools=[_to_gemini_tool(tools)] if tools else None,
        )
        async with _log_gemini_errors():
            response = await self._client.aio.models.generate_content(
                model=self._chat_model, contents=_to_gemini_contents(messages), config=config
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
                model=self._analytics_model, contents=_to_gemini_contents(messages), config=config
            )
        _log_usage(response)
        return response.parsed


def _to_gemini_schema(properties: dict[str, Any]) -> types.Schema:
    json_type = properties.get("type", "string")
    kwargs: dict[str, Any] = {"type": _JSON_SCHEMA_TO_GEMINI_TYPE[json_type]}
    if "description" in properties:
        kwargs["description"] = properties["description"]
    if "enum" in properties:
        kwargs["enum"] = properties["enum"]
    if json_type == "array" and "items" in properties:
        kwargs["items"] = _to_gemini_schema(properties["items"])
    return types.Schema(**kwargs)


def _to_gemini_tool(tools: list[ToolSpec]) -> types.Tool:
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name=spec.name,
                description=spec.description,
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        name: _to_gemini_schema(prop) for name, prop in spec.properties.items()
                    },
                    required=spec.required,
                ),
            )
            for spec in tools
        ]
    )


def _to_gemini_contents(messages: list[dict[str, Any]]) -> list[types.Content]:
    contents = []
    for message in messages:
        role = message["role"]
        if role == "user":
            contents.append(types.Content(role="user", parts=[types.Part(text=message["text"])]))
        elif role == "assistant":
            parts = []
            if message.get("text"):
                parts.append(types.Part(text=message["text"]))
            for call in message.get("tool_calls", []):
                parts.append(
                    types.Part(
                        function_call=types.FunctionCall(
                            id=call["id"], name=call["name"], args=call["args"]
                        ),
                        # Required verbatim on the follow-up request, or Gemini rejects the
                        # turn with 400 INVALID_ARGUMENT ("Function call is missing a
                        # thought_signature") — caught live, not documented up front.
                        thought_signature=call.get("extra", {}).get("thought_signature"),
                    )
                )
            contents.append(types.Content(role="model", parts=parts))
        elif role == "tool_result":
            parts = [
                types.Part(
                    function_response=types.FunctionResponse(
                        id=result["id"], name=result["name"], response=result["output"]
                    )
                )
                for result in message["results"]
            ]
            contents.append(types.Content(role="user", parts=parts))
    return contents


def _to_llm_response(response: types.GenerateContentResponse) -> LLMResponse:
    candidate = response.candidates[0]
    tool_calls = [
        ToolCallRequest(
            id=part.function_call.id or part.function_call.name,
            name=part.function_call.name,
            args=dict(part.function_call.args or {}),
            extra={"thought_signature": part.thought_signature} if part.thought_signature else {},
        )
        for part in candidate.content.parts
        if part.function_call
    ]
    usage_metadata = response.usage_metadata
    usage = Usage(
        input_tokens=usage_metadata.prompt_token_count or 0,
        cache_read_input_tokens=usage_metadata.cached_content_token_count or 0,
        output_tokens=usage_metadata.candidates_token_count or 0,
    )
    return LLMResponse(
        text=(response.text or "").strip() or None, tool_calls=tool_calls, usage=usage
    )


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
