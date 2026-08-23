import re

import pytest

from app.agent.prompt_builder import build

_PLACEHOLDER_RE = re.compile(r"\{\{\w+\}\}")


@pytest.mark.parametrize("channel", ["chat", "voice"])
def test_channel_builds(channel: str) -> None:
    prompt = build(channel)
    assert isinstance(prompt, str)
    assert len(prompt) > 0


@pytest.mark.parametrize("channel", ["chat", "voice"])
def test_no_unrendered_placeholders(channel: str) -> None:
    assert _PLACEHOLDER_RE.search(build(channel)) is None


@pytest.mark.parametrize("channel", ["chat", "voice"])
def test_all_five_known_facts_present(channel: str) -> None:
    prompt = build(channel)
    # The five known facts from PRD.md §5.1 that any grounded reply must be able to draw on.
    assert "Sector 79" in prompt
    assert "2 BHK" in prompt and "1.35 crore" in prompt
    assert "3 BHK" in prompt and "1.75 crore" in prompt
    assert "site visit" in prompt.lower() or "site-visit" in prompt.lower()
    assert "Hindi" in prompt and "Hinglish" in prompt


def test_voice_contains_no_markup_rule() -> None:
    assert "No markup" in build("voice") or "no markup" in build("voice").lower()


def test_chat_does_not_contain_voice_no_markup_rule() -> None:
    assert "No markup" not in build("chat")


def test_invalid_channel_raises() -> None:
    with pytest.raises(ValueError):
        build("smoke_signal")
