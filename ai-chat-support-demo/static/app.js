const messagesEl = document.querySelector("#messages");
const formEl = document.querySelector("#chat-form");
const inputEl = document.querySelector("#chat-input");
const modelPill = document.querySelector("#model-pill");
const riskPill = document.querySelector("#risk-pill");
const clusterEl = document.querySelector("#cluster");
const riskScoreEl = document.querySelector("#risk-score");
const confidenceEl = document.querySelector("#confidence");
const signalsEl = document.querySelector("#signals");
const actionsEl = document.querySelector("#actions");
const rawJsonEl = document.querySelector("#raw-json");

const userId = getOrCreate("context-demo-user", () => `demo-user-${crypto.randomUUID()}`);
const conversationId = getOrCreate("context-demo-conversation", () => `thread-${crypto.randomUUID()}`);
const messages = [
  {
    role: "assistant",
    content: "你好，我是一个普通 AI 助手。你可以像平时聊天一样说，我会尽量理解你的处境。",
  },
];

renderMessages();

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.value = "";
  messages.push({ role: "user", content: text });
  renderMessages();

  try {
    const chatResponse = await fetch("/demo/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    });
    if (!chatResponse.ok) throw new Error(await chatResponse.text());
    const chatPayload = await chatResponse.json();
    modelPill.textContent = chatPayload.model || "assistant";
    messages.push(chatPayload.message);
    renderMessages();
  } catch (error) {
    messages.push({
      role: "assistant",
      content: `聊天模型暂时不可用：${error instanceof Error ? error.message : String(error)}`,
    });
    renderMessages();
  }

  void analyzeInBackground();
});

async function analyzeInBackground() {
  try {
    const response = await fetch("/demo/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        external_user_id: userId,
        conversation_id: conversationId,
        messages,
        metadata: {
          demo: true,
          user_agent: navigator.userAgent,
        },
      }),
    });
    if (!response.ok) throw new Error(await response.text());
    renderAnalysis(await response.json());
  } catch (error) {
    rawJsonEl.textContent = JSON.stringify({ error: error instanceof Error ? error.message : String(error) }, null, 2);
  }
}

function renderMessages() {
  messagesEl.innerHTML = "";
  for (const message of messages) {
    const item = document.createElement("article");
    item.className = `message ${message.role}`;
    const role = document.createElement("small");
    role.textContent = message.role;
    const content = document.createElement("div");
    content.textContent = message.content;
    item.append(role, content);
    messagesEl.append(item);
  }
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderAnalysis(payload) {
  riskPill.textContent = payload.risk_level;
  riskPill.className = `pill ${payload.risk_level}`;
  clusterEl.textContent = payload.cluster || "-";
  riskScoreEl.textContent = Number(payload.risk_score || 0).toFixed(3);
  confidenceEl.textContent = Number(payload.confidence || 0).toFixed(3);
  rawJsonEl.textContent = JSON.stringify(payload, null, 2);

  signalsEl.innerHTML = "";
  const signals = payload.signals || [];
  signalsEl.className = signals.length ? "signals" : "signals empty";
  if (!signals.length) {
    signalsEl.textContent = "暂无支持/风险信号。";
  } else {
    for (const signal of signals) {
      const item = document.createElement("article");
      item.className = "signal";
      item.innerHTML = `
        <strong>${escapeHtml(signal.label)} · ${escapeHtml(signal.severity)} · ${Number(signal.confidence || 0).toFixed(2)}</strong>
        <p>${escapeHtml(signal.suggested_action || "")}</p>
        <p>${escapeHtml((signal.evidence || []).join(" / "))}</p>
      `;
      signalsEl.append(item);
    }
  }

  actionsEl.innerHTML = "";
  for (const action of payload.immediate_actions || []) {
    const item = document.createElement("li");
    item.textContent = action;
    actionsEl.append(item);
  }
}

function getOrCreate(key, factory) {
  const existing = localStorage.getItem(key);
  if (existing) return existing;
  const created = factory();
  localStorage.setItem(key, created);
  return created;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
