from datetime import UTC, datetime, timedelta

import pytest

from app.services.booking import BookingService

_TODAY = datetime.now(UTC).date()
_VALID_DATE = (_TODAY + timedelta(days=2)).isoformat()
_PHONE = "9876543210"


def test_slots_for_date_are_ninety_minutes_apart_within_business_hours() -> None:
    service = BookingService()
    slots = service.slots_for_date(_TODAY)
    assert slots[0] == "10:00"
    assert slots[-1] == "16:00"
    for slot in slots:
        hour, minute = (int(part) for part in slot.split(":"))
        assert 10 <= hour <= 16


@pytest.mark.parametrize(
    "days_ahead, expected",
    [(0, False), (1, True), (30, True), (31, False)],
)
def test_date_window_is_one_to_thirty_days_ahead(days_ahead: int, expected: bool) -> None:
    service = BookingService()
    target = _TODAY + timedelta(days=days_ahead)
    assert service.is_date_in_window(target, today=_TODAY) is expected


@pytest.mark.parametrize(
    "phone, expected",
    [("9876543210", True), ("8123456789", True), ("5123456789", False), ("98765432", False)],
)
def test_indian_mobile_validation(phone: str, expected: bool) -> None:
    assert BookingService().is_valid_indian_mobile(phone) is expected


def test_book_happy_path_returns_reference() -> None:
    service = BookingService()
    slot = service.slots_for_date(_TODAY + timedelta(days=2))[0]
    result = service.book(date_str=_VALID_DATE, slot=slot, phone=_PHONE)
    assert result.ok is True
    assert result.reference is not None
    assert result.reference.startswith("NS-")
    assert result.date == _VALID_DATE
    assert result.slot == slot


def test_book_rejects_invalid_phone() -> None:
    service = BookingService()
    slot = service.slots_for_date(_TODAY + timedelta(days=2))[0]
    result = service.book(date_str=_VALID_DATE, slot=slot, phone="12345")
    assert result.ok is False
    assert result.error_code == "invalid_phone"


def test_book_rejects_out_of_window_date() -> None:
    service = BookingService()
    result = service.book(
        date_str=(_TODAY + timedelta(days=60)).isoformat(), slot="10:00", phone=_PHONE
    )
    assert result.ok is False
    assert result.error_code == "invalid_date"


def test_book_rejects_unavailable_slot_with_alternatives() -> None:
    service = BookingService()
    result = service.book(date_str=_VALID_DATE, slot="23:45", phone=_PHONE)
    assert result.ok is False
    assert result.error_code == "slot_unavailable"
    assert len(result.alternatives) > 0


@pytest.mark.parametrize(
    "mode", ["slot_unavailable", "invalid_date", "invalid_phone", "system_error"]
)
def test_forced_failure_modes_are_deterministic(mode: str) -> None:
    service = BookingService(force_failure=mode)
    slot = service.slots_for_date(_TODAY + timedelta(days=2))[0]
    result = service.book(date_str=_VALID_DATE, slot=slot, phone=_PHONE)
    assert result.ok is False
    assert result.error_code == mode


def test_forced_system_error_never_claims_a_booking() -> None:
    service = BookingService(force_failure="system_error")
    slot = service.slots_for_date(_TODAY + timedelta(days=2))[0]
    result = service.book(date_str=_VALID_DATE, slot=slot, phone=_PHONE)
    assert result.ok is False
    assert result.reference is None


def test_unknown_force_failure_value_raises_at_construction() -> None:
    with pytest.raises(ValueError):
        BookingService(force_failure="not_a_real_mode")


def test_check_availability_reports_alternatives_when_out_of_window() -> None:
    service = BookingService()
    result = service.check_availability((_TODAY + timedelta(days=60)).isoformat())
    assert result["available"] is False
    assert result["slots"] == []
    assert len(result["nearest_alternatives"]) == 2
