import logging
import time
from datetime import UTC, datetime
from typing import Any

from google.genai import types

from app.models import ContactPreference, Session, Stage, ToolEvent
from app.services.booking import BookingService
from app.services.crm import CrmService

logger = logging.getLogger(__name__)

_STAGE_VALUES = [stage.value for stage in Stage]
_PREFERENCE_VALUES = [preference.value for preference in ContactPreference]

# Recovery hints per Architecture.md §5: a failed tool tells the model what to do next rather
# than just that it failed — the model recovers far better with an instruction than a code.
_BOOKING_RECOVERY_HINTS = {
    "slot_unavailable": "Offer the customer the alternative slots returned, on the same day.",
    "invalid_date": "Ask the customer to pick a date between 1 and 30 days from today.",
    "invalid_phone": (
        "Ask the customer to share a valid 10-digit Indian mobile number starting with 6-9."
    ),
    "system_error": (
        "Apologise, do NOT claim the booking succeeded, and tell the customer the team will "
        "confirm within one business day."
    ),
}

# Five tools (Architecture.md §5), declared per rules.md A5: types.Tool(function_declarations=
# [...]), each with an explicit `required` list. NOTE: the SDK's local Schema type also accepts
# `additional_properties`, but the live Gemini API rejects it on tool parameter schemas with
# "Unknown name additional_properties ... Cannot find field" (400 INVALID_ARGUMENT) — caught by
# a live call, not by inspection. There is no additionalProperties:false equivalent for Gemini
# function-calling; `required` is the only closed-schema guard available (rules.md A5).
TOOLS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="update_lead_profile",
            description=(
                "Record or update any lead details the customer has revealed, even partially. "
                "Call this as soon as you learn something new — do not wait to have every field "
                "before calling it."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "name": types.Schema(type="STRING"),
                    "phone": types.Schema(
                        type="STRING", description="10-digit Indian mobile number"
                    ),
                    "budget_min_inr": types.Schema(type="INTEGER"),
                    "budget_max_inr": types.Schema(type="INTEGER"),
                    "configuration_interest": types.Schema(
                        type="ARRAY", items=types.Schema(type="STRING")
                    ),
                    "primary_configuration": types.Schema(type="STRING"),
                    "purpose": types.Schema(type="STRING"),
                    "timeline": types.Schema(type="STRING"),
                    "decision_authority": types.Schema(type="STRING"),
                    "location_fit": types.Schema(type="STRING"),
                    "language_preference": types.Schema(type="STRING"),
                    "notes": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
                    "stage": types.Schema(type="STRING", enum=_STAGE_VALUES),
                },
                required=[],
            ),
        ),
        types.FunctionDeclaration(
            name="check_slot_availability",
            description="Look up open site-visit windows for a given date.",
            parameters=types.Schema(
                type="OBJECT",
                properties={"date_str": types.Schema(type="STRING", description="YYYY-MM-DD")},
                required=["date_str"],
            ),
        ),
        types.FunctionDeclaration(
            name="book_site_visit",
            description="Attempt to book a site visit for the customer.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "date_str": types.Schema(type="STRING", description="YYYY-MM-DD"),
                    "slot": types.Schema(type="STRING", description="HH:MM, 24-hour"),
                    "phone": types.Schema(
                        type="STRING", description="10-digit Indian mobile number"
                    ),
                },
                required=["date_str", "slot", "phone"],
            ),
        ),
        types.FunctionDeclaration(
            name="escalate_to_human",
            description="Hand the conversation off to a human team member.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "reason": types.Schema(type="STRING"),
                    "summary": types.Schema(
                        type="STRING", description="One or two sentences of context for the human"
                    ),
                },
                required=["reason", "summary"],
            ),
        ),
        types.FunctionDeclaration(
            name="set_contact_preference",
            description="Record how, or whether, the customer wants to be contacted going forward.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "preference": types.Schema(type="STRING", enum=_PREFERENCE_VALUES),
                    "callback_time": types.Schema(
                        type="STRING", description="Only set when preference is callback_later"
                    ),
                },
                required=["preference"],
            ),
        ),
    ]
)


class ToolDispatcher:
    """Executes model-requested tool calls and applies their side effects to session state
    (Architecture.md §5). Every call is recorded as a ToolEvent, success or failure — a tool
    never raises out of dispatch and kills the turn (rules.md A8)."""

    def __init__(self, booking: BookingService, crm: CrmService) -> None:
        self._booking = booking
        self._crm = crm
        self._handlers = {
            "update_lead_profile": self._update_lead_profile,
            "check_slot_availability": self._check_slot_availability,
            "book_site_visit": self._book_site_visit,
            "escalate_to_human": self._escalate_to_human,
            "set_contact_preference": self._set_contact_preference,
        }

    def dispatch(self, name: str, args: dict[str, Any], session: Session) -> dict[str, Any]:
        start = time.monotonic()
        try:
            handler = self._handlers[name]
            output = handler(args, session)
        except Exception:
            logger.exception("tool dispatch failed name=%s", name)
            output = {
                "ok": False,
                "error_code": "tool_error",
                "message": "That action could not be completed.",
                "recovery_hint": (
                    "Apologise briefly and continue the conversation without retrying this "
                    "exact call."
                ),
            }
        latency_ms = int((time.monotonic() - start) * 1000)
        session.tool_events.append(
            ToolEvent(
                name=name,
                input=args,
                output=output,
                ok=bool(output.get("ok", True)),
                error_code=output.get("error_code"),
                latency_ms=latency_ms,
                at=datetime.now(UTC),
            )
        )
        return output

    def force_escalation(self, session: Session, *, reason: str) -> None:
        """System-forced escalation when the iteration cap is hit (Architecture.md §3.2.d) —
        not a model-invoked call, but recorded the same way so the tool trace stays honest."""
        self.dispatch(
            "escalate_to_human",
            {
                "reason": reason,
                "summary": "Agent could not resolve the request within the turn's iteration cap.",
            },
            session,
        )

    def _update_lead_profile(self, args: dict[str, Any], session: Session) -> dict[str, Any]:
        stage = args.get("stage")
        updates = {
            key: value for key, value in args.items() if key != "stage" and value is not None
        }
        session.lead = session.lead.model_copy(update=updates)
        if stage:
            session.stage = Stage(stage)
        return {"ok": True, "profile": session.lead.model_dump()}

    def _check_slot_availability(self, args: dict[str, Any], session: Session) -> dict[str, Any]:
        result = self._booking.check_availability(args["date_str"])
        return {"ok": True, **result}

    def _book_site_visit(self, args: dict[str, Any], session: Session) -> dict[str, Any]:
        result = self._booking.book(
            date_str=args["date_str"], slot=args["slot"], phone=args["phone"]
        )
        output = result.model_dump(exclude_none=True)
        if result.ok:
            session.stage = Stage.CONFIRMED
        else:
            output["recovery_hint"] = _BOOKING_RECOVERY_HINTS.get(
                result.error_code, "Apologise and offer to follow up."
            )
        return output

    def _escalate_to_human(self, args: dict[str, Any], session: Session) -> dict[str, Any]:
        ticket = self._crm.escalate(reason=args["reason"], summary=args["summary"])
        session.stage = Stage.ESCALATED
        return {"ok": True, **ticket}

    def _set_contact_preference(self, args: dict[str, Any], session: Session) -> dict[str, Any]:
        preference = ContactPreference(args["preference"])
        session.contact_preference = preference
        if preference == ContactPreference.DO_NOT_CONTACT:
            session.stage = Stage.DO_NOT_CONTACT
            self._crm.add_to_do_not_contact(session.lead.phone)
        elif preference == ContactPreference.CALLBACK_LATER:
            session.stage = Stage.CALLBACK_SCHEDULED
        return {"ok": True, "preference": preference.value}
