import io, sys

p = "/home/tom/LilyGo-EPD47/src/rmt_compat.c"
s = io.open(p, encoding="utf-8").read()

old = (
    "void rmt_compat_tx_enable_interrupt(rmt_compat_channel_t channel, bool enable) {\n"
    "    const uint32_t tx_end_bit = 1u << (channel * 3);\n"
    "    if (enable) {\n"
    "        RMT.int_ena.val |= tx_end_bit;\n"
    "    } else {\n"
    "        RMT.int_ena.val &= ~tx_end_bit;\n"
    "    }\n"
    "}"
)

new = (
    "void rmt_compat_tx_enable_interrupt(rmt_compat_channel_t channel, bool enable) {\n"
    "    // The per-channel tx-done interrupt bit layout is chip-specific. On the\n"
    "    // original ESP32 the bits are stride-3 (tx_end/rx_end/err interleaved),\n"
    "    // but on ESP32-S3 (and other newer RMT variants) the tx-done bits are\n"
    "    // contiguous at bit `channel`. Using the wrong layout leaves our CKV\n"
    "    // channel's interrupt disabled, so the done-ISR never fires and\n"
    "    // pulse_ckv_ticks() blocks forever. Use the HAL macro for correctness.\n"
    "    const uint32_t tx_done_bit = RMT_LL_EVENT_TX_DONE(channel);\n"
    "    if (enable) {\n"
    "        RMT.int_ena.val |= tx_done_bit;\n"
    "    } else {\n"
    "        RMT.int_ena.val &= ~tx_done_bit;\n"
    "    }\n"
    "}"
)

if old not in s:
    print("ERROR: old block not found")
    sys.exit(1)

s = s.replace(old, new)
io.open(p, "w", encoding="utf-8").write(s)
print("patched OK")
