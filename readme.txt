create new venv:
python -m venv .venv

activate it (linux):
source ./.venv/bin/activate

activate it (windows):
.venv\Scripts\activate  


pip install -r requirements.txt



Windows: 

listusb ports:
py -c "import serial.tools.list_ports as p; print([x.device for x in p.comports()])"
