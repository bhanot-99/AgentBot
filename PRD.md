# PRD — Northstar Agent

**Product:** Northstar Agent — an AI sales agent for Northstar Homes
**Repository:** `AgentBot`
**Context:** Huvo AI — Forward Deployed Engineer take-home assignment
**Owner:** Ashish Bhanot
**Version:** 1.0 (Draft — pre-implementation)
**Date:** 2026-08-23
**Deadline:** 24 hours from assignment receipt

---

## 1. Executive Summary

Northstar Agent is a multilingual (English / Hindi / Hinglish) AI sales agent for a fictional
real-estate developer, **Northstar Homes**, selling its project **Northstar One** in
**Sector 79, Gurugram**.

The agent holds a natural sales conversation with an inbound or outbound prospect, qualifies
the lead, handles objections, answers only what it actually knows, books a site visit
(including gracefully recovering when the booking fails), escalates to a human when it should,
respects requests to stop contact, and — after the conversation ends — emits a structured
analytics record the sales team can act on.

**The product is the prompt.** The code is a thin, honest harness that proves the prompt works
and makes its behaviour observable. Every architectural decision in this project is subordinate
to that: nothing may be added that obscures prompt quality or makes the agent's behaviour harder
to inspect.

---

## 2. Problem Statement

Real-estate sales teams in the Delhi NCR market are drowning in top-of-funnel volume. A typical
project receives hundreds of portal leads (99acres, MagicBricks, Housing) and ad-form leads per
week. Human callers:

- reach only ~30–40% of leads on the first attempt,
- spend most of their time on unqualified or unreachable contacts,
- lose context between calls (no reliable record of what the buyer said last time),
- and answer inconsistently — some invent possession dates or discounts to keep a lead warm,
  which creates real legal and reputational exposure under RERA.

**The opportunity:** an AI agent that handles first contact and qualification consistently,
in the language the buyer actually speaks, never invents a fact, and hands the human team a
clean, structured lead record — so humans only spend time on prospects worth their time.

**The constraint that makes this hard:** we have been given exactly five facts about
Northstar One. A naive LLM sales agent will confidently fabricate carpet areas, possession
dates, amenities, and discounts within three turns. Preventing that — while still sounding
like a warm, persuasive salesperson rather than a compliance robot — is the core engineering
problem of this project.

---

## 3. Goals and Non-Goals

### 3.1 Goals

| # | Goal | How we know we hit it |
|---|---|---|
| G1 | A single system prompt that works unchanged in both chat and voice channels | Same prompt file drives both; only a small channel adapter block differs |
| G2 | Zero fabricated facts | Adversarial test suite (`unknowns` scenarios) shows 0 invented prices/dates/amenities/discounts |
| G3 | Natural code-switching across English, Hindi, Hinglish | Agent mirrors the customer's language within one turn, including mid-conversation switches |
| G4 | Reliable lead qualification | Analytics record populates budget, configuration, timeline, purpose and authority whenever the customer revealed them |
| G5 | Site-visit booking that degrades gracefully | Both the success path and every failure mode produce a sensible, in-language recovery |
| G6 | Conversation memory within a session | Agent never re-asks something the customer already answered |
| G7 | A reviewer can run the whole thing in under two minutes | `pip install -r requirements.txt` → set one env var → `uvicorn` → open browser. No Node, no Docker, no database |
| G8 | Every assignment requirement is demonstrably met | Traceability matrix (§12) maps each assignment bullet to a feature ID and a test |

### 3.2 Non-Goals (explicitly out of scope for v1)

- Real telephony / TTS / STT. The prompt is **voice-ready**; we do not integrate a voice stack.
- Real CRM, database, or persistence beyond process memory.
- Authentication, multi-tenancy, or multi-project support.
- Outbound campaign dialling, scheduling, or lead import.
- Streaming token-by-token responses (typing indicator only — see Architecture §9).
- Payment, booking-amount collection, or any transaction.
- Fine-tuning, RAG over a document corpus, or vector search. The knowledge base is five facts;
  a vector store here would be pure theatre.

---

## 4. Target Users

### 4.1 Primary users — the people who talk to the agent

**Persona A — "Sunita", the end-user family buyer**
45, lives in Najafgarh, husband runs a small business. Speaks Hindi, reads Devanagari
comfortably. Buying a home to live in with two children and in-laws. Cares about: number of
rooms, whether it is ready to move in, schools nearby, safety, total money required including
"hidden charges". Budget realistically ₹1.3–1.6 Cr, needs a loan.
*What she needs from the agent:* to be spoken to in Hindi, not rushed, and given an honest
"I'll have our team confirm that" instead of a made-up answer.

**Persona B — "Rohan", the NRI / investor**
34, works in Dubai, family in Gurugram. Speaks English. Evaluating Northstar One purely as an
investment. Asks about rental yield, appreciation, RERA registration, builder track record,
payment plans. Will compare against three other Sector 79 projects.
*What he needs:* fast, precise answers; a clear statement of what is not yet confirmed;
and a human specialist for the commercial detail. He is the persona most likely to trigger
hallucination, and most likely to notice it.

**Persona C — "Amit", the busy professional**
38, works in Cyber City, drives home at 8pm. Speaks Hinglish ("2 BHK ka kya rate hai?").
Answers the call while doing something else. Low patience: three turns to prove value or he
hangs up. Frequently says "abhi busy hoon", "baad mein call karna", or "not interested".
*What he needs:* short turns, no monologues, an immediate value statement, and an agent that
takes "call me later" seriously and actually stops.

**Persona D — "Mrs. Khanna", the wrong / hostile contact**
Never enquired. Annoyed. Says "who gave you my number?", "stop calling me", "I'll report this".
*What she needs:* immediate, unconditional, polite compliance — no retention attempt, no
"but sir just one minute". This path is a compliance requirement, not a sales opportunity.

### 4.2 Secondary users — the people who consume the agent's output

**Persona E — "Priya", Northstar Homes sales manager**
Runs a team of six callers. Does not read transcripts. Reads the analytics record: is this lead
hot, what is the budget, did they book, when do we call back, what did they object to, and what
question did we fail to answer.
*What she needs:* a structured, machine-readable lead record with a `next_best_action` she can
assign to a caller in under ten seconds.

**Persona F — the Huvo AI evaluation panel**
Will clone the repo, read the prompt, run the bot, watch a demo video, and judge prompt quality,
agent behaviour, situation handling, memory, whether it works, code clarity, and depth of
understanding. They are a real stakeholder with real acceptance criteria (§12).
*What they need:* to reach a working bot fast, and to find the reasoning behind every decision
written down.

---

## 5. Product Knowledge Base — the only facts that exist

This is the single source of truth. It lives in code at `data/project_facts.yaml` and is injected
into the prompt. **Nothing outside this table may ever be stated as fact by the agent.**

### 5.1 Known facts

| Field | Value |
|---|---|
| Developer | Northstar Homes |
| Project name | Northstar One |
| Location | Sector 79, Gurugram, Haryana |
| Configurations offered | 2 BHK, 3 BHK |
| 2 BHK starting price | ₹1.35 crore onwards |
| 3 BHK starting price | ₹1.75 crore onwards |
| Site visits | Available; can be arranged by the agent |
| Languages supported | English, Hindi, Hinglish |

### 5.2 Explicitly unknown — the deflection register

These are the questions real buyers ask that we **cannot** answer. Each is pre-registered with a
deflection policy so the model never has to improvise, and each occurrence is logged to analytics
so the human team knows what to prepare.

| Category | Example questions | Policy |
|---|---|---|
| Area / size | "carpet area kitna hai?", "sq ft?" | Not confirmed — sales team will share exact layouts |
| Possession | "possession kab milega?", "ready to move?" | Not confirmed — team will confirm timeline |
| Floor plans | "can you send the floor plan?" | Team will share on WhatsApp/email after the call |
| Amenities | "clubhouse? pool? gym? parking?" | Not confirmed — best seen at the site visit |
| Payment plan | "construction linked?", "booking amount?" | Team will share the payment schedule |
| RERA | "RERA number?" | Team will share official registration details |
| Inventory | "which floors are left?", "how many units?" | Live availability confirmed by the team |
| Charges | "maintenance? IFMS? PLC? stamp duty?" | Not confirmed — full cost sheet from the team |
| Discounts | "koi discount milega?", "best price?" | **Never negotiate or imply a discount.** Price is "starting from"; the team handles commercials |
| Loans | "which banks?", "EMI kitni?" | No bank tie-ups confirmed; do not compute EMIs as commitments |
| Projections | "rental yield?", "appreciation?" | Never forecast returns |
| Comparisons | "X project is better, no?" | Do not disparage or make claims about other projects |

**Prime directive (verbatim, to be carried into the prompt):**
> If it is not in the known-facts table, you do not know it. Say so plainly, tell the customer who
> will confirm it and when, and move the conversation forward. Never estimate, never approximate,
> never say "typically" or "usually" about this project.

---

## 6. Core Features

Feature IDs are used by `phases.md`, the test suite, and the traceability matrix.

### F-01 — Natural sales conversation
The agent opens with a short, human introduction (who it is, which project, why it is contacting),
then leads a two-way conversation. Turns are short (chat: ≤ 60 words; voice: ≤ 35 words). It asks
one question at a time, never interrogates, and never sends a wall of text.
**Acceptance:** No agent turn exceeds the channel word cap. No turn contains more than one question mark.

### F-02 — Multilingual & code-switching
Detects the customer's language per turn and mirrors it: English → English, Hindi → Hindi
(Devanagari), Hinglish/Romanised Hindi → Hinglish in Roman script. Handles mid-conversation
switches. Never announces the switch ("I will now speak Hindi"); it just switches.
**Acceptance:** In the language scenarios, agent script matches customer script in ≥ 95% of turns;
a mid-conversation switch is followed within one turn.

### F-03 — Lead qualification (BANTL)
Naturally elicits, without a questionnaire feel:
**B**udget · **A**uthority (sole/joint decision) · **N**eed (2 vs 3 BHK, end-use vs investment,
family size) · **T**imeline · **L**ocation fit.
Never asks more than one qualification question per turn; always trades value for information
(answer something, then ask).
**Acceptance:** In a cooperative 10-turn scenario, ≥ 4 of the 5 BANTL slots are filled in analytics.

### F-04 — Conversation memory
Everything the customer states is retained for the session and never re-asked. Contradictions are
resolved in favour of the most recent statement, and the change is acknowledged.
**Acceptance:** Zero repeated questions across a 15-turn transcript; a corrected budget is reflected
in analytics as the corrected value.

### F-05 — Grounded answers / anti-hallucination
Answers strictly from §5.1. For anything in §5.2 (or anything unlisted), uses the deflection
pattern: **acknowledge → state honestly that it is not confirmed → name who will confirm →
pivot to the next step.**
**Acceptance:** Across the adversarial `unknowns` scenarios (including pressure: "just give me a
rough idea, off the record"), zero fabricated facts and zero implied discounts.

### F-06 — Objection handling
Playbook for the twelve objections real NCR buyers raise (price, location/distance, builder trust,
possession-delay fear, market timing, loan worries, prefers resale, competitor comparison, needs
family approval, no time, already bought, not looking). Each objection is **acknowledged before it
is answered**, answered only with known facts or genuine value (site visit, human specialist),
and followed by a soft next step — never a hard re-pitch.
**Acceptance:** Every objection scenario produces acknowledgement + non-fabricated response +
one clear next step, with no more than two consecutive attempts to move forward.

### F-07 — Busy / uninterested / call-later handling
- **Busy** → offer to be brief or to call back; take an actual time; end warmly.
- **Uninterested** → one respectful value probe maximum, then accept and close cleanly.
- **Call later** → capture a concrete time window, confirm it, set `follow_up_required`.
**Acceptance:** Never more than one re-engagement attempt after a clear refusal; callback time
appears in analytics.

### F-08 — Do-not-contact compliance
On any stop signal ("stop calling", "remove my number", "don't contact me", "मुझे कॉल मत करो",
"report kar dunga"), the agent **immediately** stops selling, apologises once, confirms removal,
and ends. No retention attempt, no counter-offer, no "just one last thing". Flags
`contact_preference = do_not_contact` and `follow_up_required = false`.
**Acceptance:** DNC scenarios end within two turns with zero sales content after the signal.

### F-09 — Site-visit booking
Collects name, phone, preferred date and time window, and configuration of interest, then calls
`check_slot_availability` and `book_site_visit`. Confirms back with a booking reference and the
exact date/time in the customer's language.
**Acceptance:** Happy path yields `site_visit_status = booked` with a reference and a confirmed slot.

### F-10 — Booking-failure recovery
Four distinct failure modes, each with its own recovery:
| Failure | Agent behaviour |
|---|---|
| Slot unavailable | Apologise, offer the two nearest real alternatives from the availability response |
| Invalid date (past / beyond 30 days) | Explain the window, ask for a date inside it |
| Invalid phone | Ask once for a 10-digit Indian mobile; after a second failure, escalate |
| Booking system error | Do **not** claim the visit is booked. Say the team will confirm within a stated time, capture contact, set `site_visit_status = attempted_failed` and `follow_up_required = true` |
**Acceptance:** On forced failure, the agent never states or implies a confirmed booking; analytics
reflect `attempted_failed`.

### F-11 — Human escalation
Escalates when: the customer explicitly asks for a human; commercial negotiation is requested;
the customer is angry or the conversation has broken down; a legal/RERA/documentation question
is asked; or the same unknown is asked three times. Produces a reason and a summary for the human,
tells the customer what will happen and when.
**Acceptance:** Escalation scenarios set `escalated_to_human = true` with a non-empty reason and
a summary of ≤ 3 sentences.

### F-12 — Proper conversation ending
Every ending — booked, follow-up, refusal, DNC, escalation — closes with a recap of what was
agreed, the concrete next step, and a warm sign-off in the customer's language. No dangling turns,
no re-pitching after a close.
**Acceptance:** Every terminal scenario ends with a recap + next step + sign-off.

### F-13 — Channel duality (chat ⇄ voice)
One core prompt plus a small channel adapter block. Chat mode may use short line breaks and plain
punctuation; **voice mode forbids markdown, bullets, emoji, and symbols** (₹ → "rupees",
"1.35 Cr" → "one crore thirty five lakhs"), caps turns at ~35 words, and adds ASR-noise tolerance
(mishearings, partial words, background interruption, barge-in).
**Acceptance:** With `channel=voice`, zero markdown/emoji/symbol characters in agent output and no
turn over 35 words, using the same core prompt.

### F-14 — Post-conversation analytics
On session end, a second model call extracts a validated structured record (§7) from the transcript
plus the tool-event log. Rendered in the UI and available at
`GET /api/session/{id}/analytics`.
**Acceptance:** Valid record for every ended session, including empty/hostile conversations
(fields absent → `unknown`/`null`, never invented).

### F-15 — Web chat interface
Single-page interface served by FastAPI: message list with clear agent/customer distinction,
Devanagari-safe typography, channel toggle (chat/voice), typing indicator, live tool-event trace
(so a reviewer can *see* `book_site_visit` fire and fail), and an "End conversation" button that
renders the analytics panel.
**Acceptance:** A reviewer can complete a full booking conversation and view analytics without
touching a terminal.

### F-16 — Test evidence
A scenario suite (`tests/scenarios/*.yaml`) declaring **input · expected behaviour · actual output**
for each requirement, plus a runner that produces `docs/TEST_RESULTS.md`.
**Acceptance:** `TEST_RESULTS.md` committed, covering at minimum F-02, F-04, F-05, F-06, F-07,
F-08, F-09, F-10, F-11, F-13.

---

## 7. Analytics Specification

Emitted once per session, validated by a Pydantic model. Any field the conversation did not
establish is `unknown`/`null` — **never guessed**.

```
session_id, channel, started_at, ended_at, turn_count, duration_seconds

languages_used[]            english | hindi | hinglish
primary_language

lead_name                   string | null
lead_phone                  string | null      (masked in logs)
phone_captured              bool

budget_stated               bool
budget_min_inr              int | null
budget_max_inr              int | null
budget_fit                  within | below | above | unknown

configuration_interest[]    2BHK | 3BHK
primary_configuration       2BHK | 3BHK | undecided | unknown
purpose                     end_use | investment | unknown
timeline                    immediate | 1_3_months | 3_6_months | 6_12_months | 12_plus | unknown
decision_authority          sole | joint | unknown
location_fit                yes | no | unknown

interest_level              hot | warm | cold
qualification_score         0-100
objections_raised[]         enum (see F-06)
unknown_questions_asked[]   free text — what we failed to answer

site_visit_status           booked | attempted_failed | declined | not_discussed
site_visit_date             ISO date | null
site_visit_slot             string | null
booking_reference           string | null

contact_preference          ok | callback_later | do_not_contact
follow_up_required          bool
follow_up_at                ISO datetime | null
follow_up_reason            string | null

escalated_to_human          bool
escalation_reason           string | null

conversation_outcome        visit_booked | follow_up_scheduled | not_interested |
                            do_not_contact | escalated | abandoned
sentiment                   positive | neutral | negative
summary                     2-3 sentences
next_best_action            one imperative sentence for the human caller
```

**Lead scoring rules (deterministic, applied over the extracted fields):**

| Level | Rule |
|---|---|
| **Hot** | Site visit booked, **or** (budget within range **and** timeline ≤ 3 months **and** phone captured) |
| **Warm** | Engaged and configuration known, but budget or timeline unconfirmed; or callback requested |
| **Cold** | Budget clearly below range, explicit disinterest, DNC, wrong number, or already purchased |

---

## 8. Success Metrics

| Metric | Target | Measured by |
|---|---|---|
| Fabrication rate | **0** | Adversarial scenario suite, manual review of every `unknowns` transcript |
| Language mirroring accuracy | ≥ 95% of turns | Script detection over language scenarios |
| BANTL slot fill (cooperative lead) | ≥ 4 / 5 | Analytics record |
| Repeated-question rate | 0 | Manual review of 15-turn transcripts |
| DNC compliance | 100%, ≤ 2 turns | DNC scenarios |
| Booking-failure honesty | 100% (never claims a false booking) | Forced-failure scenarios |
| Median chat turn latency | < 4 s | Local timing during demo |
| Time-to-first-run for a reviewer | < 2 min | Fresh-clone dry run before submission |

---

## 9. Constraints

**Hard constraints (from the assignment):**
- Backend **must** be FastAPI (Python). Express.js or any other backend framework is rejected.
- Deliverables: public GitHub repo (final prompt, source, README, `.env.example`, no secrets),
  demo video, README covering how to run / assumptions / limitations / AI tools used.
- 24-hour delivery window.
- "Keep the implementation simple."

**Self-imposed constraints (to protect the above):**
- No frontend build step. Vanilla HTML/CSS/JS served by FastAPI. A reviewer must never run `npm`.
- No database. In-memory session store behind an interface.
- Total production dependency count ≤ 6.
- Every knowledge fact lives in exactly one file (`data/project_facts.yaml`).

---

## 10. Assumptions

1. Prices given are "starting from" / "onwards" and refer to all-inclusive-of-nothing base pricing.
   The agent always says "starting from" and never quotes a total.
2. Currency is INR; "Cr" = crore = 10,000,000; "lakh" = 100,000.
3. Site visits run daily 10:00–18:00 IST in 90-minute windows; bookable 1–30 days ahead.
   This is a **simulation parameter** we invented for the booking service, disclosed in the README —
   it is not presented to the customer as a developer-confirmed fact beyond "our team will confirm".
4. Indian mobile numbers: 10 digits beginning 6–9, optional `+91`/`0` prefix.
5. One conversation = one lead. No cross-session identity resolution.
6. Voice mode is simulated as text; we optimise the prompt for voice, not the transport.
7. The demo runs on a single machine for one reviewer at a time — no horizontal scaling required.

---

## 11. Risks

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | Model invents a fact under sales pressure | Fatal — fails the core evaluation criterion | Explicit unknown register in the prompt; adversarial test suite; Phase 7 red-team pass |
| R2 | Agent becomes a compliance robot ("I cannot confirm that") and stops selling | Fails "agent behaviour" criterion | Deflection pattern *requires* a forward pivot; tone rules; scenarios assert a next step exists |
| R3 | Hindi output degrades into transliterated English or wrong script | Fails multilingual criterion | Script-mirroring rule with worked examples in the prompt; Devanagari-capable font in UI; language scenarios |
| R4 | Over-engineering eats the 24 hours | Nothing ships | `phases.md` time boxes; `rules.md` hard "do not build" list; Phase 4 UI is deliberately dependency-free |
| R5 | Booking failure path never demonstrated in the demo | Explicit assignment requirement appears unmet | Deterministic failure injection (`FORCE_BOOKING_FAILURE`) so the demo video can trigger it on cue |
| R6 | API key leaked in the public repo | Disqualifying | `.env` gitignored from commit #1; `.env.example` only; pre-submission secret scan (Phase 8) |
| R7 | Reviewer cannot run it (missing key, wrong Python) | Fails "whether the bot works" | Python version pinned in README; clear failure message when key is missing; fresh-clone dry run |
| R8 | Latency makes the demo feel sluggish | Weakens demo | Prompt caching on the system prompt; `effort: low` for chat turns; ≤ 1024 output tokens |

---

## 12. Requirement Traceability

Every bullet of the assignment brief, mapped to a feature and its evidence.

| Assignment requirement | Feature | Evidence |
|---|---|---|
| Natural conversation | F-01 | `scenarios/happy_path.yaml` |
| Customer qualification | F-03 | Analytics BANTL fields |
| English, Hindi, and Hinglish | F-02 | `scenarios/language_*.yaml` |
| Common objections | F-06 | `scenarios/objection_*.yaml` |
| Busy or uninterested customers | F-07 | `scenarios/busy.yaml`, `uninterested.yaml` |
| Requests to contact later | F-07 | `scenarios/callback.yaml` |
| Requests to stop communication | F-08 | `scenarios/dnc.yaml` |
| Unknown questions | F-05 | `scenarios/unknowns_*.yaml` |
| Site-visit booking | F-09 | `scenarios/booking_success.yaml` |
| Booking failures | F-10 | `scenarios/booking_failure_*.yaml` |
| Human escalation | F-11 | `scenarios/escalation.yaml` |
| Proper conversation ending | F-12 | Asserted in every terminal scenario |
| Must not invent prices/discounts/availability | F-05 | `scenarios/pressure_discount.yaml` |
| Same prompt for chat **and** voice | F-13 | `scenarios/voice_*.yaml` |
| Accept messages / respond via final prompt | F-01, F-15 | `POST /api/chat` |
| Remember information shared | F-04 | `scenarios/memory.yaml` |
| Simulate a site-visit booking | F-09 | Booking service + tool trace in UI |
| Handle a failed booking correctly | F-10 | `FORCE_BOOKING_FAILURE` demo |
| Post-conversation analytics | F-14 | `GET /api/session/{id}/analytics` |
| Test cases: input, expected, actual | F-16 | `docs/TEST_RESULTS.md` |
| FastAPI backend (mandatory) | — | `app/main.py` |
| Public repo: prompt, source, README, `.env.example` | — | Phase 8 |
| Demo video | — | Phase 8 |
| README: run / assumptions / limitations / AI tools | — | Phase 8 |

---

## 13. Deliverables Checklist

- [ ] `prompts/FINAL_PROMPT.md` — the complete, rendered system prompt
- [ ] `prompts/modules/*.md` — the composable prompt source
- [ ] FastAPI backend + vanilla web UI
- [ ] `data/project_facts.yaml` — single source of factual truth
- [ ] `docs/TEST_RESULTS.md` — input / expected / actual for every scenario
- [ ] `README.md` — run instructions, assumptions, limitations, AI tools used
- [ ] `.env.example` — no real keys anywhere in history
- [ ] Demo video — bot working, sample conversation, prompt approach, implementation walkthrough
- [ ] Submission email to `aditi@huvo.ai`, cc `nikhil@huvo.ai`, `vaibhav@huvo.ai`, `rohit@huvo.ai`

---

## 14. Deferred to v2

Streaming responses (SSE) · Redis-backed sessions · real telephony via a voice provider ·
CRM webhook on session end · multi-project knowledge base · WhatsApp channel adapter ·
LLM-judge scoring in CI · admin dashboard over historical leads.
