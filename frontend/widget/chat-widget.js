/* Premium-feel chat widget for website assistants.
 * Exposes window.AIChatWidget.init({ apiBase, websiteId, sessionId?, visitorId? }).
 * Lightweight: vanilla JS + injected CSS only.
 */

(function () {
  const defaultConfig = {
    apiBase: "",
    websiteId: "",
    sessionId: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()),
    visitorId: crypto.randomUUID ? crypto.randomUUID() : String(Date.now() + 1),
    title: "Ask AI",
  };

  const state = {
    streaming: false,
    controller: null,
  };

  const els = {};
  let config = { ...defaultConfig };
  let initialized = false;

  function init(userConfig = {}) {
    if (initialized) return;
    config = { ...config, ...userConfig };
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
    const style = document.createElement("style");
    style.id = "ai-chat-widget-styles";
    style.textContent = `
      :root {
        --ai-gradient: linear-gradient(135deg, #6c5ce7 0%, #8f6cf7 40%, #16a1ff 100%);
        --ai-surface: #0f172a;
        --ai-muted: #6b7280;
        --ai-border: rgba(255,255,255,0.08);
      }
      #ai-chat-widget {
        position: fixed;
        inset: auto 18px 18px auto;
        z-index: 2147483000;
        font-family: "Inter", "SF Pro Text", system-ui, -apple-system, sans-serif;
        color: #0f172a;
      }
      #ai-chat-bubble {
        width: 58px;
        height: 58px;
        border-radius: 50%;
        border: none;
        cursor: pointer;
        background-image: var(--ai-gradient);
        color: #fff;
        display: grid;
        place-items: center;
        box-shadow: 0 10px 30px rgba(52, 104, 255, 0.35);
        transition: transform 0.2s ease, box-shadow 0.25s ease, filter 0.25s ease;
        animation: ai-bubble-pulse 2.8s ease-in-out infinite;
      }
      #ai-chat-bubble:hover {
        transform: translateY(-2px) scale(1.02);
        box-shadow: 0 14px 32px rgba(52, 104, 255, 0.45);
        filter: brightness(1.03);
      }
      #ai-chat-bubble:active { transform: scale(0.98); }
      #ai-chat-bubble.open { animation: none; }
      #ai-chat-bubble .ai-icon {
        font-size: 20px;
        font-weight: 700;
        letter-spacing: -0.02em;
      }
      #ai-chat-panel {
        position: fixed;
        width: 360px;
        max-width: 90vw;
        inset: auto 18px 88px auto;
        background: #0b1220;
        color: #e5e7eb;
        border-radius: 16px;
        box-shadow: 0 18px 46px rgba(11, 17, 32, 0.55);
        border: 1px solid rgba(255,255,255,0.06);
        overflow: hidden;
        opacity: 0;
        pointer-events: none;
        transform: translateY(12px) scale(0.98);
        transition: opacity 0.25s ease, transform 0.25s ease;
      }
      #ai-chat-panel.open {
        opacity: 1;
        pointer-events: auto;
        transform: translateY(0) scale(1);
      }
      .ai-panel-header {
        padding: 14px 16px;
        display: flex;
        align-items: center;
        gap: 10px;
        background: rgba(255,255,255,0.03);
        border-bottom: 1px solid var(--ai-border);
      }
      .ai-panel-title {
        font-weight: 700;
        font-size: 15px;
        letter-spacing: -0.01em;
      }
      .ai-status-dot {
        width: 9px;
        height: 9px;
        border-radius: 50%;
        background-image: var(--ai-gradient);
        box-shadow: 0 0 0 6px rgba(121, 134, 255, 0.15);
      }
      .ai-panel-body {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding: 12px 12px 10px;
        height: 420px;
        background: radial-gradient(circle at 20% 20%, rgba(255,255,255,0.02), transparent 30%), #0b1220;
      }
      .ai-messages {
        flex: 1;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding-right: 4px;
        scrollbar-width: thin;
      }
      .ai-messages::-webkit-scrollbar { width: 6px; }
      .ai-messages::-webkit-scrollbar-thumb {
        background: rgba(255,255,255,0.12);
        border-radius: 4px;
      }
      .ai-empty {
        text-align: center;
        padding: 36px 16px;
        color: #a5b4fc;
        background: rgba(255,255,255,0.02);
        border: 1px dashed rgba(255,255,255,0.08);
        border-radius: 12px;
        font-weight: 600;
        letter-spacing: -0.01em;
      }
      .ai-msg {
        max-width: 88%;
        padding: 12px 14px;
        border-radius: 14px;
        font-size: 14px;
        line-height: 1.45;
        position: relative;
        animation: ai-message-in 0.25s ease;
        backdrop-filter: blur(6px);
      }
      .ai-msg.assistant {
        align-self: flex-start;
        background-image: var(--ai-gradient);
        color: #fff;
        box-shadow: 0 10px 28px rgba(53, 125, 255, 0.28);
        border: 1px solid rgba(255,255,255,0.08);
      }
      .ai-msg.user {
        align-self: flex-end;
        background: rgba(255,255,255,0.06);
        color: #e5e7eb;
        border: 1px solid rgba(255,255,255,0.08);
      }
      .ai-msg.streaming::after {
        content: "";
        position: absolute;
        inset: -1px;
        border-radius: inherit;
        background: rgba(255,255,255,0.08);
        pointer-events: none;
        mask: radial-gradient(circle, rgba(255,255,255,0.2) 0%, transparent 60%);
        animation: ai-stream-glow 1.6s ease-in-out infinite;
      }
      .ai-typing {
        display: inline-flex;
        gap: 4px;
        align-items: center;
      }
      .ai-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #fff;
        opacity: 0.75;
        animation: ai-bounce 1s infinite;
      }
      .ai-dot:nth-child(2) { animation-delay: 0.15s; }
      .ai-dot:nth-child(3) { animation-delay: 0.3s; }
      .ai-input {
        display: flex;
        gap: 8px;
        align-items: center;
        background: rgba(255,255,255,0.05);
        border: 1px solid var(--ai-border);
        border-radius: 12px;
        padding: 10px 12px;
      }
      .ai-input input {
        flex: 1;
        background: transparent;
        border: none;
        outline: none;
        color: #e5e7eb;
        font-size: 14px;
      }
      .ai-input button {
        background-image: var(--ai-gradient);
        color: #fff;
        border: none;
        border-radius: 10px;
        padding: 8px 12px;
        font-weight: 700;
        cursor: pointer;
        box-shadow: 0 10px 24px rgba(52, 104, 255, 0.35);
        transition: transform 0.18s ease, box-shadow 0.18s ease;
      }
      .ai-input button:hover { transform: translateY(-1px); }
      .ai-input button:active { transform: translateY(0); box-shadow: 0 8px 16px rgba(52,104,255,0.28); }
      @keyframes ai-bubble-pulse {
        0%, 100% { transform: scale(1); box-shadow: 0 10px 30px rgba(52, 104, 255, 0.3); }
        50% { transform: scale(1.04); box-shadow: 0 14px 34px rgba(52, 104, 255, 0.45); }
      }
      @keyframes ai-message-in {
        from { opacity: 0; transform: translateY(6px); }
        to { opacity: 1; transform: translateY(0); }
      }
      @keyframes ai-bounce {
        0%, 100% { transform: translateY(0); opacity: 0.4; }
        50% { transform: translateY(-4px); opacity: 1; }
      }
      @keyframes ai-stream-glow {
        0%, 100% { opacity: 0.18; }
        50% { opacity: 0.32; }
      }
      @media (max-width: 600px) {
        #ai-chat-widget { inset: auto 12px 12px auto; }
        #ai-chat-panel { width: calc(100vw - 24px); inset: auto 12px 80px auto; }
        #ai-chat-bubble { width: 54px; height: 54px; }
      }
    `;
    document.head.appendChild(style);
  }

  function buildUI() {
    const root = document.createElement("div");
    root.id = "ai-chat-widget";

    const bubble = document.createElement("button");
    bubble.id = "ai-chat-bubble";
    bubble.setAttribute("aria-label", "Open AI chat");
    bubble.innerHTML = `<span class="ai-icon">✦</span>`;
    bubble.addEventListener("click", togglePanel);

    const panel = document.createElement("div");
    panel.id = "ai-chat-panel";

    const header = document.createElement("div");
    header.className = "ai-panel-header";
    header.innerHTML = `
      <div class="ai-status-dot"></div>
      <div class="ai-panel-title">${config.title}</div>
    `;

    const body = document.createElement("div");
    body.className = "ai-panel-body";

    const messages = document.createElement("div");
    messages.className = "ai-messages";

    const empty = document.createElement("div");
    empty.className = "ai-empty";
    empty.textContent = "Ask me anything about this website.";
    messages.appendChild(empty);

    const form = document.createElement("form");
    form.className = "ai-input";
    form.innerHTML = `
      <input type="text" name="message" autocomplete="off" placeholder="Type a message..." />
      <button type="submit">Send</button>
    `;
    form.addEventListener("submit", onSubmit);

    body.appendChild(messages);
    body.appendChild(form);

    panel.appendChild(header);
    panel.appendChild(body);

    root.appendChild(panel);
    root.appendChild(bubble);
    document.body.appendChild(root);

    els.root = root;
    els.bubble = bubble;
    els.panel = panel;
    els.messages = messages;
    els.empty = empty;
    els.input = form.querySelector("input");
    els.sendBtn = form.querySelector("button");
  }

  // --- UI helpers ----------------------------------------------------------
  function togglePanel() {
    const open = !els.panel.classList.contains("open");
    els.panel.classList.toggle("open", open);
    els.bubble.classList.toggle("open", open);
    if (open) {
      els.input.focus();
      scrollMessages();
    }
  }

  function scrollMessages() {
    requestAnimationFrame(() => {
      els.messages.scrollTop = els.messages.scrollHeight;
    });
  }

  function showEmptyState(show) {
    els.empty.style.display = show ? "block" : "none";
  }

  function addMessage(role, text, opts = {}) {
    showEmptyState(false);
    const msg = document.createElement("div");
    msg.className = `ai-msg ${role}${opts.streaming ? " streaming" : ""}`;
    msg.textContent = text;
    els.messages.appendChild(msg);
    scrollMessages();
    return msg;
  }

  function setTypingIndicator(visible) {
    if (visible) {
      if (els.typing) return;
      const typing = document.createElement("div");
      typing.className = "ai-msg assistant";
      typing.dataset.typing = "true";
      typing.innerHTML = `<span class="ai-typing"><span class="ai-dot"></span><span class="ai-dot"></span><span class="ai-dot"></span></span>`;
      els.messages.appendChild(typing);
      els.typing = typing;
      scrollMessages();
    } else if (els.typing) {
      els.typing.remove();
      els.typing = null;
    }
  }

  // --- Networking / streaming ---------------------------------------------
  async function onSubmit(ev) {
    ev.preventDefault();
    const value = (els.input.value || "").trim();
    if (!value) return;

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
    if (state.streaming) {
      state.controller?.abort();
    }
    state.streaming = true;
    state.controller = new AbortController();
    setTypingIndicator(true);

    const assistantMsg = addMessage("assistant", "", { streaming: true });
    let fullText = "";

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

      if (!response.ok || !response.body) {
        throw new Error("Unable to reach assistant.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const part of parts) {
          const parsed = parseSSE(part.trim());
          if (!parsed) continue;

          if (parsed.event === "token" && parsed.data?.text) {
            fullText += parsed.data.text;
            assistantMsg.textContent = fullText;
            scrollMessages();
          } else if (parsed.event === "final") {
            if (parsed.data?.message) {
              fullText = parsed.data.message;
              assistantMsg.textContent = fullText;
            }
            assistantMsg.classList.remove("streaming");
            state.streaming = false;
            setTypingIndicator(false);
          }
        }
      }
    } catch (err) {
      assistantMsg.classList.remove("streaming");
      assistantMsg.textContent =
        "I had trouble responding just now. Please try again.";
      console.error("[AIChatWidget]", err);
    } finally {
      state.streaming = false;
      setTypingIndicator(false);
      state.controller = null;
      scrollMessages();
    }
  }

  function joinUrl(base, path) {
    if (!base) return path;
    return base.replace(/\/+$/, "") + path;
  }

  // Expose globally
  window.AIChatWidget = { init, toggle: togglePanel };
})();