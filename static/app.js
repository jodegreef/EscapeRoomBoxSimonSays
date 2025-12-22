let lastId = 0;
let es;

function connectStream() {
  es = new EventSource("/api/stream");
  es.onmessage = (evt) => {
    if (!evt.data) return;
    try {
      const payload = JSON.parse(evt.data);
      handlePayload(payload);
    } catch (e) {
      console.error("Bad SSE payload", e);
    }
  };
  es.onerror = () => {
    es.close();
    // simple retry after delay
    setTimeout(connectStream, 2000);
  };
}

function handlePayload(payload) {
  if (payload.type === "messages" && payload.messages) {
    updateMessages(payload.messages);
    updateStatuses(payload.status);
  } else if (payload.type === "status" && payload.status) {
    updateStatuses(payload.status);
  }
}

function updateMessages(msgs) {
  if (!Array.isArray(msgs)) return;
  const log = document.getElementById("log");
  const lines = log.textContent ? log.textContent.split("\n") : [];
  msgs.forEach((m) => {
    if (typeof m.id === "number") {
      lastId = Math.max(lastId, m.id);
    }
    const deviceTag = m.device ? `[${m.device}] ` : "";
    lines.push(`${deviceTag}[${m.src}] ${m.text}`);
  });
  const maxLines = 400;
  const trimmed = lines.slice(-maxLines);
  log.textContent = trimmed.join("\n");
}

function updateStatuses(statuses) {
  debugger
  // aggregate: if any device has a flag, show it
  if (!statuses) return;
  let agg = { ready: false, armed: false, win: false, fail: false };
  Object.values(statuses).forEach((s) => {
    agg.ready = agg.ready || s.ready;
    agg.armed = agg.armed || s.armed;
    agg.win = agg.win || s.win;
    agg.fail = agg.fail || s.fail;
  });
  setDot("dot-ready", agg.ready ? "ok" : "");
  setDot("dot-armed", agg.armed ? "warn" : "");
  setDot("dot-win", agg.win ? "ok" : "");
  setDot("dot-fail", agg.fail ? "bad" : "");
}

function setDot(id, cls) {
  const el = document.getElementById(id);
  if (el) el.className = "dot " + cls;
}

async function sendCommand(cmd) {
  if (!cmd) return;
  await fetch("/api/send", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cmd }),
  });
}

async function sendForm(ev) {
  ev.preventDefault();
  const text = document.getElementById("param-text").value.trim();
  const mode = document.getElementById("param-mode").value;
  const flag = document.getElementById("param-flag").checked ? "ON" : "OFF";
  const cmd = `SET ${mode} ${flag} ${text || "NO_TEXT"}`;
  await sendCommand(cmd);
  ev.target.reset();
}

window.onload = () => {
  connectStream();
};
