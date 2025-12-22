Setup
=====
- Create venv: `python -m venv .venv`
- Activate (Linux): `source ./.venv/bin/activate`
- Activate (Windows): `.venv\Scripts\activate`
- Install deps: `pip install -r requirements.txt`

Linux audio deps (playsound)
============================
- Install once for GStreamer backend:
  `sudo apt-get install python3-gi gir1.2-gstreamer-1.0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good`

Find Ports (Windows)
====================
- List USB serial ports:
  `py -c "import serial.tools.list_ports as p; print([x.device for x in p.comports()])"`

Run the app
===========
- Windows examples:
  - `python app.py web COM4:serial,dummy1:dummy`
  - `python app.py web "COM4:serial,COM5:EscapeRoom"`
- Raspberry Pi / Linux (override port as needed, custom port via `FLASK_PORT`):
  - `FLASK_PORT=7000 python app.py web "/dev/ttyUSB0:serial"`



Fixing audio files
==================
The files get clipped when playing so we have to add a padding of 0.2 sec at the start:
sox -r 22050 -c 1 -n pad.wav synth 0.2 sine 300 vol 0.01
sox pad.wav filetofix.wav fixed.wav
