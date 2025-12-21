import os
import sys

from cli import run_cli
from serial_worker import SOUND_HOOKS, SerialWorker, find_default_port, open_serial
from webapp import create_app

FLASK_DEFAULT_PORT = int(os.environ.get("FLASK_PORT", "5000"))


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
    worker = SerialWorker(serial_conn, sound_hooks=SOUND_HOOKS, echo_to_console=(mode == "cli"))

    try:
        if mode == "web":
            worker.start()
            app = create_app(worker)
            app.run(host="0.0.0.0", port=FLASK_DEFAULT_PORT, debug=False)
        else:
            run_cli(worker)
    finally:
        worker.close()


if __name__ == "__main__":
    main()
