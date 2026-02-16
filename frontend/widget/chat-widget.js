/* Premium-feel chat widget (light UI, configurable theme).
 * Exposes window.AIChatWidget.init({ apiBase, websiteId, sessionId?, visitorId?, title?, subtitle?, theme? }).
 * SSE contract (unchanged): server emits `event: token` with data {"text": "..."} and `event: final` with data {"message": "..."}.
 *
 * Includes thumbs up/down feedback buttons (UI + callback hook). No refresh button, no quick replies, no suggested replies,
 * no emoji/attachment buttons, no online status.
 */

(function () {
  const defaultConfig = {
    apiBase: "",
    websiteId: "",
    sessionId: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()),
    visitorId: crypto.randomUUID ? crypto.randomUUID() : String(Date.now() + 1),
    title: "AI Assistant",
    subtitle: "Here to help",

    // Theme is easily configurable via init({ theme: { ... } })
    theme: {
      primary: "#6D28D9",
      primary2: "#7C3AED",
      border: "rgba(17,24,39,.10)",
      shadow: "0 18px 50px rgba(17,24,39,.18)",
      bg: "#ffffff",
      text: "#111827",
      muted: "rgba(17,24,39,.55)",
      botBubbleBg: "rgba(17,24,39,.04)",
      panelBgFx1: "rgba(124,58,237,.05)", // subtle background glow
      panelBgFx2: "rgba(99,102,241,.04)", // subtle background glow
    },

    // Optional: feedback handler hook
    // Called when user clicks 👍 or 👎 on the latest assistant message.
    // You can wire this to your backend later.
    onFeedback: null, // ({websiteId, sessionId, visitorId, rating: "up"|"down", message, ts}) => void
  };

  const state = {
    streaming: false,
    controller: null,
    lastAssistantText: "",
    lastAssistantBubble: null,
  };

  const els = {};
  let config = { ...defaultConfig };
  let initialized = false;

  function init(userConfig = {}) {
    if (initialized) return;
    config = deepMerge({ ...defaultConfig }, userConfig);
    if (!config.websiteId) {
      console.warn("[AIChatWidget] websiteId is missing. Calls may be rejected.");
    }

    injectStyles();
    buildUI();
    initialized = true;
  }

  // --- UI builders ---------------------------------------------------------
  function injectStyles() {
    if (document.getElementById("ai-chat-widget-styles")) return;

    const t = config.theme || defaultConfig.theme;

    const style = document.createElement("style");
    style.id = "ai-chat-widget-styles";
    style.textContent = `
      :root{
        --aiw-primary: ${t.primary};
        --aiw-primary2: ${t.primary2};
        --aiw-border: ${t.border};
        --aiw-shadow: ${t.shadow};
        --aiw-bg: ${t.bg};
        --aiw-text: ${t.text};
        --aiw-muted: ${t.muted};
        --aiw-botBubbleBg: ${t.botBubbleBg};
        --aiw-fx1: ${t.panelBgFx1};
        --aiw-fx2: ${t.panelBgFx2};
        --aiw-font: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji","Segoe UI Emoji";
      }

      #ai-chat-widget{
        position: fixed;
        right: 22px;
        bottom: 22px;
        z-index: 2147483000;
        font-family: var(--aiw-font);
        color: var(--aiw-text);
      }

      /* Launcher */
      #ai-chat-bubble{
        width: 56px;
        height: 56px;
        border-radius: 999px;
        border: 1px solid var(--aiw-border);
        background: radial-gradient(120% 120% at 10% 10%, color-mix(in oklab, var(--aiw-primary2) 92%, white 8%), color-mix(in oklab, var(--aiw-primary) 82%, black 18%));
        box-shadow: var(--aiw-shadow);
        display:flex;
        align-items:center;
        justify-content:center;
        cursor:pointer;
        user-select:none;
        transition: transform .15s ease, filter .15s ease;
        padding: 0;
      }
      #ai-chat-bubble:hover{ transform: translateY(-1px); filter: brightness(1.02); }
      #ai-chat-bubble:active{ transform: translateY(0px) scale(.98); }
      #ai-chat-bubble:focus-visible{ outline: 2px solid var(--aiw-primary); outline-offset: 2px; }
      #ai-chat-bubble .ai-icon{
        width: 26px; height: 26px;
        display:block;
        fill: #fff;
        opacity:.95;
      }

      /* Panel */
      #ai-chat-panel{
        position: fixed;
        right: 22px;
        bottom: 90px;
        width: 380px;
        max-width: calc(100vw - 44px);
        height: 580px;
        max-height: calc(100vh - 130px);
        border-radius: 18px;
        background: var(--aiw-bg);
        border: 1px solid var(--aiw-border);
        box-shadow: var(--aiw-shadow);
        overflow: hidden;
        transform-origin: bottom right;
        transform: scale(.98);
        opacity: 0;
        pointer-events: none;
        transition: transform .16s ease, opacity .16s ease;
        display: flex;
        flex-direction: column;
      }
      #ai-chat-panel.open{
        transform: scale(1);
        opacity: 1;
        pointer-events: auto;
      }

      /* Header */
      .ai-panel-header{
        display:flex;
        align-items:center;
        justify-content: space-between;
        padding: 20px 18px 16px 20px;
        border-bottom: 1px solid rgba(17,24,39,.06);
        background: linear-gradient(180deg, color-mix(in oklab, var(--aiw-primary) 7%, white 93%), rgba(255,255,255,0));
      }
      .ai-brand{
        display:flex;
        align-items:center;
        gap: 11px;
        min-width: 0;
      }
      .ai-avatar{
        width: 36px;
        height: 36px;
        border-radius: 11px;
        background: radial-gradient(120% 120% at 20% 20%, color-mix(in oklab, var(--aiw-primary2) 92%, white 8%), color-mix(in oklab, var(--aiw-primary) 82%, black 18%));
        display:flex;
        align-items:center;
        justify-content:center;
        flex: 0 0 auto;
        box-shadow: 0 6px 18px color-mix(in oklab, var(--aiw-primary) 25%, transparent 75%);
      }
      .ai-avatar svg{ width: 20px; height: 20px; fill: #fff; opacity:.95; }
      .ai-title{
        display:flex;
        flex-direction: column;
        min-width: 0;
      }
      .ai-panel-title{
        font-size: 14px;
        font-weight: 700;
        color: var(--aiw-text);
        line-height: 1.2;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-bottom: 1px;
      }
      .ai-panel-subtitle{
        font-size: 11px;
        color: var(--aiw-muted);
        line-height: 1.2;
      }

      .ai-actions{
        display:flex;
        align-items:center;
        gap: 6px;
      }
      .ai-iconbtn{
        width: 40px;
        height: 40px;
        border-radius: 12px;
        border: 1px solid rgba(17,24,39,.08);
        background: #fff;
        display:flex;
        align-items:center;
        justify-content:center;
        cursor:pointer;
        transition: background .12s ease, transform .12s ease;
        padding: 0;
      }
      .ai-iconbtn:hover{ background: color-mix(in oklab, var(--aiw-primary) 6%, white 94%); }
      .ai-iconbtn:active{ transform: scale(.98); }
      .ai-iconbtn:focus-visible{ outline: 2px solid var(--aiw-primary); outline-offset: 2px; }
      .ai-iconbtn svg{ width: 17px; height: 17px; stroke: rgba(17,24,39,.65); fill: none; }

      /* Body */
      .ai-panel-body{
        flex: 1;
        padding: 16px 14px 20px;
        overflow: auto;
        scroll-behavior: smooth;
        background:
          radial-gradient(100% 90% at 30% 0%, var(--aiw-fx1), rgba(255,255,255,0) 60%),
          radial-gradient(90% 80% at 80% 20%, var(--aiw-fx2), rgba(255,255,255,0) 55%),
          var(--aiw-bg);
      }

      .ai-meta{
        text-align:center;
        font-size: 11px;
        color: rgba(17,24,39,.40);
        margin: 6px 0 14px;
        font-weight: 500;
        letter-spacing: 0.3px;
      }
      .ai-messages{
        display:flex;
        flex-direction: column;
        gap: 12px;
      }

      .ai-msgrow{ display:flex; flex-direction: column; }
      .ai-msgrow.left{ align-items: flex-start; }
      .ai-msgrow.right{ align-items: flex-end; }

      .ai-msg{
        max-width: 80%;
        padding: 11px 13px;
        font-size: 13.5px;
        line-height: 1.45;
        border-radius: 16px;
        border: 1px solid rgba(17,24,39,.08);
        color: var(--aiw-text);
        background: var(--aiw-botBubbleBg);
        box-shadow: 0 6px 18px rgba(17,24,39,.06);
        white-space: pre-wrap;
        word-break: break-word;
        overflow-wrap: break-word;
        word-wrap: break-word;
        position: relative;
      }
      .ai-msg.user{
        background: linear-gradient(135deg, var(--aiw-primary), var(--aiw-primary2));
        color: #fff;
        border: 1px solid color-mix(in oklab, var(--aiw-primary) 40%, transparent 60%);
        box-shadow: 0 10px 26px color-mix(in oklab, var(--aiw-primary) 22%, transparent 78%);
      }

      /* Pulsing background for streaming message */
      .ai-msg.streaming::before {
        content: "";
        position: absolute;
        inset: -1px;
        border-radius: inherit;
        background: color-mix(in oklab, var(--aiw-primary) 10%, transparent 90%);
        pointer-events: none;
        animation: aiwPulse 1.6s ease-in-out infinite;
      }

      @keyframes aiwPulse {
        0%, 100% { opacity: .12; }
        50% { opacity: .28; }
      }

      /* Typing dots container */
      .ai-msg.streaming::after {
        content: "";
        display: inline-block;
        margin-left: 6px;
        width: 1.5em;
        height: 1em;
        vertical-align: middle;
        background-image:
          radial-gradient(circle, rgba(109, 40, 217, 0.5) 35%, transparent 35%),
          radial-gradient(circle, rgba(109, 40, 217, 0.5) 35%, transparent 35%),
          radial-gradient(circle, rgba(109, 40, 217, 0.5) 35%, transparent 35%);
        background-size: 6px 6px;
        background-position: 0 50%, 50% 50%, 100% 50%;
        background-repeat: no-repeat;
        opacity: 0.7;
        animation: aiwDots 1.4s infinite ease-in-out;
      }

      /* Dots animation - staggered bounce */
      @keyframes aiwDots {
        0%, 100% {
          background-position: 0 50%, 50% 50%, 100% 50%;
        }
        20% {
          background-position: 0 30%, 50% 50%, 100% 50%;
        }
        40% {
          background-position: 0 50%, 50% 30%, 100% 50%;
        }
        60% {
          background-position: 0 50%, 50% 50%, 100% 30%;
        }
        80% {
          background-position: 0 50%, 50% 50%, 100% 50%;
        }
      }

      /* Footer */
      .ai-footer{
        border-top: 1px solid rgba(17,24,39,.06);
        padding: 12px 16px 10px;
        background: var(--aiw-bg);
      }
      .ai-powered{
        text-align: center;
        font-size: 11px;
        color: rgba(17,24,39,.45);
        margin-top: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 4px;
      }
      .ai-powered svg{
        width: 12px;
        height: 12px;
        fill: rgba(17,24,39,.45);
      }
      .ai-inputwrap{
        height: 48px;
        border-radius: 14px;
        border: 1px solid rgba(17,24,39,.10);
        background: rgba(17,24,39,.025);
        display:flex;
        align-items:center;
        gap: 10px;
        padding: 0 10px;
        transition: border-color .2s ease, background .2s ease;
      }
      .ai-inputwrap:focus-within{
        border-color: color-mix(in oklab, var(--aiw-primary) 40%, transparent 60%);
        background: rgba(17,24,39,.015);
      }
      .ai-inputwrap input{
        flex: 1 1 auto;
        min-width: 0;
        height: 100%;
        border: none;
        outline: none;
        background: transparent;
        font-size: 13.5px;
        color: var(--aiw-text);
        padding: 0 2px;
      }
      .ai-inputwrap input::placeholder{
        color: color-mix(in oklab, var(--aiw-text) 42%, white 58%);
      }
      .ai-inputwrap input:disabled{
        opacity: 0.6;
        cursor: not-allowed;
      }

      .ai-send{
        width: 40px;
        height: 40px;
        border-radius: 14px;
        border: none;
        cursor:pointer;
        background: linear-gradient(135deg, var(--aiw-primary), var(--aiw-primary2));
        display:flex;
        align-items:center;
        justify-content:center;
        box-shadow: 0 10px 24px color-mix(in oklab, var(--aiw-primary) 22%, transparent 78%);
        padding: 0;
        transition: transform .12s ease, opacity .12s ease;
      }
      .ai-send:disabled{ opacity:.5; cursor:not-allowed; box-shadow:none; }
      .ai-send:not(:disabled):hover{ transform: translateY(-1px); }
      .ai-send:not(:disabled):active{ transform: translateY(0) scale(.98); }
      .ai-send:focus-visible{ outline: 2px solid var(--aiw-primary); outline-offset: 2px; }
      .ai-send svg{ width: 18px; height: 18px; fill: #fff; }

      /* Retry */
      .ai-retry-row{
        margin-top: 8px;
        display:flex;
        gap: 8px;
        align-items:center;
        justify-content:flex-start;
      }
      .ai-retry-btn{
        border: 1px solid rgba(17,24,39,.12);
        background: #fff;
        color: rgba(17,24,39,.75);
        border-radius: 12px;
        padding: 7px 11px;
        font-size: 12px;
        cursor: pointer;
        transition: background .12s ease, transform .12s ease, border-color .12s ease;
        display: flex;
        align-items: center;
        gap: 5px;
        font-weight: 500;
      }
      .ai-retry-btn:hover{
        background: color-mix(in oklab, var(--aiw-primary) 6%, white 94%);
        border-color: rgba(17,24,39,.18);
      }
      .ai-retry-btn:active{ transform: scale(.98); }
      .ai-retry-btn:focus-visible{ outline: 2px solid var(--aiw-primary); outline-offset: 2px; }
      .ai-retry-btn svg{
        width: 14px;
        height: 14px;
        stroke: currentColor;
        fill: none;
      }
      .ai-retry-hint{
        font-size: 11.5px;
        color: rgba(17,24,39,.50);
      }

      /* Feedback */
      .ai-feedback{
        display:flex;
        justify-content:flex-start;
        gap: 6px;
        margin-top: 8px;
        user-select:none;
      }
      .ai-fbbtn{
        border: 1px solid rgba(17,24,39,.10);
        background: #fff;
        color: rgba(17,24,39,.75);
        border-radius: 10px;
        padding: 6px 11px;
        font-size: 13px;
        cursor: pointer;
        transition: background .12s ease, transform .12s ease, border-color .12s ease;
        min-width: 40px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .ai-fbbtn:hover{
        background: color-mix(in oklab, var(--aiw-primary) 6%, white 94%);
        border-color: rgba(17,24,39,.16);
      }
      .ai-fbbtn:active{ transform: scale(.98); }
      .ai-fbbtn:focus-visible{ outline: 2px solid var(--aiw-primary); outline-offset: 2px; }
      .ai-fbbtn[disabled]{
        opacity:.5;
        cursor:not-allowed;
        transform:none;
        background: rgba(17,24,39,.04);
      }

      @media (max-width: 600px){
        #ai-chat-widget{ right: 12px; bottom: 12px; }
        #ai-chat-panel{
          right: 12px;
          bottom: 80px;
          width: calc(100vw - 24px);
          height: calc(100vh - 100px);
        }
      }
    `;
    document.head.appendChild(style);
  }

  function buildUI() {
    const root = document.createElement("div");
    root.id = "ai-chat-widget";

    const bubble = document.createElement("button");
    bubble.id = "ai-chat-bubble";
    bubble.type = "button";
    bubble.setAttribute("aria-label", "Open AI chat");
    bubble.innerHTML = `
      <svg class="ai-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 4h16v11a4 4 0 0 1-4 4H9l-4.5 2.6A1 1 0 0 1 3 20.8V8a4 4 0 0 1 4-4z"></path>
      </svg>
    `;
    bubble.addEventListener("click", togglePanel);

    const panel = document.createElement("div");
    panel.id = "ai-chat-panel";

    const header = document.createElement("div");
    header.className = "ai-panel-header";
    header.innerHTML = `
      <div class="ai-brand">
        <div class="ai-avatar" title="AI Assistant">
          <svg viewBox="0 0 24 24" aria-hidden="true">
              <rect x="3.5" y="6" width="17" height="11"
                    rx="2" ry="2"
                    fill="none" stroke="white" stroke-width="1.6"></rect>
              <path d="M9 17 L11 17 L10 19 Z"
                    fill="none" stroke="white" stroke-width="1.6"
                    stroke-linejoin="round"></path>
              <circle cx="9.5" cy="11.5" r="1.3" fill="white"></circle>
              <circle cx="12"  cy="11.5" r="1.3" fill="white"></circle>
              <circle cx="14.5" cy="11.5" r="1.3" fill="white"></circle>
           </svg>
        </div>
        <div class="ai-title">
          <div class="ai-panel-title">${escapeHtml(config.title || "AI Assistant")}</div>
          <div class="ai-panel-subtitle">${escapeHtml(config.subtitle || "Here to help")}</div>
        </div>
      </div>

      <div class="ai-actions">
        <button class="ai-iconbtn" type="button" data-action="minimize" aria-label="Minimize" title="Minimize">
          <svg viewBox="0 0 24 24" stroke-width="2">
            <path d="M7 12h10"></path>
          </svg>
        </button>
      </div>
    `;

    const body = document.createElement("div");
    body.className = "ai-panel-body";

    const meta = document.createElement("div");
    meta.className = "ai-meta";
    meta.textContent = new Date().toLocaleDateString(undefined, {
      year: "numeric",
      month: "long",
      day: "numeric",
    });

    const messages = document.createElement("div");
    messages.className = "ai-messages";
    messages.setAttribute("aria-live", "polite");
    messages.setAttribute("aria-relevant", "additions");

    body.appendChild(meta);
    body.appendChild(messages);

    const footer = document.createElement("div");
    footer.className = "ai-footer";

    const form = document.createElement("form");
    form.className = "ai-inputwrap";
    form.innerHTML = `
      <input type="text" name="message" autocomplete="off" placeholder="Type your message..." aria-label="Message input" />
      <button class="ai-send" type="submit" aria-label="Send message">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M2 21 23 12 2 3v7l15 2-15 2v7z"></path>
        </svg>
      </button>
    `;
    form.addEventListener("submit", onSubmit);

    const powered = document.createElement("div");
    powered.className = "ai-powered";
    powered.innerHTML = `
      Powered by GM-Intelligence
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M13 2L3 14h8l-1 8 10-12h-8l1-8z"></path>
      </svg>
    `;

    footer.appendChild(form);
    footer.appendChild(powered);

    panel.appendChild(header);
    panel.appendChild(body);
    panel.appendChild(footer);

    root.appendChild(panel);
    root.appendChild(bubble);
    document.body.appendChild(root);

    els.root = root;
    els.bubble = bubble;
    els.panel = panel;
    els.header = header;
    els.body = body;
    els.messages = messages;
    els.meta = meta;
    els.input = form.querySelector("input");
    els.sendBtn = form.querySelector('button[type="submit"]');

    root.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-action]");
      if (!btn) return;

      const action = btn.getAttribute("data-action");
      if (action === "minimize") {
        els.panel.classList.remove("open");
        return;
      }
    });

    // Optional initial assistant message
    addMessage("assistant", "Hi! How can I help you today?");
  }

  function attachRetryControl(assistantMsg, promptToRetry) {
    // Avoid duplicate retry buttons in the same message bubble
    if (assistantMsg.querySelector(".ai-retry-row")) return;

    const row = document.createElement("div");
    row.className = "ai-retry-row";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ai-retry-btn";
    btn.innerHTML = `
      <svg viewBox="0 0 24 24" stroke-width="2">
        <path d="M21 2v6h-6M3 12a9 9 0 0 1 15-6.7L21 8"></path>
      </svg>
      Retry
    `;

    const small = document.createElement("span");
    small.className = "ai-retry-hint";
    small.textContent = "If the issue persists, please try again later.";

    btn.addEventListener("click", () => {
      // Prevent retry if already streaming
      if (state.streaming) return;
      // Remove retry controls so UI is clean before retry
      row.remove();
      streamMessage(promptToRetry);
    });

    row.appendChild(btn);
    row.appendChild(small);
    assistantMsg.appendChild(row);
  }

  function clearRetryControl(assistantMsg) {
    const row = assistantMsg.querySelector(".ai-retry-row");
    if (row) row.remove();
  }

  // --- UI helpers ----------------------------------------------------------
  function togglePanel() {
    const open = !els.panel.classList.contains("open");
    els.panel.classList.toggle("open", open);
    if (open) {
      els.input.focus();
      scrollMessages();
    }
  }

  function scrollMessages() {
    requestAnimationFrame(() => {
      (els.body || els.messages).scrollTop = (els.body || els.messages).scrollHeight;
    });
  }

  function addMessage(role, text, opts = {}) {
    const row = document.createElement("div");
    row.className = `ai-msgrow ${role === "user" ? "right" : "left"}`;

    const bubble = document.createElement("div");
    bubble.className = `ai-msg ${role}${opts.streaming ? " streaming" : ""}`;
    bubble.textContent = text;

    row.appendChild(bubble);
    els.messages.appendChild(row);
    scrollMessages();

    if (role === "assistant") {
      state.lastAssistantBubble = bubble;
      state.lastAssistantText = text || "";
    }

    return bubble;
  }

  function attachFeedbackControls(assistantBubble, finalMessageText) {
    // Remove any existing feedback controls
    const existing = els.messages.querySelector(".ai-feedback");
    if (existing) existing.remove();

    const wrap = document.createElement("div");
    wrap.className = "ai-feedback";

    const up = document.createElement("button");
    up.type = "button";
    up.className = "ai-fbbtn";
    up.setAttribute("aria-label", "Helpful");
    up.textContent = "👍";

    const down = document.createElement("button");
    down.type = "button";
    down.className = "ai-fbbtn";
    down.setAttribute("aria-label", "Not helpful");
    down.textContent = "👎";

    const disableBoth = () => {
      up.disabled = true;
      down.disabled = true;
    };

    up.addEventListener("click", () => {
      disableBoth();
      emitFeedback("up", finalMessageText);
    });

    down.addEventListener("click", () => {
      disableBoth();
      emitFeedback("down", finalMessageText);
    });

    wrap.appendChild(up);
    wrap.appendChild(down);

    // Place feedback in the same row as the assistant bubble
    const row = assistantBubble?.parentElement;
    if (row && row.parentElement === els.messages) {
      row.appendChild(wrap);
    }

    scrollMessages();
  }

  function emitFeedback(rating, message) {
    const payload = {
      websiteId: config.websiteId,
      sessionId: config.sessionId,
      visitorId: config.visitorId,
      rating,
      message,
      ts: new Date().toISOString(),
    };

    // Hook for you to wire later
    if (typeof config.onFeedback === "function") {
      try {
        config.onFeedback(payload);
      } catch (e) {
        console.error("[AIChatWidget] onFeedback error:", e);
      }
    } else {
      // Default: log only (safe no-op)
      console.log("[AIChatWidget] feedback:", payload);
    }
  }

  // --- Networking / streaming ---------------------------------------------
  async function onSubmit(ev) {
    ev.preventDefault();
    const value = (els.input.value || "").trim();
    if (!value || state.streaming) return;

    addMessage("user", value);
    els.input.value = "";
    await streamMessage(value);
  }

  function parseSSE(chunk) {
    const lines = chunk.split("\n");
    let event = "message";
    let data = "";
    for (const line of lines) {
      if (line.startsWith("event:")) {
        event = line.replace("event:", "").trim();
      } else if (line.startsWith("data:")) {
        data += line.replace("data:", "").trim();
      }
    }
    if (!data) return null;
    try {
      return { event, data: JSON.parse(data) };
    } catch {
      return null;
    }
  }

  async function streamMessage(prompt) {
    // Store last prompt for retry
    state.lastUserPrompt = prompt;

    // If already streaming, abort the existing stream first
    if (state.streaming) {
      state.controller?.abort();
    }

    state.streaming = true;
    state.controller = new AbortController();

    // Disable input while streaming
    els.input.disabled = true;
    els.sendBtn.disabled = true;

    const assistantMsg = addMessage("assistant", "Thinking", { streaming: true });
    clearRetryControl(assistantMsg);

    let fullText = "";
    let gotFinal = false;
    let hasStartedTyping = false;

    // --- Watchdog (abort if no SSE activity for X ms) ---
    const WATCHDOG_MS = 25000;
    let watchdogTimer = null;

    const resetWatchdog = () => {
      if (watchdogTimer) clearTimeout(watchdogTimer);
      watchdogTimer = setTimeout(() => {
        try {
          state.controller?.abort();
        } catch (_) {}
      }, WATCHDOG_MS);
    };

    // Start watchdog immediately
    resetWatchdog();

    try {
      const response = await fetch(joinUrl(config.apiBase, "/chat/stream"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          website_id: config.websiteId,
          message: prompt,
          session_id: config.sessionId,
          visitor_id: config.visitorId,
        }),
        signal: state.controller.signal,
      });

      if (!response.body) {
        throw new Error("Unable to reach assistant.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        resetWatchdog();

        buffer += decoder.decode(value, { stream: true });

        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const part of parts) {
          const parsed = parseSSE(part.trim());
          if (!parsed) continue;

          resetWatchdog();

          if (parsed.event === "token" && parsed.data?.text) {
            // Clear "Thinking" placeholder on first token
            if (!hasStartedTyping) {
              fullText = "";
              hasStartedTyping = true;
            }
            fullText += parsed.data.text;
            assistantMsg.textContent = fullText;
            scrollMessages();

          } else if (parsed.event === "final") {
            gotFinal = true;

            if (parsed.data?.message) {
              fullText = parsed.data.message;
              assistantMsg.textContent = fullText;
            } else if (parsed.data?.error?.message) {
              fullText = parsed.data.error.message;
              assistantMsg.textContent = fullText;

              if (parsed.data?.error?.retryable) {
                attachRetryControl(assistantMsg, state.lastUserPrompt);
              }
            } else {
              assistantMsg.textContent = fullText || "I had trouble responding just now. Please try again.";
              if (parsed.data?.error?.retryable) {
                attachRetryControl(assistantMsg, state.lastUserPrompt);
              }
            }

            assistantMsg.classList.remove("streaming");
            state.lastAssistantText = fullText || "";
            state.lastAssistantBubble = assistantMsg;

            if (!parsed.data?.error) {
              attachFeedbackControls(assistantMsg, state.lastAssistantText);
            }

            state.streaming = false;
          }
        }
      }

      if (!gotFinal) {
        assistantMsg.classList.remove("streaming");

        if (fullText && fullText.trim().length > 0) {
          assistantMsg.textContent = fullText + "\n\n(Interrupted. Please retry.)";
        } else {
          assistantMsg.textContent = "I had trouble responding just now. Please try again.";
        }

        attachRetryControl(assistantMsg, state.lastUserPrompt);
      }

    } catch (err) {
      assistantMsg.classList.remove("streaming");

      const isAbort = err?.name === "AbortError";

      assistantMsg.textContent = isAbort
        ? "The connection stalled. Please retry."
        : "I had trouble responding just now. Please try again.";

      attachRetryControl(assistantMsg, state.lastUserPrompt);
      console.error("[AIChatWidget]", err);

    } finally {
      if (watchdogTimer) clearTimeout(watchdogTimer);
      state.streaming = false;
      state.controller = null;
      els.input.disabled = false;
      els.sendBtn.disabled = false;
      els.input.focus();
      scrollMessages();
    }
  }

  function joinUrl(base, path) {
    if (!base) return path;
    return base.replace(/\/+$/, "") + path;
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function deepMerge(target, source) {
    const out = { ...target };
    if (!source || typeof source !== "object") return out;
    for (const k of Object.keys(source)) {
      const sv = source[k];
      const tv = out[k];
      if (sv && typeof sv === "object" && !Array.isArray(sv) && tv && typeof tv === "object" && !Array.isArray(tv)) {
        out[k] = deepMerge(tv, sv);
      } else {
        out[k] = sv;
      }
    }
    return out;
  }

  // Expose globally
  window.AIChatWidget = { init, toggle: togglePanel };
})();