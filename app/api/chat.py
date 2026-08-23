from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.agent.orchestrator import Orchestrator
from app.agent.prompt_builder import build as build_system_prompt
from app.llm.base import LLMClient
from app.models import ChatRequest, ChatResponse
from app.store.base import SessionStore

router = APIRouter(prefix="/api", tags=["chat"])


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


def get_llm_client(request: Request) -> LLMClient:
    return request.app.state.llm_client


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    store: Annotated[SessionStore, Depends(get_session_store)],
    llm: Annotated[LLMClient, Depends(get_llm_client)],
) -> ChatResponse:
    session = await store.get(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    if session.ended_at is not None:
        raise HTTPException(status_code=409, detail="session_ended")

    session.messages.append({"role": "user", "content": [{"type": "text", "text": body.message}]})

    system_prompt = build_system_prompt(session.channel.value)
    reply_text, usage = await Orchestrator(llm, system_prompt).run_turn(session)

    await store.save(session)

    turn_id = sum(1 for message in session.messages if message["role"] == "assistant")

    return ChatResponse(
        session_id=session.id,
        turn_id=turn_id,
        reply=reply_text,
        stage=session.stage,
        lead_profile=session.lead,
        tool_events=session.tool_events,
        session_ended=False,
        usage=usage,
    )
