import epd

e = epd.EPD47()

# 16 vertical bands, 4bpp GS4_HMSB: nibble 0x0=black .. 0xF=white
# 960 px wide / 16 bands = 60 px/band = 30 bytes/band/row
row = bytearray()
for b in range(16):
    row += bytes([(b << 4) | b]) * 30
buf = bytearray(bytes(row) * 540)  # 480 bytes/row * 540 rows = 259200

e.power(1)
e.clear()
e.bitmap(buf, 0, 0, 960, 540)
e.power(0)
print("grayscale bands done", len(buf))
