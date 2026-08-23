# Project Memory — Northstar Agent

**This is the live state tracker. It is the first file to read when picking work up, and the last
file to write before putting work down.**

**Last updated:** 2026-08-24 01:15 IST
**Current phase:** P1 — Knowledge Base & Prompt v1 (gate passed)
**Overall status:** P0–P1 complete · P2 not begun
**Elapsed:** ~4.5 h of 24 h · **Remaining:** ~19.5 h

---

## How to use this file

Update it at **every phase gate** — before starting the next phase, never in a batch at the end
(`rules.md` AI7). A stale tracker is worse than no tracker, because it is trusted.

Update rules:
1. **Currently Working On** (§3) has exactly one entry. If it has none, work is not in progress.
2. **Completed Log** (§2) is append-only. Never rewrite history; if something was wrong, add a
   correcting entry with the date.
3. Any decision that changes the shape of the deliverable gets a **Decision Log** (§5) row the
   moment it is made — not later, when the reasoning has evaporated.
4. **Blockers** (§6) beat everything. A blocker with no owner and no next action is not recorded
   properly.
5. Commit `memory.md` in the same commit as the work it describes (`rules.md` G4).

---

## 1. Progress Board

| Phase | Name | Box | Status | Gate passed |
|---|---|---|---|---|
| — | Assignment analysis | — | Done | 2026-08-23 |
| — | Foundation documents (these six) | — | Done | 2026-08-23 |
| P0 | Foundation & Scaffolding | 1.0 h | Gate passed | 2026-08-24 |
| P1 | Knowledge Base & Prompt v1 | 3.0 h | Gate passed | 2026-08-24 |
| P2 | Agent Core & Chat API | 2.5 h | Not started | — |
| P3 | Tools & Booking Simulation | 2.0 h | Not started | — |
| P4 | Web Interface | 2.5 h | Not started | — |
| P5 | Analytics Engine | 2.0 h | Not started | — |
| P6 | Test Harness & Scenarios | 2.5 h | Not started | — |
| P7 | Prompt Hardening | 3.0 h | Not started | — |
| P8 | Docs, Demo Video & Submission | 2.5 h | Not started | — |

Status values: `Not started` · `In progress` · `Gate passed` · `Blocked` · `Descoped`

### Feature status

| ID | Feature | Phase | Status |
|---|---|---|---|
| F-01 | Natural sales conversation | P1, P2 | Prompt written (P1) — not yet exercised live |
| F-02 | Multilingual & code-switching | P1, P7 | Prompt written (P1) — not yet exercised live |
| F-03 | Lead qualification (BANTL) | P1, P3 | Prompt written (P1) — tool wiring is P3 |
| F-04 | Conversation memory | P2 | Not started |
| F-05 | Grounded answers / anti-hallucination | P1, P7 | Prompt written (P1) — hardening is P7 |
| F-06 | Objection handling | P1, P7 | Prompt written (P1) — hardening is P7 |
| F-07 | Busy / uninterested / call-later | P1 | Prompt written (P1) — not yet exercised live |
| F-08 | Do-not-contact compliance | P1, P3 | Prompt written (P1) — code short-circuit is P3 |
| F-09 | Site-visit booking | P3 | Not started |
| F-10 | Booking-failure recovery | P3, P7 | Not started |
| F-11 | Human escalation | P3 | Not started |
| F-12 | Proper conversation ending | P1 | Prompt written (P1) — not yet exercised live |
| F-13 | Channel duality (chat / voice) | P1, P7 | Prompt written (P1) — hardening is P7 |
| F-14 | Post-conversation analytics | P5 | Not started |
| F-15 | Web chat interface | P4 | Not started |
| F-16 | Test evidence | P6 | Not started |

---

## 2. Completed Log

Append-only. Newest last.

### 2026-08-23 · 23:26 IST — Assignment analysis

Read the three screenshot pages of the Huvo AI Forward Deployed Engineer brief and recorded the
extracted requirements in `image_analysis.md`. Re-verified the transcription against the original
images before planning, so the requirement set is confirmed first-hand rather than inherited.

**Established constraints:** FastAPI backend mandatory · 24-hour deadline · prompt engineering is
the primary evaluation axis · one prompt must serve both chat and voice · English / Hindi /
Hinglish · must not invent prices, discounts, availability, or any unprovided information ·
deliverables are a public repo (final prompt, source, README, `.env.example`), a demo video, and a
README covering run steps, assumptions, limitations, and AI tools used.

### 2026-08-23 · 23:45 IST — Foundation documents complete

Produced all six mandatory planning documents.

| File | What it fixes |
|---|---|
| `PRD.md` | 16 features (F-01…F-16) with acceptance criteria · 6 personas · the known-facts table and the twelve-category unknown/deflection register · the full analytics schema · success metrics · 8 risks · a traceability matrix mapping every assignment bullet to a feature and a test |
| `Architecture.md` | Layered system design · turn-loop and analytics flows · conversation stage machine · modular prompt architecture · 5 tool definitions · full folder tree · tech stack with model configuration · API contract · error-handling strategy · 10 recorded decisions |
| `rules.md` | Approved and banned stack · 15 Anthropic API rules · 10 prompt rules · 11 code rules · 7 testing rules · 5 git rules · 10 AI-assistance boundaries · definition of done |
| `phases.md` | 9 phases, 21 h planned + 3 h reserve, each with an exit gate and a named descope · critical path · descope ladder with a do-not-cut line |
| `design.md` | "Warm Premium Trust" theme · full light and dark token palettes with contrast targets · Plus Jakarta Sans + Noto Sans Devanagari + JetBrains Mono with stack-ordering rationale · 1.250 type scale · 10 typography guidelines · component specs · WCAG 2.2 AA rules |
| `memory.md` | This tracker |

**Verified during writing:** current Anthropic Python SDK usage — adaptive thinking and
`output_config.effort` in place of the removed `budget_tokens`; `messages.parse(output_format=…)`
for structured analytics; `strict: true` tool schemas; the prompt-caching prefix rules; and the
specific-first exception chain. These are recorded as rules A1–A15 so they are not re-derived later.

### 2026-08-24 · 00:10 IST — Phase 0 gate passed

`git init -b main`; `.gitignore` (`.env`, `__pycache__/`, `*.pyc`, `.venv/`, `*.log`, `.DS_Store`,
`.obsidian/`) committed alone as the root commit on `main` (rule G1), verified via `git log`.
Created branch `phase-0` off `main` for the rest of the scaffolding.

Implemented: `.env.example` (all seven tunables from `phases.md` P0 task 2); `requirements.txt`
(six production deps + pytest, pytest-asyncio, ruff); `app/config.py` (`pydantic-settings`
`Settings`, fail-fast at import time on a missing `ANTHROPIC_API_KEY` with one named-variable
message, no traceback); `app/main.py` (FastAPI app, CORS from `ALLOWED_ORIGINS`, `GET /health`,
static mount, structured JSON logging with a phone-masking `logging.Filter`); `ruff.toml`.

**Bug caught and fixed before commit:** the first `PhoneMaskingFilter` masked `record.msg`, which
is the raw `%s` template, not the interpolated string — so a phone number passed as a lazy `%s`
arg (the recommended logging pattern) never actually got masked. Fixed by masking
`record.getMessage()` and clearing `record.args`. Caught by manually emitting a log line and
reading the JSON output, not by static review — a template-vs-interpolated-string bug like this is
invisible without executing the log call.

**Exit gate verified live, not just by reading the code:**
- `python -c "from app.main import app"` with no `ANTHROPIC_API_KEY` set → one clean sentence
  naming the variable, exit code 1, no traceback.
- `uvicorn app.main:app` with a fake key → `GET /health` → 200 `{"status":"ok"}`; `GET /docs` →
  200.
- `ruff check .` and `ruff format --check .` clean after one auto-format pass (two lines over the
  100-char limit).
- `pip install -r requirements.txt` into a fresh `.venv` succeeded with no version conflicts.

`app/main.py` lifespan is an intentional no-op with `# TODO(P2): construct the LLMClient and
SessionStore singletons here` — those seams don't exist until Phase 2.

### 2026-08-24 · 01:15 IST — Phase 1 gate passed

Branch `phase-0` renamed to `p0-p4` (this branch now carries Phases 0–4 through to the Web UI).

`data/project_facts.yaml`: the five known facts and all twelve deflection categories, copied
verbatim from `PRD.md` §5.1/§5.2 — nothing invented (rule P2). Wrote all nine prompt modules
(`Architecture.md` §4), each with the required worked example(s): `20_language.md` has all three
scripts plus a mid-conversation switch; `40_objections.md` covers all twelve PRD F-06 objections
verbatim, each with one sample line; `50_edge_cases.md` covers all eight required cases.

`app/agent/prompt_builder.py`: loads `project_facts.yaml`, renders `{{PLACEHOLDER}}` tokens (a
small regex substitution — no Jinja2, to stay inside the six-dependency budget) across every
module, not just `10_knowledge_base.md`, so no prompt module hand-types a fact PR2 says must be
rendered. Raises `KeyError` on any placeholder with no matching value, so a typo'd placeholder
fails the build instead of shipping literal `{{TEXT}}` into the system prompt. `build(channel)` is
`lru_cache`d per `Architecture.md` §4 ("cache the composed string per channel").
`scripts/export_prompt.py` writes both variants to `prompts/FINAL_PROMPT.md` with a generated/
do-not-edit banner (rule PR6).

**Two real bugs found and fixed during the manual read-through (rule AI10), not by a tool:**
1. `00_identity.md` hardcoded "Northstar One" once instead of using `{{PROJECT_NAME}}` — a literal
   PR2 violation (a fact typed instead of rendered) that no test would have caught, since the
   literal text happens to match the current YAML value.
2. `71_channel_voice.md` had a typo — "asterrisk" — inside the one worked example in that module.

**Token budget:** initial draft was ~5,050 tokens (chat) / ~5,220 (voice), over the 2,500–4,500
target (`phases.md` P1 exit gate). Trimmed by cutting restated guardrail prose from
`40_objections.md`/`50_edge_cases.md` (the rule already lives once in `60_guardrails.md` — repeating
it per-entry was tokens not doing work, per rule AI10) and removing a duplicated prime-directive
quote block. Final, char-count-estimated (`len(prompt) // 4`, no live tokenizer call was made — no
API key used this phase): **chat ≈ 4,306 tokens, voice ≈ 4,482 tokens.** Both inside target.

`tests/conftest.py` implemented (was a stub) — inserts the repo root onto `sys.path` so `import
app.*` resolves whether pytest is invoked as `pytest` or `python -m pytest`; without it, bare
`pytest` failed with `ModuleNotFoundError` even though `python -m pytest` passed. A reviewer is
more likely to type the bare form.

**Verified live:**
- `python scripts/export_prompt.py` writes both variants; zero unrendered `{{...}}` in the output.
- `pytest` (bare invocation) — 9/9 pass, **no `ANTHROPIC_API_KEY` set** (rule T1).
- `ruff check .` / `ruff format --check .` clean.

**Open question resolved:** Q1 (agent name) — used **Aarav**, matching the worked example already
in `Architecture.md` §8's API contract, rather than introducing a different name.
**Still open:** Q2 (inbound/outbound greeting framing) — the static greeting itself is a Phase 2
artifact (`app/api/session.py`), not a Phase 1 module; unresolved until then.

---

## 3. Currently Working On

**File:** *none — between phases*
**Phase:** P1 gate passed; P2 not started
**Next action:** `app/llm/base.py` (`LLMClient` Protocol), then `app/llm/anthropic_client.py`
(SDK wrapper — explicit timeouts, `max_tokens`, `output_config.effort`, prompt caching with the
volatile-state second system block, the A14 exception chain).

> Exactly one entry belongs here at any time. Replace it, do not append.

---

## 4. Next Up (immediate queue)

1. **P2 · `app/llm/base.py` + `anthropic_client.py`** — the `LLMClient` Protocol and the SDK
   wrapper (rules A2–A5, A11–A14).
2. **P2 · `app/models.py`** — `Session`, `LeadProfile`, `ToolEvent`, `Stage`, request/response
   models.
3. **P2 · `app/store/base.py` + `memory_store.py`** — `SessionStore` Protocol + dict-backed store
   with TTL sweep.
4. **P2 · `app/agent/orchestrator.py`** — the turn loop (`Architecture.md` §3.2), no tool dispatch
   yet (that's P3).
5. **P2 · `app/api/session.py`, `app/api/chat.py`** — endpoints, guardrails (2000-char cap, rate
   limit, ended-session check), global exception handlers → the error envelope (§8).
6. **P2 · `tests/fakes.py`** (`FakeLLMClient`) + `tests/test_api.py`.

---

## 5. Decision Log

Seeded from `Architecture.md` §14. Add a row the moment a decision is made.

| ID | Date | Decision | Rejected alternative | Rationale |
|---|---|---|---|---|
| D1 | 2026-08-23 | Vanilla HTML/CSS/JS frontend served by FastAPI | React + Vite | A reviewer must not run `npm`. A build step risks the "whether the bot works" criterion for no behavioural gain |
| D2 | 2026-08-23 | In-memory session store behind a Protocol | Redis / SQLite | No behaviour depends on persistence; the seam makes the upgrade a small file |
| D3 | 2026-08-23 | Manual tool loop | SDK beta `tool_runner` | Needs per-tool side effects on session state and a UI-visible event trace, with no beta dependency; about 30 readable lines |
| D4 | 2026-08-23 | Model tool-calling for booking | Regex / intent parsing | Tool use *is* the agent behaviour being evaluated, and it makes booking failure inspectable |
| D5 | 2026-08-23 | Modular prompt plus generated `FINAL_PROMPT.md` | One hand-written prompt file | Diffable per concern; the export guarantees the committed prompt is the one actually sent |
| D6 | 2026-08-23 | Analytics: deterministic overwrite of system facts | Trust the model's whole record | The model infers intent well and reports system state badly. Booking status must come from the booking service |
| D7 | 2026-08-23 | Static, prompt-authored greeting | Model-generated opener | Removes a round-trip and guarantees the opener we actually tested |
| D8 | 2026-08-23 | Two model calls per session (chat + analytics) | One call doing both | Keeps extraction instructions out of the conversation prompt, where they would leak |
| D9 | 2026-08-23 | `claude-opus-5` with `effort: low` for chat turns | Downgrade to a faster or cheaper tier | Anti-hallucination is the core graded requirement, so keep the strongest instruction-following; `effort` is the correct latency lever on Opus 5 |
| D10 | 2026-08-23 | Deterministic booking-failure injection via `FORCE_BOOKING_FAILURE` | Random failure | A demo video needs the failure to fire on cue; randomness is unrecordable |
| D11 | 2026-08-23 | `update_lead_profile` exposed as a model tool | Post-hoc extraction only | Forces the model to commit to what it believes it learned, making memory failures visible in the tool trace instead of silent |
| D12 | 2026-08-23 | Noto Sans Devanagari second in the font stack | A single Latin family | Plus Jakarta Sans has no Devanagari glyphs; without the fallback every Hindi reply renders as tofu boxes and F-02 fails on camera |

---

## 6. Blockers

*None.*

> Format when one exists: **[date] What is blocked · why · owner · next action · impact on the box.**

---

## 7. Open Questions

| # | Question | Impact | Resolution plan |
|---|---|---|---|
| Q1 | Which agent name and persona presentation? | Cosmetic; affects prompt tone | Decide in P1. Default: a neutral first name, no gendered self-description, since the brief specifies none |
| Q2 | Inbound or outbound framing for the greeting? | Small prompt effect | P1. Default: outbound framing ("you had enquired about…"), since the brief describes an outbound-style sales agent |
| Q3 | Do the Hindi segments of the demo video need subtitles? | Reviewer comprehension | P8. Default: yes — on-screen English gloss for Hindi turns, since the panel may not read Devanagari |

---

## 8. Failure Queue (populated by P6, cleared by P7)

Scenario failures land here from the Phase 6 run and are worked in severity order:
**fabrication > DNC violation > false booking claim > wrong script > missing next step > tone.**

*Empty — Phase 6 has not run.*

| Scenario | Requirement | Severity | Symptom | Owning prompt module | Status |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

---

## 9. Deliverables Tracker

| Deliverable | Phase | Status |
|---|---|---|
| `prompts/FINAL_PROMPT.md` (both channel variants) | P1 | Not started |
| FastAPI backend | P0–P5 | Not started |
| Web chat interface | P4 | Not started |
| `data/project_facts.yaml` | P1 | Not started |
| `docs/TEST_RESULTS.md` | P6, P7 | Not started |
| `README.md` (run · assumptions · limitations · AI tools) | P8 | Not started |
| `.env.example`, no secrets in history | P0, P8 | Not started |
| Demo video | P8 | Not started |
| Public GitHub repo | P8 | Not started |
| Submission email to `aditi@huvo.ai` plus 3 cc | P8 | Not started |

---

## 10. Session Handoff Notes

**For whoever picks this up next — including a future session of me:**

- Read in this order: `memory.md` (§3 and §4) → `phases.md` for the current phase → `rules.md`
  before writing any code.
- The three non-negotiables, in priority order: **never invent a project fact** · **never claim a
  booking that did not succeed** · **stop immediately on a do-not-contact request.** Everything
  else is negotiable under time pressure; these three are not (`phases.md` descope ladder).
- The clock is the real adversary. If a phase overruns its box, take the named descope rather than
  borrowing from Phase 7 — prompt hardening is what makes this submission good rather than merely
  complete.
- `data/project_facts.yaml` is the only place a fact about Northstar One may live. If a number
  appears anywhere else, it is a bug.
