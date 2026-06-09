#!/usr/bin/env python3
# Fix: full-screen fast path passed a PSRAM pointer (possibly unaligned) directly
# to calc_epd_input_4bpp via uint32_t*. Copy into the aligned stack `line` buffer
# first, matching the original dual-task feed_display behavior.
import sys

path = "/home/" + __import__("os").environ.get("USER", "") + "/LilyGo-EPD47/src/epd_driver.c"
# Resolve home robustly
import os
home = os.path.expanduser("~")
path = os.path.join(home, "LilyGo-EPD47/src/epd_driver.c")

with open(path, "r") as f:
    src = f.read()

old = (
    "        if (area.width == EPD_WIDTH && area.x == 0)\n"
    "        {\n"
    "            lp = (uint32_t *)ptr;\n"
    "            ptr += EPD_WIDTH / 2;\n"
    "        }\n"
)
new = (
    "        if (area.width == EPD_WIDTH && area.x == 0)\n"
    "        {\n"
    "            memcpy(line, ptr, EPD_WIDTH / 2);\n"
    "            lp = (uint32_t *)line;\n"
    "            ptr += EPD_WIDTH / 2;\n"
    "        }\n"
)

count = src.count(old)
print("occurrences found:", count)
if count == 0:
    print("ERROR: pattern not found")
    sys.exit(1)

# Replace only the LAST occurrence (draw_frame_inline)
idx = src.rfind(old)
src = src[:idx] + new + src[idx + len(old):]

with open(path, "w") as f:
    f.write(src)
print("patched draw_frame_inline full-screen branch (last occurrence)")
