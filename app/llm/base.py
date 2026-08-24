from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, Field

from app.models import Usage

T = TypeVar("T", bound=BaseModel)


class ToolSpec(BaseModel):
    """A provider-neutral tool declaration. Each LLMClient implementation translates this
    into its own wire format (Gemini's types.Schema vs Anthropic's raw JSON Schema) — the
    orchestrator and app/agent/tools.py never see a provider-specific type (Architecture.md §2).

    `properties` values use standard JSON Schema conventions (lowercase "string"/"integer"/
    "array"/"object", "enum", "items", "description") — not any one provider's dialect.
    """

    name: str
    description: str
    properties: dict[str, Any]
    required: list[str] = Field(default_factory=list)


class ToolCallRequest(BaseModel):
    id: str
    name: str
    args: dict[str, Any]
    # Opaque per-provider passthrough (e.g. Gemini's thought_signature, required verbatim on
    # the next request's function_call Part or the API rejects the turn with 400
    # INVALID_ARGUMENT). Anthropic never populates or reads this.
    extra: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    text: str | None
    tool_calls: list[ToolCallRequest]
    usage: Usage


class LLMClient(Protocol):
    """The one seam between the agent and the model provider (Architecture.md §2).

    `messages` is always the provider-neutral shape session.py/chat.py/orchestrator.py build
    and store — never a raw Gemini or Anthropic wire type:
      - {"role": "user", "text": str}
      - {"role": "assistant", "text": str | None, "tool_calls": [{"id", "name", "args"}, ...]}
      - {"role": "tool_result", "results": [{"id", "name", "output"}, ...]}
    Each implementation converts to/from its own SDK's format internally.
    """

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse: ...

    async def parse(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        output_format: type[T],
    ) -> T: ...
