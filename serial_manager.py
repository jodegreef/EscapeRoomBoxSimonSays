from typing import Dict, List, Optional, Tuple

from workers.dummy_worker import DummyWorker
from workers.serial_worker_escape_room import EscapeRoomWorker
from workers.serial_worker_simon_says import SimonSaysWorker
from workers.serial_utils import open_serial


class SerialManager:
    def __init__(self, device_specs: List[Tuple[str, str, Optional[str]]], sound_hooks=None, echo_to_console=False):
        """
        device_specs: list of (device_id, worker_type, port)
        worker_type: "serial" or "dummy"
        port: required for serial, ignored for dummy
        """
        self.workers: Dict[str, object] = {}
        for dev_id, worker_type, port in device_specs:
            wt = worker_type.lower()
            if wt in ("serial", "simon", "simonsays"):
                if not port:
                    raise ValueError(f"Missing port for device {dev_id or 'serial worker'}")
                ser = open_serial(port)
                worker = SimonSaysWorker(ser, sound_hooks=sound_hooks, echo_to_console=echo_to_console)
                name = dev_id or worker.default_id
                if name and (name.upper().startswith("COM") or name.startswith("/dev/")):
                    name = worker.default_id
            elif wt in ("escape", "escaperoom"):
                if not port:
                    raise ValueError(f"Missing port for device {dev_id or 'escape worker'}")
                ser = open_serial(port)
                worker = EscapeRoomWorker(ser, sound_hooks=sound_hooks, echo_to_console=echo_to_console)
                name = dev_id or worker.default_id
                if name and (name.upper().startswith("COM") or name.startswith("/dev/")):
                    name = worker.default_id
            elif wt == "dummy":
                worker = DummyWorker(name=dev_id or "dummy")
                name = dev_id or worker.name
            else:
                raise ValueError(f"Unknown worker type: {worker_type}")

            unique_name = self._make_unique_name(name)
            self.workers[unique_name] = worker

    def _make_unique_name(self, base: str) -> str:
        if base not in self.workers:
            return base
        idx = 2
        while f"{base}_{idx}" in self.workers:
            idx += 1
        return f"{base}_{idx}"

    def start_all(self):
        for w in self.workers.values():
            if hasattr(w, "start"):
                w.start()

    def get_worker(self, device: Optional[str]):
        if device and device in self.workers:
            return self.workers[device]
        return self.get_default_worker()

    def get_default_worker(self):
        return next(iter(self.workers.values())) if self.workers else None

    def list_devices(self) -> List[str]:
        return list(self.workers.keys())

    def get_statuses(self) -> Dict[str, Dict[str, bool]]:
        return {dev: worker.get_status() for dev, worker in self.workers.items()}

    def get_messages_since(self, last_ids: Dict[str, int]) -> Tuple[List[Dict,], Dict[str, int]]:
        combined: List[Dict] = []
        new_last: Dict[str, int] = dict(last_ids)
        for dev, worker in self.workers.items():
            lid = last_ids.get(dev, 0)
            msgs = worker.get_messages_since(lid)
            if msgs:
                new_last[dev] = msgs[-1].get("id", lid)
                for m in msgs:
                    nm = dict(m)
                    nm["device"] = dev
                    combined.append(nm)
        combined.sort(key=lambda m: m.get("ts", 0))
        return combined, new_last

    def close_all(self):
        for w in self.workers.values():
            if hasattr(w, "close"):
                w.close()
