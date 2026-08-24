from datetime import UTC, datetime

from app.models import (
    BudgetFit,
    Channel,
    ConfigurationChoice,
    ContactPreference,
    ConversationAnalytics,
    ConversationOutcome,
    InterestLevel,
    SiteVisitStatus,
    Timeline,
)
from app.services.scoring import score_lead

_NOW = datetime.now(UTC)


def _analytics(**overrides: object) -> ConversationAnalytics:
    defaults: dict[str, object] = {
        "session_id": "s1",
        "channel": Channel.CHAT,
        "started_at": _NOW,
        "ended_at": _NOW,
        "turn_count": 4,
        "duration_seconds": 120,
    }
    defaults.update(overrides)
    return ConversationAnalytics(**defaults)


def test_booked_site_visit_is_always_hot() -> None:
    analytics = _analytics(site_visit_status=SiteVisitStatus.BOOKED)
    level, _ = score_lead(analytics)
    assert level == InterestLevel.HOT


def test_budget_within_short_timeline_and_phone_is_hot() -> None:
    analytics = _analytics(
        budget_fit=BudgetFit.WITHIN,
        timeline=Timeline.ONE_TO_THREE_MONTHS,
        phone_captured=True,
    )
    level, _ = score_lead(analytics)
    assert level == InterestLevel.HOT


def test_budget_within_but_long_timeline_is_not_hot() -> None:
    analytics = _analytics(
        budget_fit=BudgetFit.WITHIN,
        timeline=Timeline.TWELVE_PLUS_MONTHS,
        phone_captured=True,
    )
    level, _ = score_lead(analytics)
    assert level != InterestLevel.HOT


def test_do_not_contact_is_always_cold() -> None:
    analytics = _analytics(
        contact_preference=ContactPreference.DO_NOT_CONTACT,
        budget_fit=BudgetFit.WITHIN,
        timeline=Timeline.IMMEDIATE,
        phone_captured=True,
    )
    level, _ = score_lead(analytics)
    assert level == InterestLevel.COLD


def test_budget_below_range_is_cold() -> None:
    analytics = _analytics(budget_fit=BudgetFit.BELOW)
    level, _ = score_lead(analytics)
    assert level == InterestLevel.COLD


def test_explicit_not_interested_outcome_is_cold() -> None:
    analytics = _analytics(conversation_outcome=ConversationOutcome.NOT_INTERESTED)
    level, _ = score_lead(analytics)
    assert level == InterestLevel.COLD


def test_callback_requested_is_warm() -> None:
    analytics = _analytics(contact_preference=ContactPreference.CALLBACK_LATER)
    level, _ = score_lead(analytics)
    assert level == InterestLevel.WARM


def test_configuration_known_and_phone_captured_without_budget_is_warm() -> None:
    analytics = _analytics(
        primary_configuration=ConfigurationChoice.TWO_BHK,
        phone_captured=True,
    )
    level, _ = score_lead(analytics)
    assert level == InterestLevel.WARM


def test_minimal_engagement_defaults_to_cold() -> None:
    analytics = _analytics()
    level, _ = score_lead(analytics)
    assert level == InterestLevel.COLD


def test_score_is_clamped_between_zero_and_hundred() -> None:
    hot = _analytics(
        site_visit_status=SiteVisitStatus.BOOKED,
        budget_fit=BudgetFit.WITHIN,
        timeline=Timeline.IMMEDIATE,
        phone_captured=True,
        primary_configuration=ConfigurationChoice.TWO_BHK,
        decision_authority="sole",
    )
    _, score = score_lead(hot)
    assert 0 <= score <= 100

    cold = _analytics(
        budget_fit=BudgetFit.BELOW,
        contact_preference=ContactPreference.DO_NOT_CONTACT,
        conversation_outcome=ConversationOutcome.NOT_INTERESTED,
    )
    _, score = score_lead(cold)
    assert score == 0


def test_hot_score_exceeds_cold_score() -> None:
    hot = _analytics(
        site_visit_status=SiteVisitStatus.BOOKED,
        budget_fit=BudgetFit.WITHIN,
        timeline=Timeline.IMMEDIATE,
        phone_captured=True,
    )
    cold = _analytics(budget_fit=BudgetFit.BELOW)

    _, hot_score = score_lead(hot)
    _, cold_score = score_lead(cold)
    assert hot_score > cold_score
