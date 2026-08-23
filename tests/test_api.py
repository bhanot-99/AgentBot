from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api import chat as chat_module
from app.api import session as session_module
from app.main import app
from app.store.memory_store import InMemorySessionStore
from tests.fakes import FakeLLMClient

# DNC short-circuit (no LLM call once do_not_contact is set) is added in Phase 3, once
# set_contact_preference exists — there is nothing to short-circuit without it yet.


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
def client(fake_llm: FakeLLMClient) -> Iterator[TestClient]:
    store = InMemorySessionStore(ttl_minutes=120)
    app.dependency_overrides[session_module.get_session_store] = lambda: store
    app.dependency_overrides[chat_module.get_session_store] = lambda: store
    app.dependency_overrides[chat_module.get_llm_client] = lambda: fake_llm
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def _create_session(client: TestClient, channel: str = "chat") -> str:
    response = client.post("/api/session", json={"channel": channel})
    assert response.status_code == 201
    return response.json()["session_id"]


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_session_returns_greeting(client: TestClient) -> None:
    response = client.post("/api/session", json={"channel": "chat"})
    assert response.status_code == 201
    body = response.json()
    assert body["channel"] == "chat"
    assert "session_id" in body
    assert "Northstar One" in body["greeting"]
    assert "started_at" in body


def test_create_session_rejects_unknown_channel(client: TestClient) -> None:
    response = client.post("/api/session", json={"channel": "carrier_pigeon"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_chat_returns_reply_and_updates_turn_id(client: TestClient) -> None:
    session_id = _create_session(client)

    response = client.post("/api/chat", json={"session_id": session_id, "message": "Hi there"})
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert body["reply"] == "Thanks for reaching out! How can I help you today?"
    # The greeting is the first assistant message, so this is turn 2.
    assert body["turn_id"] == 2
    assert body["session_ended"] is False
    assert body["usage"]["input_tokens"] == 100


def test_chat_unknown_session_is_404(client: TestClient) -> None:
    response = client.post("/api/chat", json={"session_id": "does-not-exist", "message": "hi"})
    assert response.status_code == 404
    envelope = response.json()
    assert envelope["error"]["code"] == "session_not_found"
    assert "request_id" in envelope["error"]


def test_chat_after_session_end_is_409(client: TestClient) -> None:
    session_id = _create_session(client)
    end_response = client.post(f"/api/session/{session_id}/end")
    assert end_response.status_code == 200

    response = client.post("/api/chat", json={"session_id": session_id, "message": "hi"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "session_ended"


def test_chat_message_over_length_cap_is_400(client: TestClient) -> None:
    session_id = _create_session(client)
    response = client.post("/api/chat", json={"session_id": session_id, "message": "a" * 2001})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_chat_empty_message_is_400(client: TestClient) -> None:
    session_id = _create_session(client)
    response = client.post("/api/chat", json={"session_id": session_id, "message": ""})
    assert response.status_code == 400


def test_fake_llm_received_the_composed_system_prompt(
    client: TestClient, fake_llm: FakeLLMClient
) -> None:
    session_id = _create_session(client, channel="chat")
    client.post("/api/chat", json={"session_id": session_id, "message": "Hi"})

    assert len(fake_llm.calls) == 1
    system_blocks = fake_llm.calls[0]["system"]
    assert system_blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in system_blocks[1]
    assert "Northstar One" in system_blocks[0]["text"]
