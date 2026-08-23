from typing import Any, Protocol, TypeVar

from anthropic.types import Message, TextBlockParam
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    """The one seam between the agent and the model provider (Architecture.md §2)."""

    async def complete(
        self,
        *,
        system: list[TextBlockParam],
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> Message: ...

    async def parse(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        output_format: type[T],
    ) -> T: ...
