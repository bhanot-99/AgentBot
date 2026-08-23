from datetime import UTC, datetime, timedelta

import pytest
from google.genai import types

from app.agent.orchestrator import Orchestrator
from app.agent.tools import ToolDispatcher
from app.models import Channel, Session, Stage
from app.services.booking import BookingService
from app.services.crm import CrmService
from tests.fakes import FakeLLMClient, text_response

_TODAY = datetime.now(UTC).date()
_VALID_DATE = (_TODAY + timedelta(days=2)).isoformat()


def _tool_call_response(
    *calls: tuple[str, dict], finish_reason: str = "STOP"
) -> types.GenerateContentResponse:
    parts = [
        types.Part(function_call=types.FunctionCall(id=f"call_{i}", name=name, args=args))
        for i, (name, args) in enumerate(calls)
    ]
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=parts), finish_reason=finish_reason
            )
        ],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=100, candidates_token_count=20, cached_content_token_count=0
        ),
    )


def _session() -> Session:
    return Session(id="s1", channel=Channel.CHAT, created_at=datetime.now(UTC))


def _dispatcher(force_failure: str = "") -> ToolDispatcher:
    return ToolDispatcher(BookingService(force_failure=force_failure), CrmService())


@pytest.mark.asyncio
async def test_no_tool_call_returns_text_directly() -> None:
    llm = FakeLLMClient([text_response("Hi there!")])
    session = _session()

    reply, usage = await Orchestrator(llm, "SYSTEM", _dispatcher()).run_turn(session)

    assert reply == "Hi there!"
    assert usage.input_tokens == 100
    assert session.tool_events == []


@pytest.mark.asyncio
async def test_single_tool_call_dispatches_and_loops() -> None:
    llm = FakeLLMClient(
        [
            _tool_call_response(("update_lead_profile", {"name": "Rohit"})),
            text_response("Got it, Rohit!"),
        ]
    )
    session = _session()

    reply, _ = await Orchestrator(llm, "SYSTEM", _dispatcher()).run_turn(session)

    assert reply == "Got it, Rohit!"
    assert session.lead.name == "Rohit"
    assert len(session.tool_events) == 1
    assert session.tool_events[0].name == "update_lead_profile"
    assert session.tool_events[0].ok is True
    # All results for one model turn go back in a single following user-role message
    # (rules.md A7), never split across messages. FakeLLMClient.calls holds a live reference
    # to session.messages, so it reflects the final state — check session.messages by index
    # for the state as of that point in the loop instead.
    tool_result_message = session.messages[1]
    assert tool_result_message["role"] == "user"
    assert "function_response" in tool_result_message["parts"][0]


@pytest.mark.asyncio
async def test_parallel_tool_calls_go_back_in_one_user_message() -> None:
    llm = FakeLLMClient(
        [
            _tool_call_response(
                ("update_lead_profile", {"name": "Priya"}),
                ("check_slot_availability", {"date_str": _VALID_DATE}),
            ),
            text_response("Thanks!"),
        ]
    )
    session = _session()

    await Orchestrator(llm, "SYSTEM", _dispatcher()).run_turn(session)

    assert len(session.tool_events) == 2
    tool_result_message = session.messages[1]
    assert tool_result_message["role"] == "user"
    assert len(tool_result_message["parts"]) == 2


@pytest.mark.asyncio
async def test_iteration_cap_forces_graceful_close_and_escalates() -> None:
    # The model never stops asking for a tool — every scripted turn is another tool call.
    script = [
        _tool_call_response(("check_slot_availability", {"date_str": _VALID_DATE}))
        for _ in range(4)
    ]
    llm = FakeLLMClient(script)
    session = _session()

    reply, _ = await Orchestrator(llm, "SYSTEM", _dispatcher()).run_turn(session)

    assert "team" in reply.lower()
    assert session.stage == Stage.ESCALATED
    assert any(event.name == "escalate_to_human" for event in session.tool_events)


@pytest.mark.asyncio
async def test_booking_failure_records_error_code_and_recovery_hint_never_confirms() -> None:
    llm = FakeLLMClient(
        [
            _tool_call_response(
                (
                    "book_site_visit",
                    {"date_str": _VALID_DATE, "slot": "10:00", "phone": "9876543210"},
                )
            ),
            text_response("Let's find another time."),
        ]
    )
    session = _session()
    dispatcher = _dispatcher(force_failure="slot_unavailable")

    await Orchestrator(llm, "SYSTEM", dispatcher).run_turn(session)

    event = session.tool_events[0]
    assert event.ok is False
    assert event.error_code == "slot_unavailable"
    assert "recovery_hint" in event.output
    assert session.stage != Stage.CONFIRMED


@pytest.mark.asyncio
async def test_dnc_tool_call_sets_stage_and_registers_phone() -> None:
    llm = FakeLLMClient(
        [
            _tool_call_response(("set_contact_preference", {"preference": "do_not_contact"})),
            text_response("Understood."),
        ]
    )
    session = _session()
    session.lead.phone = "9876543210"
    crm = CrmService()
    dispatcher = ToolDispatcher(BookingService(), crm)

    await Orchestrator(llm, "SYSTEM", dispatcher).run_turn(session)

    assert session.stage == Stage.DO_NOT_CONTACT
    assert crm.is_on_do_not_contact("9876543210") is True


@pytest.mark.asyncio
async def test_unknown_tool_call_does_not_crash_the_turn() -> None:
    llm = FakeLLMClient(
        [
            _tool_call_response(("not_a_real_tool", {})),
            text_response("Sorry about that."),
        ]
    )
    session = _session()

    reply, _ = await Orchestrator(llm, "SYSTEM", _dispatcher()).run_turn(session)

    assert reply == "Sorry about that."
    assert session.tool_events[0].ok is False
