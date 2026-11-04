import serial
import time

try:
    ser = serial.Serial('COM11', 115200, timeout=1)
    ser.dtr = True
    ser.rts = True
    time.sleep(0.5)
    ser.write(b"AT\r\n")
    time.sleep(0.5)
    res = ser.read_all()
    print(f"AT result with DTR: {res}")
    ser.close()
except Exception as e:
    print(f"Error: {e}")
