import sys
import time

import serial

PORT = "COM5"
OUT = sys.argv[1] if len(sys.argv) > 1 else "device.log"

try:
    s = serial.Serial(PORT, 115200, timeout=0.2)
except Exception as e:
    print("could not open", PORT, e)
    sys.exit(1)

with open(OUT, "a", encoding="utf-8", errors="replace") as f:
    f.write("\n==== capture start {} ====\n".format(time.strftime("%H:%M:%S")))
    f.flush()
    while True:
        try:
            data = s.read(256)
            if data:
                f.write(data.decode("utf-8", "replace"))
                f.flush()
        except Exception as e:
            f.write("\n[reader error] {}\n".format(e))
            f.flush()
            time.sleep(0.5)
