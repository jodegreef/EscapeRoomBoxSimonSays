import serial
import time
from glob import glob

ports = glob("/dev/serial/by-id/*")
port = ports[0] if ports else "/dev/ttyACM0"

ser = serial.Serial(port, 115200, timeout=1)
time.sleep(2)  # give ESP32 time after reset

def send(cmd: str):
    ser.write((cmd + "\n").encode("utf-8"))
    return ser.readline().decode("utf-8", errors="replace").strip()

print("ESP says:", ser.readline().decode().strip())
print(send("PING"))
print(send("LED ON"))
time.sleep(1)
print(send("LED OFF"))
