from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Channel(StrEnum):
    CHAT = "chat"
    VOICE = "voice"


class Stage(StrEnum):
    GREETING = "GREETING"
    DISCOVERY = "DISCOVERY"
    QUALIFICATION = "QUALIFICATION"
    OBJECTION_HANDLING = "OBJECTION_HANDLING"
    BOOKING = "BOOKING"
    CONFIRMED = "CONFIRMED"
    CALLBACK_SCHEDULED = "CALLBACK_SCHEDULED"
    NOT_INTERESTED = "NOT_INTERESTED"
    ESCALATED = "ESCALATED"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"
    ENDED = "ENDED"


class ContactPreference(StrEnum):
    OK = "ok"
    CALLBACK_LATER = "callback_later"
    DO_NOT_CONTACT = "do_not_contact"


class LeadProfile(BaseModel):
    name: str | None = None
    phone: str | None = None
    budget_min_inr: int | None = None
    budget_max_inr: int | None = None
    configuration_interest: list[str] = Field(default_factory=list)
    primary_configuration: str | None = None
    purpose: str | None = None
    timeline: str | None = None
    decision_authority: str | None = None
    location_fit: str | None = None
    language_preference: str | None = None
    notes: list[str] = Field(default_factory=list)


class ToolEvent(BaseModel):
    name: str
    input: dict[str, Any]
    output: dict[str, Any]
    ok: bool
    error_code: str | None = None
    latency_ms: int
    at: datetime


class Usage(BaseModel):
    input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int


class BookingResult(BaseModel):
    ok: bool
    reference: str | None = None
    date: str | None = None
    slot: str | None = None
    error_code: str | None = None
    message: str | None = None
    alternatives: list[str] = Field(default_factory=list)


class Session(BaseModel):
    id: str
    channel: Channel
    created_at: datetime
    ended_at: datetime | None = None
    language_hint: str | None = None
    # Gemini Content blocks (role: "user"|"model", parts: [...]), stored verbatim and replayed
    # as-is (rules.md A9) — never rewritten into a bespoke format, the standard cause of
    # tool-loop corruption.
    messages: list[dict[str, Any]] = Field(default_factory=list)
    lead: LeadProfile = Field(default_factory=LeadProfile)
    tool_events: list[ToolEvent] = Field(default_factory=list)
    stage: Stage = Stage.GREETING
    contact_preference: ContactPreference = ContactPreference.OK
    analytics: dict[str, Any] | None = None


class SessionCreateRequest(BaseModel):
    channel: Channel


class SessionCreateResponse(BaseModel):
    session_id: str
    channel: Channel
    greeting: str
    started_at: datetime


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    session_id: str
    turn_id: int
    reply: str
    stage: Stage
    lead_profile: LeadProfile
    tool_events: list[ToolEvent]
    session_ended: bool
    usage: Usage


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorEnvelope(BaseModel):
    error: ErrorDetail
