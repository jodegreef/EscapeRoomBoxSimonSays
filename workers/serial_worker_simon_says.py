import glob
import os
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

import serial
from serial.tools import list_ports

try:
    from playsound import playsound
except ImportError:
    playsound = None

BAUD = 115200
READY_TOKEN = "SIMON:READY"
ARMED_TOKEN = "SIMON:ARMED"
WIN_TOKEN = "SIMON:WIN"
FAIL_TOKEN = "SIMON:FAIL"
DEFAULT_SOUND_FILE = Path(os.environ.get("SIMON_READY_MP3", "letsgo.wav"))
MAX_MESSAGES = 200
FAIL_SOUND_FILE = Path(os.environ.get("SIMON_FAIL_MP3", "dontangerit.wav"))


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


DEFAULT_SOUND_HOOKS: Dict[str, Path] = {
    READY_TOKEN: DEFAULT_SOUND_FILE,
    FAIL_TOKEN: FAIL_SOUND_FILE,
}
ENV_SOUND_HOOKS: Dict[str, Path] = parse_env_sound_hooks(os.environ.get("SIMON_SOUNDS", ""))
SOUND_HOOKS: Dict[str, Path] = {**DEFAULT_SOUND_HOOKS, **ENV_SOUND_HOOKS}


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
        if "usb" in s:
            pref += 10
        if "cp210" in s or "silicon labs" in s:
            pref += 5
        if "ch340" in s or "wch" in s:
            pref += 5
        if "ftdi" in s:
            pref += 5
        if "acm" in (p.device or "").lower():
            pref += 2
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


class SimonSaysWorker:
    default_id = "SimonSays"

    def __init__(
        self,
        ser: serial.Serial,
        sound_hooks: Optional[Dict[str, Path]] = None,
        echo_to_console: bool = True,
    ):
        self.ser = ser
        self.sound_hooks = sound_hooks or SOUND_HOOKS
        self.echo_to_console = echo_to_console
        self.messages: List[Dict[str, str]] = []
        self.messages_lock = threading.Lock()
        self.status_lock = threading.Lock()
        self.status = {"ready": False, "armed": False, "win": False, "fail": False}
        self.msg_counter = 0
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.thread.start()

    def _reader_loop(self):
        while self.running:
            raw = self.ser.readline()  # blocks until '\n'
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            if self.echo_to_console:
                print(f"\nESP32: {line}\n> ", end="", flush=True)
            self._trigger_sound_for_token(line)
            self._append_message("ESP32", line)

    def send_line(self, line: str):
        self.ser.write((line.strip() + "\n").encode("utf-8"))
        self._append_message("HOST", line.strip())

    def _trigger_sound_for_token(self, token: str):
        path = self.sound_hooks.get(token)
        if not path:
            return
        self._play_sound_file(path)

    def _play_sound_file(self, path: Path):
        # Play the MP3/WAV in a background thread so serial reading is not blocked
        if not path.exists():
            print(f"(Sound file not found at {path}. Check SIMON_SOUNDS or SIMON_READY_MP3.)")
            return
        if playsound is None:
            print("(playsound not installed; add it to requirements and pip install to enable audio.)")
            return
        threading.Thread(target=playsound, args=(str(path),), daemon=True).start()

    def _append_message(self, src: str, text: str):
        with self.messages_lock:
            self.msg_counter += 1
            self.messages.append({"id": self.msg_counter, "src": src, "text": text, "ts": time.time()})
            if len(self.messages) > MAX_MESSAGES:
                del self.messages[:-MAX_MESSAGES]
        self._update_status(text)

    def _update_status(self, token: str):
        with self.status_lock:
            if token == READY_TOKEN:
                self.status["ready"] = True
                self.status["armed"] = False
            elif token == ARMED_TOKEN:
                self.status["armed"] = True
                self.status["ready"] = False
            elif token == WIN_TOKEN:
                self.status["win"] = True
            elif token == FAIL_TOKEN:
                self.status["fail"] = True

    def get_status(self) -> Dict[str, bool]:
        with self.status_lock:
            return dict(self.status)

    def get_messages(self) -> List[Dict[str, str]]:
        with self.messages_lock:
            return list(self.messages)

    def get_messages_since(self, last_id: int) -> List[Dict[str, str]]:
        with self.messages_lock:
            if last_id <= 0:
                return list(self.messages)
            return [m for m in self.messages if m.get("id", 0) > last_id]

    def close(self):
        self.running = False
        try:
            self.ser.close()
        except Exception:
            pass
