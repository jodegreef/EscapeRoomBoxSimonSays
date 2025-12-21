import sys
import time
import threading
import serial
from serial.tools import list_ports
from pathlib import Path
import glob
import os

try:
    from playsound import playsound
except ImportError:
    playsound = None

BAUD = 115200
READY_TOKEN = "SIMON:READY"
SOUND_FILE = Path(os.environ.get("SIMON_READY_MP3", "overhere.wav"))

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
            if line == READY_TOKEN:
                trigger_ready_sound()

def send_line(ser: serial.Serial, line: str):
    ser.write((line.strip() + "\n").encode("utf-8"))

def trigger_ready_sound():
    # Play the MP3 in a background thread so serial reading is not blocked
    if not SOUND_FILE.exists():
        print(f"(MP3 not found at {SOUND_FILE}. Set SIMON_READY_MP3 to override.)")
        return
    if playsound is None:
        print("(playsound not installed; add it to requirements and pip install to enable audio.)")
        return
    threading.Thread(target=playsound, args=(str(SOUND_FILE),), daemon=True).start()

def main():
    port = sys.argv[1] if len(sys.argv) > 1 else find_default_port()
    print(f"Using port: {port}")

    ser = open_serial(port)

    t = threading.Thread(target=reader_loop, args=(ser,), daemon=True)
    t.start()

    print("Type commands to send. Ctrl+C to quit.")
    while True:
        try:
            cmd = input("> ").strip()
            if not cmd:
                continue
            send_line(ser, cmd)
        except KeyboardInterrupt:
            break

    ser.close()

if __name__ == "__main__":
    main()
