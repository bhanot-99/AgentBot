import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.agent.prompt_builder import load_known_facts
from app.models import Channel, Session, SessionCreateRequest, SessionCreateResponse
from app.store.base import SessionStore

router = APIRouter(prefix="/api", tags=["session"])


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


def _greeting(channel: Channel) -> str:
    facts = load_known_facts()
    intro = (
        f"Hi! This is Aarav from {facts['developer']}, reaching out about "
        f"{facts['project_name']} in {facts['location']}."
    )
    return f"{intro} Do you have a couple of minutes to chat?"


@router.post("/session", status_code=201, response_model=SessionCreateResponse)
async def create_session(
    body: SessionCreateRequest,
    store: Annotated[SessionStore, Depends(get_session_store)],
) -> SessionCreateResponse:
    now = datetime.now(UTC)
    greeting = _greeting(body.channel)

    session = Session(id=str(uuid.uuid4()), channel=body.channel, created_at=now)
    session.messages.append({"role": "assistant", "text": greeting, "tool_calls": []})
    await store.create(session)

    return SessionCreateResponse(
        session_id=session.id, channel=body.channel, greeting=greeting, started_at=now
    )


@router.post("/session/{session_id}/end")
async def end_session(
    session_id: str,
    store: Annotated[SessionStore, Depends(get_session_store)],
) -> dict[str, Any]:
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    session.ended_at = datetime.now(UTC)
    await store.save(session)

    # TODO(P5): replace with the full ConversationAnalytics record (Architecture.md §8).
    return {"session_id": session.id, "ended_at": session.ended_at.isoformat()}
