from flask import Flask, jsonify, render_template_string, request, url_for

from serial_worker import SerialWorker


def create_app(worker: SerialWorker) -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index():
        return render_template_string(
            """
<!doctype html>
<html>
<head>
  <title>Simon Says Dashboard</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
  <script>
    const statusTokens = {
      ready: "SIMON:READY",
      armed: "SIMON:ARMED",
      win: "SIMON:WIN",
      fail: "SIMON:FAIL",
    };

    function computeStatus(messages) {
      const last = {};
      messages.forEach(m => { last[m.text] = m.ts; });
      return {
        // Armed overrides ready indicator
        ready: !!last[statusTokens.ready] && !last[statusTokens.armed],
        armed: !!last[statusTokens.armed],
        win: !!last[statusTokens.win],
        fail: !!last[statusTokens.fail],
      };
    }

    async function refresh() {
      const res = await fetch('/api/messages');
      const data = await res.json();
      const lines = data.messages.map(m => `[${m.src}] ${m.text}`);
      document.getElementById('log').textContent = lines.join('\\n');

      const stat = computeStatus(data.messages);
      setDot('dot-ready', stat.ready ? 'ok' : '');
      setDot('dot-armed', stat.armed ? 'warn' : '');
      setDot('dot-win', stat.win ? 'ok' : '');
      setDot('dot-fail', stat.fail ? 'bad' : '');
    }

    function setDot(id, cls) {
      const el = document.getElementById(id);
      el.className = 'dot ' + cls;
    }

    async function sendCommand(cmd) {
      if (!cmd) return;
      await fetch('/api/send', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({cmd})});
      refresh();
    }

    async function sendForm(ev) {
      ev.preventDefault();
      const text = document.getElementById('param-text').value.trim();
      const mode = document.getElementById('param-mode').value;
      const flag = document.getElementById('param-flag').checked ? "ON" : "OFF";
      const cmd = `SET ${mode} ${flag} ${text || "NO_TEXT"}`;
      await sendCommand(cmd);
      ev.target.reset();
    }

    window.onload = () => {
      refresh();
      setInterval(refresh, 1500);
    };
  </script>
</head>
<body>
  <h1>Simon Says Dashboard</h1>
  <div class="grid">
    <div class="panel">
      <div class="flex-between">
        <h3>Status</h3>
        <small>Based on recent messages</small>
      </div>
      <div class="status-list">
        <div class="status"><span id="dot-ready" class="dot"></span> Ready</div>
        <div class="status"><span id="dot-armed" class="dot"></span> Simon: Armed</div>
        <div class="status"><span id="dot-win" class="dot"></span> Win</div>
        <div class="status"><span id="dot-fail" class="dot"></span> Fail</div>
      </div>
    </div>

    <div class="panel">
      <h3>Quick Commands</h3>
      <div class="btn-row">
        <button onclick="sendCommand('SIMON:ARM')" class="secondary">Arm SimonSays</button>
        <button onclick="sendCommand('SIMON:DEBUG')">SIMON:DEBUG</button>
        <button onclick="sendCommand('PLAY_SOUND')" class="secondary">Play Sound</button>
        <button onclick="sendCommand('LIGHTS ON')">Lights On</button>
        <button onclick="sendCommand('LIGHTS OFF')">Lights Off</button>
      </div>
    </div>

    <div class="panel">
      <h3>Command with Parameters</h3>
      <form onsubmit="sendForm(event)">
        <label for="param-text">Text</label>
        <input id="param-text" type="text" placeholder="Enter text payload" />

        <label for="param-mode">Mode</label>
        <select id="param-mode">
          <option value="MODE1">MODE1</option>
          <option value="MODE2">MODE2</option>
          <option value="MODE3">MODE3</option>
        </select>

        <label><input id="param-flag" type="checkbox" /> Enable flag</label>

        <div style="margin-top:0.8rem">
          <button type="submit">Send Command</button>
        </div>
      </form>
    </div>

    <div class="panel" style="grid-column: 1 / -1;">
      <div class="flex-between">
        <h3>Serial Log</h3>
        <small>Live tail</small>
      </div>
      <pre id="log"></pre>
    </div>
  </div>
</body>
</html>
"""
        )

    @app.route("/api/messages")
    def api_messages():
        return jsonify({"messages": worker.get_messages()})

    @app.route("/api/send", methods=["POST"])
    def api_send():
        data = request.get_json(silent=True) or {}
        cmd = (data.get("cmd") or data.get("command") or "").strip()
        if not cmd:
            return jsonify({"error": "Missing 'cmd'"}), 400
        worker.send_line(cmd)
        return jsonify({"ok": True})

    return app
