#!/usr/bin/env python3
"""Insert epd_progress breadcrumbs into epd_init and rmt_pulse_init (IDF5 path)
to pinpoint where epd.init() hangs/faults. Idempotent-ish: bails if markers exist."""
import io, sys, os

HOME = os.path.expanduser("~")
DRV = os.path.join(HOME, "LilyGo-EPD47/src/epd_driver.c")
RMT = os.path.join(HOME, "LilyGo-EPD47/src/rmt_pulse.c")


def read(p):
    with io.open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def write(p, s):
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(s)


# --- 1) epd_driver.c: instrument epd_init ---
drv = read(DRV)
old_init = (
    "void epd_init()\n"
    "{\n"
    "    skipping = 0;\n"
    "    epd_base_init(EPD_WIDTH);\n"
    "\n"
    "    conversion_lut = (uint8_t *)heap_caps_malloc(1 << 16, MALLOC_CAP_8BIT);\n"
    "    assert(conversion_lut != NULL);\n"
    "    output_queue = xQueueCreate(64, EPD_WIDTH / 2);\n"
    "}"
)
new_init = (
    "void epd_init()\n"
    "{\n"
    "    epd_progress = 200;\n"
    "    skipping = 0;\n"
    "    epd_base_init(EPD_WIDTH);\n"
    "    epd_progress = 205;\n"
    "\n"
    "    conversion_lut = (uint8_t *)heap_caps_malloc(1 << 16, MALLOC_CAP_8BIT);\n"
    "    epd_progress = 206;\n"
    "    assert(conversion_lut != NULL);\n"
    "    output_queue = xQueueCreate(64, EPD_WIDTH / 2);\n"
    "    epd_progress = 207;\n"
    "}"
)
if "epd_progress = 200;" in drv:
    print("DRV already instrumented")
elif old_init in drv:
    drv = drv.replace(old_init, new_init)
    write(DRV, drv)
    print("DRV instrumented OK")
else:
    print("DRV PATTERN NOT FOUND")
    sys.exit(2)

# --- 2) rmt_pulse.c: add extern + breadcrumbs in IDF5 rmt_pulse_init ---
rmt = read(RMT)
if "epd_progress = 210;" in rmt:
    print("RMT already instrumented")
    sys.exit(0)

# add extern after the IDF5 include of esp_intr_alloc.h
anchor = '#include "esp_intr_alloc.h"'
if anchor not in rmt:
    print("RMT anchor include NOT FOUND")
    sys.exit(3)
rmt = rmt.replace(anchor, anchor + "\nextern volatile uint32_t epd_progress;", 1)

old_rmt = (
    "void rmt_pulse_init(gpio_num_t pin)\n"
    "{\n"
    "    rmt_compat_enable_clock(CKV_RMT_CHANNEL);\n"
    "    rmt_compat_connect_gpio(CKV_RMT_CHANNEL, pin);\n"
    "    rmt_compat_set_group_clock_src(CKV_RMT_CHANNEL);\n"
    "    rmt_compat_set_clock_div(CKV_RMT_CHANNEL, 8);   /* 80MHz/8 -> 0.1us tick */\n"
    "    rmt_compat_set_mem_blocks(CKV_RMT_CHANNEL, 2);\n"
    "    rmt_compat_enable_mem_access_nonfifo(true);\n"
    "    rmt_compat_tx_enable_loop(CKV_RMT_CHANNEL, false);\n"
    "    rmt_compat_tx_enable_carrier(CKV_RMT_CHANNEL, false);\n"
    "    rmt_compat_tx_set_idle_level(CKV_RMT_CHANNEL, 0, true);\n"
    "\n"
    "    esp_intr_alloc(\n"
    "        rmt_compat_get_irq_source(),\n"
    "        ESP_INTR_FLAG_LEVEL3,\n"
    "        rmt_interrupt_handler,\n"
    "        0,\n"
    "        &gRMT_intr_handle);\n"
    "    rmt_compat_tx_enable_interrupt(CKV_RMT_CHANNEL, true);\n"
    "}"
)
new_rmt = (
    "void rmt_pulse_init(gpio_num_t pin)\n"
    "{\n"
    "    epd_progress = 210;\n"
    "    rmt_compat_enable_clock(CKV_RMT_CHANNEL);\n"
    "    epd_progress = 211;\n"
    "    rmt_compat_connect_gpio(CKV_RMT_CHANNEL, pin);\n"
    "    epd_progress = 212;\n"
    "    rmt_compat_set_group_clock_src(CKV_RMT_CHANNEL);\n"
    "    epd_progress = 213;\n"
    "    rmt_compat_set_clock_div(CKV_RMT_CHANNEL, 8);   /* 80MHz/8 -> 0.1us tick */\n"
    "    rmt_compat_set_mem_blocks(CKV_RMT_CHANNEL, 2);\n"
    "    rmt_compat_enable_mem_access_nonfifo(true);\n"
    "    rmt_compat_tx_enable_loop(CKV_RMT_CHANNEL, false);\n"
    "    rmt_compat_tx_enable_carrier(CKV_RMT_CHANNEL, false);\n"
    "    rmt_compat_tx_set_idle_level(CKV_RMT_CHANNEL, 0, true);\n"
    "    epd_progress = 214;\n"
    "\n"
    "    esp_intr_alloc(\n"
    "        rmt_compat_get_irq_source(),\n"
    "        ESP_INTR_FLAG_LEVEL3,\n"
    "        rmt_interrupt_handler,\n"
    "        0,\n"
    "        &gRMT_intr_handle);\n"
    "    epd_progress = 215;\n"
    "    rmt_compat_tx_enable_interrupt(CKV_RMT_CHANNEL, true);\n"
    "    epd_progress = 216;\n"
    "}"
)
if old_rmt in rmt:
    rmt = rmt.replace(old_rmt, new_rmt)
    write(RMT, rmt)
    print("RMT instrumented OK")
else:
    print("RMT PATTERN NOT FOUND")
    sys.exit(4)
