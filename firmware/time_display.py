import epd, time

W, H = 960, 540
band_bytes = (W // 2) // 16  # 30
row = bytearray()
for b in range(16):
    row += bytes([(b << 4) | b]) * band_bytes
buf = bytearray(bytes(row) * H)

epd.init()
epd.clear()

t0 = time.ticks_ms()
epd.display(buf)
dt = time.ticks_diff(time.ticks_ms(), t0)

with open("timing.txt", "w") as f:
    f.write("display_ms=%d\n" % dt)
