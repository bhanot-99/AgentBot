# Engineering Rules — Northstar Agent

**Status:** Binding. **Version:** 1.0 · 2026-08-23

These rules exist to protect three things: the 24-hour deadline, the evaluation criteria
(prompt quality, agent behaviour, code clarity), and the reviewer's ability to run this in
under two minutes. Every rule below has a reason attached. If a rule blocks something genuinely
necessary, change the rule in this file **first**, with the reason — do not silently violate it.

Rule IDs are stable and referenced from `phases.md` and code review.

---

## 1. The Prime Rules

**P1 — The prompt is the product.**
If a change makes the agent's behaviour harder to read, reason about, or test, it is wrong even
if the code is elegant. When code and prompt can both solve a problem, and the problem is about
*how the agent talks*, solve it in the prompt. When the problem is about *what is true*
(booking rules, validation, scoring), solve it in code.

**P2 — Never invent a fact.**
This applies to the agent **and** to us. No fact about Northstar One may exist anywhere except
`data/project_facts.yaml`. No amenity, area, possession date, RERA number, or discount may appear
in a prompt module, a test fixture, a UI placeholder, a demo script, or the README — not even as
an example. A plausible-looking fabricated fact in a test fixture will end up in the demo.

**P3 — Ship the whole scope, thin.**
Every feature in `PRD.md` §6 must exist in some working form before any feature is deepened.
Breadth first, depth second. A missing requirement is a failed evaluation; a shallow one is not.

**P4 — Optimise for the reviewer's first two minutes.**
Clone → install → one env var → one command → working bot. Anything that adds a step to that path
needs an explicit justification in `Architecture.md`.

---

## 2. Stack — What We Use

| Layer | Approved | Notes |
|---|---|---|
| Language | Python 3.11+ | Type hints on every public function |
| Web | **FastAPI** + Uvicorn | Mandated by the assignment |
| Validation | Pydantic v2 | Requests, responses, domain models, analytics schema |
| Config | pydantic-settings | The **only** place `os.environ` is read |
| LLM | `google-genai` (official SDK) | Never raw `requests`/`httpx` against the API |
| Data | PyYAML | `data/project_facts.yaml` only |
| Frontend | Vanilla HTML + CSS + JS | No framework, no bundler, no transpiler |
| Fonts | Google Fonts | Plus Jakarta Sans · Noto Sans Devanagari · JetBrains Mono |
| Tests | pytest, pytest-asyncio, httpx | `TestClient` for API contracts |
| Lint | ruff | Lint + format. One tool |

**Production dependency budget: 6.** `fastapi`, `uvicorn`, `google-genai`, `pydantic`,
`pydantic-settings`, `pyyaml`. Adding a seventh requires deleting one or amending this table
with a written reason.

**Provider history:** v1 used the `anthropic` SDK (Claude). Switched to `google-genai` (Gemini) —
decision D13, `memory.md` 2026-08-24. The `LLMClient` Protocol (`app/llm/base.py`) is the seam this
swap exercises; it previously leaked Anthropic-specific types into its signature, which was fixed
as part of this switch (see D13's rationale) rather than repeated.

---

## 3. Stack — What We Do Not Use

| Banned | Why |
|---|---|
| **Any non-FastAPI backend** | Express/Flask/Django = instant rejection per the brief |
| LangChain, LlamaIndex, CrewAI, AutoGen, Semantic Kernel | The agent loop is ~30 lines. A framework hides exactly the behaviour being evaluated, and adds 40+ transitive dependencies |
| Vector DBs, embeddings, RAG | The knowledge base is five facts. Retrieval here is theatre |
| React / Vue / Svelte / Next / Tailwind | Forces a build step. Violates P4 |
| Postgres, MongoDB, SQLAlchemy, Alembic | Nothing needs persistence in v1 |
| Redis, Celery, RabbitMQ | No background work exists |
| Docker / docker-compose | Adds a prerequisite the reviewer may not have |
| `requests`, `httpx` calls to the Gemini API | Use the SDK. Mixing transports is explicitly wrong |
| OpenAI SDK, Anthropic SDK, LiteLLM, OpenAI-compatible shims | This is a `google-genai` build; a shim or a second provider SDK would obscure real SDK usage |
| `os.getenv` outside `config.py` | Untraceable configuration |
| `print()` for diagnostics | Use the configured logger |
| Global mutable singletons other than the injected store/client | Untestable |
| Auth, RBAC, multi-tenancy | Out of scope (PRD §3.2) |

---

## 4. Model Provider API Rules (Gemini / `google-genai`)

These were verified against the installed `google-genai==2.19.0` SDK's actual signatures before
being written (not assumed) — see D13 in `memory.md` for how. Several concepts don't map 1:1 from
the Anthropic SDK v1 used; the differences are called out explicitly, not papered over.

**A1 — Model IDs come from config, never hardcoded in business logic.** Set via `config.py` and
overridable via `CHAT_MODEL` / `ANALYTICS_MODEL`. Defaults (`gemini-2.5-flash` chat,
`gemini-2.5-pro` analytics) were current as of this project's knowledge cutoff — **verify current
availability in Google AI Studio before relying on them**; Gemini model names move faster than
this document.

**A2 — Reasoning depth via `GenerateContentConfig.thinking_config.thinking_level`:** `"low"` for
chat turns, `"medium"` for analytics extraction. Not a raw token budget.

**A3 — No `temperature` / `top_p` / `top_k` set.** Left at provider defaults — thinking level is
this project's tuning lever, not sampling parameters.

**A4 — Structured extraction uses `response_schema=PydanticModel` + `response_mime_type=
"application/json"`** on `GenerateContentConfig`, reading `response.parsed` (already a validated
instance of the Pydantic model). Never hand-roll JSON parsing of `response.text`.

**A5 — Tools are declared as `types.Tool(function_declarations=[...])`**, each with an explicit
`required` list in its parameter schema. *(Phase 3 — no tools exist yet.)*

**A6 — A tool call is detected by a `function_call` Part in `candidate.content.parts`, not by a
distinct `finish_reason`.** Unlike some APIs, a successful function call normally still reports
`finish_reason == "STOP"` — check the parts, not just the finish reason. *(Phase 3.)*

**A7 — All tool results for one model turn go back as `function_response` Parts inside a single
following `user`-role `Content`.** Splitting them across messages silently trains the model out of
parallel tool use. *(Phase 3.)*

**A8 — Failed tools are recorded with an explicit error flag and a recovery hint** in the
`function_response` payload — never a dropped result, never a raised exception that kills the
turn. *(Phase 3.)*

**A9 — Conversation history stores Gemini `Content` blocks verbatim**
(`role: "user"` / `"model"`, `parts: [...]`). Append the response's own content, not an extracted
string. Rewriting blocks into a bespoke format and back is the standard cause of tool-loop
corruption.

**A10 — `max_output_tokens` is set deliberately:** 1024 for chat (turns are word-capped), 4096 for
analytics. Not left to chance, not set to 16000 "to be safe".

**A11 — Timeouts are explicit via `GenerateContentConfig.http_options.timeout`** (milliseconds):
30000 for chat, 60000 for analytics. The SDK has no chat-appropriate default.

**A12 — Retries are explicit via `http_options.retry_options=types.HttpRetryOptions(attempts=3)`.**
Unlike the Anthropic SDK this project used before, `google-genai` does **not** retry by default
(a single attempt) — omitting this means one transient failure surfaces immediately to the user.

**A13 — Catch a specific chain, most-specific-first, branching on `errors.ClientError.status`
(the canonical string — e.g. `"UNAUTHENTICATED"`) not `.code` (the HTTP int).** Verified against a
live call with a bad key: an invalid key returns `code=400, status="INVALID_ARGUMENT"`, not the
401 a naive int-based branch would expect — don't assume the HTTP code without checking. Branch:
`.status` in `("UNAUTHENTICATED", "PERMISSION_DENIED")` → authentication; `"NOT_FOUND"` → not
found; `"RESOURCE_EXHAUSTED"` → rate limited; any other `ClientError` or `ServerError` → general
status error; `(httpx.TimeoutException, httpx.ConnectError, httpx2.TimeoutException,
httpx2.ConnectError)` → connection error (the SDK vendors both an `httpx` and an `httpx2`
transport — catch both). Gemini error responses do not carry a per-request id the way Anthropic's
did — log `.code` / `.status` / `.message`, do not fabricate a request-id field that isn't there.

**A14 — Never log the API key, a full prompt, or a full transcript at INFO.** Mask phone numbers
to the last four digits everywhere.

**A15 — Explicit context caching is not used in v1.** Gemini's caching is a separate stateful
resource (`client.aio.caches.create`, TTL-bound, with its own minimum-token-count requirements) —
not an inline per-request flag like Anthropic's `cache_control`. Given the 24-hour build scope, the
full system prompt is sent every turn. `usage_metadata.cached_content_token_count` will read `0` as
a result; **this is expected, not a bug**, unless and until explicit caching is added as a later
enhancement. Documented as a deliberate simplification (D13), not silently dropped.

---

## 5. Prompt Engineering Rules

**PR1 — Modules are single-concern.** One file per concern (`Architecture.md` §4). A rule about
Hindi belongs in `20_language.md` and nowhere else.

**PR2 — Facts are rendered, never typed.** `10_knowledge_base.md` is generated from
`data/project_facts.yaml`. Editing a price means editing the YAML.

**PR3 — Every behavioural instruction has a worked example.** "Handle objections gracefully" is
worthless; a two-line sample exchange is not. Examples are the highest-leverage tokens in the file.

**PR4 — Negative instructions are paired with a positive alternative.** Never "don't say X"; always
"don't say X — say Y instead." Bare prohibitions leave the model with no move.

**PR5 — Guardrails go last, channel adapter last of all.** Recency matters; format rules are the
narrowest instruction and belong closest to generation.

**PR6 — `FINAL_PROMPT.md` is generated, never edited by hand.** It carries a "do not edit"
banner and is regenerated by `scripts/export_prompt.py` before every commit that touches a module.
A hand-edited final prompt that drifts from what the code sends is a submission-level failure.

**PR7 — One prompt, two adapters.** No forking the core prompt per channel. If a rule differs
between chat and voice, it belongs in the adapter; if it does not, it belongs in the core.

**PR8 — Prompt changes require a scenario run.** Any edit to a module is followed by re-running the
affected scenarios before it is considered done. Prompt regressions are invisible without them.

**PR9 — The unknown register is exhaustive and closed.** Every commonly-asked unanswerable question
is listed in `project_facts.yaml` with a deflection policy. The default for anything unlisted is
also deflection — the model is never left to decide whether it "probably knows".

**PR10 — Word caps are stated as hard limits with a reason.** "Keep it short" produces paragraphs;
"never exceed 60 words — the customer is reading this on a phone" produces short turns.

---

## 6. Code Rules

**C1 — Type hints on every function signature.** Pydantic models for every boundary. No bare
`dict` crossing a layer.

**C2 — Layer boundaries hold.** `api/` never calls the SDK. `agent/` never touches FastAPI
request objects. `services/` never imports from `agent/`. `store/` and `llm/` depend on nothing
above them. A violation means the wrong file is being edited.

**C3 — Dependency injection via FastAPI `Depends`.** The store and LLM client are injected, so
tests substitute fakes without patching. No module-level client construction at import time except
the single app-lifespan singleton.

**C4 — Functions under 50 lines; files under 300.** `orchestrator.py` is the one place a longer
function is acceptable, and only for the turn loop itself.

**C5 — Comments explain *why*, never *what*.** The turn loop, the deterministic-overwrite step in
analytics, and every failure-injection path get a why-comment. Nothing else needs one.

**C6 — Errors are returned as values where they are expected, raised where they are not.**
A failed booking is a `BookingResult(ok=False, ...)`, not an exception — it is a normal outcome the
agent must handle. A missing session is an exception mapped to 404.

**C7 — No silent excepts.** `except Exception: pass` is banned. Every caught exception is logged
with context and either recovered from explicitly or re-raised.

**C8 — No stack trace or internal message ever reaches the client.** The error envelope
(`Architecture.md` §8) is the only shape the browser sees.

**C9 — The UI renders text with `textContent`.** `innerHTML` on model output is banned.

**C10 — Naming is domain-accurate.** `LeadProfile`, `BookingResult`, `site_visit_status` — not
`data`, `info`, `result2`, `handler`.

**C11 — No dead code, no commented-out blocks, no `TODO` without an owner and a phase number.**

---

## 7. Testing Rules

**T1 — Tier 1 tests never call the API.** They must pass with no `GEMINI_API_KEY` set, in under
two seconds, using `FakeLLMClient`. If a test needs a key, it belongs in Tier 2.

**T2 — Every requirement in `PRD.md` §6 has at least one scenario file** carrying its feature ID.

**T3 — Every scenario declares input, expected behaviour, and assertions** — this is the
assignment's test-case deliverable, not an internal convenience.

**T4 — Assertions are deterministic** (keyword, regex, analytics field). No LLM judge in v1:
non-reproducible results are not evidence.

**T5 — Every booking failure mode has a test.** Slot unavailable, invalid date, invalid phone,
system error. The system-error path must assert the agent **never** claims a confirmed booking.

**T6 — `docs/TEST_RESULTS.md` is regenerated before submission**, and its actual outputs are the
real ones — never edited by hand, never aspirational.

**T7 — Language scenarios assert script, not just content.** A Hindi reply written in Roman script
is a failure of F-02 even if the meaning is right.

---

## 8. Git & Delivery Rules

**G1 — `.gitignore` exists and contains `.env` before the first commit.** Not after.

**G2 — No secret ever enters history.** A key committed and then removed is still a leaked key —
it would mean rewriting history or rotating the key. Prevent, don't repair.

**G3 — Conventional commits scoped by phase:** `feat(agent): tool loop with parallel results`,
`docs(phase-8): README`. The history should read as the build log.

**G4 — Commit at every phase gate**, with `memory.md` updated in the same commit.

**G5 — Pre-submission gate (Phase 8), all mandatory:** a secret scan over the working tree and
history returns nothing · a fresh clone into a clean venv runs successfully ·
`docs/TEST_RESULTS.md` regenerated · `prompts/FINAL_PROMPT.md` regenerated · README covers
run / assumptions / limitations / AI-tools · repo is public.

---

## 9. Boundaries for AI Assistance

This project is built with AI assistance, disclosed in the README. These are the boundaries.

**AI1 — The AI never invents project facts.** If a fact is not in `data/project_facts.yaml`, the
correct output is a deflection, not a plausible value — in generated code, tests, prompts, docs,
and demo scripts alike. This is the single most important rule in the file.

**AI2 — The AI does not add dependencies.** Any new package requires explicit human approval and a
`rules.md` amendment. Framework suggestions (LangChain and friends) are declined by default.

**AI3 — The AI does not exceed the requested scope.** No speculative abstractions, no "while I was
here" refactors, no extra endpoints, no new files outside the structure in `Architecture.md` §6.
Three named seams exist (`LLMClient`, `SessionStore`, tool dispatch); a fourth needs justification.

**AI4 — The AI does not weaken a test to make it pass.** If a scenario fails, the fix is in the
prompt or the code. Loosening an assertion or deleting a case is prohibited. A red test is
information, and hiding it forfeits the information.

**AI5 — The AI does not touch `.env`, real credentials, or git history.** It may edit
`.env.example`. It never runs `git push`, `git commit --amend`, `git rebase`, `git reset --hard`,
or any force operation without an explicit instruction for that specific command.

**AI6 — The AI reports honestly.** "Implemented and tested" means the test was run and passed, with
output shown. Untested code is reported as untested. A skipped step is stated as skipped.

**AI7 — The AI updates `memory.md` at every phase gate** — before starting the next phase, not in a
batch at the end. A stale tracker is worse than no tracker.

**AI8 — The AI stops and asks when a decision changes the shape of the deliverable** — a different
model, an extra dependency, a schema change, dropping a requirement. It proceeds without asking on
ordinary implementation judgement inside an approved phase.

**AI9 — Generated code is read before it is committed.** No file lands unread because it looked
plausible. Code clarity is an explicit evaluation criterion; unreviewed generated code is the
fastest way to fail it.

**AI10 — Prompt modules are human-reviewed line by line.** The prompt *is* the deliverable being
graded. Every line is either doing work or is deleted.

---

## 10. Definition of Done

A phase is complete only when **all** of the following hold:

1. Every acceptance criterion for its features (`PRD.md` §6) is met.
2. Tier 1 tests pass with no API key set.
3. Relevant Tier 2 scenarios have been run and their output reviewed.
4. `ruff check` and `ruff format --check` are clean.
5. No rule in this file was violated, or the violation is documented as an amendment here.
6. `memory.md` is updated: completed log, current file, decisions, next up.
7. The work is committed.
