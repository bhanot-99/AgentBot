# Design System — Northstar Agent

**Version:** 1.0 · 2026-08-23
**Consumed by:** `app/static/styles.css` · `app/static/index.html`

---

## 1. Design Direction

**Theme name: Warm Premium Trust.**

Two things must be true at once. Real estate at ₹1.35 crore is an aspirational purchase, so the
interface has to feel *premium* — deep ink, warm paper, a restrained brass accent, generous
typographic hierarchy. But the product is a sales agent whose defining virtue is that it never
lies, so it must also feel *trustworthy and legible* — not a flashy proptech gradient, not a
generic purple AI chat widget.

The resolution: **navy ink on warm limestone, with brass reserved for action.** Brass appears only
where the user can act or where the system is reporting what happened. Everything else is ink,
paper, and space.

**Three rules the whole system follows**

1. **Brass means action or status.** A brass element is a button, a focus ring, a live indicator,
   or the agent's speaking edge. Brass is never decoration.
2. **The conversation is the interface.** Chrome recedes. Nothing competes with the message column
   for attention — no sidebars of features, no badges chasing the eye.
3. **Honesty is visible.** Failed tool calls are shown in the same weight as successful ones. The
   analytics panel shows `unknown` as a real, legible value, not an empty cell. The product's
   integrity is a design requirement, not only a prompt requirement.

**Anti-references:** neon-on-black "AI assistant" aesthetics · purple/indigo gradient hero ·
glassmorphism · rounded-everything bubble chat · emoji in product chrome.

---

## 2. Colour Palette

All colour lives in CSS custom properties. The light palette is defined on bare `:root`; dark
redefines **only the token values**, never the rules that use them.

### 2.1 Light theme (default)

| Token | Hex | Name | Use |
|---|---|---|---|
| `--bg` | `#FAF8F5` | Limestone | Page canvas |
| `--surface` | `#FFFFFF` | Paper | Cards, agent bubbles, composer |
| `--surface-alt` | `#F2EEE8` | Limestone 100 | Panel backgrounds, table stripes |
| `--surface-sunken` | `#EBE5DC` | Limestone 200 | Wells, code blocks, tool trace |
| `--border` | `#E3DCD2` | Sand | Default hairlines |
| `--border-strong` | `#C9BFB1` | Sand 400 | Emphasised dividers, input borders |
| `--ink` | `#14213D` | Northstar Navy | Body text, headings, customer bubble fill |
| `--text-muted` | `#5A6478` | Slate | Secondary text, labels |
| `--text-subtle` | `#8A93A6` | Slate 400 | Timestamps, placeholders — **large / non-essential text only** |
| `--on-ink` | `#F7F9FC` | — | Text on navy fill |
| `--brand` | `#C8952E` | Brass | CTA fill, focus ring, agent accent edge |
| `--brand-hover` | `#B08123` | Brass 600 | CTA hover |
| `--brand-text` | `#8A6314` | Brass 800 | Brass-coloured *text* on light surfaces |
| `--brand-soft` | `#FBF1DC` | Brass 50 | Badge and highlight backgrounds |
| `--on-brand` | `#14213D` | — | Text on brass fill (navy, not white) |
| `--success` | `#1B7F5A` | Evergreen | Booking confirmed, tool OK |
| `--success-soft` | `#E4F4EC` | | |
| `--warning` | `#B4690E` | Amber | Pending, retry, follow-up due |
| `--warning-soft` | `#FDF0DC` | | |
| `--danger` | `#B3261E` | Terracotta | Booking failed, DNC, errors |
| `--danger-soft` | `#FBE9E7` | | |
| `--info` | `#0E6C86` | Teal | Neutral system notes, escalation |
| `--info-soft` | `#E1F1F6` | | |

### 2.2 Dark theme

Only these values change. `--brand` lightens so it still reads as brass against a dark ground;
`--on-brand` stays navy, so the CTA looks like the same object in both themes.

| Token | Hex |
|---|---|
| `--bg` | `#0B111F` |
| `--surface` | `#121B2C` |
| `--surface-alt` | `#1A2437` |
| `--surface-sunken` | `#080D18` |
| `--border` | `#27324A` |
| `--border-strong` | `#3A4762` |
| `--ink` | `#ECF1F8` |
| `--text-muted` | `#A3AFC4` |
| `--text-subtle` | `#74819A` |
| `--on-ink` | `#0B111F` |
| `--brand` | `#E0B45C` |
| `--brand-hover` | `#EFC876` |
| `--brand-text` | `#E0B45C` |
| `--brand-soft` | `#2A2415` |
| `--on-brand` | `#14213D` |
| `--success` / `--success-soft` | `#4CC38A` / `#122A21` |
| `--warning` / `--warning-soft` | `#E0A458` / `#2B2113` |
| `--danger` / `--danger-soft` | `#F2776C` / `#2E1614` |
| `--info` / `--info-soft` | `#5CB4CE` / `#122430` |

**Customer bubble in dark** uses `--surface-alt` fill with `--ink` text rather than a navy fill —
navy-on-navy would vanish. This is the one component whose fill differs by theme, handled with a
dedicated `--bubble-user-bg` token so no rule is duplicated.

### 2.3 Contrast targets (WCAG 2.2 AA)

| Pair | Target | Notes |
|---|---|---|
| `--ink` on `--bg` | ≥ 12:1 | Body text — comfortably exceeds AA |
| `--text-muted` on `--bg` | ≥ 4.5:1 | AA for normal text |
| `--text-subtle` on `--bg` | ≥ 3:1 | **Large text / non-essential only.** Never body copy |
| `--on-brand` on `--brand` | ≥ 4.5:1 | Navy on brass, both themes |
| `--on-ink` on `--ink` | ≥ 12:1 | |
| Status colours on their `-soft` pair | ≥ 4.5:1 | Badge text |
| `--border-strong` vs `--surface` | ≥ 3:1 | Non-text UI boundary requirement |

Verify every pair with a contrast checker during Phase 4; do not ship an unverified pair.

### 2.4 Theme switching

Three states must be handled: explicit light, explicit dark, and system default.

```css
:root { /* full light palette — every token defined here */ }

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { /* dark overrides */ }
}

:root[data-theme="dark"] { /* same dark overrides — toggle wins */ }
```

No colour may have its only definition inside a media query or a `[data-theme]` block.
`body` always gets an explicit `background: var(--bg)`.

---

## 3. Typography

### 3.1 The exact fonts

| Role | Family | Weights | Source |
|---|---|---|---|
| Display, UI, body (Latin) | **Plus Jakarta Sans** | 400, 500, 600, 700, 800 | Google Fonts |
| Devanagari (Hindi) | **Noto Sans Devanagari** | 400, 500, 600 | Google Fonts |
| Mono — JSON, tool trace, booking references | **JetBrains Mono** | 400, 500 | Google Fonts |

**Why these three.** Plus Jakarta Sans is a geometric humanist sans with a tall x-height and a
slightly warm, non-corporate feel — it reads as premium without being cold, and its 700/800 weights
give real display presence without needing a second display family. JetBrains Mono has a large
x-height and clearly disambiguated `0/O` and `1/l/I`, which matters when a booking reference is
read aloud on a call.

**Noto Sans Devanagari is a functional requirement, not a style choice.** Plus Jakarta Sans has no
Devanagari glyphs; without it, every Hindi reply renders as tofu boxes and F-02 fails visibly in
the demo. This is a multilingual product, so its Hindi typography gets the same care as its English.

### 3.2 Font stacks — order matters

```css
--font-sans: "Plus Jakarta Sans", "Noto Sans Devanagari",
             -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
             "Helvetica Neue", Arial, sans-serif;

--font-mono: "JetBrains Mono", "SFMono-Regular", Consolas,
             "Liberation Mono", Menlo, monospace;
```

Plus Jakarta Sans is listed **first** and Noto Sans Devanagari **second**. The browser falls
through per glyph: Latin characters render in Jakarta, Devanagari characters fall through to Noto.
A single `font-family` therefore renders a mixed Hinglish sentence correctly, with no `:lang()`
switching and no flash of the wrong face. Reversing this order would render Latin text in Noto —
a subtly worse result that is easy to ship by accident.

**Loading** (the only permitted external resource — see `Architecture.md` §7):

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Noto+Sans+Devanagari:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
```

`display=swap` so text is never invisible while fonts load. Every stack ends in a real system
fallback, so the app stays fully usable offline.

### 3.3 Type scale

Base 16 px, **1.250 (major third)**, rounded to whole pixels.

`12 · 13 · 14 · 16 · 18 · 22 · 27 · 34 · 44`

| Token | Size | Line height | Weight | Letter-spacing | Use |
|---|---|---|---|---|---|
| `--fs-display` | 44px / 2.75rem | 1.08 | 800 | −0.03em | Hero / empty state only |
| `--fs-h1` | 34px / 2.125rem | 1.15 | 700 | −0.022em | Page title |
| `--fs-h2` | 27px / 1.6875rem | 1.22 | 700 | −0.016em | Panel titles |
| `--fs-h3` | 22px / 1.375rem | 1.30 | 600 | −0.010em | Section headings |
| `--fs-h4` | 18px / 1.125rem | 1.40 | 600 | 0 | Card headings, stat labels |
| `--fs-body-lg` | 18px / 1.125rem | 1.60 | 400 | 0 | Intro text, voice-mode messages |
| `--fs-body` | 16px / 1rem | 1.60 | 400 | 0 | **Chat messages** — the workhorse |
| `--fs-body-sm` | 14px / 0.875rem | 1.55 | 400 | 0 | Secondary text, analytics values |
| `--fs-caption` | 13px / 0.8125rem | 1.45 | 500 | +0.005em | Timestamps, field labels |
| `--fs-overline` | 12px / 0.75rem | 1.30 | 700 | +0.09em, uppercase | Section eyebrows |
| `--fs-mono` | 13px / 0.8125rem | 1.50 | 400 | 0 | JSON, tool trace, references |

### 3.4 Typography guidelines

1. **Never below 13px**, and 13px only for captions and mono. 16px is the floor for anything a
   customer reads as content — this is a chat product read on phones.
2. **Measure: 60–75 characters.** Message bubbles cap at `max-width: 34rem`. Long measure is the
   fastest way to make a chat feel like a wall of text.
3. **Line height scales inversely with size.** Display 1.08 → body 1.60. Never set a uniform
   line-height across the scale.
4. **Negative tracking above 22px only.** Body and small text keep tracking at 0; tightening small
   text hurts legibility, especially in Devanagari.
5. **Devanagari needs more vertical room.** Elements containing Devanagari get
   `line-height: 1.75` (vs 1.60) — the shirorekha plus ascending and descending matras occupy more
   of the em box. Apply via `:lang(hi)`, and set `lang="hi"` on the element so assistive tech
   selects the right voice.
6. **Weight, not colour, carries hierarchy.** Three weights per screen maximum: 400 body,
   600 headings, 700/800 display. Do not use colour to imply importance.
7. **Sentence case everywhere.** Uppercase only in `--fs-overline`, and only for eyebrow labels.
8. **Numbers in the UI use tabular figures** (`font-variant-numeric: tabular-nums`) so prices,
   scores, and latencies do not jitter as they update.
9. **Prices are written the way the agent says them:** "₹1.35 crore onwards" in the chat UI. The
   voice channel's verbalisation rules live in the prompt, not here.
10. **No italics for emphasis** — Plus Jakarta Sans has no true italic in the loaded set, and faux
    italic on Devanagari is unacceptable. Use weight 600.

---

## 4. Spacing, Radius, Elevation, Motion

**Spacing — 4px base.** Only these steps:

```
--sp-1: 4px    --sp-2: 8px    --sp-3: 12px   --sp-4: 16px
--sp-5: 20px   --sp-6: 24px   --sp-8: 32px   --sp-10: 40px
--sp-12: 48px  --sp-16: 64px
```
Component padding uses 3 / 4 / 6. Section rhythm uses 8 / 12 / 16. Nothing in between.

**Radius**

```
--r-sm: 6px      inputs, small badges, tool-trace rows
--r-md: 10px     buttons, stat tiles
--r-lg: 14px     message bubbles, cards, panels
--r-xl: 20px     modals, the composer shell
--r-pill: 999px  channel toggle, badges, send button
```
The bubble's "tail" corner drops to 4px on the speaker's side — a quiet directional cue with no
extra markup.

**Elevation** — navy-tinted, low alpha. Three levels, no more.

```
--sh-sm: 0 1px 2px rgba(20,33,61,.06)
--sh-md: 0 2px 8px rgba(20,33,61,.08)
--sh-lg: 0 8px 24px rgba(20,33,61,.10)
```
Dark theme swaps the tint to `rgba(0,0,0,.45)` at the same three steps. Message bubbles use borders,
not shadows — a hundred shadowed bubbles look like static.

**Motion**

```
--dur-instant: 100ms   --dur-fast: 160ms   --dur-base: 220ms   --dur-slow: 320ms
--ease-out:    cubic-bezier(0.2, 0, 0, 1)        default
--ease-spring: cubic-bezier(0.34, 1.3, 0.64, 1)  bubble entry only
```
Animate `transform` and `opacity` only. New bubbles enter with a 6px rise plus fade over
`--dur-base`. Under `prefers-reduced-motion: reduce`, all durations collapse to 0.01ms and the
typing indicator becomes a static label.

---

## 5. Components

### 5.1 App shell
Two columns at ≥ 1024px: conversation `1fr`, insight rail `380px` fixed. Below 1024px the rail
becomes a bottom sheet toggled from the header. Below 640px everything is full-bleed with `--sp-4`
gutters. Minimum supported width: 360px.

### 5.2 Header — 64px
North-star mark (inline SVG, brass) · **Northstar One** in `--fs-h4` · location
"Sector 79, Gurugram" in `--fs-caption` / `--text-muted` · channel toggle · theme toggle.
Bottom hairline `--border`. Never sticky-shadowed; it sits flat on the canvas.

### 5.3 Message bubbles

| | Agent | Customer |
|---|---|---|
| Align | left | right |
| Fill | `--surface` | `--bubble-user-bg` |
| Text | `--ink` | `--bubble-user-fg` |
| Border | `1px solid --border` | none |
| Accent | 3px `--brand` left edge | none |
| Radius | `--r-lg`, bottom-left 4px | `--r-lg`, bottom-right 4px |
| Padding | `--sp-3` `--sp-4` | same |
| Max width | `34rem` | `34rem` |
| Type | `--fs-body` (`--fs-body-lg` in voice mode) | `--fs-body` |

Timestamp sits below the bubble in `--fs-caption` / `--text-subtle`, revealed on hover on desktop
and always visible on touch. Bubble stack gap `--sp-3`; gap between speakers `--sp-5`.

### 5.4 Typing indicator
Three 6px `--text-subtle` dots in an agent-shaped bubble, 1.2s staggered opacity loop.
`aria-label="Agent is typing"`. Replaced by a static "Agent is replying…" label under reduced
motion.

### 5.5 Composer
`--surface` shell, `--r-xl`, `1px solid --border-strong`, `--sh-sm`. Auto-growing textarea from
1 to 5 lines, `--fs-body`. **Enter** sends, **Shift+Enter** newlines (stated in the placeholder).
Send button: 40px pill, `--brand` fill, `--on-brand` glyph, disabled at 40% opacity when empty.
Focus moves the shell border to `--brand` and adds the focus ring.

### 5.6 Channel toggle
Segmented pill, two options (`Chat` / `Voice`), `--surface-alt` track, `--brand` active pill with
`--on-brand` label, slide transition `--dur-fast`. Selecting Voice shows a one-line `--info-soft`
banner: "Voice mode — replies are formatted to be spoken aloud." Switching channels starts a new
session; the UI says so before it does it.

### 5.7 Tool-event trace
The honesty surface. Collapsed row, `--font-mono`, `--fs-mono`, `--surface-sunken`, `--r-sm`:

```
● book_site_visit          412 ms   FAILED
● check_slot_availability    3 ms   OK
```

Status dot **plus** text label — never colour alone. `--success` OK · `--danger` FAILED ·
`--warning` pending. Expanding reveals pretty-printed input and output JSON in a `--surface-sunken`
well with `overflow-x: auto`. Failed rows are expanded by default: the failure is the interesting
part, and hiding it would contradict rule 3 of the design direction.

### 5.8 Analytics panel
- **Header row:** interest-level badge plus qualification score.
- **Interest badge:** pill, `--fs-caption`, weight 600 — hot `--danger-soft`/`--danger`,
  warm `--warning-soft`/`--warning`, cold `--info-soft`/`--info`. Always carries the word.
- **Score meter:** 6px track `--surface-sunken`, fill `--brand`, `--r-pill`, with the numeral
  beside it in tabular figures. Never the meter alone.
- **Field groups:** Lead · Qualification · Site visit · Follow-up · Outcome. Label in
  `--fs-caption` / `--text-muted`, value in `--fs-body-sm` / `--ink`.
- **`unknown` renders as the literal word** in `--text-muted` at weight 500 — never an empty cell
  or a dash. The reader must be able to tell "not asked" from "not rendered".
- **`summary`** in `--fs-body-sm`, measure-capped. **`next_best_action`** in a `--brand-soft` card
  with a `--brand` left edge — it is the one thing a sales manager acts on.
- Booking references and phone numbers in `--font-mono`.

### 5.9 Badges, buttons, states
- **Primary button:** `--brand` fill, `--on-brand` text, `--r-md`, `--sp-3` / `--sp-5`, weight 600.
- **Secondary:** transparent fill, `1px --border-strong`, `--ink` text.
- **Danger (End conversation):** transparent, `1px --danger`, `--danger` text; fills on hover.
- **Focus:** `outline: 2px solid var(--brand); outline-offset: 2px` on `:focus-visible` only.
- **Empty state:** north-star mark at 20% opacity, one `--fs-h3` line, one `--fs-body-sm` hint —
  "Try: 2 BHK ka rate kya hai?"
- **Error toast:** `--danger-soft` fill, `--danger` left edge, top-right, auto-dismiss 6s, carrying
  the human-readable `message` from the error envelope and never a stack trace.

### 5.10 Iconography
No icon library (dependency budget, `rules.md` §2). Inline SVG only: 20px box, 1.5px stroke,
`currentColor`, round caps. Maximum six icons in the whole app — send, chevron, close, sun/moon,
check, alert. The north-star mark is the only filled shape.

---

## 6. Accessibility

Target: **WCAG 2.2 AA**.

- Text contrast ≥ 4.5:1; large text and UI boundaries ≥ 3:1. `--text-subtle` is barred from body copy.
- **Never colour alone.** Tool status carries a word; interest level carries a word; the score meter
  carries a numeral.
- Touch targets ≥ 44×44 px, including the theme and channel toggles.
- The message list is `role="log"` `aria-live="polite"` `aria-relevant="additions"`, so new agent
  messages are announced without stealing focus.
- **Devanagari message elements carry `lang="hi"`**, Hinglish `lang="hi-Latn"`, English `lang="en"` —
  screen readers then choose the right voice for a Hindi reply. On a multilingual product this is
  the accessibility detail that actually matters.
- Full keyboard path: toggles → composer → send → end conversation → analytics. Visible focus at
  every stop. No keyboard trap in the expandable tool trace.
- `prefers-reduced-motion` respected globally.
- The page renders correctly at 200% browser zoom and 400% text-only zoom.

---

## 7. Token Reference (paste-ready)

```css
:root {
  /* colour — light */
  --bg:#FAF8F5; --surface:#FFFFFF; --surface-alt:#F2EEE8; --surface-sunken:#EBE5DC;
  --border:#E3DCD2; --border-strong:#C9BFB1;
  --ink:#14213D; --text-muted:#5A6478; --text-subtle:#8A93A6; --on-ink:#F7F9FC;
  --brand:#C8952E; --brand-hover:#B08123; --brand-text:#8A6314;
  --brand-soft:#FBF1DC; --on-brand:#14213D;
  --success:#1B7F5A; --success-soft:#E4F4EC;
  --warning:#B4690E; --warning-soft:#FDF0DC;
  --danger:#B3261E;  --danger-soft:#FBE9E7;
  --info:#0E6C86;    --info-soft:#E1F1F6;
  --bubble-user-bg:var(--ink); --bubble-user-fg:var(--on-ink);

  /* type */
  --font-sans:"Plus Jakarta Sans","Noto Sans Devanagari",-apple-system,BlinkMacSystemFont,
              "Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  --font-mono:"JetBrains Mono","SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;
  --fs-display:2.75rem; --fs-h1:2.125rem; --fs-h2:1.6875rem; --fs-h3:1.375rem;
  --fs-h4:1.125rem; --fs-body-lg:1.125rem; --fs-body:1rem; --fs-body-sm:0.875rem;
  --fs-caption:0.8125rem; --fs-overline:0.75rem; --fs-mono:0.8125rem;
  --lh-tight:1.15; --lh-snug:1.30; --lh-normal:1.60; --lh-deva:1.75;

  /* space, radius, elevation, motion */
  --sp-1:4px; --sp-2:8px; --sp-3:12px; --sp-4:16px; --sp-5:20px;
  --sp-6:24px; --sp-8:32px; --sp-10:40px; --sp-12:48px; --sp-16:64px;
  --r-sm:6px; --r-md:10px; --r-lg:14px; --r-xl:20px; --r-pill:999px;
  --sh-sm:0 1px 2px rgba(20,33,61,.06);
  --sh-md:0 2px 8px rgba(20,33,61,.08);
  --sh-lg:0 8px 24px rgba(20,33,61,.10);
  --dur-instant:100ms; --dur-fast:160ms; --dur-base:220ms; --dur-slow:320ms;
  --ease-out:cubic-bezier(0.2,0,0,1);
  --ease-spring:cubic-bezier(0.34,1.3,0.64,1);
  --measure:34rem;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg:#0B111F; --surface:#121B2C; --surface-alt:#1A2437; --surface-sunken:#080D18;
    --border:#27324A; --border-strong:#3A4762;
    --ink:#ECF1F8; --text-muted:#A3AFC4; --text-subtle:#74819A; --on-ink:#0B111F;
    --brand:#E0B45C; --brand-hover:#EFC876; --brand-text:#E0B45C;
    --brand-soft:#2A2415; --on-brand:#14213D;
    --success:#4CC38A; --success-soft:#122A21;
    --warning:#E0A458; --warning-soft:#2B2113;
    --danger:#F2776C;  --danger-soft:#2E1614;
    --info:#5CB4CE;    --info-soft:#122430;
    --bubble-user-bg:var(--surface-alt); --bubble-user-fg:var(--ink);
    --sh-sm:0 1px 2px rgba(0,0,0,.45);
    --sh-md:0 2px 8px rgba(0,0,0,.45);
    --sh-lg:0 8px 24px rgba(0,0,0,.50);
  }
}

:root[data-theme="dark"] { /* identical dark overrides — the toggle wins in both directions */ }

:lang(hi) { line-height: var(--lh-deva); }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration:.01ms !important; transition-duration:.01ms !important; }
}
```

---

## 8. Do Not

- Do not introduce a colour outside §2. Every colour is a token.
- Do not use gradients, glassmorphism, or blur effects.
- Do not use emoji in product chrome. (Customer *messages* may contain emoji; that is their text.)
- Do not use brass for body text on a light surface — that is what `--brand-text` is for.
- Do not add a fourth font family or a size outside the scale.
- Do not use `!important` outside the reduced-motion block.
- Do not animate `width`, `height`, `top`, or `left`. Transform and opacity only.
- Do not hide a failed tool call, an `unknown` analytics value, or an error behind an icon.
- Do not centre body text or justify anything.
- Do not add a UI element that has no counterpart in `PRD.md` §6.
