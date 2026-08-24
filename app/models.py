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


class Language(StrEnum):
    ENGLISH = "english"
    HINDI = "hindi"
    HINGLISH = "hinglish"


class BudgetFit(StrEnum):
    WITHIN = "within"
    BELOW = "below"
    ABOVE = "above"
    UNKNOWN = "unknown"


class ConfigurationChoice(StrEnum):
    TWO_BHK = "2BHK"
    THREE_BHK = "3BHK"
    UNDECIDED = "undecided"
    UNKNOWN = "unknown"


class Purpose(StrEnum):
    END_USE = "end_use"
    INVESTMENT = "investment"
    UNKNOWN = "unknown"


class Timeline(StrEnum):
    IMMEDIATE = "immediate"
    ONE_TO_THREE_MONTHS = "1_3_months"
    THREE_TO_SIX_MONTHS = "3_6_months"
    SIX_TO_TWELVE_MONTHS = "6_12_months"
    TWELVE_PLUS_MONTHS = "12_plus"
    UNKNOWN = "unknown"


class DecisionAuthority(StrEnum):
    SOLE = "sole"
    JOINT = "joint"
    UNKNOWN = "unknown"


class LocationFitAnswer(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class InterestLevel(StrEnum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class Objection(StrEnum):
    """The twelve objections in prompts/modules/40_objections.md, same order."""

    PRICE = "price"
    LOCATION = "location"
    BUILDER_TRUST = "builder_trust"
    POSSESSION_DELAY = "possession_delay"
    MARKET_TIMING = "market_timing"
    LOAN_WORRIES = "loan_worries"
    PREFERS_RESALE = "prefers_resale"
    COMPETITOR_COMPARISON = "competitor_comparison"
    FAMILY_APPROVAL = "family_approval"
    NO_TIME = "no_time"
    ALREADY_BOUGHT = "already_bought"
    NOT_LOOKING = "not_looking"


class SiteVisitStatus(StrEnum):
    BOOKED = "booked"
    ATTEMPTED_FAILED = "attempted_failed"
    DECLINED = "declined"
    NOT_DISCUSSED = "not_discussed"


class ConversationOutcome(StrEnum):
    VISIT_BOOKED = "visit_booked"
    FOLLOW_UP_SCHEDULED = "follow_up_scheduled"
    NOT_INTERESTED = "not_interested"
    DO_NOT_CONTACT = "do_not_contact"
    ESCALATED = "escalated"
    ABANDONED = "abandoned"


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


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


class ExtractedAnalytics(BaseModel):
    """The subset of ConversationAnalytics the model is asked to infer from the transcript
    (PRD §7) — deliberately excludes every field the code already knows for certain (session
    identity/timing, booking outcome, contact preference, escalation, the computed score).
    Asking the model to guess those too, only to discard the guess, wastes its attention on
    fields it structurally cannot know (rules.md D6's rationale, applied at the schema level
    rather than only at the overwrite step)."""

    languages_used: list[Language] = Field(default_factory=list)
    primary_language: Language | None = None

    lead_name: str | None = None
    lead_phone: str | None = None
    phone_captured: bool = False

    budget_stated: bool = False
    budget_min_inr: int | None = None
    budget_max_inr: int | None = None
    budget_fit: BudgetFit = BudgetFit.UNKNOWN

    configuration_interest: list[str] = Field(default_factory=list)
    primary_configuration: ConfigurationChoice = ConfigurationChoice.UNKNOWN
    purpose: Purpose = Purpose.UNKNOWN
    timeline: Timeline = Timeline.UNKNOWN
    decision_authority: DecisionAuthority = DecisionAuthority.UNKNOWN
    location_fit: LocationFitAnswer = LocationFitAnswer.UNKNOWN

    objections_raised: list[Objection] = Field(default_factory=list)
    unknown_questions_asked: list[str] = Field(default_factory=list)

    follow_up_required: bool = False
    follow_up_at: datetime | None = None
    follow_up_reason: str | None = None

    conversation_outcome: ConversationOutcome = ConversationOutcome.ABANDONED
    sentiment: Sentiment = Sentiment.NEUTRAL
    summary: str = ""
    next_best_action: str = ""


class ConversationAnalytics(BaseModel):
    """The full record (PRD §7). Fields below are deterministically overwritten from the
    tool-event log and session state after extraction (decision D6) — never trusted from the
    model, because the model infers intent well and reports system state badly: session_id,
    channel, started_at, ended_at, turn_count, duration_seconds, site_visit_status,
    site_visit_date, site_visit_slot, booking_reference, contact_preference,
    escalated_to_human, escalation_reason. Everything else comes from ExtractedAnalytics."""

    session_id: str
    channel: Channel
    started_at: datetime
    ended_at: datetime
    turn_count: int
    duration_seconds: int

    languages_used: list[Language] = Field(default_factory=list)
    primary_language: Language | None = None

    lead_name: str | None = None
    lead_phone: str | None = None
    phone_captured: bool = False

    budget_stated: bool = False
    budget_min_inr: int | None = None
    budget_max_inr: int | None = None
    budget_fit: BudgetFit = BudgetFit.UNKNOWN

    configuration_interest: list[str] = Field(default_factory=list)
    primary_configuration: ConfigurationChoice = ConfigurationChoice.UNKNOWN
    purpose: Purpose = Purpose.UNKNOWN
    timeline: Timeline = Timeline.UNKNOWN
    decision_authority: DecisionAuthority = DecisionAuthority.UNKNOWN
    location_fit: LocationFitAnswer = LocationFitAnswer.UNKNOWN

    interest_level: InterestLevel = InterestLevel.COLD
    qualification_score: int = 0
    objections_raised: list[Objection] = Field(default_factory=list)
    unknown_questions_asked: list[str] = Field(default_factory=list)

    site_visit_status: SiteVisitStatus = SiteVisitStatus.NOT_DISCUSSED
    site_visit_date: str | None = None
    site_visit_slot: str | None = None
    booking_reference: str | None = None

    contact_preference: ContactPreference = ContactPreference.OK
    follow_up_required: bool = False
    follow_up_at: datetime | None = None
    follow_up_reason: str | None = None

    escalated_to_human: bool = False
    escalation_reason: str | None = None

    conversation_outcome: ConversationOutcome = ConversationOutcome.ABANDONED
    sentiment: Sentiment = Sentiment.NEUTRAL
    summary: str = ""
    next_best_action: str = ""


class Session(BaseModel):
    id: str
    channel: Channel
    created_at: datetime
    ended_at: datetime | None = None
    language_hint: str | None = None
    # Provider-neutral shape (app/llm/base.py), not a Gemini or Anthropic wire type — see D14
    # in memory.md. Stored and replayed as-is; never rewritten into a bespoke format, the
    # standard cause of tool-loop corruption.
    messages: list[dict[str, Any]] = Field(default_factory=list)
    lead: LeadProfile = Field(default_factory=LeadProfile)
    tool_events: list[ToolEvent] = Field(default_factory=list)
    stage: Stage = Stage.GREETING
    contact_preference: ContactPreference = ContactPreference.OK
    analytics: ConversationAnalytics | None = None


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
