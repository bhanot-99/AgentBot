import logging
from datetime import UTC, datetime

from app.agent.tools import TOOL_SPECS, ToolDispatcher
from app.llm.base import LLMClient
from app.models import LeadProfile, Session, Usage

logger = logging.getLogger(__name__)

# The realistic maximum turn is update_lead_profile -> check_slot_availability ->
# book_site_visit -> final text. A fifth iteration means the model is stuck
# (Architecture.md §3.2).
MAX_ITERATIONS = 4

_GRACEFUL_CLOSE_TEXT = (
    "I'm having trouble continuing this conversation right now — let me have our team follow up "
    "with you directly. Thanks for your time!"
)

_ZERO_USAGE = Usage(input_tokens=0, cache_read_input_tokens=0, output_tokens=0)


class Orchestrator:
    def __init__(self, llm: LLMClient, system_prompt: str, dispatcher: ToolDispatcher) -> None:
        self._llm = llm
        self._system_prompt = system_prompt
        self._dispatcher = dispatcher

    async def run_turn(self, session: Session) -> tuple[str, Usage]:
        """Runs the agent loop for one already-appended user turn (Architecture.md §3.2, step 5).

        The caller is responsible for appending the user's message to `session.messages`
        before calling this (step 4) and persisting the session afterward (step 7).

        `session.messages` is the provider-neutral shape (app/llm/base.py) — this method never
        touches a Gemini or Anthropic wire type directly; that translation lives entirely inside
        whichever LLMClient is injected.
        """
        # No explicit caching in v1 (rules.md A15), so the composed prompt and the volatile
        # per-turn state are just one system_instruction string — there is no cache boundary
        # to keep them either side of.
        system = f"{self._system_prompt}\n\n---\n\n{_live_state_block(session.lead)}"

        for _ in range(MAX_ITERATIONS):
            response = await self._llm.complete(
                system=system, messages=session.messages, tools=TOOL_SPECS
            )
            session.messages.append(
                {
                    "role": "assistant",
                    "text": response.text,
                    "tool_calls": [call.model_dump() for call in response.tool_calls],
                }
            )

            if not response.tool_calls:
                return response.text or "", response.usage

            # All results for this turn go back in a single following tool_result message
            # (rules.md A7) — never split across messages, regardless of provider.
            results = [
                {
                    "id": call.id,
                    "name": call.name,
                    "output": self._dispatcher.dispatch(call.name, call.args, session),
                }
                for call in response.tool_calls
            ]
            session.messages.append({"role": "tool_result", "results": results})

        # Iteration cap reached: the model is stuck. Force a graceful close and flag the
        # session for escalation rather than looping forever (Architecture.md §3.2.d).
        self._dispatcher.force_escalation(session, reason="iteration_cap_reached")
        return _GRACEFUL_CLOSE_TEXT, _ZERO_USAGE


def _live_state_block(lead: LeadProfile) -> str:
    today = datetime.now(UTC).date().isoformat()
    known = lead.model_dump(exclude_none=True, exclude_defaults=True)
    lead_line = (
        ", ".join(f"{key}={value}" for key, value in known.items()) or "nothing recorded yet"
    )
    return f"Today's date: {today}\nCurrent lead profile: {lead_line}"
