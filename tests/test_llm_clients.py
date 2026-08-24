import base64
import json

from google.genai import types

from app.agent.tools import TOOL_SPECS
from app.llm.anthropic_client import _to_anthropic_messages, _to_anthropic_tool
from app.llm.base import ToolSpec
from app.llm.gemini_client import _to_gemini_contents, _to_gemini_tool, _to_llm_response


def _usage_metadata() -> types.GenerateContentResponseUsageMetadata:
    return types.GenerateContentResponseUsageMetadata(
        prompt_token_count=10, candidates_token_count=0, cached_content_token_count=0
    )


def test_gemini_response_with_none_parts_does_not_crash() -> None:
    # Regression: a truncated (MAX_TOKENS) response can have parts=None with no text and no
    # tool call — the live scenario runner crashed on this with "NoneType is not iterable"
    # before content.parts was guarded.
    response = types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=None), finish_reason="MAX_TOKENS"
            )
        ],
        usage_metadata=_usage_metadata(),
    )

    result = _to_llm_response(response)

    assert result.text is None
    assert result.tool_calls == []


def test_gemini_response_with_none_content_does_not_crash() -> None:
    # Regression: a safety-blocked response can have content=None entirely.
    response = types.GenerateContentResponse(
        candidates=[types.Candidate(content=None, finish_reason="SAFETY")],
        usage_metadata=_usage_metadata(),
    )

    result = _to_llm_response(response)

    assert result.text is None
    assert result.tool_calls == []


def test_gemini_thought_signature_round_trips_on_replay() -> None:
    # Regression: the neutral ToolCallRequest shape must preserve Gemini's thought_signature,
    # or the live API rejects the follow-up turn with 400 INVALID_ARGUMENT (caught live).
    # Stored as a base64 str in `extra`, not raw bytes — a second live bug (GET /transcript
    # 500ing on non-JSON-serializable bytes) is pinned by the test right below this one.
    encoded = base64.b64encode(b"opaque-signature-bytes").decode("ascii")
    messages = [
        {
            "role": "assistant",
            "text": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "name": "check_slot_availability",
                    "args": {"date_str": "2026-09-01"},
                    "extra": {"thought_signature": encoded},
                }
            ],
        }
    ]

    contents = _to_gemini_contents(messages)

    part = contents[0].parts[0]
    assert part.function_call.name == "check_slot_availability"
    assert part.thought_signature == b"opaque-signature-bytes"


def test_gemini_tool_call_extra_stays_json_serializable() -> None:
    # Regression: GET /session/{id}/transcript returns session.messages verbatim as a plain
    # dict — a raw `bytes` value anywhere inside it 500s (FastAPI's default encoder can't
    # serialize bytes that aren't valid UTF-8), caught live.
    message = {
        "role": "assistant",
        "text": None,
        "tool_calls": [
            {
                "id": "call_1",
                "name": "check_slot_availability",
                "args": {"date_str": "2026-09-01"},
                "extra": {"thought_signature": base64.b64encode(b"\xff\xfe\x00signature").decode()},
            }
        ],
    }

    json.dumps(message)  # must not raise


def test_gemini_missing_thought_signature_defaults_to_none() -> None:
    messages = [
        {
            "role": "assistant",
            "text": None,
            "tool_calls": [{"id": "call_1", "name": "check_slot_availability", "args": {}}],
        }
    ]

    contents = _to_gemini_contents(messages)

    assert contents[0].parts[0].thought_signature is None


def test_gemini_tool_declaration_maps_json_schema_types() -> None:
    spec = ToolSpec(
        name="example",
        description="desc",
        properties={
            "count": {"type": "integer"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        required=["count"],
    )

    tool = _to_gemini_tool([spec])

    schema = tool.function_declarations[0].parameters
    assert schema.properties["count"].type == "INTEGER"
    assert schema.properties["tags"].type == "ARRAY"
    assert schema.properties["tags"].items.type == "STRING"
    assert schema.required == ["count"]


def test_gemini_tool_declarations_build_for_all_five_specs() -> None:
    tool = _to_gemini_tool(TOOL_SPECS)
    assert len(tool.function_declarations) == 5


def test_anthropic_tool_declaration_sets_strict_and_closed_schema() -> None:
    spec = ToolSpec(
        name="example", description="desc", properties={"x": {"type": "string"}}, required=["x"]
    )

    declaration = _to_anthropic_tool(spec)

    assert declaration["strict"] is True
    assert declaration["input_schema"]["additionalProperties"] is False
    assert declaration["input_schema"]["required"] == ["x"]


def test_anthropic_tool_result_sets_is_error_from_ok_flag() -> None:
    messages = [
        {
            "role": "tool_result",
            "results": [
                {
                    "id": "call_1",
                    "name": "book_site_visit",
                    "output": {"ok": False, "error_code": "slot_unavailable"},
                },
                {"id": "call_2", "name": "update_lead_profile", "output": {"ok": True}},
            ],
        }
    ]

    anthropic_messages = _to_anthropic_messages(messages)

    blocks = anthropic_messages[0]["content"]
    assert blocks[0]["tool_use_id"] == "call_1"
    assert blocks[0]["is_error"] is True
    assert blocks[1]["is_error"] is False


def test_anthropic_assistant_message_includes_text_and_tool_use_blocks() -> None:
    messages = [
        {
            "role": "assistant",
            "text": "Sure, one moment.",
            "tool_calls": [
                {
                    "id": "call_1",
                    "name": "check_slot_availability",
                    "args": {"date_str": "2026-09-01"},
                }
            ],
        }
    ]

    anthropic_messages = _to_anthropic_messages(messages)

    content = anthropic_messages[0]["content"]
    assert content[0] == {"type": "text", "text": "Sure, one moment."}
    assert content[1]["type"] == "tool_use"
    assert content[1]["input"] == {"date_str": "2026-09-01"}
