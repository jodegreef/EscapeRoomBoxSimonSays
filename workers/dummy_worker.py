import threading
import time
from typing import Dict, List, Optional


class DummyWorker:
    """
    Simple in-memory worker used as a placeholder device.
    Generates periodic status messages and echoes commands.
    """

    def __init__(self, name: str = "dummy"):
        self.name = name
        self.messages: List[Dict] = []
        self.messages_lock = threading.Lock()
        self.status = {"ready": False, "armed": False, "win": False, "fail": False}
        self.status_lock = threading.Lock()
        self.msg_counter = 0
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        sequence = ["DUMMY:READY", "DUMMY:ARMED", "DUMMY:FAIL", "DUMMY:READY", "DUMMY:WIN"]
        idx = 0
        while self.running:
            token = sequence[idx % len(sequence)]
            self._append_message("ESP32", token)
            time.sleep(2)
            idx += 1

    def send_line(self, line: str):
        self._append_message("HOST", line)

    def _append_message(self, src: str, text: str):
        with self.messages_lock:
            self.msg_counter += 1
            self.messages.append({"id": self.msg_counter, "src": src, "text": text, "ts": time.time()})
            if len(self.messages) > 200:
                del self.messages[:-200]
        with self.status_lock:
            if text == "DUMMY:READY":
                self.status["ready"] = True
                self.status["armed"] = False
            elif text == "DUMMY:ARMED":
                self.status["armed"] = True
                self.status["ready"] = False
            elif text == "DUMMY:WIN":
                self.status["win"] = True
            elif text == "DUMMY:FAIL":
                self.status["fail"] = True

    def get_messages(self):
        with self.messages_lock:
            return list(self.messages)

    def get_messages_since(self, last_id: int):
        with self.messages_lock:
            if last_id <= 0:
                return list(self.messages)
            return [m for m in self.messages if m.get("id", 0) > last_id]

    def get_status(self):
        with self.status_lock:
            return dict(self.status)

    def close(self):
        self.running = False
