import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.agent.analytics import AnalyticsExtractor
from app.agent.prompt_builder import load_known_facts
from app.llm.base import LLMClient
from app.models import (
    Channel,
    ConversationAnalytics,
    Session,
    SessionCreateRequest,
    SessionCreateResponse,
)
from app.store.base import SessionStore

router = APIRouter(prefix="/api", tags=["session"])


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


def get_llm_client(request: Request) -> LLMClient:
    return request.app.state.llm_client


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


@router.post("/session/{session_id}/end", response_model=ConversationAnalytics)
async def end_session(
    session_id: str,
    store: Annotated[SessionStore, Depends(get_session_store)],
    llm: Annotated[LLMClient, Depends(get_llm_client)],
) -> ConversationAnalytics:
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    # Idempotent: ending an already-ended session returns the cached record rather than
    # re-running extraction (and spending another LLM call) on every repeat call.
    if session.analytics is not None:
        return session.analytics

    session.ended_at = session.ended_at or datetime.now(UTC)
    session.analytics = await AnalyticsExtractor(llm).extract(session)
    await store.save(session)

    return session.analytics
