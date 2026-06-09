import sys
import time
import serial

port = sys.argv[1] if len(sys.argv) > 1 else "COM5"
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 12.0

s = serial.Serial(port, 115200, timeout=0.1)
# Trigger a reset so we capture a fresh boot + any panic.
try:
    s.dtr = False
    s.rts = True
    time.sleep(0.1)
    s.rts = False
    time.sleep(0.1)
except Exception as e:
    print("reset toggle failed:", e)

end = time.time() + secs
buf = b""
while time.time() < end:
    data = s.read(4096)
    if data:
        buf += data
        try:
            sys.stdout.write(data.decode("utf-8", "replace"))
            sys.stdout.flush()
        except Exception:
            pass
s.close()
print("\n---- captured", len(buf), "bytes ----")
