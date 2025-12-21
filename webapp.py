from flask import Flask, jsonify, render_template_string, request

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
  <title>Simon Says Serial Console</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 1.5rem; }
    pre { background: #111; color: #0f0; padding: 1rem; max-height: 60vh; overflow: auto; }
    form { margin-top: 1rem; }
    label { display: block; margin-bottom: 0.5rem; }
  </style>
  <script>
    async function refreshMessages() {
      const res = await fetch('/api/messages');
      const data = await res.json();
      const lines = data.messages.map(m => `[${m.src}] ${m.text}`);
      document.getElementById('log').textContent = lines.join('\\n');
    }
    async function sendCommand(ev) {
      ev.preventDefault();
      const cmd = document.getElementById('cmd').value.trim();
      if (!cmd) return;
      await fetch('/api/send', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({cmd})});
      document.getElementById('cmd').value = '';
      refreshMessages();
    }
    setInterval(refreshMessages, 1500);
    window.onload = refreshMessages;
  </script>
</head>
<body>
  <h1>Simon Says Serial Console</h1>
  <pre id="log"></pre>
  <form onsubmit="sendCommand(event)">
    <label>Send command to ESP32:</label>
    <input id="cmd" type="text" autofocus />
    <button type="submit">Send</button>
  </form>
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

