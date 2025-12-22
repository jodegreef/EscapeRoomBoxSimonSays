import os
import sys
from typing import List, Tuple

from cli import run_cli
from serial_manager import SerialManager
from workers.serial_worker_simon_says import SOUND_HOOKS, SimonSaysWorker, find_default_port, open_serial
from webapp import create_app

FLASK_DEFAULT_PORT = int(os.environ.get("FLASK_PORT", "5000"))


def parse_device_specs(arg: str | None) -> List[Tuple[str, str, str | None]]:
    """
    Parse device specs of the form:
      - "COM3" -> device id COM3 using serial worker on port COM3
      - "game:serial:COM4" -> device id "game", serial worker on COM4
      - "dummy1:dummy" -> device id "dummy1" using dummy worker
    Multiple specs separated by commas.
    """
    specs: List[Tuple[str, str, str | None]] = []
    if not arg:
        port = find_default_port()
        specs.append((port, "serial", port))
        return specs

    for token in arg.split(","):
        token = token.strip()
        if not token:
            continue
        parts = token.split(":")
        if len(parts) == 1:
            # port only, use default id later
            port = parts[0]
            specs.append((None, "serial", port))
        elif len(parts) == 2:
            dev_id, worker_type = parts
            worker_type = worker_type.lower()
            if worker_type == "dummy":
                specs.append((dev_id, worker_type, None))
            else:
                specs.append((dev_id, worker_type, dev_id))
        else:
            dev_id, worker_type, port = parts[0], parts[1].lower(), parts[2]
            specs.append((dev_id, worker_type, port))
    if not specs:
        port = find_default_port()
        specs.append((port, "serial", port))
    return specs


def parse_args():
    # CLI: python app.py [device_specs]
    # Web: python app.py web [device_specs]
    args = sys.argv[1:]
    mode = "cli"
    device_arg: str | None = None
    if args and args[0].lower() == "web":
        mode = "web"
        args = args[1:]
    if args:
        device_arg = args[0]
    return mode, device_arg


def main():
    mode, device_arg = parse_args()
    specs = parse_device_specs(device_arg)
    print("Device spec format: <id>:<worker>[:port], worker in {serial,dummy}; comma-separated for multiples.")
    print("Devices:")
    for dev_id, worker_type, port in specs:
        port_info = port or "n/a"
        print(f"  {dev_id}: {worker_type} (port {port_info})")

    if mode == "web":
        manager = SerialManager(specs, sound_hooks=SOUND_HOOKS, echo_to_console=False)
        manager.start_all()
        app = create_app(manager)
        try:
            app.run(host="0.0.0.0", port=FLASK_DEFAULT_PORT, debug=False)
        finally:
            manager.close_all()
    else:
        # CLI mode uses first device only
        first = specs[0]
        dev_id, worker_type, port = first
        if worker_type != "serial":
            raise RuntimeError("CLI mode supports serial devices only. Use web mode for dummy workers.")
        serial_conn = open_serial(port or find_default_port())
        worker = SimonSaysWorker(serial_conn, sound_hooks=SOUND_HOOKS, echo_to_console=True)

        try:
            run_cli(worker)
        finally:
            worker.close()


if __name__ == "__main__":
    main()
