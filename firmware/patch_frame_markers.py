import io, sys

p = "/home/tom/LilyGo-EPD47/src/epd_driver.c"
s = io.open(p, encoding="utf-8").read()

old = """    uint8_t frame_count = 15;
    for (uint8_t k = 0; k < frame_count; k++)
    {
        epd_progress = 30 + k;
        draw_frame_inline(area, data, k, mode);
    }
    epd_progress = 21;
}"""
new = """    uint8_t frame_count = 15;
    for (uint8_t k = 0; k < frame_count; k++)
    {
        epd_progress = 30 + k;
        draw_frame_inline(area, data, k, mode);
        vTaskDelay(1);  // yield between frames (feeds watchdog / idle task)
    }
    epd_progress = 21;
}"""
already = """        epd_progress = 30 + k;
        draw_frame_inline(area, data, k, mode);
        vTaskDelay(1);  // yield between frames (feeds watchdog / idle task)"""
if already in s:
    print("yield already present")
elif old not in s:
    print("ERROR: marker block not found"); sys.exit(1)
else:
    s = s.replace(old, new, 1)
    io.open(p, "w", encoding="utf-8").write(s)
    print("per-frame markers + yield installed")
