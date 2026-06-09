import io, sys

p = "/home/tom/LilyGo-EPD47/src/ed047tc1.c"
s = io.open(p, encoding="utf-8").read()

repls = [
    ("void  epd_skip()", "void IRAM_ATTR epd_skip()"),
    ("void  epd_output_row(uint32_t output_time_dus)", "void IRAM_ATTR epd_output_row(uint32_t output_time_dus)"),
    ("void  epd_switch_buffer()", "void IRAM_ATTR epd_switch_buffer()"),
    ("uint8_t *  epd_get_current_buffer()", "uint8_t * IRAM_ATTR epd_get_current_buffer()"),
]

for old, new in repls:
    if old not in s:
        print("ERROR: not found:", repr(old))
        sys.exit(1)
    if s.count(old) != 1:
        print("ERROR: ambiguous:", repr(old), s.count(old))
        sys.exit(1)
    s = s.replace(old, new)

io.open(p, "w", encoding="utf-8").write(s)
print("restored IRAM_ATTR on 4 functions")
