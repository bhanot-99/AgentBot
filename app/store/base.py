from typing import Protocol

from app.models import Session


class SessionStore(Protocol):
    """The seam that makes swapping in Redis a small file, not a rewrite (Architecture.md §2)."""

    async def create(self, session: Session) -> None: ...

    async def get(self, session_id: str) -> Session | None: ...

    async def save(self, session: Session) -> None: ...

    async def delete(self, session_id: str) -> None: ...
