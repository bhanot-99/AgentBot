from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.agent.orchestrator import Orchestrator
from app.agent.prompt_builder import build as build_system_prompt
from app.agent.tools import ToolDispatcher
from app.llm.base import LLMClient
from app.models import ChatRequest, ChatResponse, ContactPreference, Usage
from app.services.booking import BookingService
from app.services.crm import CrmService
from app.store.base import SessionStore

router = APIRouter(prefix="/api", tags=["chat"])

# Fixed acknowledgement for the DNC short-circuit (phases.md P3 task 5) — once a session is
# marked do_not_contact, every subsequent turn returns this with no model call, ever.
_DNC_ACKNOWLEDGEMENT = (
    "Understood — you won't be contacted again about this. Thanks for letting us know, and "
    "apologies for the trouble."
)
_ZERO_USAGE = Usage(input_tokens=0, cache_read_input_tokens=0, output_tokens=0)


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


def get_llm_client(request: Request) -> LLMClient:
    return request.app.state.llm_client


def get_booking_service(request: Request) -> BookingService:
    return request.app.state.booking_service


def get_crm_service(request: Request) -> CrmService:
    return request.app.state.crm_service


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    store: Annotated[SessionStore, Depends(get_session_store)],
    llm: Annotated[LLMClient, Depends(get_llm_client)],
    booking: Annotated[BookingService, Depends(get_booking_service)],
    crm: Annotated[CrmService, Depends(get_crm_service)],
) -> ChatResponse:
    session = await store.get(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    if session.ended_at is not None:
        raise HTTPException(status_code=409, detail="session_ended")

    session.messages.append({"role": "user", "text": body.message})

    if session.contact_preference == ContactPreference.DO_NOT_CONTACT:
        session.messages.append(
            {"role": "assistant", "text": _DNC_ACKNOWLEDGEMENT, "tool_calls": []}
        )
        await store.save(session)
        turn_id = sum(1 for message in session.messages if message["role"] == "assistant")
        return ChatResponse(
            session_id=session.id,
            turn_id=turn_id,
            reply=_DNC_ACKNOWLEDGEMENT,
            stage=session.stage,
            lead_profile=session.lead,
            tool_events=session.tool_events,
            session_ended=False,
            usage=_ZERO_USAGE,
        )

    system_prompt = build_system_prompt(session.channel.value)
    dispatcher = ToolDispatcher(booking, crm)
    reply_text, usage = await Orchestrator(llm, system_prompt, dispatcher).run_turn(session)

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
