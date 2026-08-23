import logging
from datetime import UTC, datetime

from anthropic.types import TextBlockParam

from app.llm.base import LLMClient
from app.models import LeadProfile, Session, Usage

logger = logging.getLogger(__name__)

# The realistic maximum without tools is one call; once Phase 3 wires tool dispatch, a
# cooperative turn is update_lead_profile -> check_slot_availability -> book_site_visit ->
# final text. A fifth iteration means the model is stuck (Architecture.md §3.2).
MAX_ITERATIONS = 4

_GRACEFUL_CLOSE_TEXT = (
    "I'm having trouble continuing this conversation right now — let me have our team follow up "
    "with you directly. Thanks for your time!"
)


class Orchestrator:
    def __init__(self, llm: LLMClient, system_prompt: str) -> None:
        self._llm = llm
        self._system_prompt = system_prompt

    async def run_turn(self, session: Session) -> tuple[str, Usage]:
        """Runs the agent loop for one already-appended user turn (Architecture.md §3.2, step 5).

        The caller is responsible for appending the user's message to `session.messages`
        before calling this (step 4) and persisting the session afterward (step 7).
        """
        system: list[TextBlockParam] = [
            {"type": "text", "text": self._system_prompt, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": _live_state_block(session.lead)},
        ]

        for _ in range(MAX_ITERATIONS):
            response = await self._llm.complete(system=system, messages=session.messages)
            session.messages.append(
                {"role": "assistant", "content": [block.model_dump() for block in response.content]}
            )
            usage = Usage(
                input_tokens=response.usage.input_tokens,
                cache_read_input_tokens=response.usage.cache_read_input_tokens,
                output_tokens=response.usage.output_tokens,
            )

            if response.stop_reason == "tool_use":
                # TODO(P3): dispatch every tool_use block, append results in one user
                # message, and loop. No tools are registered yet, so this model turn has
                # nothing to call and the honest response is a graceful close, not a retry.
                logger.warning("stop_reason=tool_use with no tool dispatch configured")
                return _GRACEFUL_CLOSE_TEXT, usage

            return _extract_text(response.content), usage

        # Unreachable while no tools are registered (every call above returns immediately),
        # kept so the shape matches Architecture.md §3.2.d ahead of Phase 3's tool loop.
        return _GRACEFUL_CLOSE_TEXT, Usage(
            input_tokens=0, cache_read_input_tokens=0, output_tokens=0
        )


def _extract_text(content: list) -> str:
    parts = [block.text for block in content if block.type == "text"]
    return "\n".join(parts).strip()


def _live_state_block(lead: LeadProfile) -> str:
    today = datetime.now(UTC).date().isoformat()
    known = lead.model_dump(exclude_none=True, exclude_defaults=True)
    lead_line = (
        ", ".join(f"{key}={value}" for key, value in known.items()) or "nothing recorded yet"
    )
    return f"Today's date: {today}\nCurrent lead profile: {lead_line}"
