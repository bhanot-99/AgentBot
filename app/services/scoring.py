from app.models import (
    BudgetFit,
    ConfigurationChoice,
    ContactPreference,
    ConversationAnalytics,
    ConversationOutcome,
    InterestLevel,
    SiteVisitStatus,
    Timeline,
)

_SHORT_TIMELINES = {Timeline.IMMEDIATE, Timeline.ONE_TO_THREE_MONTHS}
_COLD_OUTCOMES = {ConversationOutcome.NOT_INTERESTED, ConversationOutcome.DO_NOT_CONTACT}

# Points reflect how much of BANTL is actually confirmed, not the model's own read of interest —
# the qualification_score exists to let a sales manager scan and sort leads at a glance
# (design.md §5.8), independent of the categorical hot/warm/cold bucket below.
_SCORE_WEIGHTS = {
    "site_visit_booked": 40,
    "budget_within": 25,
    "short_timeline": 15,
    "phone_captured": 10,
    "configuration_known": 10,
    "decision_authority_known": 5,
    "budget_below": -30,
    "do_not_contact": -40,
    "cold_outcome": -25,
    "callback_requested": 5,
}


def score_lead(analytics: ConversationAnalytics) -> tuple[InterestLevel, int]:
    """Rule-based hot/warm/cold classification plus a 0-100 qualification score (PRD §7).

    The two are computed independently and deliberately: the categorical bucket follows the
    brief's literal rules so it is auditable sentence-by-sentence against PRD §7, while the
    numeric score is a separate BANTL-completeness weighting used for sorting leads within a
    bucket, not for deriving it.
    """
    return _classify(analytics), _compute_score(analytics)


def _classify(analytics: ConversationAnalytics) -> InterestLevel:
    # Hard cold overrides come first and win regardless of any other signal — a DNC request in
    # particular must never be out-ranked by an otherwise-qualified budget/timeline/phone combo
    # stated earlier in the same conversation (rule A8-adjacent: trust-and-safety beats scoring).
    if (
        analytics.contact_preference == ContactPreference.DO_NOT_CONTACT
        or analytics.budget_fit == BudgetFit.BELOW
        or analytics.conversation_outcome in _COLD_OUTCOMES
    ):
        return InterestLevel.COLD

    if analytics.site_visit_status == SiteVisitStatus.BOOKED:
        return InterestLevel.HOT
    if (
        analytics.budget_fit == BudgetFit.WITHIN
        and analytics.timeline in _SHORT_TIMELINES
        and analytics.phone_captured
    ):
        return InterestLevel.HOT

    configuration_known = analytics.primary_configuration not in (
        ConfigurationChoice.UNKNOWN,
        ConfigurationChoice.UNDECIDED,
    )
    if analytics.contact_preference == ContactPreference.CALLBACK_LATER or (
        configuration_known and analytics.phone_captured
    ):
        return InterestLevel.WARM

    return InterestLevel.COLD


def _compute_score(analytics: ConversationAnalytics) -> int:
    score = 0
    if analytics.site_visit_status == SiteVisitStatus.BOOKED:
        score += _SCORE_WEIGHTS["site_visit_booked"]
    if analytics.budget_fit == BudgetFit.WITHIN:
        score += _SCORE_WEIGHTS["budget_within"]
    if analytics.timeline in _SHORT_TIMELINES:
        score += _SCORE_WEIGHTS["short_timeline"]
    if analytics.phone_captured:
        score += _SCORE_WEIGHTS["phone_captured"]
    if analytics.primary_configuration not in (
        ConfigurationChoice.UNKNOWN,
        ConfigurationChoice.UNDECIDED,
    ):
        score += _SCORE_WEIGHTS["configuration_known"]
    if analytics.decision_authority.value != "unknown":
        score += _SCORE_WEIGHTS["decision_authority_known"]
    if analytics.budget_fit == BudgetFit.BELOW:
        score += _SCORE_WEIGHTS["budget_below"]
    if analytics.contact_preference == ContactPreference.DO_NOT_CONTACT:
        score += _SCORE_WEIGHTS["do_not_contact"]
    if analytics.conversation_outcome in _COLD_OUTCOMES:
        score += _SCORE_WEIGHTS["cold_outcome"]
    if analytics.contact_preference == ContactPreference.CALLBACK_LATER:
        score += _SCORE_WEIGHTS["callback_requested"]
    return max(0, min(100, score))
