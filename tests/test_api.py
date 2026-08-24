import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api import analytics as analytics_module
from app.api import chat as chat_module
from app.api import session as session_module
from app.main import app
from app.models import ContactPreference, ExtractedAnalytics
from app.store.memory_store import InMemorySessionStore
from tests.fakes import FakeLLMClient


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
def client(fake_llm: FakeLLMClient) -> Iterator[TestClient]:
    store = InMemorySessionStore(ttl_minutes=120)
    app.dependency_overrides[session_module.get_session_store] = lambda: store
    app.dependency_overrides[session_module.get_llm_client] = lambda: fake_llm
    app.dependency_overrides[chat_module.get_session_store] = lambda: store
    app.dependency_overrides[chat_module.get_llm_client] = lambda: fake_llm
    app.dependency_overrides[analytics_module.get_session_store] = lambda: store
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
    system = fake_llm.calls[0]["system"]
    assert isinstance(system, str)
    assert "Northstar One" in system
    # The volatile live-state block (rules.md A15 — no explicit caching in v1) is appended
    # after the composed prompt, in the same string.
    assert "Current lead profile" in system


def test_chat_short_circuits_with_no_llm_call_once_do_not_contact(
    client: TestClient, fake_llm: FakeLLMClient
) -> None:
    session_id = _create_session(client)
    store = app.dependency_overrides[chat_module.get_session_store]()
    session = asyncio.run(store.get(session_id))
    session.contact_preference = ContactPreference.DO_NOT_CONTACT
    asyncio.run(store.save(session))

    response = client.post(
        "/api/chat", json={"session_id": session_id, "message": "stop contacting me"}
    )

    assert response.status_code == 200
    assert "won't be contacted" in response.json()["reply"]
    assert len(fake_llm.calls) == 0


def test_end_session_returns_analytics_record(client: TestClient, fake_llm: FakeLLMClient) -> None:
    session_id = _create_session(client)
    fake_llm._parse_script.append(ExtractedAnalytics(summary="A cooperative lead."))

    response = client.post(f"/api/session/{session_id}/end")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert body["summary"] == "A cooperative lead."
    assert body["interest_level"] in ("hot", "warm", "cold")


def test_end_session_is_idempotent(client: TestClient, fake_llm: FakeLLMClient) -> None:
    session_id = _create_session(client)
    fake_llm._parse_script.append(ExtractedAnalytics(summary="first"))

    first = client.post(f"/api/session/{session_id}/end")
    second = client.post(f"/api/session/{session_id}/end")

    assert first.json() == second.json()
    assert len(fake_llm.parse_calls) == 1  # second call did not re-extract


def test_end_session_unknown_session_is_404(client: TestClient) -> None:
    response = client.post("/api/session/does-not-exist/end")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "session_not_found"


def test_get_analytics_before_end_is_404_with_distinct_code(client: TestClient) -> None:
    session_id = _create_session(client)
    response = client.get(f"/api/session/{session_id}/analytics")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "analytics_not_available"


def test_get_analytics_after_end_returns_the_cached_record(
    client: TestClient, fake_llm: FakeLLMClient
) -> None:
    session_id = _create_session(client)
    fake_llm._parse_script.append(ExtractedAnalytics(summary="cached"))
    client.post(f"/api/session/{session_id}/end")

    response = client.get(f"/api/session/{session_id}/analytics")

    assert response.status_code == 200
    assert response.json()["summary"] == "cached"


def test_get_transcript_returns_messages_and_tool_events(client: TestClient) -> None:
    session_id = _create_session(client)
    client.post("/api/chat", json={"session_id": session_id, "message": "Hi"})

    response = client.get(f"/api/session/{session_id}/transcript")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert len(body["messages"]) >= 2
    assert body["tool_events"] == []
