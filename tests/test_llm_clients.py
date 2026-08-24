from app.agent.tools import TOOL_SPECS
from app.llm.anthropic_client import _to_anthropic_messages, _to_anthropic_tool
from app.llm.base import ToolSpec
from app.llm.gemini_client import _to_gemini_contents, _to_gemini_tool


def test_gemini_thought_signature_round_trips_on_replay() -> None:
    # Regression: the neutral ToolCallRequest shape must preserve Gemini's thought_signature,
    # or the live API rejects the follow-up turn with 400 INVALID_ARGUMENT (caught live).
    messages = [
        {
            "role": "assistant",
            "text": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "name": "check_slot_availability",
                    "args": {"date_str": "2026-09-01"},
                    "extra": {"thought_signature": b"opaque-signature-bytes"},
                }
            ],
        }
    ]

    contents = _to_gemini_contents(messages)

    part = contents[0].parts[0]
    assert part.function_call.name == "check_slot_availability"
    assert part.thought_signature == b"opaque-signature-bytes"


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
