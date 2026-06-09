// modepd.c - MicroPython binding for the LilyGo EPD47 (ED047TC1) e-paper driver.
//
// Exposes a Python `epd` module that satisfies the backend contract used by
// src/lib/display.py:
//     epd.init()
//     epd.display(buffer)                       # full-screen 4bpp GS4_HMSB push
//     epd.display_partial(buffer, x, y, w, h)   # crop region of full framebuffer
//     epd.clear()
//     epd.power_on() / epd.power_off()
//     epd.WIDTH / epd.HEIGHT
//
// The pixel format produced by framebuf.GS4_HMSB (upper nibble = left pixel,
// 0x0 = black .. 0xF = white) is byte-for-byte identical to what the LilyGo
// driver's epd_draw_image() expects, so the framebuffer is passed straight
// through with no conversion.

#include <string.h>

#include "py/runtime.h"
#include "py/obj.h"
#include "py/mphal.h"

#include "epd_driver.h"  // LilyGo-EPD47 driver (epd47 component)

extern volatile uint32_t epd_progress;

// epd.init()
static mp_obj_t epd_init_(void) {
    epd_init();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(epd_init_obj, epd_init_);

// epd.power_on()
static mp_obj_t epd_power_on_(void) {
    epd_poweron();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(epd_power_on_obj, epd_power_on_);

// epd.power_off()
static mp_obj_t epd_power_off_(void) {
    epd_poweroff();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(epd_power_off_obj, epd_power_off_);

// epd.clear() - full clean wipe to white
static mp_obj_t epd_clear_(void) {
    epd_poweron();
    epd_clear();
    epd_poweroff();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(epd_clear_obj, epd_clear_);

// epd.fill_black(cycles=12) - DIAGNOSTIC: repeatedly drive the dark phase to test
// whether the panel can physically darken at all. Bypasses the grayscale pipeline.
static mp_obj_t epd_fill_black_(size_t n_args, const mp_obj_t *args) {
    int cycles = (n_args >= 1) ? mp_obj_get_int(args[0]) : 12;
    Rect_t area = { .x = 0, .y = 0, .width = EPD_WIDTH, .height = EPD_HEIGHT };
    epd_poweron();
    for (int i = 0; i < cycles; i++) {
        epd_push_pixels(area, 50, 0);  // color=0 -> DARK_BYTE drive
    }
    epd_poweroff();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(epd_fill_black_obj, 0, 1, epd_fill_black_);

// epd.fill_raw(pattern, cycles=8, time=50) - DIAGNOSTIC: drive a raw byte pattern
// across the whole panel, bypassing DARK/CLEAR encoding and the grayscale LUT.
static mp_obj_t epd_fill_raw_(size_t n_args, const mp_obj_t *args) {
    int pattern = mp_obj_get_int(args[0]) & 0xFF;
    int cycles = (n_args >= 2) ? mp_obj_get_int(args[1]) : 8;
    int time = (n_args >= 3) ? mp_obj_get_int(args[2]) : 50;
    epd_poweron();
    epd_test_fill_raw((uint8_t)pattern, cycles, time);
    epd_poweroff();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(epd_fill_raw_obj, 1, 3, epd_fill_raw_);

// epd.display(buffer) - push a full-screen 4bpp framebuffer (EPD_WIDTH/2 * EPD_HEIGHT bytes)
static mp_obj_t epd_display_(mp_obj_t buf_in) {
    mp_buffer_info_t bi;
    mp_get_buffer_raise(buf_in, &bi, MP_BUFFER_READ);
    size_t need = (size_t)(EPD_WIDTH / 2) * (size_t)EPD_HEIGHT;
    if (bi.len < need) {
        mp_raise_ValueError(MP_ERROR_TEXT("framebuffer too small"));
    }
    Rect_t area = { .x = 0, .y = 0, .width = EPD_WIDTH, .height = EPD_HEIGHT };
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
static MP_DEFINE_CONST_FUN_OBJ_0(epd_progress_obj, epd_progress_);

// epd.display_partial(buffer, x, y, w, h, clear=True)
// `buffer` is the FULL framebuffer; the (x,y,w,h) sub-rectangle is cropped out
// and pushed. x/w are aligned to even pixels because each byte packs 2 pixels.
// When `clear` is True the region is first driven to white (so black pixels can
// be erased); when False only black ink is added (white->black), which is much
// faster and avoids the clear flash - ideal for purely additive updates.
static mp_obj_t epd_display_partial_(size_t n_args, const mp_obj_t *args) {
    mp_buffer_info_t bi;
    mp_get_buffer_raise(args[0], &bi, MP_BUFFER_READ);
    int x = mp_obj_get_int(args[1]);
    int y = mp_obj_get_int(args[2]);
    int w = mp_obj_get_int(args[3]);
    int h = mp_obj_get_int(args[4]);
    int clear = (n_args >= 6) ? mp_obj_is_true(args[5]) : 1;

    // Align x left and w to even pixels (2 px / byte).
    if (x & 1) { x -= 1; w += 1; }
    if (w & 1) { w += 1; }

    // Clip to panel bounds.
    if (x < 0) { w += x; x = 0; }
    if (y < 0) { h += y; y = 0; }
    if (x + w > EPD_WIDTH) { w = EPD_WIDTH - x; }
    if (y + h > EPD_HEIGHT) { h = EPD_HEIGHT - y; }
    if (w <= 0 || h <= 0) {
        return mp_const_none;
    }

    size_t need = (size_t)(EPD_WIDTH / 2) * (size_t)EPD_HEIGHT;
    if (bi.len < need) {
        mp_raise_ValueError(MP_ERROR_TEXT("framebuffer too small"));
    }

    const int src_stride = EPD_WIDTH / 2;
    const int dst_stride = w / 2;
    uint8_t *src = (uint8_t *)bi.buf;
    uint8_t *crop = m_new(uint8_t, (size_t)dst_stride * (size_t)h);
    for (int row = 0; row < h; row++) {
        memcpy(crop + (size_t)row * dst_stride,
               src + (size_t)(y + row) * src_stride + (x / 2),
               dst_stride);
    }

    Rect_t area = { .x = x, .y = y, .width = w, .height = h };
    epd_poweron();
    // E-paper draw_image in BLACK_ON_WHITE only *adds* black ink; it cannot
    // erase previously-drawn black back to white. When the caller needs pixels
    // to go light again, clear the sub-rectangle to white first; otherwise skip
    // the (slow) clear and just darken - instant white->black additive draw.
    if (clear) {
        epd_clear_area(area);
    }
    epd_draw_image(area, crop, BLACK_ON_WHITE);
    epd_poweroff();

    m_del(uint8_t, crop, (size_t)dst_stride * (size_t)h);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(epd_display_partial_obj, 5, 6, epd_display_partial_);

// epd.display_partial_many(buffer, regions)
// `regions` is a list/tuple of (x, y, w, h, clear) tuples. Performs ONE
// epd_poweron(), draws every region back-to-back, then ONE epd_poweroff(), so
// consecutive regions update with no inter-region power-cycle gap (the visible
// pause between separate display_partial() calls). `buffer` is the FULL
// framebuffer; each region is cropped out of it. clear=True drives the region
// white first (so black can be erased); clear=False is additive (white->black).
static mp_obj_t epd_display_partial_many_(mp_obj_t buf_in, mp_obj_t regions_in) {
    mp_buffer_info_t bi;
    mp_get_buffer_raise(buf_in, &bi, MP_BUFFER_READ);
    size_t need = (size_t)(EPD_WIDTH / 2) * (size_t)EPD_HEIGHT;
    if (bi.len < need) {
        mp_raise_ValueError(MP_ERROR_TEXT("framebuffer too small"));
    }
    size_t n;
    mp_obj_t *items;
    mp_obj_get_array(regions_in, &n, &items);
    if (n == 0) {
        return mp_const_none;
    }
    const int src_stride = EPD_WIDTH / 2;
    uint8_t *src = (uint8_t *)bi.buf;

    epd_poweron();
    for (size_t r = 0; r < n; r++) {
        size_t tn;
        mp_obj_t *t;
        mp_obj_get_array(items[r], &tn, &t);
        if (tn < 4) { continue; }
        int x = mp_obj_get_int(t[0]);
        int y = mp_obj_get_int(t[1]);
        int w = mp_obj_get_int(t[2]);
        int h = mp_obj_get_int(t[3]);
        int clear = (tn >= 5) ? mp_obj_is_true(t[4]) : 1;

        // Align x left and w to even pixels (2 px / byte).
        if (x & 1) { x -= 1; w += 1; }
        if (w & 1) { w += 1; }
        // Clip to panel bounds.
        if (x < 0) { w += x; x = 0; }
        if (y < 0) { h += y; y = 0; }
        if (x + w > EPD_WIDTH) { w = EPD_WIDTH - x; }
        if (y + h > EPD_HEIGHT) { h = EPD_HEIGHT - y; }
        if (w <= 0 || h <= 0) { continue; }

        const int dst_stride = w / 2;
        uint8_t *crop = m_new(uint8_t, (size_t)dst_stride * (size_t)h);
        for (int row = 0; row < h; row++) {
            memcpy(crop + (size_t)row * dst_stride,
                   src + (size_t)(y + row) * src_stride + (x / 2),
                   dst_stride);
        }
        Rect_t area = { .x = x, .y = y, .width = w, .height = h };
        if (clear) {
            epd_clear_area(area);
        }
        epd_draw_image(area, crop, BLACK_ON_WHITE);
        m_del(uint8_t, crop, (size_t)dst_stride * (size_t)h);
    }
    epd_poweroff();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(epd_display_partial_many_obj, epd_display_partial_many_);

// epd.repair(cycles=4, delay_ms=50)
// Manufacturer screen-repair / charge-neutralization sweep. Drives the WHOLE
// panel through alternating full-voltage white<->black cycles to pull trapped
// electrophoretic particles off the glass and disperse them evenly, undoing the
// ghost-boundary lines and gray burn-in that repeated partial updates cause.
// 4 cycles = routine maintenance; 10-15 = heavily ghosted panel.
static mp_obj_t epd_repair_(size_t n_args, const mp_obj_t *args) {
    int cycles = (n_args >= 1) ? mp_obj_get_int(args[0]) : 4;
    int delay_ms = (n_args >= 2) ? mp_obj_get_int(args[1]) : 50;
    if (cycles < 1) { cycles = 1; }
    if (delay_ms < 1) { delay_ms = 1; }
    Rect_t area = { .x = 0, .y = 0, .width = EPD_WIDTH, .height = EPD_HEIGHT };
    epd_poweron();
    epd_clear_area_cycles(area, cycles, delay_ms);
    epd_poweroff();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(epd_repair_obj, 0, 2, epd_repair_);

static const mp_rom_map_elem_t epd_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_epd) },
    { MP_ROM_QSTR(MP_QSTR_init), MP_ROM_PTR(&epd_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_power_on), MP_ROM_PTR(&epd_power_on_obj) },
    { MP_ROM_QSTR(MP_QSTR_power_off), MP_ROM_PTR(&epd_power_off_obj) },
    { MP_ROM_QSTR(MP_QSTR_clear), MP_ROM_PTR(&epd_clear_obj) },
    { MP_ROM_QSTR(MP_QSTR_fill_black), MP_ROM_PTR(&epd_fill_black_obj) },
    { MP_ROM_QSTR(MP_QSTR_fill_raw), MP_ROM_PTR(&epd_fill_raw_obj) },
    { MP_ROM_QSTR(MP_QSTR_display), MP_ROM_PTR(&epd_display_obj) },
    { MP_ROM_QSTR(MP_QSTR_progress), MP_ROM_PTR(&epd_progress_obj) },
    { MP_ROM_QSTR(MP_QSTR_display_partial), MP_ROM_PTR(&epd_display_partial_obj) },
    { MP_ROM_QSTR(MP_QSTR_display_partial_many), MP_ROM_PTR(&epd_display_partial_many_obj) },
    { MP_ROM_QSTR(MP_QSTR_repair), MP_ROM_PTR(&epd_repair_obj) },
    { MP_ROM_QSTR(MP_QSTR_WIDTH), MP_ROM_INT(EPD_WIDTH) },
    { MP_ROM_QSTR(MP_QSTR_HEIGHT), MP_ROM_INT(EPD_HEIGHT) },
};
static MP_DEFINE_CONST_DICT(epd_module_globals, epd_module_globals_table);

const mp_obj_module_t epd_user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&epd_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_epd, epd_user_cmodule);
