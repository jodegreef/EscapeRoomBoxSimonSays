let lastId = 0;

function connectStream() {
  const es = new EventSource("/api/stream");
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
    updateStatus(payload.status);
  } else if (payload.type === "status" && payload.status) {
    updateStatus(payload.status);
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
    lines.push(`[${m.src}] ${m.text}`);
  });
  const maxLines = 400;
  const trimmed = lines.slice(-maxLines);
  log.textContent = trimmed.join("\n");
}

function updateStatus(status) {
  if (!status) return;
  setDot("dot-ready", status.ready ? "ok" : "");
  setDot("dot-armed", status.armed ? "warn" : "");
  setDot("dot-win", status.win ? "ok" : "");
  setDot("dot-fail", status.fail ? "bad" : "");
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
