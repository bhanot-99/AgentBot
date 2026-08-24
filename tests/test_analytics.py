from datetime import UTC, datetime, timedelta

import pytest

from app.agent.analytics import AnalyticsExtractor
from app.models import (
    BudgetFit,
    Channel,
    ContactPreference,
    ExtractedAnalytics,
    Session,
    SiteVisitStatus,
    ToolEvent,
)
from tests.fakes import FakeLLMClient

_NOW = datetime.now(UTC)


def _session(**overrides: object) -> Session:
    defaults: dict[str, object] = {
        "id": "s1",
        "channel": Channel.CHAT,
        "created_at": _NOW,
        "ended_at": _NOW + timedelta(minutes=5),
    }
    defaults.update(overrides)
    return Session(**defaults)


def _tool_event(
    name: str, *, ok: bool, input: dict | None = None, output: dict | None = None
) -> ToolEvent:
    return ToolEvent(
        name=name, input=input or {}, output=output or {"ok": ok}, ok=ok, latency_ms=1, at=_NOW
    )


@pytest.mark.asyncio
async def test_booked_session_gets_deterministic_site_visit_fields() -> None:
    session = _session()
    session.messages = [
        {"role": "assistant", "text": "Hi", "tool_calls": []},
        {"role": "user", "text": "book me a visit"},
        {"role": "assistant", "text": "Booked!", "tool_calls": []},
    ]
    session.tool_events = [
        _tool_event(
            "book_site_visit",
            ok=True,
            output={"ok": True, "date": "2026-09-01", "slot": "10:00", "reference": "NS-ABC123"},
        )
    ]
    extracted = ExtractedAnalytics(budget_fit=BudgetFit.WITHIN, summary="Cooperative lead.")
    llm = FakeLLMClient(parse_script=[extracted])

    record = await AnalyticsExtractor(llm).extract(session)

    # These come from the tool-event log, never the model (decision D6) — verified even though
    # the FakeLLMClient's script didn't set them, proving the overwrite actually happened.
    assert record.site_visit_status == SiteVisitStatus.BOOKED
    assert record.booking_reference == "NS-ABC123"
    assert record.site_visit_date == "2026-09-01"
    assert record.site_visit_slot == "10:00"
    assert record.turn_count == 2  # two assistant messages
    assert record.duration_seconds == 300
    assert record.budget_fit == BudgetFit.WITHIN  # passed through from the model's extraction


@pytest.mark.asyncio
async def test_failed_booking_attempt_is_attempted_failed_not_declined() -> None:
    session = _session()
    session.tool_events = [_tool_event("book_site_visit", ok=False)]
    llm = FakeLLMClient(parse_script=[ExtractedAnalytics()])

    record = await AnalyticsExtractor(llm).extract(session)

    assert record.site_visit_status == SiteVisitStatus.ATTEMPTED_FAILED
    assert record.booking_reference is None


@pytest.mark.asyncio
async def test_checked_availability_without_booking_is_declined() -> None:
    session = _session()
    session.tool_events = [_tool_event("check_slot_availability", ok=True)]
    llm = FakeLLMClient(parse_script=[ExtractedAnalytics()])

    record = await AnalyticsExtractor(llm).extract(session)

    assert record.site_visit_status == SiteVisitStatus.DECLINED


@pytest.mark.asyncio
async def test_no_booking_related_tool_calls_is_not_discussed() -> None:
    session = _session()
    llm = FakeLLMClient(parse_script=[ExtractedAnalytics()])

    record = await AnalyticsExtractor(llm).extract(session)

    assert record.site_visit_status == SiteVisitStatus.NOT_DISCUSSED


@pytest.mark.asyncio
async def test_escalation_reason_comes_from_tool_input_not_the_model() -> None:
    session = _session()
    session.tool_events = [
        _tool_event("escalate_to_human", ok=True, input={"reason": "angry customer"})
    ]
    llm = FakeLLMClient(parse_script=[ExtractedAnalytics(summary="model would say something else")])

    record = await AnalyticsExtractor(llm).extract(session)

    assert record.escalated_to_human is True
    assert record.escalation_reason == "angry customer"


@pytest.mark.asyncio
async def test_contact_preference_comes_from_session_not_the_model() -> None:
    session = _session()
    session.contact_preference = ContactPreference.DO_NOT_CONTACT
    llm = FakeLLMClient(parse_script=[ExtractedAnalytics()])

    record = await AnalyticsExtractor(llm).extract(session)

    assert record.contact_preference == ContactPreference.DO_NOT_CONTACT


@pytest.mark.asyncio
async def test_hostile_two_turn_conversation_yields_unknowns_not_invented_facts() -> None:
    session = _session()
    session.messages = [{"role": "assistant", "text": "Hi", "tool_calls": []}]
    # The model correctly reports nothing was established — defaults already encode this.
    llm = FakeLLMClient(parse_script=[ExtractedAnalytics()])

    record = await AnalyticsExtractor(llm).extract(session)

    assert record.budget_min_inr is None
    assert record.budget_max_inr is None
    assert record.lead_name is None
    assert record.budget_fit == BudgetFit.UNKNOWN


@pytest.mark.asyncio
async def test_extraction_failure_retries_once_then_returns_partial_record() -> None:
    session = _session()
    llm = FakeLLMClient(parse_script=[RuntimeError("boom"), RuntimeError("boom again")])

    record = await AnalyticsExtractor(llm).extract(session)

    assert record.summary == "Analytics extraction failed"
    assert len(llm.parse_calls) == 2  # one retry, per phases.md P5 task 6
    # Deterministic fields are still correct even on total extraction failure.
    assert record.turn_count == 0
    assert record.site_visit_status == SiteVisitStatus.NOT_DISCUSSED


@pytest.mark.asyncio
async def test_extraction_succeeds_on_second_attempt() -> None:
    session = _session()
    llm = FakeLLMClient(parse_script=[RuntimeError("transient"), ExtractedAnalytics(summary="ok")])

    record = await AnalyticsExtractor(llm).extract(session)

    assert record.summary == "ok"
    assert len(llm.parse_calls) == 2
