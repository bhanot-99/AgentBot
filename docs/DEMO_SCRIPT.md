# Demo Video — Shot List

Target length: ~5 minutes (descope floor: 3 minutes, but the booking-failure recovery and the
unknown-deflection moments in Beat 2 stay in regardless — see `phases.md` Phase 8 descope note).
Record at 1280×800+ browser width so the UI never hits the mobile breakpoint.

Setup before recording:
- `.env`: confirm `CHAT_MODEL=gemini-3.6-flash` / `ANALYTICS_MODEL=gemini-3.6-flash` (the real
  shipping default, not the dev quota-workaround `gemini-3.1-flash-lite`).
- `uvicorn app.main:app --port 8000`, browser open to `http://127.0.0.1:8000`, chat channel, dark
  or light — whichever demos cleaner on screen.
- Have a second tab ready on `/docs` (Swagger) for Beat 4, and this repo open in an editor for the
  prompt-module walkthrough.

---

## Beat 1 — What it is & how to run (~30s)

Talking points, camera on screen (no need to show terminal commands in full, just narrate them):
- "This is Northstar Agent — a real-estate sales chatbot for a fictional project, Northstar One,
  built for the Huvo AI take-home."
- "One system prompt drives the whole thing — lead qualification, objections, multilingual
  English/Hindi/Hinglish, booking, escalation — across both a chat UI and a text-simulated voice
  channel."
- "To run it: clone, `pip install -r requirements.txt`, set a Gemini key in `.env`, `uvicorn
  app.main:app` — no database, no Node, no Docker."

## Beat 2 — Live conversation (~2 min)

One continuous conversation, each beat back-to-back, no restarts:

1. **Hinglish opener** — reply to the agent's greeting in Hinglish, e.g. *"Haan bataiye, 3 BHK ka
   kya price hai?"* — shows code-switching and price recall in one turn.
2. **Qualification** — mention a budget and timeline unprompted, e.g. *"Budget around 1.8 crore
   hai, 2-3 mahine mein shift karna hai."* — watch the tool-event trace fire `update_lead_profile`
   live.
3. **An objection** — *"Itna mehenga kyun hai, discount milega?"* — agent should acknowledge,
   decline to invent a discount, redirect to the team, never fabricate a number.
4. **An unknown, deflected** — *"Carpet area exact kitna hai?"* — agent states it's not confirmed,
   names who will confirm it, moves on. **This moment stays in even if the video is cut short.**
5. **A booking attempt that fails, then recovers** — ask for a site visit, pick a date; if the
   first slot picked doesn't fail naturally, ask for a specific popular slot to trigger
   `slot_unavailable` (or set `FORCE_BOOKING_FAILURE=slot_unavailable` in `.env` beforehand for a
   guaranteed take). Agent should offer real alternatives, never claim a false success. **This
   moment also stays in regardless of cut length.**
6. **A successful booking** — accept one of the offered alternative slots — agent confirms with a
   real reference number.

## Beat 3 — Analytics walkthrough (~1 min)

- Click "End conversation."
- Walk through the rendered analytics panel: interest level, qualification score, budget fit,
  site-visit status with the real booking reference, follow-up requirement.
- One sentence on the deterministic-overwrite design: "Anything the code can verify for certain —
  did the booking actually succeed, was do-not-contact triggered — is force-overwritten from the
  tool-event log after extraction, never just trusted from the model's read of the transcript."

## Beat 4 — Prompt architecture (~1 min)

- Show `prompts/modules/` in the editor — point out the file list (identity, knowledge base,
  qualification flow, edge cases, guardrails, one channel adapter) and say one sentence on why it's
  modular: "each behavior lives in exactly one file, so a fix to the callback flow can't silently
  change how price objections are handled."
- Show `data/project_facts.yaml` — "every fact the agent can state traces to this one file;
  anything outside it is a named deflection, never a guess."
- Optionally flash `/docs` (Swagger) to show the API surface, and `prompts/FINAL_PROMPT.md` as the
  actual exported artifact that ships.

## Beat 5 — Limitations, honestly stated (~30s)

State plainly, matching `README.md` §8:
- "Voice mode is text-simulated — there's no real telephony or speech integration, by design; the
  assignment asked for a text-based bot with a voice-ready prompt, not a phone system."
- "Sessions are in-memory, so they don't survive a restart — fine for this demo, swappable behind
  the `SessionStore` interface for anything real."
- "One known, documented gap: the escalation tool call has measured reliability variance on the
  free-tier model — the agent's wording is always correct, but the tool firing itself isn't 100%
  on that tier. Not one of the zero-tolerance criteria, and it's written up in the README."

---

## Recording notes

- Prefer one continuous take over cut-and-splice — the live tool-event trace and analytics panel
  are more convincing shown as they actually happen.
- If a take needs a redo, redo the whole conversation beat (2) rather than splicing, since session
  state (lead profile, tool events) is what's actually being demonstrated.
- Narration can be live voiceover while clicking, or recorded separately and dubbed — either is
  fine; Loom's built-in mic capture is the simplest path.
