import logging
from datetime import UTC, datetime

from google.genai import types

from app.agent.tools import TOOLS, ToolDispatcher
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
        """
        # No explicit caching in v1 (rules.md A15), so the composed prompt and the volatile
        # per-turn state are just one system_instruction string — there is no cache boundary
        # to keep them either side of.
        system = f"{self._system_prompt}\n\n---\n\n{_live_state_block(session.lead)}"
        usage = _ZERO_USAGE

        for _ in range(MAX_ITERATIONS):
            response = await self._llm.complete(
                system=system, messages=session.messages, tools=[TOOLS]
            )
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

            # A tool call is a function_call Part, not a distinct finish_reason (rules.md A6).
            calls = [part.function_call for part in candidate.content.parts if part.function_call]
            if not calls:
                return (response.text or "").strip(), usage

            # All results for this turn go back as function_response Parts inside a single
            # following user-role Content (rules.md A7) — never split across messages.
            response_parts = []
            for call in calls:
                output = self._dispatcher.dispatch(call.name, dict(call.args or {}), session)
                function_response = types.FunctionResponse(
                    id=call.id, name=call.name, response=output
                )
                response_parts.append(types.Part(function_response=function_response).model_dump())
            session.messages.append({"role": "user", "parts": response_parts})

        # Iteration cap reached: the model is stuck. Force a graceful close and flag the
        # session for escalation rather than looping forever (Architecture.md §3.2.d).
        self._dispatcher.force_escalation(session, reason="iteration_cap_reached")
        return _GRACEFUL_CLOSE_TEXT, usage


def _live_state_block(lead: LeadProfile) -> str:
    today = datetime.now(UTC).date().isoformat()
    known = lead.model_dump(exclude_none=True, exclude_defaults=True)
    lead_line = (
        ", ".join(f"{key}={value}" for key, value in known.items()) or "nothing recorded yet"
    )
    return f"Today's date: {today}\nCurrent lead profile: {lead_line}"
