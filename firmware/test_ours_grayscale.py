# Decisive Path-B test on OUR IDF5 firmware.
# Draws 16 vertical grayscale bands through the REAL draw path (epd.display ->
# epd_draw_image, identical to the manufacturer's working e.bitmap path).
import epd

W = epd.WIDTH      # 960
H = epd.HEIGHT     # 540
BPP_STRIDE = W // 2  # 480 bytes/row

# Build one row: 16 bands across the width. Band b (0..15) uses nibble value b
# (0x0 = black .. 0xF = white). Each band is W/16 px = 60 px = 30 bytes.
band_bytes = BPP_STRIDE // 16  # 30
row = bytearray()
for b in range(16):
    row += bytes([(b << 4) | b]) * band_bytes
# pad to stride if needed
if len(row) < BPP_STRIDE:
    row += bytes([0xFF]) * (BPP_STRIDE - len(row))

buf = bytearray(bytes(row) * H)
print("buf len", len(buf), "expected", BPP_STRIDE * H)

epd.init()
epd.clear()
epd.display(buf)
print("display done")
