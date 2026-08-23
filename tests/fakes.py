from typing import Any, TypeVar

from google.genai import types
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def text_response(text: str, *, finish_reason: str = "STOP") -> types.GenerateContentResponse:
    """Builds a real google.genai.types.GenerateContentResponse so callers see exactly what
    the SDK returns."""
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=[types.Part(text=text)]),
                finish_reason=finish_reason,
            )
        ],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=100, candidates_token_count=20, cached_content_token_count=0
        ),
    )


class FakeLLMClient:
    """Scripted, deterministic LLMClient for Tier 1 tests (rules.md T1) — no network, no key."""

    def __init__(self, script: list[types.GenerateContentResponse] | None = None) -> None:
        self._script = list(script or [])
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> types.GenerateContentResponse:
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
