import epd, time

W, H = 960, 540
band_bytes = (W // 2) // 16
row = bytearray()
for b in range(16):
    row += bytes([(b << 4) | b]) * band_bytes
buf = bytearray(bytes(row) * H)

epd.init()
epd.clear()

open("a_before.txt", "w").write("before")
t0 = time.ticks_ms()
epd.display(buf)
dt = time.ticks_diff(time.ticks_ms(), t0)
open("b_after.txt", "w").write("after ms=%d" % dt)
