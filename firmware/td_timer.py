import epd, time, machine

W, H = 960, 540
band_bytes = (W // 2) // 16
row = bytearray()
for b in range(16):
    row += bytes([(b << 4) | b]) * band_bytes
buf = bytearray(bytes(row) * H)

epd.init()
epd.clear()

_tim = machine.Timer(0)


def _cb(t):
    t0 = time.ticks_ms()
    epd.display(buf)
    dt = time.ticks_diff(time.ticks_ms(), t0)
    with open("timing.txt", "w") as f:
        f.write("display_ms=%d\n" % dt)


_tim.init(period=1500, mode=machine.Timer.ONE_SHOT, callback=_cb)
