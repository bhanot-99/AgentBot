from typing import Any, Protocol, TypeVar

from google.genai.types import GenerateContentResponse, Tool
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    """The one seam between the agent and the model provider (Architecture.md §2)."""

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[Tool] | None = None,
    ) -> GenerateContentResponse: ...

    async def parse(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        output_format: type[T],
    ) -> T: ...
