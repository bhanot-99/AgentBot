from typing import Any, TypeVar

from anthropic.types import Message, TextBlock, TextBlockParam
from anthropic.types import Usage as AnthropicUsage
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def text_message(text: str, *, stop_reason: str = "end_turn") -> Message:
    """Builds a real anthropic.types.Message so callers see exactly what the SDK returns."""
    return Message(
        id="msg_fake",
        content=[TextBlock(text=text, type="text")],
        model="claude-opus-5-fake",
        role="assistant",
        stop_reason=stop_reason,
        type="message",
        usage=AnthropicUsage(input_tokens=100, output_tokens=20, cache_read_input_tokens=0),
    )


class FakeLLMClient:
    """Scripted, deterministic LLMClient for Tier 1 tests (rules.md T1) — no network, no key."""

    def __init__(self, script: list[Message] | None = None) -> None:
        self._script = list(script or [])
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        *,
        system: list[TextBlockParam],
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> Message:
        self.calls.append({"system": system, "messages": messages, "tools": tools})
        if self._script:
            return self._script.pop(0)
        return text_message("Thanks for reaching out! How can I help you today?")

    async def parse(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        output_format: type[T],
    ) -> T:
        raise NotImplementedError("FakeLLMClient.parse is wired in Phase 5 (analytics)")
