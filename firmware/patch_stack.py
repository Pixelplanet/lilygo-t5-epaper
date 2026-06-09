import io, sys

p = "/home/tom/LilyGo-EPD47/src/epd_driver.c"
s = io.open(p, encoding="utf-8").read()

repls = [
    ('xTaskCreatePinnedToCore((void (*)(void *))provide_out, "privide_out", 8192,',
     'xTaskCreatePinnedToCore((void (*)(void *))provide_out, "privide_out", 16384,'),
    ('xTaskCreatePinnedToCore((void (*)(void *))feed_display, "render", 8192, &p2,',
     'xTaskCreatePinnedToCore((void (*)(void *))feed_display, "render", 16384, &p2,'),
]

for old, new in repls:
    if old not in s:
        print("ERROR not found:", repr(old)); sys.exit(1)
    if s.count(old) != 1:
        print("ERROR ambiguous:", repr(old), s.count(old)); sys.exit(1)
    s = s.replace(old, new)

io.open(p, "w", encoding="utf-8").write(s)
print("bumped task stacks to 16384")
