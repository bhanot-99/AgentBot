from datetime import UTC, datetime, timedelta

from app.models import Session


class InMemorySessionStore:
    def __init__(self, ttl_minutes: int) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._sessions: dict[str, Session] = {}
        self._expires_at: dict[str, datetime] = {}

    async def create(self, session: Session) -> None:
        self._sessions[session.id] = session
        self._touch(session.id)

    async def get(self, session_id: str) -> Session | None:
        self._sweep()
        return self._sessions.get(session_id)

    async def save(self, session: Session) -> None:
        self._sessions[session.id] = session
        self._touch(session.id)

    async def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._expires_at.pop(session_id, None)

    def _touch(self, session_id: str) -> None:
        self._expires_at[session_id] = datetime.now(UTC) + self._ttl

    def _sweep(self) -> None:
        now = datetime.now(UTC)
        expired = [sid for sid, expires_at in self._expires_at.items() if expires_at < now]
        for sid in expired:
            self._sessions.pop(sid, None)
            self._expires_at.pop(sid, None)
