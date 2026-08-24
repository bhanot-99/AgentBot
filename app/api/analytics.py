from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models import ConversationAnalytics
from app.store.base import SessionStore

router = APIRouter(prefix="/api", tags=["analytics"])


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


@router.get("/session/{session_id}/analytics", response_model=ConversationAnalytics)
async def get_analytics(
    session_id: str,
    store: Annotated[SessionStore, Depends(get_session_store)],
) -> ConversationAnalytics:
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    if session.analytics is None:
        raise HTTPException(status_code=404, detail="analytics_not_available")
    return session.analytics


@router.get("/session/{session_id}/transcript")
async def get_transcript(
    session_id: str,
    store: Annotated[SessionStore, Depends(get_session_store)],
) -> dict[str, Any]:
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    return {
        "session_id": session.id,
        "messages": session.messages,
        "tool_events": [event.model_dump() for event in session.tool_events],
    }
