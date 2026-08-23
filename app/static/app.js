// Fetch, render, tool trace, analytics panel. No framework — the reviewer must be able to
// `uvicorn app.main:app` and open a browser, nothing else (design.md D1).

const STORAGE_CHANNEL = "northstar_channel";
const STORAGE_THEME = "northstar_theme";

const state = {
  channel: localStorage.getItem(STORAGE_CHANNEL) || "chat",
  sessionId: null,
  ended: false,
};

const els = {
  messageList: document.getElementById("message-list"),
  emptyState: document.getElementById("empty-state"),
  composer: document.getElementById("composer"),
  composerInput: document.getElementById("composer-input"),
  composerSend: document.getElementById("composer-send"),
  endConversation: document.getElementById("end-conversation"),
  channelOptions: document.querySelectorAll(".channel-toggle__option"),
  voiceBanner: document.getElementById("voice-banner"),
  themeToggle: document.getElementById("theme-toggle"),
  railToggle: document.getElementById("rail-toggle"),
  insightRail: document.getElementById("insight-rail"),
  toolTrace: document.getElementById("tool-trace"),
  toolTraceEmpty: document.getElementById("tool-trace-empty"),
  analyticsEmpty: document.getElementById("analytics-empty"),
  analyticsJson: document.getElementById("analytics-json"),
  toastStack: document.getElementById("toast-stack"),
};

const DEVANAGARI_RE = /[ऀ-ॿ]/;

function langFor(text) {
  return DEVANAGARI_RE.test(text) ? "hi" : "en";
}

// ---------------------------------------------------------------------------
// Theme
// ---------------------------------------------------------------------------

function applyTheme(theme) {
  if (theme === "light" || theme === "dark") {
    document.documentElement.setAttribute("data-theme", theme);
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
}

function initTheme() {
  const stored = localStorage.getItem(STORAGE_THEME) || "system";
  applyTheme(stored);
}

function cycleTheme() {
  const current = localStorage.getItem(STORAGE_THEME) || "system";
  const next = current === "system" ? "dark" : current === "dark" ? "light" : "system";
  localStorage.setItem(STORAGE_THEME, next);
  applyTheme(next);
}

// ---------------------------------------------------------------------------
// Toasts (error envelope -> human message, never a stack trace, rule C8)
// ---------------------------------------------------------------------------

function showToast(message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.setAttribute("role", "alert");
  toast.textContent = message;
  els.toastStack.appendChild(toast);
  setTimeout(() => toast.remove(), 6000);
}

// ---------------------------------------------------------------------------
// Message rendering (rule C9 — textContent only, never innerHTML)
// ---------------------------------------------------------------------------

function clearEmptyState() {
  if (els.emptyState.parentNode) {
    els.emptyState.remove();
  }
}

function appendMessage(role, text) {
  clearEmptyState();

  const row = document.createElement("div");
  row.className = `message-row message-row--${role === "model" ? "agent" : "customer"}`;

  const bubble = document.createElement("div");
  bubble.className = `bubble bubble--${role === "model" ? "agent" : "customer"}`;
  if (state.channel === "voice" && role === "model") {
    bubble.classList.add("bubble--voice");
  }
  bubble.lang = langFor(text);
  bubble.textContent = text;

  const timestamp = document.createElement("div");
  timestamp.className = "message-timestamp";
  timestamp.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  row.appendChild(bubble);
  row.appendChild(timestamp);
  els.messageList.appendChild(row);
  els.messageList.scrollTop = els.messageList.scrollHeight;
  return row;
}

let typingRow = null;

function showTyping() {
  clearEmptyState();
  typingRow = document.createElement("div");
  typingRow.className = "message-row message-row--agent";

  const bubble = document.createElement("div");
  bubble.className = "typing-bubble";
  bubble.setAttribute("aria-label", "Agent is typing");

  for (let i = 0; i < 3; i += 1) {
    const dot = document.createElement("span");
    dot.className = "typing-bubble__dot";
    bubble.appendChild(dot);
  }

  const label = document.createElement("span");
  label.className = "typing-bubble__label";
  label.textContent = "Agent is replying…";
  bubble.appendChild(label);

  typingRow.appendChild(bubble);
  els.messageList.appendChild(typingRow);
  els.messageList.scrollTop = els.messageList.scrollHeight;
}

function hideTyping() {
  if (typingRow) {
    typingRow.remove();
    typingRow = null;
  }
}

// ---------------------------------------------------------------------------
// Tool trace (design.md §5.7 — failed rows expanded by default)
// ---------------------------------------------------------------------------

function renderToolEvents(toolEvents) {
  els.toolTrace.textContent = "";

  if (!toolEvents || toolEvents.length === 0) {
    els.toolTraceEmpty.hidden = false;
    return;
  }
  els.toolTraceEmpty.hidden = true;

  for (const event of toolEvents) {
    const row = document.createElement("li");
    row.className = "tool-trace-row";

    const details = document.createElement("details");
    details.open = !event.ok;

    const summary = document.createElement("summary");
    summary.className = "tool-trace-row__summary";

    const dot = document.createElement("span");
    dot.className = `tool-trace-row__dot tool-trace-row__dot--${event.ok ? "ok" : "failed"}`;

    const name = document.createElement("span");
    name.className = "tool-trace-row__name";
    name.textContent = event.name;

    const latency = document.createElement("span");
    latency.className = "tool-trace-row__latency";
    latency.textContent = `${event.latency_ms} ms`;

    const status = document.createElement("span");
    status.className = `tool-trace-row__status tool-trace-row__status--${event.ok ? "ok" : "failed"}`;
    status.textContent = event.ok ? "OK" : "FAILED";

    summary.appendChild(dot);
    summary.appendChild(name);
    summary.appendChild(latency);
    summary.appendChild(status);

    const detail = document.createElement("pre");
    detail.className = "tool-trace-row__detail";
    detail.textContent = JSON.stringify({ input: event.input, output: event.output }, null, 2);

    details.appendChild(summary);
    details.appendChild(detail);
    row.appendChild(details);
    els.toolTrace.appendChild(row);
  }
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

async function parseErrorEnvelope(response) {
  try {
    const body = await response.json();
    if (body && body.error && body.error.message) {
      return body.error.message;
    }
  } catch {
    // fall through to the generic message below
  }
  return "Something went wrong. Please try again.";
}

async function createSession(channel) {
  const response = await fetch("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ channel }),
  });
  if (!response.ok) {
    throw new Error(await parseErrorEnvelope(response));
  }
  return response.json();
}

async function sendMessage(sessionId, message) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  if (!response.ok) {
    throw new Error(await parseErrorEnvelope(response));
  }
  return response.json();
}

async function endSession(sessionId) {
  const response = await fetch(`/api/session/${sessionId}/end`, { method: "POST" });
  if (!response.ok) {
    throw new Error(await parseErrorEnvelope(response));
  }
  return response.json();
}

// ---------------------------------------------------------------------------
// Session lifecycle
// ---------------------------------------------------------------------------

async function startSession(channel) {
  state.channel = channel;
  state.sessionId = null;
  state.ended = false;

  els.messageList.textContent = "";
  els.messageList.appendChild(els.emptyState);
  renderToolEvents([]);
  els.analyticsJson.hidden = true;
  els.analyticsEmpty.hidden = false;
  els.endConversation.disabled = false;
  els.composerSend.disabled = els.composerInput.value.trim().length === 0;
  els.voiceBanner.hidden = channel !== "voice";

  try {
    const session = await createSession(channel);
    state.sessionId = session.session_id;
    appendMessage("model", session.greeting);
  } catch (err) {
    showToast(err.message);
  }
}

async function handleSend(message) {
  if (!state.sessionId || state.ended) {
    return;
  }

  appendMessage("user", message);
  showTyping();
  els.composerInput.disabled = true;
  els.composerSend.disabled = true;

  try {
    const result = await sendMessage(state.sessionId, message);
    hideTyping();
    appendMessage("model", result.reply);
    renderToolEvents(result.tool_events);
  } catch (err) {
    hideTyping();
    showToast(err.message);
  } finally {
    els.composerInput.disabled = false;
    els.composerInput.focus();
    els.composerSend.disabled = els.composerInput.value.trim().length === 0;
  }
}

async function handleEndConversation() {
  if (!state.sessionId || state.ended) {
    return;
  }

  try {
    const record = await endSession(state.sessionId);
    state.ended = true;
    els.endConversation.disabled = true;
    els.composerInput.disabled = true;
    els.composerSend.disabled = true;
    els.analyticsEmpty.hidden = true;
    els.analyticsJson.hidden = false;
    els.analyticsJson.textContent = JSON.stringify(record, null, 2);
    if (window.matchMedia("(max-width: 1023.98px)").matches) {
      openRail();
    }
  } catch (err) {
    showToast(err.message);
  }
}

// ---------------------------------------------------------------------------
// Channel toggle (design.md §5.6 — switching starts a new session)
// ---------------------------------------------------------------------------

function setChannelUI(channel) {
  for (const option of els.channelOptions) {
    option.setAttribute("aria-checked", String(option.dataset.channel === channel));
  }
}

async function handleChannelChange(channel) {
  if (channel === state.channel) {
    return;
  }
  showToast(`Switching to ${channel === "voice" ? "Voice" : "Chat"} — starting a new conversation.`);
  localStorage.setItem(STORAGE_CHANNEL, channel);
  setChannelUI(channel);
  await startSession(channel);
}

// ---------------------------------------------------------------------------
// Insight rail (mobile bottom sheet)
// ---------------------------------------------------------------------------

function openRail() {
  els.insightRail.classList.add("is-open");
  els.railToggle.setAttribute("aria-expanded", "true");
}

function closeRail() {
  els.insightRail.classList.remove("is-open");
  els.railToggle.setAttribute("aria-expanded", "false");
}

function toggleRail() {
  if (els.insightRail.classList.contains("is-open")) {
    closeRail();
  } else {
    openRail();
  }
}

// ---------------------------------------------------------------------------
// Composer
// ---------------------------------------------------------------------------

function autoGrowComposer() {
  els.composerInput.style.height = "auto";
  els.composerInput.style.height = `${els.composerInput.scrollHeight}px`;
}

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------

initTheme();
setChannelUI(state.channel);
els.voiceBanner.hidden = state.channel !== "voice";

els.themeToggle.addEventListener("click", cycleTheme);
els.railToggle.addEventListener("click", toggleRail);

for (const option of els.channelOptions) {
  option.addEventListener("click", () => handleChannelChange(option.dataset.channel));
}

els.composerInput.addEventListener("input", () => {
  autoGrowComposer();
  els.composerSend.disabled = els.composerInput.value.trim().length === 0;
});

els.composerInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    els.composer.requestSubmit();
  }
});

els.composer.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = els.composerInput.value.trim();
  if (!message) {
    return;
  }
  els.composerInput.value = "";
  autoGrowComposer();
  els.composerSend.disabled = true;
  handleSend(message);
});

els.endConversation.addEventListener("click", handleEndConversation);

startSession(state.channel);
