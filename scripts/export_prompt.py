"""Renders both channel variants of the system prompt to prompts/FINAL_PROMPT.md.

Run before any commit that touches a prompt module (rules.md PR6) so the committed
"final prompt" never drifts from what the code actually sends.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent.prompt_builder import build  # noqa: E402

_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "FINAL_PROMPT.md"

_BANNER = (
    "<!-- GENERATED — DO NOT EDIT. Run `python scripts/export_prompt.py` to regenerate. -->\n"
    "<!-- Source: prompts/modules/*.md + data/project_facts.yaml -->\n"
)


def main() -> None:
    chat_prompt = build("chat")
    voice_prompt = build("voice")

    content = (
        f"{_BANNER}\n"
        "# Final Prompt — Northstar Agent\n\n"
        "## Channel: chat\n\n"
        f"{chat_prompt}\n\n"
        "---\n\n"
        "## Channel: voice\n\n"
        f"{voice_prompt}\n"
    )

    _OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"Wrote {_OUTPUT_PATH} ({len(chat_prompt)} chars chat, {len(voice_prompt)} chars voice)")


if __name__ == "__main__":
    main()
