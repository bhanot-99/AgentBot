import logging
from datetime import UTC, datetime

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
        # No explicit caching in v1 (rules.md A15), so the composed prompt and the volatile
        # per-turn state are just one system_instruction string — there is no cache boundary
        # to keep them either side of.
        system = f"{self._system_prompt}\n\n---\n\n{_live_state_block(session.lead)}"

        for _ in range(MAX_ITERATIONS):
            response = await self._llm.complete(system=system, messages=session.messages)
            candidate = response.candidates[0]
            session.messages.append(
                {"role": "model", "parts": [part.model_dump() for part in candidate.content.parts]}
            )
            usage_metadata = response.usage_metadata
            usage = Usage(
                input_tokens=usage_metadata.prompt_token_count or 0,
                cache_read_input_tokens=usage_metadata.cached_content_token_count or 0,
                output_tokens=usage_metadata.candidates_token_count or 0,
            )

            has_tool_call = any(part.function_call for part in candidate.content.parts)
            if has_tool_call:
                # TODO(P3): dispatch every function_call part, append function_response
                # parts in one user Content, and loop. No tools are registered yet, so this
                # model turn has nothing to call and the honest response is a graceful
                # close, not a retry.
                logger.warning("model requested a tool call with no tool dispatch configured")
                return _GRACEFUL_CLOSE_TEXT, usage

            return (response.text or "").strip(), usage

        # Unreachable while no tools are registered (every call above returns immediately),
        # kept so the shape matches Architecture.md §3.2.d ahead of Phase 3's tool loop.
        return _GRACEFUL_CLOSE_TEXT, Usage(
            input_tokens=0, cache_read_input_tokens=0, output_tokens=0
        )


def _live_state_block(lead: LeadProfile) -> str:
    today = datetime.now(UTC).date().isoformat()
    known = lead.model_dump(exclude_none=True, exclude_defaults=True)
    lead_line = (
        ", ".join(f"{key}={value}" for key, value in known.items()) or "nothing recorded yet"
    )
    return f"Today's date: {today}\nCurrent lead profile: {lead_line}"
