Setup
=====
- Create venv: `python -m venv .venv`
- Activate (Linux): `source ./.venv/bin/activate`
- Activate (Windows): `.venv\Scripts\activate`
- Install deps: `pip install -r requirements.txt`

Find Ports (Windows)
====================
- List USB serial ports:
  `py -c "import serial.tools.list_ports as p; print([x.device for x in p.comports()])"`

Run the app
===========
- Windows examples:
  - `python app.py web COM4:serial,dummy1:dummy`
  - `python app.py web "COM4:serial,COM5:EscapeRoom"`
- Raspberry Pi (override port if needed):
  - `FLASK_PORT=7000 python app.py web "/dev/ttyUSB0:serial"`
