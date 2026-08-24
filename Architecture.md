# Architecture — Northstar Agent

**Version:** 1.0 · **Date:** 2026-08-23 · **Status:** Approved for implementation

---

## 1. Architectural Principles

1. **The prompt is the product.** Code exists to prove the prompt works and to make agent
   behaviour observable. Any code that obscures prompt behaviour is a liability.
2. **One source of truth for facts.** `data/project_facts.yaml` is the only place a fact about
   Northstar One may be written. The prompt renders from it; the tests assert against it.
3. **Deterministic where it can be, probabilistic only where it must be.** Language, tone,
   objection handling and grounding are the model's job. Booking rules, validation, lead scoring
   and failure injection are ordinary code with ordinary tests.
4. **Zero-friction execution.** One `pip install`, one env var, one `uvicorn` command. No build
   step, no database, no container.
5. **Everything the agent does is visible.** Every tool call is recorded and surfaced in the UI,
   so a reviewer can watch `book_site_visit` fail rather than take our word for it.
6. **Boring dependencies.** Six production packages, all first-party or foundational.

---

## 2. System Architecture

```
┌───────────────────────────────────────────────────────────────────────────┐
│  BROWSER — vanilla HTML/CSS/JS (no build step)                            │
│  index.html · styles.css · app.js                                          │
│  chat pane │ channel toggle (chat│voice) │ tool-event trace │ analytics    │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │ fetch() JSON over HTTP
┌───────────────────────────────▼───────────────────────────────────────────┐
│  FastAPI  (app/main.py)                                                   │
│  ├── StaticFiles  "/"                          → serves the SPA           │
│  └── API routers  "/api/*"                     → Pydantic in / out        │
├───────────────────────────────────────────────────────────────────────────┤
│  AGENT LAYER                                                              │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │ PromptBuilder   │  │ Orchestrator     │  │ AnalyticsExtractor       │  │
│  │ composes system │─▶│ turn loop +      │  │ transcript → structured  │  │
│  │ prompt from     │  │ tool dispatch    │  │ record (messages.parse)  │  │
│  │ modules + facts │  │ + error recovery │  │                          │  │
│  └─────────────────┘  └────────┬─────────┘  └──────────────────────────┘  │
├────────────────────────────────┼──────────────────────────────────────────┤
│  TOOL LAYER  (app/agent/tools.py — schemas + dispatch)                    │
│   update_lead_profile · check_slot_availability · book_site_visit ·       │
│   escalate_to_human · set_contact_preference                              │
├────────────────────────────────┼──────────────────────────────────────────┤
│  SERVICE LAYER (deterministic, unit-tested, no LLM)                       │
│   BookingService (slots, validation, failure injection)                    │
│   CrmService     (escalation tickets, DNC register, lead record)          │
│   LeadScorer     (rule-based hot/warm/cold + 0-100 score)                  │
├────────────────────────────────┼──────────────────────────────────────────┤
│  INFRASTRUCTURE                                                           │
│   SessionStore (Protocol) ──▶ InMemorySessionStore   [Redis-ready]        │
│   LLMClient    (Protocol) ──▶ GeminiClient / AnthropicClient (D14)        │
└────────────────────────────────┼──────────────────────────────────────────┘
                                 ▼
                Gemini API (primary) or Anthropic API (fallback) — LLM_PROVIDER
```

**Why layered this way:** the Forward Deployed Engineer reality is that a customer will want to
swap the model, swap the session store for Redis, and point the booking tool at their real CRM.
Those three seams are the only abstractions in the codebase. Everything else is concrete.

---

## 3. Application Flow

### 3.1 Session start

```
Browser                     FastAPI                  Agent                Store
   │  POST /api/session       │                        │                    │
   │  {channel:"chat"}        │                        │                    │
   ├─────────────────────────▶│                        │                    │
   │                          │  create Session        │                    │
   │                          ├───────────────────────────────────────────▶│
   │                          │  PromptBuilder.build(channel)               │
   │                          ├──────────────────────▶│                    │
   │                          │  ◀── system prompt ────┤                    │
   │  ◀── {session_id,        │                        │                    │
   │       greeting}          │                        │                    │
```

The greeting is a **static, prompt-authored opener** (per channel, per default language) — not a
model call. It removes a round-trip from first paint and guarantees the opener is exactly the one
we tested.

### 3.2 A conversation turn (the core loop)

```
1.  POST /api/chat {session_id, message}
2.  Load session → history, lead profile, tool events
3.  Guardrails: length cap (2000 chars), rate limit, session-ended check
4.  Append user message to history
5.  ── AGENT LOOP (max 4 iterations) ───────────────────────────────────
    a. client.messages.create(
         model=CHAT_MODEL,
         system=[{ text: SYSTEM_PROMPT, cache_control:{type:"ephemeral"} },
                 { text: LIVE_STATE_BLOCK }],          # volatile → after cache point
         messages=history,
         tools=TOOL_SCHEMAS,
         max_tokens=1024,
         output_config={"effort": "low"},
       )
    b. stop_reason == "end_turn"  → break
    c. stop_reason == "tool_use"  →
         • append assistant content (all blocks) to history
         • execute EVERY tool_use block
         • apply side effects to session state
         • record ToolEvent{name, input, output, ok, latency_ms}
         • append ALL tool_results in ONE user message
         • loop
    d. iteration cap reached → force a graceful close, flag for escalation
6.  Extract final text → append to history
7.  Persist session
8.  Return {reply, tool_events, lead_profile, stage, turn_id}
```

**Iteration cap of 4** is deliberate: the realistic maximum is
`update_lead_profile` → `check_slot_availability` → `book_site_visit` → final text. A fifth
iteration means the model is stuck, and the honest response is a graceful close plus escalation,
not an unbounded loop.

### 3.3 Session end and analytics

```
POST /api/session/{id}/end
  → mark ended, stop accepting turns
  → AnalyticsExtractor:
        client.messages.parse(
          model=ANALYTICS_MODEL,
          output_format=ConversationAnalytics,      # Pydantic → validated
          messages=[{role:"user", content: rendered_transcript + tool_event_log}],
          system=ANALYTICS_PROMPT,
          max_tokens=4096,
        )
  → overwrite model-derived fields with deterministic ground truth:
        site_visit_status, booking_reference, escalated_to_human,
        contact_preference, turn_count, duration  ← from tool events, not the model
  → LeadScorer.score(record) → interest_level, qualification_score
  → cache on session; return record
```

**Why we overwrite:** the model is good at reading intent from a transcript and bad at being an
authoritative record of what the system did. Anything the code knows for certain (did the booking
tool actually succeed?) comes from the tool-event log. The model only supplies what is genuinely
inferential — budget, timeline, sentiment, objections, summary.

### 3.4 Conversation stage machine

The model owns the flow; the code merely observes the stage it reports via `update_lead_profile`,
for analytics and UI.

```
                    ┌──────────┐
                    │ GREETING │
                    └────┬─────┘
                         ▼
                  ┌─────────────┐
             ┌───▶│  DISCOVERY  │◀──┐
             │    └──────┬──────┘   │
             │           ▼          │
             │   ┌───────────────┐  │
             │   │ QUALIFICATION │──┘
             │   └───────┬───────┘
             │           ▼
             │   ┌────────────────────┐
             └───│ OBJECTION_HANDLING │
                 └─────────┬──────────┘
                           ▼
                   ┌───────────────┐
                   │    BOOKING    │
                   └───────┬───────┘
                           ▼
     ┌─────────────────────┴─────────────────────┐
     ▼            ▼            ▼          ▼      ▼
 CONFIRMED   CALLBACK_    NOT_        ESCALATED  DO_NOT_
             SCHEDULED    INTERESTED             CONTACT
     └─────────────┴────────────┴──────────┴──────────┘
                              ▼
                            ENDED   → analytics
```

Terminal states are absorbing: once `DO_NOT_CONTACT` or `NOT_INTERESTED` is set, the prompt
forbids further sales content. `DO_NOT_CONTACT` additionally short-circuits in code — the
orchestrator returns a fixed acknowledgement without an LLM call.

---

## 4. Prompt Architecture

The single most important design decision in this project: **the prompt is source code**, so it is
modular, versioned, reviewable, and rendered deterministically.

```
prompts/modules/
  00_identity.md        Persona, company, role, tone, turn-length discipline
  10_knowledge_base.md  {{ rendered from data/project_facts.yaml }}
  20_language.md        English / Hindi / Hinglish mirroring rules + worked examples
  30_qualification.md   BANTL framework, one-question-per-turn, value-for-information trade
  40_objections.md      12-objection playbook: acknowledge → respond → soft next step
  50_edge_cases.md      Busy · uninterested · callback · DNC · unknowns · booking failure ·
                        escalation · closing
  60_guardrails.md      Prime directive, unknown register, never-do list, safety rails
  70_channel_chat.md    Chat adapter: formatting, ≤60 words
  71_channel_voice.md   Voice adapter: no markup, number verbalisation, ≤35 words, ASR tolerance
```

`PromptBuilder.build(channel)` concatenates `00`–`60`, then exactly one of `70`/`71`, injecting
the rendered facts table. `scripts/export_prompt.py` writes the fully-rendered result to
`prompts/FINAL_PROMPT.md` (both channel variants) so the repo contains the single "final prompt"
the assignment asks for, always in sync with what the code actually sends.

**Ordering rationale:** identity → facts → language → method → objections → edge cases →
guardrails. Guardrails sit last because recency matters, and the channel adapter sits after them
because it is the narrowest, most format-specific instruction.

**Caching:** modules `00`–`71` are byte-stable for a given channel — under the original Anthropic
design this formed an inline cached prefix (`cache_control: {"type": "ephemeral"}`), sent fresh but
priced once. Gemini's caching is a separate stateful resource (`client.aio.caches.create`, TTL-
bound) rather than an inline per-request flag; explicit caching is **not used in v1** (rules.md
A15) given the 24-hour build scope, so the composed system prompt plus volatile per-turn state
(current lead profile, today's date, booking window) is sent as one `system_instruction` string
every turn. The tool list is still built once at import time and never reordered.

---

## 5. Tool Design

Five tools, declared as `types.Tool(function_declarations=[...])` with an explicit `required`
list per parameter schema (rules.md A5). **Correction from the pre-D13 draft of this section:**
there is no Gemini equivalent of OpenAI/Anthropic's `strict: true` /
`additionalProperties: false` — the live API rejects an `additional_properties` field on a tool
parameter schema outright (`400 INVALID_ARGUMENT`, "Unknown name additional_properties ... Cannot
find field"), caught by a live call during Phase 3, not by inspection. `required` is the only
closed-schema guard Gemini function-calling actually offers.

| Tool | Purpose | Returns |
|---|---|---|
| `update_lead_profile` | Slot-fill what the customer revealed: name, phone, budget range, configuration, purpose, timeline, authority, location fit, language, stage | `{ok, profile}` |
| `check_slot_availability` | Look up open site-visit windows for a date | `{available: bool, slots: [...], nearest_alternatives: [...]}` |
| `book_site_visit` | Attempt the booking | Success `{ok:true, reference, date, slot}` · Failure `{ok:false, error_code, message, alternatives?}` |
| `escalate_to_human` | Hand off | `{ok, ticket_id, callback_window}` |
| `set_contact_preference` | `ok` / `callback_later` (with time) / `do_not_contact` | `{ok, preference}` |

**Design notes**

- `update_lead_profile` is intentionally a *tool* rather than post-hoc extraction. It forces the
  model to commit explicitly to what it believes it has learned, which makes memory failures
  visible in the tool trace instead of silent.
- Tool failures return `is_error: true` **with a conversational recovery hint**, e.g.
  `"Slot unavailable. Offer the customer 11:30 or 15:00 on the same day."` The model is far better
  at recovering when the error tells it what to do next.
- Parallel tool calls are supported: all results go back in a **single** user message. Splitting
  them across messages silently teaches the model to stop batching.
- Tool inputs are always read as parsed dicts, never string-matched.

---

## 6. Folder & File Structure

```
AgentBot/
├── README.md                       Run instructions, assumptions, limitations, AI tools
├── PRD.md                          What we are building and for whom
├── Architecture.md                 This file
├── rules.md                        Engineering rules and AI boundaries
├── phases.md                       Time-boxed delivery plan
├── design.md                       Colour, type, spacing, components
├── memory.md                       Live state tracker — updated every phase
│
├── .env.example                    GEMINI_API_KEY= (empty) + tunables
├── .gitignore                      .env, __pycache__, .venv, *.log
├── requirements.txt                6 production deps + 3 dev deps
│
├── app/
│   ├── __init__.py
│   ├── main.py                     FastAPI app, CORS, static mount, exception handlers
│   ├── config.py                   pydantic-settings — all env access lives here
│   ├── models.py                   Pydantic: requests, responses, domain, analytics
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── session.py              POST /api/session · POST /api/session/{id}/end
│   │   ├── chat.py                 POST /api/chat
│   │   └── analytics.py            GET /api/session/{id}/analytics · /transcript
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── prompt_builder.py       Compose modules + facts → system prompt
│   │   ├── orchestrator.py         Turn loop, tool dispatch, error recovery
│   │   ├── tools.py                Tool schemas + dispatch table + side effects
│   │   └── analytics.py            Transcript → ConversationAnalytics (response_schema)
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py                 LLMClient Protocol + provider-neutral ToolSpec/LLMResponse (D14)
│   │   ├── gemini_client.py        google-genai SDK impl: retries, timeouts, usage
│   │   └── anthropic_client.py     anthropic SDK impl — fallback provider (D14)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── booking.py              Slot logic, validation, deterministic failure injection
│   │   ├── crm.py                  Escalation tickets, DNC register, lead records
│   │   └── scoring.py              Rule-based lead scoring
│   │
│   ├── store/
│   │   ├── __init__.py
│   │   ├── base.py                 SessionStore Protocol
│   │   └── memory_store.py         Dict-backed, TTL sweep
│   │
│   └── static/
│       ├── index.html
│       ├── styles.css              Design tokens from design.md
│       └── app.js                  Fetch, render, tool trace, analytics panel
│
├── prompts/
│   ├── FINAL_PROMPT.md             Generated — the assignment deliverable
│   └── modules/                    00_identity … 71_channel_voice (see §4)
│
├── data/
│   └── project_facts.yaml          Known facts + unknown/deflection register
│
├── scripts/
│   ├── export_prompt.py            Render FINAL_PROMPT.md
│   └── run_scenarios.py            Live scenario runner → docs/TEST_RESULTS.md
│
├── tests/
│   ├── conftest.py
│   ├── fakes.py                    FakeLLMClient — scripted, deterministic
│   ├── test_prompt_builder.py      Facts present, channel rules applied, no placeholders
│   ├── test_booking.py             Slots, validation, every failure mode
│   ├── test_orchestrator.py        Tool loop, parallel results, iteration cap, error path
│   ├── test_scoring.py             Hot/warm/cold boundaries
│   ├── test_api.py                 Endpoint contracts, guardrails, DNC short-circuit
│   └── scenarios/                  *.yaml — input · expected behaviour · assertions
│
└── docs/
    ├── TEST_RESULTS.md             Generated — input / expected / actual
    └── DEMO_SCRIPT.md              Shot list for the demo video
```

---

## 7. Tech Stack

### Backend

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Assignment mandate; `|` union syntax, `StrEnum` |
| Web framework | **FastAPI** | **Mandated.** Also: Pydantic-native, auto OpenAPI docs at `/docs` |
| Server | Uvicorn | FastAPI's reference server; one command to run everything |
| Validation | Pydantic v2 | Request/response contracts **and** the analytics output schema |
| Config | pydantic-settings | Typed env loading; single place env vars are read |
| LLM SDK | `google-genai` (primary) + `anthropic` (fallback, D14) | Typed errors, structured output, function calling on both; `LLM_PROVIDER` selects the active one |
| Facts file | PyYAML | Human-editable knowledge base a non-engineer can review |

### Model configuration

| Setting | Value | Rationale |
|---|---|---|
| `CHAT_MODEL` | `gemini-3.6-flash` | Verified live 2026-08-24 against the real API — the first-guess default (`gemini-2.5-flash`) turned out retired for new accounts; the API's own error named this replacement |
| Chat `thinking_config.thinking_level` | `low` | Conversational turns need speed, not deliberation |
| `max_output_tokens` (chat) | `1024` | Turns are capped at 60 words. Deliberately short output |
| `ANALYTICS_MODEL` | `gemini-3.6-flash` | Same model as chat, **not by design** — the test account's free tier has zero quota for any `pro`-tier model (confirmed live). A paid tier can restore a stronger analytics model via `.env` alone |
| Analytics `thinking_config.thinking_level` | `medium` | Structured extraction over a full transcript benefits from more deliberation than a chat turn |
| `max_output_tokens` (analytics) | `4096` | Full structured record |
| Timeout | 30 s chat / 60 s analytics, via `http_options.timeout` (ms) | Bounded turn latency; the SDK has no chat-appropriate default |
| Retries | explicit `http_options.retry_options=HttpRetryOptions(attempts=3)` | `google-genai` does not retry by default, unlike the Anthropic SDK used previously — this must be set, not assumed |

Both model IDs are environment variables. A customer who wants a cheaper or faster tier — or who
has billing that unlocks `pro`-tier quota — changes `.env`, not code.

**Explicitly not used in v1:** `temperature`/`top_p`/`top_k` (thinking level is the tuning lever
instead), streaming (deferred), explicit context caching (rules.md A15 — a documented
simplification, not an oversight), compaction (sessions never approach the context window).

### Frontend

| Concern | Choice | Why |
|---|---|---|
| Framework | **None** — vanilla HTML/CSS/JS | A reviewer must not run `npm install`. Zero build step is a feature, not a shortcut |
| Serving | `StaticFiles` mounted at `/` | One process, one port, one command |
| Styling | Hand-written CSS with custom properties | Tokens come straight from `design.md`; light + dark from the same variables |
| Fonts | Google Fonts (Plus Jakarta Sans, Noto Sans Devanagari, JetBrains Mono) | Devanagari coverage is a functional requirement, not decoration |
| State | Plain JS object + `localStorage` for the channel toggle | The server owns conversation state |

### Development

pytest · pytest-asyncio · httpx (FastAPI `TestClient`) · ruff (lint + format).

---

## 8. API Contract

Base: `/api`. All responses are JSON. All errors use one envelope.

### `POST /api/session`
```jsonc
// request
{ "channel": "chat" }                  // "chat" | "voice"
// 201
{ "session_id": "uuid", "channel": "chat",
  "greeting": "Hi! This is Aarav from Northstar Homes …",
  "started_at": "2026-08-23T18:04:11Z" }
```

### `POST /api/chat`
```jsonc
// request
{ "session_id": "uuid", "message": "2 BHK ka rate kya hai?" }
// 200
{ "session_id": "uuid",
  "turn_id": 3,
  "reply": "2 BHK ki starting price ₹1.35 crore onwards hai …",
  "stage": "QUALIFICATION",
  "lead_profile": { "budget_max_inr": 15000000, "primary_configuration": "2BHK", … },
  "tool_events": [
    { "name": "update_lead_profile", "input": {…}, "output": {…},
      "ok": true, "latency_ms": 2 }
  ],
  "session_ended": false,
  "usage": { "input_tokens": 210, "cache_read_input_tokens": 3480, "output_tokens": 96 } }
```

### `POST /api/session/{id}/end`
```jsonc
// 200 → the full ConversationAnalytics record (PRD §7)
```

### `GET /api/session/{id}/analytics`
```jsonc
// 200 → the same cached ConversationAnalytics record end returned; 404 analytics_not_available
// if the session hasn't been ended yet — a distinct code from session_not_found (both 404)
```

### `GET /api/session/{id}/transcript`
```jsonc
// 200
{ "session_id": "uuid",
  "messages": [ /* provider-neutral shape, app/llm/base.py — not raw Gemini/Anthropic wire types */ ],
  "tool_events": [ { "name": "book_site_visit", "input": {…}, "output": {…}, "ok": true, … } ] }
```

### `GET /health`

### Error envelope
```jsonc
{ "error": { "code": "session_not_found",     // machine-readable
             "message": "Session has expired or does not exist.",
             "request_id": "req_018Ee…" } }   // for support correlation
```

| HTTP | `code` | When |
|---|---|---|
| 400 | `invalid_request` | Body fails validation, message > 2000 chars |
| 404 | `session_not_found` | Unknown or expired session |
| 404 | `analytics_not_available` | `GET /analytics` called before the session has ended |
| 409 | `session_ended` | Turn attempted after end |
| 429 | `rate_limited` | Per-session token bucket exhausted |
| 502 | `llm_unavailable` | Upstream failed after retries |
| 500 | `internal_error` | Anything else — never leaks a stack trace |

---

## 9. Error Handling Strategy

| Failure | Handling |
|---|---|
| `ClientError` (`.status == "RESOURCE_EXHAUSTED"`) | Explicit retry (rules.md A12); on final failure → 502 + in-language "one moment, technical issue" reply |
| `ServerError` / other `ClientError` | Explicit retries via `retry_options`; then degraded reply + auto-escalate + `follow_up_required = true` |
| `(httpx.TimeoutException, httpx.ConnectError, httpx2.TimeoutException, httpx2.ConnectError)` | Same degraded path. The customer is never shown a stack trace or an English error in a Hindi conversation |
| `ClientError` (`.status` `"UNAUTHENTICATED"`/`"PERMISSION_DENIED"`) | Fail fast at startup with a clear message naming `GEMINI_API_KEY` — not on the first user message. Note: an invalid key returns `.status == "INVALID_ARGUMENT"` (code 400), not an auth-specific status — verified live, not assumed |
| Tool raises | Caught in dispatch → `tool_result` with `is_error: true` + recovery hint. The conversation continues |
| Booking failure | A **domain outcome**, not an exception. Structured `{ok:false, error_code}`. F-10 |
| Iteration cap hit | Graceful close, `escalated_to_human = true`, logged as an anomaly |
| Analytics parse failure | One retry; then a partial record built from deterministic fields only, with `summary = "Analytics extraction failed"` — never a fabricated record |
| Malformed client request | Pydantic → 400 with field detail |

Exception chains are ordered most-specific-first (`NotFoundError` → `RateLimitError` →
`APIStatusError` → `APIConnectionError`); a single broad `except APIStatusError` would erase the
retryable/non-retryable distinction.

**Logging:** structured JSON, one line per turn, carrying `session_id`, `turn_id`, `stage`,
`latency_ms`, token usage, and `_request_id`. **Phone numbers are masked to the last four digits
in every log line.** Prompts and full transcripts are never logged at INFO.

---

## 10. Data Models (shape only — full definitions live in `app/models.py`)

```
Session
  id · channel · created_at · ended_at · language_hint
  messages: list[dict]                  # provider-neutral shape (app/llm/base.py) — see D14
  lead: LeadProfile
  tool_events: list[ToolEvent]
  stage: Stage
  contact_preference: ContactPreference
  analytics: ConversationAnalytics | None

LeadProfile
  name · phone · budget_min_inr · budget_max_inr · configuration_interest[] ·
  primary_configuration · purpose · timeline · decision_authority · location_fit ·
  language_preference · notes[]

ToolEvent
  name · input · output · ok · error_code · latency_ms · at

BookingResult
  ok · reference · date · slot · error_code · message · alternatives[]

ConversationAnalytics
  … PRD §7, as a Pydantic model passed as `response_schema`, read from `response.parsed`
```

`Session.messages` stores a provider-neutral shape (D14, superseding the original Gemini-only
design): `{"role":"user","text"}` · `{"role":"assistant","text","tool_calls":[{"id","name","args",
"extra"}]}` · `{"role":"tool_result","results":[{"id","name","output"}]}`. Each `LLMClient`
implementation translates to/from its own wire format entirely inside itself — the orchestrator
and storage never see a Gemini `Content`/`Part` or an Anthropic `MessageParam` directly. `extra` is
an opaque per-provider passthrough bag (e.g. Gemini's `thought_signature`, required verbatim on
the next request or the live API rejects the turn — caught live during the D14 build, not
documented up front). Rewriting a provider's own tool-call representation into a bespoke format
and back within its client is still the classic source of tool-loop corruption; that discipline
just moved one layer down from where it lived pre-D14.

---

## 11. Security & Privacy

- **Secrets:** only ever from the environment via `config.py`. `.env` is gitignored before the
  first commit; `.env.example` carries empty values. No key is ever logged or returned.
- **PII:** names and phone numbers stay in process memory for the session lifetime (2-hour TTL,
  then swept). Phones are masked in logs. The only third party that sees conversation content is
  Google (Gemini API) — disclosed in the README.
- **Input hardening:** 2000-char cap, per-session token-bucket rate limit, JSON-only bodies.
- **Prompt injection:** customer text is only ever a `user` message — never concatenated into the
  system prompt. Operator instructions never travel through user content.
- **CORS:** locked to configured origins; defaults to same-origin only.
- **Output:** the UI renders agent text as `textContent`, never `innerHTML`. No XSS surface.

---

## 12. Testing Architecture

**Tier 1 — deterministic (no API key, runs in CI, < 2 s)**
`FakeLLMClient` replays scripted responses including `tool_use` blocks. Covers the orchestrator
loop, parallel tool results, the iteration cap, error paths, booking rules, validation, scoring,
prompt composition, and every API contract.

**Tier 2 — live behavioural (needs a key, run manually)**
`scripts/run_scenarios.py` drives real conversations against the real model from
`tests/scenarios/*.yaml`. Each scenario declares:

```yaml
id: booking_failure_slot_taken
requirement: F-10
channel: chat
setup: { force_booking_failure: slot_unavailable }
turns:
  - user: "Saturday 3pm site visit book kar do"
expect:
  must_not:  ["confirmed", "booked successfully", "पक्का हो गया"]
  must:      ["alternative", "another"]
  analytics: { site_visit_status: "attempted_failed" }
```

Assertions are keyword/regex/analytics-field based — deliberately not an LLM judge, so results are
reproducible and auditable. The runner writes **input · expected behaviour · actual output** to
`docs/TEST_RESULTS.md`, which is the assignment's test-case deliverable.

---

## 13. Deployment & Runtime

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # add GEMINI_API_KEY
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000        UI
# → http://localhost:8000/docs   OpenAPI
```

Single process, single port, no external services. Sessions live in process memory and vanish on
restart — correct for a demo, and the `SessionStore` Protocol is the documented seam for Redis.

---

## 14. Key Decisions & Trade-offs

| # | Decision | Alternative | Why |
|---|---|---|---|
| D1 | Vanilla JS frontend | React + Vite | Reviewer runs one command. A build step risks the "whether the bot works" criterion for zero behavioural gain |
| D2 | In-memory sessions | Redis / SQLite | No behaviour depends on persistence. The Protocol seam makes the upgrade a 40-line file |
| D3 | Manual tool loop | SDK beta `tool_runner` | We need per-tool side effects on session state and a UI-visible event trace, with no beta dependency. The loop is ~30 readable lines |
| D4 | Model tools for booking | Regex/intent parsing | Tool use *is* the agent behaviour being evaluated, and it makes booking failure inspectable |
| D5 | Modular prompt + generated `FINAL_PROMPT.md` | One hand-written prompt file | Reviewable and diffable per concern; the export guarantees the committed prompt is the one actually sent |
| D6 | Deterministic overwrite of analytics facts | Trust the model's record | The model infers intent well and reports system state badly. Booking status must come from the booking service |
| D7 | Static greeting | Model-generated opener | Removes a round-trip and guarantees the tested opener |
| D8 | Two model calls per session (chat + analytics) | One call doing both | Separation keeps the chat prompt free of extraction instructions that would leak into conversation |
| D9 | `effort: low` for chat, not a smaller model | Downgrade to a faster tier | Keeps the strongest instruction-following for the anti-hallucination requirement; effort is the correct latency lever |
| D10 | Failure injection via env + tool input | Random failures | A demo video needs failure **on cue**; randomness is unrecordable |
| D13 | `google-genai` (Gemini) instead of `anthropic` (Claude) | Stay on Anthropic | User's explicit choice after the Anthropic test account hit a billing block mid-Phase-2; `LLMClient` was the designed-for swap seam. Fixed a real bug in the same change: the Protocol previously leaked Anthropic-specific types into its signature instead of being genuinely provider-neutral |
| D14 | Reinstate `anthropic` as an explicit fallback (`LLM_PROVIDER=anthropic`), built before Phase 6 | Wait until Gemini quota actually blocks P6/P7, then build reactively | The Gemini free-tier daily quota was already hit twice in P3; P6's ~19-scenario suite and P7's iterative re-runs need far more volume. Built proactively so a mid-phase quota wall is a config change, not a stop-and-code interruption. Required making `LLMClient` genuinely provider-neutral (project-owned `ToolSpec`/`ToolCallRequest`/`LLMResponse` types, `session.messages` no longer Gemini `Content` blocks) rather than leaving it honestly Gemini-specific as D13 did — the right time for that abstraction is when a second provider is actually needed |
