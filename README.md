# Northstar Agent

An AI sales chatbot for **Northstar Homes**' fictional project **Northstar One** (Sector 79,
Gurugram) — built for the Huvo AI Forward Deployed Engineer take-home assignment. One system
prompt drives natural, multilingual (English / Hindi / Hinglish) lead qualification, objection
handling, and site-visit booking across both a chat UI and a text-simulated voice channel, backed
by a FastAPI service with deterministic tools, post-conversation analytics, and a live scenario
test harness.

Full requirement trace and design rationale live in [`PRD.md`](PRD.md) and
[`Architecture.md`](Architecture.md); the graded artifact — the system prompt itself — is
[`prompts/FINAL_PROMPT.md`](prompts/FINAL_PROMPT.md).

---

## 1. Quickstart

Requirements: Python 3.12+, a Gemini API key (free tier is enough —
[aistudio.google.com/apikey](https://aistudio.google.com/apikey)).

```bash
git clone <this-repo-url>
cd AgentBot

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# open .env and set GEMINI_API_KEY=<your key>

uvicorn app.main:app --reload --port 8000
```

Open **http://127.0.0.1:8000** — that's the whole app, served straight off the backend (no Node,
no separate frontend build, no database). `/docs` has interactive Swagger; `/health` is a liveness
check.

No key on hand? Set `LLM_PROVIDER=anthropic` in `.env` and fill `ANTHROPIC_API_KEY` instead — the
LLM layer is provider-neutral (see §3) and either one boots the app unchanged.

---

## 2. What it does

- **Natural conversation** — short turns, one question at a time, opens with a human-style
  introduction, closes with a recap + next step.
- **Lead qualification** — silently slot-fills budget, configuration, purpose, timeline, and
  decision authority as the customer reveals them; never interrogates.
- **Multilingual** — detects and mirrors English, Hindi (Devanagari), or Hinglish per turn,
  including mid-conversation switches, without ever announcing the switch.
- **Zero fabrication** — every project fact traces to one file
  ([`data/project_facts.yaml`](data/project_facts.yaml)); anything not in it is deflected by name
  ("the sales team will confirm"), never guessed.
- **Objections, busy/uninterested customers, callback requests, and do-not-contact** — each has an
  explicit, tested behaviour; DNC is immediate and irreversible for the rest of the session.
- **Site-visit booking** — a real (simulated) slot-booking tool, including every failure mode
  (slot taken, system error), with graceful in-language recovery — never a false "booked!"
  confirmation.
- **Human escalation** — hands off on direct request, commercial negotiation, a breakdown, or a
  repeated unknown, stated as already arranged rather than proposed.
- **Chat ⇄ voice duality** — one core prompt, a small channel adapter block: voice mode forbids
  markdown/symbols, spells out numbers ("₹1.35 crore" → "one crore thirty five lakhs rupees"), and
  caps turns shorter. See [Known limitations](#8-known-limitations) — voice is prompt-ready, not a
  real telephony integration.
- **Post-conversation analytics** — on session end, a structured record (budget fit, interest
  level, qualification score, site-visit status, follow-up requirement, sentiment, etc.), with
  every field the code can verify independently (booking status, DNC, escalation, turn count)
  overwritten from the actual tool-event log rather than trusted from the model.

---

## 3. Architecture

```
Browser (vanilla HTML/CSS/JS, app/static/)
   │ fetch() JSON over HTTP
   ▼
FastAPI (app/main.py) ── StaticFiles "/" (serves the SPA) + API routers "/api/*"
   │
   ├── PromptBuilder        composes the system prompt from modules + project_facts.yaml
   ├── Orchestrator         the turn loop: call LLM → dispatch tool calls → loop (max 4x)
   ├── AnalyticsExtractor   transcript + tool log → structured record on session end
   │
   ├── ToolDispatcher       update_lead_profile · check_slot_availability ·
   │                        book_site_visit · escalate_to_human · set_contact_preference
   │
   ├── BookingService       slot logic, validation, failure injection (deterministic, unit-tested)
   ├── CrmService           escalation tickets, DNC register, lead record
   ├── score_lead()         rule-based hot/warm/cold + 0-100 qualification score
   │
   ├── SessionStore (Protocol) → InMemorySessionStore   [swap for Redis without touching callers]
   └── LLMClient (Protocol)    → GeminiLLMClient / AnthropicLLMClient
          │
          ▼
   Gemini API (primary) or Anthropic API (fallback) — chosen by LLM_PROVIDER
```

**Why layered this way:** a Forward Deployed Engineer's reality is that a real customer will want
to swap the model, swap the session store for Redis, and point the booking tool at their real CRM.
Those three seams — `LLMClient`, `SessionStore`, and the tool layer — are the only abstractions in
the codebase; everything else is concrete. Full sequence diagrams for a chat turn and session-end
analytics are in [`Architecture.md`](Architecture.md) §3.

---

## 4. Prompt approach

The system prompt is **modular**, assembled at request time from small files under
[`prompts/modules/`](prompts/modules) (identity, knowledge base, qualification flow, edge cases,
guardrails, one channel adapter) rather than one monolithic block — each behaviour (an objection
type, DNC, escalation) lives in exactly one place, so a fix to how the agent handles "call me
later" can't accidentally touch how it handles a price objection. The exported, fully-composed
prompt actually shipped is [`prompts/FINAL_PROMPT.md`](prompts/FINAL_PROMPT.md)
(`scripts/export_prompt.py` regenerates it from the live modules — never hand-edited).

**Anti-hallucination is structural, not just an instruction.** Every fact the agent may state comes
from one YAML file (`data/project_facts.yaml`); anything outside it is on a closed
"unknown question" list with a named deflection ("not confirmed — the sales team will share exact
layouts"), so the model is never asked to judge whether it "probably knows" something. On top of
that, every field in the post-conversation analytics that the code can verify independently
(booking success, DNC status, escalation, turn count) is force-overwritten from the tool-event log
after extraction — the model's read of the transcript is never treated as ground truth for
anything the system already knows for certain.

---

## 5. API reference

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/session` | Start a session (`{"channel": "chat" \| "voice"}`) → `session_id` + static greeting |
| `POST` | `/api/chat` | Send a customer message, run the agent turn, get the reply + tool trace |
| `POST` | `/api/session/{id}/end` | End the session, run analytics extraction, return the record |
| `GET` | `/api/session/{id}/analytics` | Fetch the analytics record (404 until the session has ended) |
| `GET` | `/api/session/{id}/transcript` | Full raw message + tool-event log for the session |
| `GET` | `/health` | Liveness check |
| `GET` | `/docs` | Interactive Swagger UI |

Full request/response schemas are in [`Architecture.md`](Architecture.md) §8, or just open `/docs`
against a running instance.

---

## 6. Testing

```bash
pytest -q          # 82 unit/integration tests - prompt assembly, scoring, LLM adapters,
                    # orchestrator loop, booking, analytics - no live API calls
ruff check .        # lint
ruff format --check .
```

**Live scenario suite** (`scripts/run_scenarios.py`) drives 25 real conversations — 19 core +
6 adversarial (prompt injection, false-premise questions, off-record data requests) — through the
real LLM against regex `must`/`must_not` assertions and exact analytics-field matches, deliberately
*not* an LLM judge. Results are in [`docs/TEST_RESULTS.md`](docs/TEST_RESULTS.md) — **24/25
passing**. To re-run (costs real API calls):

```bash
python scripts/run_scenarios.py               # full suite, regenerates TEST_RESULTS.md
python scripts/run_scenarios.py escalation     # a single scenario by id
```

The one known failure (`escalation`, F-11) is a genuine, documented model-reliability gap, not a
prompt-wording bug — see [Known limitations](#8-known-limitations).

---

## 7. Key assumptions

1. Prices are "starting from" / "onwards" pricing; the agent never quotes a final total.
2. Currency is INR; "Cr"/"crore" = 10,000,000, "lakh" = 100,000.
3. Site visits run daily 10:00-18:00 IST in 90-minute windows, bookable 1-30 days ahead — an
   invented simulation parameter for the booking service, never presented to the customer as more
   certain than "our team will confirm."
4. Indian mobile numbers: 10 digits starting 6-9, optional `+91`/`0` prefix.
5. One conversation = one lead; no cross-session identity resolution.
6. Voice mode is simulated as text — the prompt is optimised for how a voice call *sounds*, not for
   a real audio transport.
7. Single machine, single reviewer at a time — no horizontal scaling required for this submission.

---

## 8. Known limitations

- **No real telephony / TTS / STT.** Voice mode changes what the agent *writes* (no markdown,
  spelled-out numbers, shorter turns) but the interface is still text in, text out. Explicitly
  out of scope per the assignment ("simple text-based conversational bot"); see PRD §3.2.
- **In-memory session store.** Sessions do not survive a process restart and there is no horizontal
  scaling — acceptable for a single-reviewer demo, swappable via the `SessionStore` protocol.
- **No real CRM, database, or payment/booking-amount collection.** `CrmService` and
  `BookingService` are deterministic in-process simulations.
- **No LLM-judge in the test harness by design** — assertions are regex `must`/`must_not` patterns
  plus exact analytics-field matches, so results are reproducible and don't depend on a second
  model's opinion. This means test coverage is only as good as the assertions written, not a
  semantic judgment of "did this feel right."
- **Escalation tool-call reliability (documented, non-blocking).** The agent's *text* correctly and
  consistently states the hand-off as already arranged, but on the `escalate_to_human` **tool
  call** itself there is measured live variance on the free-tier `gemini-3.1-flash-lite` model
  (4/5 pass rate across repeated live runs) — this is model behaviour, not a prompt-wording gap,
  and it is not one of the four zero-tolerance criteria (zero fabrication, zero false booking
  claims, 100% DNC compliance, >=95% script mirroring), all of which are independently confirmed met.
- **Single project, single tenant.** All facts are scoped to Northstar One via one YAML file; there
  is no multi-project or multi-tenant support.
- **English-only structured logs.** The conversation itself is fully multilingual; internal log
  messages and error codes are English-only.
- **No token-by-token streaming.** The UI shows a typing indicator, not a live token stream.

---

## 9. AI tools used

The entire project — architecture design, prompt engineering, application code, test harness, and
this documentation — was built using **Claude Code** (Anthropic), working from a set of
project-tracked planning documents (`PRD.md`, `Architecture.md`, `phases.md`, `rules.md`,
`memory.md`) that record every phase gate, decision, and fix made along the way. Live scenario
testing used real calls against the Gemini API (and, for provider-fallback verification, the
Anthropic API) — none of the behaviour described above is simulated or hand-waved; it was
exercised against the real model and the real FastAPI backend.

---

## 10. Project structure

```
app/
  agent/        orchestrator, prompt builder, tool dispatch, analytics extraction
  api/          FastAPI routers: session, chat, analytics
  llm/          provider-neutral LLMClient seam + Gemini/Anthropic implementations
  services/     booking, CRM, lead scoring - deterministic, no LLM
  store/        session persistence (in-memory, Protocol-backed)
  static/       the web UI (vanilla HTML/CSS/JS)
  models.py     all Pydantic models and enums
data/            project_facts.yaml - the single source of truth for project facts
prompts/         modular prompt source + the exported FINAL_PROMPT.md
scripts/         run_scenarios.py, export_prompt.py
tests/           unit tests + tests/scenarios/*.yaml live scenario definitions
docs/            TEST_RESULTS.md, DEMO_SCRIPT.md
PRD.md, Architecture.md, phases.md, rules.md, memory.md   planning & decision record
```
