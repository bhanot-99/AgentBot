from typing import Any, TypeVar

from pydantic import BaseModel

from app.llm.base import LLMResponse, ToolCallRequest, ToolSpec
from app.models import Usage

T = TypeVar("T", bound=BaseModel)

_DEFAULT_USAGE = Usage(input_tokens=100, cache_read_input_tokens=0, output_tokens=20)


def text_response(text: str, *, usage: Usage | None = None) -> LLMResponse:
    return LLMResponse(text=text, tool_calls=[], usage=usage or _DEFAULT_USAGE)


def tool_call_response(
    *calls: tuple[str, dict[str, Any]], usage: Usage | None = None
) -> LLMResponse:
    return LLMResponse(
        text=None,
        tool_calls=[
            ToolCallRequest(id=f"call_{i}", name=name, args=args)
            for i, (name, args) in enumerate(calls)
        ],
        usage=usage or _DEFAULT_USAGE,
    )


class FakeLLMClient:
    """Scripted, deterministic LLMClient for Tier 1 tests (rules.md T1) — no network, no key."""

    def __init__(self, script: list[LLMResponse] | None = None) -> None:
        self._script = list(script or [])
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        self.calls.append({"system": system, "messages": messages, "tools": tools})
        if self._script:
            return self._script.pop(0)
        return text_response("Thanks for reaching out! How can I help you today?")

    async def parse(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        output_format: type[T],
    ) -> T:
        raise NotImplementedError("FakeLLMClient.parse is wired in Phase 5 (analytics)")
