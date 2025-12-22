from workers.serial_worker_simon_says import SimonSaysWorker as SerialWorker


def run_cli(worker: SerialWorker):
    worker.start()
    print("Type commands to send. Ctrl+C to quit.")
    while True:
        try:
            cmd = input("> ").strip()
            if not cmd:
                continue
            worker.send_line(cmd)
        except KeyboardInterrupt:
            break
