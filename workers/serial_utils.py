import glob
import shutil
import subprocess
import sys
import time
from pathlib import Path

import serial
from serial.tools import list_ports

BAUD = 115200


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


def play_sound_file(path: Path):
    """
    Fire-and-forget audio playback.
    On Linux, prefer 'aplay' for fast WAV playback.
    Falls back to playsound if available.
    """
    if not path.exists():
        print(f"(Sound file not found at {path})")
        return

    # Prefer aplay on Linux
    if sys.platform.startswith("linux") and shutil.which("aplay"):
        try:
            subprocess.Popen(["aplay", "-q", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception as e:
            print(f"(aplay failed: {e})")

    try:
        from playsound import playsound  # local import to avoid hard dependency
    except Exception:
        print("(playsound not installed; install playsound or provide aplay on Linux.)")
        return

    try:
        playsound(str(path), block=False)
    except TypeError:
        # some playsound versions ignore block kwarg
        subprocess.Popen([sys.executable, "-c", f"from playsound import playsound; playsound(r'''{str(path)}''')"])
