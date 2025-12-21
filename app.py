import sys
import time
import threading
import serial
from serial.tools import list_ports
from pathlib import Path
import glob
import os
from typing import Dict, List

try:
    from flask import Flask, jsonify, render_template_string, request
except ImportError:
    Flask = None  # type: ignore
    jsonify = None  # type: ignore
    render_template_string = None  # type: ignore
    request = None  # type: ignore

try:
    from playsound import playsound
except ImportError:
    playsound = None

BAUD = 115200
READY_TOKEN = "SIMON:READY"
DEFAULT_SOUND_FILE = Path(os.environ.get("SIMON_READY_MP3", "overhere.wav"))
MAX_MESSAGES = 200
FLASK_DEFAULT_PORT = int(os.environ.get("FLASK_PORT", "5000"))
DEFAULT_SOUND_HOOKS: Dict[str, Path] = {READY_TOKEN: DEFAULT_SOUND_FILE}
ENV_SOUND_HOOKS: Dict[str, Path] = {}
SOUND_HOOKS: Dict[str, Path] = {}
MAX_MESSAGES = 200
FLASK_DEFAULT_PORT = int(os.environ.get("FLASK_PORT", "5000"))

messages: List[Dict[str, str]] = []
messages_lock = threading.Lock()
ser = None  # Active serial connection when running Flask/CLI

if Flask is not None:
    app = Flask(__name__)
else:
    app = None  # type: ignore

def parse_env_sound_hooks(raw: str) -> Dict[str, Path]:
    """
    Parse SIMON_SOUNDS env var of the form:
    TOKEN1=path/to/file.mp3;TOKEN2=another.wav
    """
    hooks: Dict[str, Path] = {}
    for pair in raw.split(";"):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        token, file_path = pair.split("=", 1)
        token = token.strip()
        file_path = file_path.strip()
        if token and file_path:
            hooks[token] = Path(file_path)
    return hooks

# Build sound hooks with env overrides (SIMON_SOUNDS) on top of the default READY sound
ENV_SOUND_HOOKS = parse_env_sound_hooks(os.environ.get("SIMON_SOUNDS", ""))
SOUND_HOOKS = {**DEFAULT_SOUND_HOOKS, **ENV_SOUND_HOOKS}

def find_default_port() -> str:
    # Linux: prefer stable by-id symlink if available
    if sys.platform.startswith("linux"):
        by_id = glob.glob("/dev/serial/by-id/*")
        if by_id:
            return by_id[0]
        # fallback
        for cand in ("/dev/ttyACM0", "/dev/ttyUSB0"):
            if Path(cand).exists():
                return cand

    # Windows/macOS/other: pick the first USB-ish serial port
    ports = list(list_ports.comports())
    if not ports:
        raise RuntimeError("No serial ports found. Plug in the ESP32 and try again.")

    # Heuristic: prefer ports that look like USB serial adapters
    def score(p):
        s = (p.description or "").lower() + " " + (p.hwid or "").lower()
        pref = 0
        if "usb" in s: pref += 10
        if "cp210" in s or "silicon labs" in s: pref += 5
        if "ch340" in s or "wch" in s: pref += 5
        if "ftdi" in s: pref += 5
        if "acm" in (p.device or "").lower(): pref += 2
        return pref

    ports.sort(key=score, reverse=True)
    return ports[0].device

def open_serial(port: str, baud: int = BAUD) -> serial.Serial:
    ser = serial.Serial(port, baudrate=baud, timeout=None)

    # Some boards reset when opening the port (DTR/RTS). These are safe on all OSes.
    try:
        ser.dtr = False
        ser.rts = False
    except Exception:
        pass

    # Give the ESP a moment to boot after opening/reset
    time.sleep(1.5)
    return ser

def reader_loop(ser: serial.Serial):
    while True:
        raw = ser.readline()  # blocks until '\n'
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace").strip()
        if line:
            print(f"\nESP32: {line}\n> ", end="", flush=True)
            trigger_sound_for_token(line)
            append_message("ESP32", line)

def send_line(ser: serial.Serial, line: str):
    ser.write((line.strip() + "\n").encode("utf-8"))
    append_message("HOST", line.strip())

def trigger_ready_sound():
    trigger_sound_for_token(READY_TOKEN)

def trigger_sound_for_token(token: str):
    path = SOUND_HOOKS.get(token)
    if not path:
        return
    play_sound_file(path)

def play_sound_file(path: Path):
    # Play the MP3/WAV in a background thread so serial reading is not blocked
    if not path.exists():
        print(f"(Sound file not found at {path}. Check SIMON_SOUNDS or SIMON_READY_MP3.)")
        return
    if playsound is None:
        print("(playsound not installed; add it to requirements and pip install to enable audio.)")
        return
    threading.Thread(target=playsound, args=(str(path),), daemon=True).start()

def append_message(src: str, text: str):
    with messages_lock:
        messages.append({"src": src, "text": text, "ts": time.time()})
        if len(messages) > MAX_MESSAGES:
            del messages[:-MAX_MESSAGES]

def start_reader_thread(serial_conn: serial.Serial):
    t = threading.Thread(target=reader_loop, args=(serial_conn,), daemon=True)
    t.start()
    return t

def run_cli(serial_conn: serial.Serial):
    start_reader_thread(serial_conn)
    print("Type commands to send. Ctrl+C to quit.")
    while True:
        try:
            cmd = input("> ").strip()
            if not cmd:
                continue
            send_line(serial_conn, cmd)
        except KeyboardInterrupt:
            break

def run_flask(serial_conn: serial.Serial, host: str = "0.0.0.0", port: int = FLASK_DEFAULT_PORT):
    if app is None:
        raise RuntimeError("Flask is not installed. Install it or run in CLI mode.")

    # Make the serial connection available to request handlers
    global ser
    ser = serial_conn
    start_reader_thread(serial_conn)

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
        with messages_lock:
            return jsonify({"messages": messages})

    @app.route("/api/send", methods=["POST"])
    def api_send():
        if ser is None:
            return jsonify({"error": "Serial connection not available"}), 503
        data = request.get_json(silent=True) or {}
        cmd = (data.get("cmd") or data.get("command") or "").strip()
        if not cmd:
            return jsonify({"error": "Missing 'cmd'"}), 400
        send_line(ser, cmd)
        return jsonify({"ok": True})

    app.run(host=host, port=port, debug=False)

def parse_args():
    # CLI: python app.py [serial_port]
    # Web: python app.py web [serial_port]
    args = sys.argv[1:]
    mode = "cli"
    serial_port_arg = None
    if args and args[0].lower() == "web":
        mode = "web"
        args = args[1:]
    if args:
        serial_port_arg = args[0]
    return mode, serial_port_arg

def main():
    mode, serial_port_arg = parse_args()
    port = serial_port_arg if serial_port_arg else find_default_port()
    print(f"Using port: {port}")

    serial_conn = open_serial(port)

    try:
        if mode == "web":
            run_flask(serial_conn)
        else:
            run_cli(serial_conn)
    finally:
        serial_conn.close()

if __name__ == "__main__":
    main()
