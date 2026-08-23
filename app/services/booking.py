import re
import uuid
from datetime import UTC, date, datetime, time, timedelta

from app.models import BookingResult

_SLOT_START_HOUR = 10
_SLOT_END_HOUR = 18
_SLOT_DURATION_MINUTES = 90
_MIN_DAYS_AHEAD = 1
_MAX_DAYS_AHEAD = 30

_INDIAN_MOBILE_RE = re.compile(r"^[6-9]\d{9}$")

_FAILURE_MODES = {"slot_unavailable", "invalid_date", "invalid_phone", "system_error"}

_INVALID_DATE_MESSAGE = (
    f"Choose a date between {_MIN_DAYS_AHEAD} and {_MAX_DAYS_AHEAD} days from today."
)
_INVALID_PHONE_MESSAGE = "Enter a 10-digit Indian mobile number starting with 6-9."


class BookingService:
    """Simulated site-visit booking — there is no real inventory system (D2). Failure modes
    are deterministic so a demo can trigger one on cue (D10), via FORCE_BOOKING_FAILURE."""

    def __init__(self, force_failure: str = "") -> None:
        if force_failure and force_failure not in _FAILURE_MODES:
            raise ValueError(f"Unknown FORCE_BOOKING_FAILURE value: {force_failure!r}")
        self._force_failure = force_failure

    def slots_for_date(self, target_date: date) -> list[str]:
        slots = []
        cursor = datetime.combine(target_date, time(_SLOT_START_HOUR))
        end = datetime.combine(target_date, time(_SLOT_END_HOUR))
        while cursor + timedelta(minutes=_SLOT_DURATION_MINUTES) <= end:
            slots.append(cursor.strftime("%H:%M"))
            cursor += timedelta(minutes=_SLOT_DURATION_MINUTES)
        return slots

    def is_date_in_window(self, target_date: date, *, today: date) -> bool:
        delta_days = (target_date - today).days
        return _MIN_DAYS_AHEAD <= delta_days <= _MAX_DAYS_AHEAD

    def is_valid_indian_mobile(self, phone: str) -> bool:
        return bool(_INDIAN_MOBILE_RE.match(phone))

    def check_availability(self, date_str: str, *, today: date | None = None) -> dict:
        today = today or datetime.now(UTC).date()
        target_date = _parse_date(date_str)

        if target_date is None or not self.is_date_in_window(target_date, today=today):
            nearest = [
                (today + timedelta(days=_MIN_DAYS_AHEAD)).isoformat(),
                (today + timedelta(days=_MIN_DAYS_AHEAD + 1)).isoformat(),
            ]
            return {"available": False, "slots": [], "nearest_alternatives": nearest}

        return {
            "available": True,
            "slots": self.slots_for_date(target_date),
            "nearest_alternatives": [],
        }

    def book(
        self, *, date_str: str, slot: str, phone: str, today: date | None = None
    ) -> BookingResult:
        today = today or datetime.now(UTC).date()

        if self._force_failure:
            return self._forced_failure(date_str, slot)

        if not self.is_valid_indian_mobile(phone):
            return BookingResult(
                ok=False, error_code="invalid_phone", message=_INVALID_PHONE_MESSAGE
            )

        target_date = _parse_date(date_str)
        if target_date is None or not self.is_date_in_window(target_date, today=today):
            return BookingResult(ok=False, error_code="invalid_date", message=_INVALID_DATE_MESSAGE)

        day_slots = self.slots_for_date(target_date)
        if slot not in day_slots:
            return BookingResult(
                ok=False,
                error_code="slot_unavailable",
                message="That slot is not available.",
                alternatives=[s for s in day_slots if s != slot][:2],
            )

        return BookingResult(
            ok=True, reference=f"NS-{uuid.uuid4().hex[:8].upper()}", date=date_str, slot=slot
        )

    def _forced_failure(self, date_str: str, slot: str) -> BookingResult:
        if self._force_failure == "slot_unavailable":
            target_date = _parse_date(date_str) or datetime.now(UTC).date()
            day_slots = self.slots_for_date(target_date)
            alternatives = [s for s in day_slots if s != slot][:2] or day_slots[:2]
            return BookingResult(
                ok=False,
                error_code="slot_unavailable",
                message="That slot just got taken.",
                alternatives=alternatives,
            )
        if self._force_failure == "invalid_date":
            return BookingResult(ok=False, error_code="invalid_date", message=_INVALID_DATE_MESSAGE)
        if self._force_failure == "invalid_phone":
            return BookingResult(
                ok=False, error_code="invalid_phone", message=_INVALID_PHONE_MESSAGE
            )
        # system_error has no organic trigger — it exists only to be forced on cue (D10).
        return BookingResult(
            ok=False,
            error_code="system_error",
            message=(
                "Our booking system is temporarily unavailable. The team will confirm "
                "within one business day."
            ),
        )


def _parse_date(date_str: str) -> date | None:
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        return None
