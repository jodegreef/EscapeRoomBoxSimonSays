import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

import serial

from workers.audio import play_sound_file
from workers.serial_utils import BAUD

READY_TOKEN = "ESCAPE:READY"
ARMED_TOKEN = "ESCAPE:ARMED"
WIN_TOKEN = "ESCAPE:WIN"
FAIL_TOKEN = "ESCAPE:FAIL"
DEFAULT_SOUND_FILE = Path(os.environ.get("ESCAPE_READY_MP3", "letsgo.wav"))
MAX_MESSAGES = 200
FAIL_SOUND_FILE = Path(os.environ.get("ESCAPE_FAIL_MP3", "dontangerit.wav"))


def parse_env_sound_hooks(raw: str) -> Dict[str, Path]:
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
ENV_SOUND_HOOKS: Dict[str, Path] = parse_env_sound_hooks(os.environ.get("ESCAPE_SOUNDS", ""))
SOUND_HOOKS: Dict[str, Path] = {**DEFAULT_SOUND_HOOKS, **ENV_SOUND_HOOKS}


class EscapeRoomWorker:
    default_id = "EscapeRoom"

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
                print(f"\nESCAPE ESP32: {line}\n> ", end="", flush=True)
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
        threading.Thread(target=play_sound_file, args=(path,), daemon=True).start()

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
