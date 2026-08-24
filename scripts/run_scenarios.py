"""Live scenario runner (Tier 2 — needs a real API key, run manually; Architecture.md §12).

Drives real conversations against the real model from tests/scenarios/*.yaml and writes
docs/TEST_RESULTS.md with input · expected behaviour · actual output · PASS/FAIL per scenario
(rules.md T4/T6). Assertions are keyword/regex/analytics-field based — deliberately not an LLM
judge, so results are reproducible and auditable.

Usage: python scripts/run_scenarios.py
"""

import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml
from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from app.api import analytics as analytics_module  # noqa: E402
from app.api import chat as chat_module  # noqa: E402
from app.api import session as session_module  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.llm.anthropic_client import AnthropicLLMClient  # noqa: E402
from app.llm.base import LLMClient  # noqa: E402
from app.llm.gemini_client import GeminiLLMClient  # noqa: E402
from app.main import app  # noqa: E402
from app.services.booking import BookingService  # noqa: E402
from app.services.crm import CrmService  # noqa: E402
from app.store.memory_store import InMemorySessionStore  # noqa: E402

_SCENARIOS_DIR = _ROOT / "tests" / "scenarios"
_RESULTS_PATH = _ROOT / "docs" / "TEST_RESULTS.md"

# Scenarios reference dates relatively (never a hardcoded YYYY-MM-DD, which would silently
# drift outside the booking service's 1-30-day window on a future re-run) via this placeholder.
_DATE_PLUS_5 = (date.today() + timedelta(days=5)).isoformat()


@dataclass
class Expect:
    must: list[str] = field(default_factory=list)
    must_not: list[str] = field(default_factory=list)
    analytics: dict[str, Any] = field(default_factory=dict)


@dataclass
class Scenario:
    id: str
    requirement: str
    channel: str
    setup: dict[str, Any]
    turns: list[dict[str, str]]
    expect: Expect


@dataclass
class ScenarioResult:
    scenario: Scenario
    replies: list[str]
    analytics: dict[str, Any]
    failures: list[str]

    @property
    def passed(self) -> bool:
        return not self.failures


def _load_scenarios() -> list[Scenario]:
    scenarios = []
    for path in sorted(_SCENARIOS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        expect_data = data.get("expect", {})
        scenarios.append(
            Scenario(
                id=data["id"],
                requirement=data["requirement"],
                channel=data.get("channel", "chat"),
                setup=data.get("setup", {}),
                turns=data["turns"],
                expect=Expect(
                    must=expect_data.get("must", []),
                    must_not=expect_data.get("must_not", []),
                    analytics=expect_data.get("analytics", {}),
                ),
            )
        )
    return scenarios


def _build_llm_client() -> LLMClient:
    settings = get_settings()
    if settings.llm_provider == "anthropic":
        return AnthropicLLMClient(
            api_key=settings.anthropic_api_key,
            chat_model=settings.anthropic_chat_model,
            analytics_model=settings.anthropic_analytics_model,
        )
    return GeminiLLMClient(
        api_key=settings.gemini_api_key,
        chat_model=settings.chat_model,
        analytics_model=settings.analytics_model,
    )


def _render_turn(text: str) -> str:
    return text.replace("{{DATE_PLUS_5}}", _DATE_PLUS_5)


def _matches(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.IGNORECASE) is not None


def run_scenario(scenario: Scenario) -> ScenarioResult:
    store = InMemorySessionStore(ttl_minutes=120)
    llm = _build_llm_client()
    booking = BookingService(force_failure=scenario.setup.get("force_booking_failure", ""))
    crm = CrmService()

    overrides = {
        session_module.get_session_store: lambda: store,
        session_module.get_llm_client: lambda: llm,
        chat_module.get_session_store: lambda: store,
        chat_module.get_llm_client: lambda: llm,
        chat_module.get_booking_service: lambda: booking,
        chat_module.get_crm_service: lambda: crm,
        analytics_module.get_session_store: lambda: store,
    }
    app.dependency_overrides.update(overrides)

    replies: list[str] = []
    analytics: dict[str, Any] = {}
    try:
        with TestClient(app) as client:
            session_response = client.post("/api/session", json={"channel": scenario.channel})
            session_id = session_response.json()["session_id"]

            for turn in scenario.turns:
                message = {"session_id": session_id, "message": _render_turn(turn["user"])}
                response = client.post("/api/chat", json=message)
                if response.status_code == 502:
                    # A 502 here is Gemini's free-tier rate limit outlasting the SDK's own
                    # retries (seen live even with inter-scenario spacing) — an infra failure,
                    # not a model response, so one longer-backoff retry is evidence-honest
                    # rather than papering over real model behaviour.
                    time.sleep(15)
                    response = client.post("/api/chat", json=message)
                if response.status_code != 200:
                    replies.append(f"[HTTP {response.status_code}] {response.text}")
                    continue
                replies.append(response.json()["reply"])

            end_response = client.post(f"/api/session/{session_id}/end")
            if end_response.status_code == 200:
                analytics = end_response.json()
    finally:
        for key in overrides:
            app.dependency_overrides.pop(key, None)

    combined = "\n".join(replies)
    failures = []
    for pattern in scenario.expect.must:
        if not _matches(pattern, combined):
            failures.append(f"missing required pattern: {pattern!r}")
    for pattern in scenario.expect.must_not:
        if _matches(pattern, combined):
            failures.append(f"forbidden pattern present: {pattern!r}")
    for field_name, expected in scenario.expect.analytics.items():
        actual = analytics.get(field_name)
        if actual != expected:
            failures.append(f"analytics.{field_name} expected {expected!r}, got {actual!r}")

    return ScenarioResult(
        scenario=scenario, replies=replies, analytics=analytics, failures=failures
    )


def _render_results(results: list[ScenarioResult]) -> str:
    passed = sum(1 for r in results if r.passed)
    lines = [
        "<!-- Generated by scripts/run_scenarios.py — do not hand-edit. -->",
        "# Test Results",
        "",
        f"Generated {date.today().isoformat()} ({len(results)} scenarios, {passed} passed).",
        "",
        "| Scenario | Requirement | Result |",
        "|---|---|---|",
    ]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"| `{r.scenario.id}` | {r.scenario.requirement} | {status} |")
    lines += ["", "---", ""]

    for r in results:
        s = r.scenario
        lines.append(f"## `{s.id}` — {s.requirement}")
        lines.append("")
        lines.append(f"**Result:** {'PASS' if r.passed else 'FAIL'}")
        lines.append("")
        lines.append("**Input:**")
        for turn in s.turns:
            lines.append(f"- {_render_turn(turn['user'])}")
        lines.append("")
        lines.append("**Expected:**")
        if s.expect.must:
            lines.append(f"- Must match: {', '.join(repr(p) for p in s.expect.must)}")
        if s.expect.must_not:
            lines.append(f"- Must NOT match: {', '.join(repr(p) for p in s.expect.must_not)}")
        if s.expect.analytics:
            lines.append(f"- Analytics: {s.expect.analytics}")
        if not (s.expect.must or s.expect.must_not or s.expect.analytics):
            lines.append("- (qualitative — for manual review of the actual output below)")
        lines.append("")
        lines.append("**Actual output:**")
        for i, reply in enumerate(r.replies, 1):
            lines.append(f"{i}. {reply}")
        lines.append("")
        if not r.passed:
            lines.append("**Failure reasons:**")
            for failure in r.failures:
                lines.append(f"- {failure}")
            lines.append("")
        lines += ["---", ""]

    return "\n".join(lines)


def main() -> None:
    scenarios = _load_scenarios()
    if not scenarios:
        print(f"No scenarios found in {_SCENARIOS_DIR}")
        sys.exit(1)

    results = []
    for i, scenario in enumerate(scenarios):
        if i > 0:
            # Gemini's free tier caps at 15 requests/minute per model — running scenarios
            # back-to-back with no gap burned through it live, producing two 502s that were
            # infra artifacts, not real model behaviour. This does not fully eliminate
            # throttling (a single scenario's own tool loop can still burst), but it keeps
            # scenario-to-scenario spacing well under the cap.
            time.sleep(4)
        results.append(run_scenario(scenario))
    _RESULTS_PATH.write_text(_render_results(results), encoding="utf-8")

    passed = sum(1 for r in results if r.passed)
    print(f"{passed}/{len(results)} scenarios passed. Results written to {_RESULTS_PATH}")
    for r in results:
        if not r.passed:
            print(f"  FAIL {r.scenario.id}: {'; '.join(r.failures)}")


if __name__ == "__main__":
    main()
