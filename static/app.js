const statusTokens = {
  ready: "SIMON:READY",
  armed: "SIMON:ARMED",
  win: "SIMON:WIN",
  fail: "SIMON:FAIL",
};

async function refresh() {
  await Promise.all([refreshStatus(), refreshMessages()]);
}

async function refreshStatus() {
  const res = await fetch("/api/status");
  const data = await res.json();
  setDot("dot-ready", data.ready ? "ok" : "");
  setDot("dot-armed", data.armed ? "warn" : "");
  setDot("dot-win", data.win ? "ok" : "");
  setDot("dot-fail", data.fail ? "bad" : "");
}

async function refreshMessages() {
  const res = await fetch("/api/messages");
  const data = await res.json();
  const lines = data.messages.map((m) => `[${m.src}] ${m.text}`);
  document.getElementById("log").textContent = lines.join("\n");
}

function setDot(id, cls) {
  const el = document.getElementById(id);
  el.className = "dot " + cls;
}

async function sendCommand(cmd) {
  if (!cmd) return;
  await fetch("/api/send", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cmd }),
  });
  refresh();
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
  refresh();
  setInterval(refresh, 1500);
};
