import uuid

_DEFAULT_CALLBACK_WINDOW = "within 1 business day"


class CrmService:
    """Escalation tickets and the do-not-contact register.

    In-memory only (D2), but instantiated once at app startup and shared across sessions —
    unlike session state, the DNC register must outlive any single conversation so a customer
    who says stop stays suppressed even in a future session.
    """

    def __init__(self) -> None:
        self._dnc_register: set[str] = set()

    def escalate(self, *, reason: str, summary: str) -> dict[str, str]:
        return {
            "ticket_id": f"ESC-{uuid.uuid4().hex[:8].upper()}",
            "callback_window": _DEFAULT_CALLBACK_WINDOW,
        }

    def add_to_do_not_contact(self, phone: str | None) -> None:
        if phone:
            self._dnc_register.add(phone)

    def is_on_do_not_contact(self, phone: str | None) -> bool:
        return phone in self._dnc_register if phone else False
