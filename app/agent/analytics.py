import logging

from app.agent.prompt_builder import load_known_facts
from app.llm.base import LLMClient
from app.models import ConversationAnalytics, ExtractedAnalytics, Session, SiteVisitStatus
from app.services.scoring import score_lead

logger = logging.getLogger(__name__)

# One retry, then a partial record — never a fabricated one (phases.md P5 task 6).
_MAX_ATTEMPTS = 2

_SYSTEM_PROMPT_TEMPLATE = """You are analyzing a completed sales conversation transcript between \
Aarav, a sales agent for {project_name} ({developer}, {location}), and a customer.

Known price facts, for judging budget fit only: 2 BHK {price_2bhk}, 3 BHK {price_3bhk}.

Read the transcript and tool event log below and extract exactly the fields in the response
schema.

Rules:
- Never invent or guess a fact the conversation did not establish. Use null, "unknown", or an
  empty list for anything not stated — a missing fact is a real, legible answer.
- budget_fit is your judgement of whether the customer's stated budget realistically fits the
  known price range above — this is inference, not a fact restated from the transcript.
- summary is 2-3 sentences. next_best_action is one imperative sentence for the human who will
  follow up.
"""


def _build_system_prompt() -> str:
    facts = load_known_facts()
    return _SYSTEM_PROMPT_TEMPLATE.format(
        project_name=facts["project_name"],
        developer=facts["developer"],
        location=facts["location"],
        price_2bhk=facts["price_2bhk_starting"],
        price_3bhk=facts["price_3bhk_starting"],
    )


def _render_transcript(session: Session) -> str:
    lines = []
    for message in session.messages:
        if message["role"] == "user":
            lines.append(f"Customer: {message['text']}")
        elif message["role"] == "assistant" and message.get("text"):
            lines.append(f"Agent: {message['text']}")

    tool_log = (
        "\n".join(
            f"- {event.name}({event.input}) -> ok={event.ok} {event.output}"
            for event in session.tool_events
        )
        or "none"
    )
    transcript = "\n".join(lines) or "(no messages)"
    return f"TRANSCRIPT:\n{transcript}\n\nTOOL EVENT LOG:\n{tool_log}"


class AnalyticsExtractor:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def extract(self, session: Session) -> ConversationAnalytics:
        extracted = await self._extract_with_retry(_render_transcript(session))
        return _assemble_record(session, extracted)

    async def _extract_with_retry(self, transcript: str) -> ExtractedAnalytics:
        system = _build_system_prompt()
        last_error: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                return await self._llm.parse(
                    system=system,
                    messages=[{"role": "user", "text": transcript}],
                    output_format=ExtractedAnalytics,
                )
            except Exception as exc:
                last_error = exc
                logger.exception(
                    "analytics extraction failed attempt=%s/%s", attempt + 1, _MAX_ATTEMPTS
                )
        logger.error("analytics extraction exhausted retries: %s", last_error)
        return ExtractedAnalytics(summary="Analytics extraction failed")


def _assemble_record(session: Session, extracted: ExtractedAnalytics) -> ConversationAnalytics:
    """Merges the model's inferential read with deterministic ground truth from the tool-event
    log and session state (decision D6) — the step that makes the record trustworthy (rule C5).
    Anything the code knows for certain overwrites the model's guess; everything else (budget,
    timeline, sentiment, summary, ...) is genuinely inferential and stays the model's own read.
    """
    turn_count = sum(1 for message in session.messages if message["role"] == "assistant")
    duration_seconds = int((session.ended_at - session.created_at).total_seconds())
    site_visit_status, site_visit_date, site_visit_slot, booking_reference = _derive_booking_state(
        session
    )
    escalated_to_human, escalation_reason = _derive_escalation_state(session)

    record = ConversationAnalytics(
        session_id=session.id,
        channel=session.channel,
        started_at=session.created_at,
        ended_at=session.ended_at,
        turn_count=turn_count,
        duration_seconds=duration_seconds,
        site_visit_status=site_visit_status,
        site_visit_date=site_visit_date,
        site_visit_slot=site_visit_slot,
        booking_reference=booking_reference,
        contact_preference=session.contact_preference,
        escalated_to_human=escalated_to_human,
        escalation_reason=escalation_reason,
        **extracted.model_dump(),
    )
    record.interest_level, record.qualification_score = score_lead(record)
    return record


def _derive_booking_state(
    session: Session,
) -> tuple[SiteVisitStatus, str | None, str | None, str | None]:
    booking_attempts = [event for event in session.tool_events if event.name == "book_site_visit"]
    successful = next((event for event in booking_attempts if event.ok), None)
    if successful:
        return (
            SiteVisitStatus.BOOKED,
            successful.output.get("date"),
            successful.output.get("slot"),
            successful.output.get("reference"),
        )
    if booking_attempts:
        return SiteVisitStatus.ATTEMPTED_FAILED, None, None, None

    checked_availability = any(
        event.name == "check_slot_availability" for event in session.tool_events
    )
    if checked_availability:
        return SiteVisitStatus.DECLINED, None, None, None
    return SiteVisitStatus.NOT_DISCUSSED, None, None, None


def _derive_escalation_state(session: Session) -> tuple[bool, str | None]:
    escalations = [event for event in session.tool_events if event.name == "escalate_to_human"]
    if not escalations:
        return False, None
    return True, escalations[-1].input.get("reason")
