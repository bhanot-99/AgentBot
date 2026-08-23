import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parent.parent.parent
_MODULES_DIR = _ROOT / "prompts" / "modules"
_FACTS_PATH = _ROOT / "data" / "project_facts.yaml"

_CORE_MODULES = (
    "00_identity.md",
    "10_knowledge_base.md",
    "20_language.md",
    "30_qualification.md",
    "40_objections.md",
    "50_edge_cases.md",
    "60_guardrails.md",
)
_CHANNEL_MODULES = {
    "chat": "70_channel_chat.md",
    "voice": "71_channel_voice.md",
}

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def _load_facts() -> dict[str, Any]:
    with _FACTS_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _known_facts_table(known: dict[str, Any]) -> str:
    rows = [
        ("Developer", known["developer"]),
        ("Project name", known["project_name"]),
        ("Location", known["location"]),
        ("Configurations offered", ", ".join(known["configurations_offered"])),
        ("2 BHK starting price", known["price_2bhk_starting"]),
        ("3 BHK starting price", known["price_3bhk_starting"]),
        ("Site visits", known["site_visits"]),
        ("Languages supported", ", ".join(known["languages_supported"])),
    ]
    lines = ["| Field | Value |", "|---|---|"]
    lines += [f"| {label} | {value} |" for label, value in rows]
    return "\n".join(lines)


def _unknown_policy_table(entries: list[dict[str, Any]]) -> str:
    lines = ["| Category | Example questions | Policy |", "|---|---|---|"]
    for entry in entries:
        examples = " · ".join(f'"{q}"' for q in entry["example_questions"])
        lines.append(f"| {entry['category']} | {examples} | {entry['policy']} |")
    return "\n".join(lines)


def _placeholder_values(facts: dict[str, Any]) -> dict[str, str]:
    known = facts["known"]
    return {
        "DEVELOPER": known["developer"],
        "PROJECT_NAME": known["project_name"],
        "LOCATION": known["location"],
        "PRIME_DIRECTIVE": facts["prime_directive"].strip(),
        "KNOWN_FACTS_TABLE": _known_facts_table(known),
        "UNKNOWN_POLICY_TABLE": _unknown_policy_table(facts["unknown_policy"]),
    }


def _render(text: str, values: dict[str, str]) -> str:
    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            # A module referenced a fact that isn't in project_facts.yaml — fail loudly
            # rather than ship a literal "{{KEY}}" into the system prompt (rules.md PR2).
            raise KeyError(f"Unrendered placeholder in prompt module: {{{{{key}}}}}")
        return values[key]

    return _PLACEHOLDER_RE.sub(_sub, text)


@lru_cache
def build(channel: str) -> str:
    if channel not in _CHANNEL_MODULES:
        raise ValueError(f"Unknown channel: {channel!r}. Expected one of {list(_CHANNEL_MODULES)}.")

    values = _placeholder_values(_load_facts())
    module_files = (*_CORE_MODULES, _CHANNEL_MODULES[channel])

    rendered = [
        _render((_MODULES_DIR / filename).read_text(encoding="utf-8"), values).strip()
        for filename in module_files
    ]
    return "\n\n---\n\n".join(rendered)
