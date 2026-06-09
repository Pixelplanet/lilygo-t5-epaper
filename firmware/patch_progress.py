import io, sys

# --- 1) epd_driver.c: add RTC progress var + markers inside epd_draw_image ---
p1 = "/home/tom/LilyGo-EPD47/src/epd_driver.c"
s1 = io.open(p1, encoding="utf-8").read()

# Ensure esp_attr.h is included (for RTC_NOINIT_ATTR).
if "esp_attr.h" not in s1:
    # insert after the first #include line
    idx = s1.index("#include")
    line_end = s1.index("\n", idx) + 1
    s1 = s1[:line_end] + '#include "esp_attr.h"\n' + s1[line_end:]

# Add the global RTC progress variable once (after includes / before first function).
if "epd_progress" not in s1:
    anchor = "static uint32_t skipping;"
    if anchor not in s1:
        print("ERROR: skipping anchor not found"); sys.exit(1)
    s1 = s1.replace(anchor,
                    "static uint32_t skipping;\n"
                    "RTC_NOINIT_ATTR volatile uint32_t epd_progress;", 1)

# Markers inside epd_draw_image: before frame loop (20) and after (21).
draw_old = """    uint8_t frame_count = 15;
    for (uint8_t k = 0; k < frame_count; k++)
    {
        draw_frame_inline(area, data, k, mode);
    }
}"""
draw_new = """    uint8_t frame_count = 15;
    epd_progress = 20;
    for (uint8_t k = 0; k < frame_count; k++)
    {
        draw_frame_inline(area, data, k, mode);
    }
    epd_progress = 21;
}"""
if draw_old not in s1:
    print("ERROR: epd_draw_image body (single-task) not found"); sys.exit(1)
s1 = s1.replace(draw_old, draw_new, 1)
io.open(p1, "w", encoding="utf-8").write(s1)
print("epd_driver.c instrumented (epd_progress 20/21)")

# --- 2) modepd.c: extern var, markers around poweron/draw/poweroff, progress() ---
# Edit the WORKSPACE source of truth (stage copies this into the build).
p2 = "/mnt/c/Projects/Lillygo Micropython/firmware/usercmod/epd/modepd.c"
s2 = io.open(p2, encoding="utf-8").read()

if "epd_progress" not in s2:
    s2 = s2.replace(
        '#include "epd_driver.h"  // LilyGo-EPD47 driver (epd47 component)',
        '#include "epd_driver.h"  // LilyGo-EPD47 driver (epd47 component)\n\n'
        'extern volatile uint32_t epd_progress;', 1)

# Instrument epd_display_.
disp_old = """    Rect_t area = { .x = 0, .y = 0, .width = EPD_WIDTH, .height = EPD_HEIGHT };
    epd_poweron();
    epd_draw_image(area, (uint8_t *)bi.buf, BLACK_ON_WHITE);
    epd_poweroff();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(epd_display_obj, epd_display_);"""
disp_new = """    Rect_t area = { .x = 0, .y = 0, .width = EPD_WIDTH, .height = EPD_HEIGHT };
    epd_progress = 10;
    epd_poweron();
    epd_progress = 11;
    epd_draw_image(area, (uint8_t *)bi.buf, BLACK_ON_WHITE);
    epd_progress = 12;
    epd_poweroff();
    epd_progress = 13;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(epd_display_obj, epd_display_);

// epd.progress() - DIAGNOSTIC: read RTC-persisted crash progress marker.
static mp_obj_t epd_progress_(void) {
    return mp_obj_new_int(epd_progress);
}
static MP_DEFINE_CONST_FUN_OBJ_0(epd_progress_obj, epd_progress_);"""
if disp_old not in s2:
    print("ERROR: epd_display_ body not found in modepd.c"); sys.exit(1)
s2 = s2.replace(disp_old, disp_new, 1)

# Register epd.progress in the globals table.
s2 = s2.replace(
    "    { MP_ROM_QSTR(MP_QSTR_display), MP_ROM_PTR(&epd_display_obj) },",
    "    { MP_ROM_QSTR(MP_QSTR_display), MP_ROM_PTR(&epd_display_obj) },\n"
    "    { MP_ROM_QSTR(MP_QSTR_progress), MP_ROM_PTR(&epd_progress_obj) },", 1)

io.open(p2, "w", encoding="utf-8").write(s2)
print("modepd.c instrumented at:", p2)
