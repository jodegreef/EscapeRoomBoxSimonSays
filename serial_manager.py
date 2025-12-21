from typing import Dict, List, Optional, Tuple

from dummy_worker import DummyWorker
from serial_worker import SerialWorker, open_serial


class SerialManager:
    def __init__(self, device_specs: List[Tuple[str, str, Optional[str]]], sound_hooks=None, echo_to_console=False):
        """
        device_specs: list of (device_id, worker_type, port)
        worker_type: "serial" or "dummy"
        port: required for serial, ignored for dummy
        """
        self.workers: Dict[str, object] = {}
        for dev_id, worker_type, port in device_specs:
            if worker_type == "serial":
                if not port:
                    raise ValueError(f"Missing port for device {dev_id}")
                ser = open_serial(port)
                worker = SerialWorker(ser, sound_hooks=sound_hooks, echo_to_console=echo_to_console)
            elif worker_type == "dummy":
                worker = DummyWorker(name=dev_id)
            else:
                raise ValueError(f"Unknown worker type: {worker_type}")
            self.workers[dev_id] = worker

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
