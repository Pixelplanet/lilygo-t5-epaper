# config.py - Central hardware configuration for the LilyGo T5 4.7" Plus.
#
# Every pin number and board-specific flag lives here so the rest of the code
# never hard-codes a GPIO. Values come straight from the research blueprint
# pin map (section 3). See docs/pinmap.md for the full table.

# --- Board revision -----------------------------------------------------------
# "V2.3" or "V2.4". The touch address scan covers both regardless, but the flag
# is available for revision-specific behaviour (e.g. op-amp whine notes).
BOARD_REV = "V2.4"

# --- Display (ED047TC1, 540x960, 16 grayscale) --------------------------------
DISPLAY_WIDTH = 960          # native landscape width
DISPLAY_HEIGHT = 540         # native landscape height
DISPLAY_ROTATION = 0         # 0/90/180/270 - UI is designed for landscape (0)

# Parallel data bus D0..D7
PIN_EPD_DATA = (8, 1, 2, 3, 4, 5, 6, 7)
# Shift register (74HCT4094D) control
PIN_CFG_DATA = 13            # shift register serial data  (SPI MOSI in bypass)
PIN_CFG_CLK = 12             # shift register clock        (SPI SCK in bypass)
PIN_CFG_STR = 0              # shift register strobe/latch
# Dedicated panel timing lines
PIN_EPD_CKV = 38             # gate clock
PIN_EPD_STH = 40             # source start pulse
PIN_EPD_CKH = 41             # source clock

# --- Shared I2C bus (GT911 touch + PCF8563 RTC) -------------------------------
PIN_I2C_SDA = 18
PIN_I2C_SCL = 17
I2C_FREQ = 400_000

# --- Touch (GT911) ------------------------------------------------------------
PIN_TOUCH_INT = 47           # active-low interrupt
# GT911 floats between these two addresses (esp. on V2.4 where RST is hardwired)
GT911_ADDRESSES = (0x14, 0x5D)
# Touch->panel coordinate mapping. Calibrated on V2.4 hardware:
# GT911 reports portrait (540x960); display is landscape (960x540) with both
# axes inverted. Verified: TL tap (rx498,ry929)->(30,41), BR (rx19,ry18)->(941,520).
TOUCH_SWAP_XY = True
TOUCH_FLIP_X = False
TOUCH_FLIP_Y = True
# GT911 reports coordinates in its native panel resolution (portrait 540x960).
TOUCH_NATIVE_W = 540
TOUCH_NATIVE_H = 960

# --- RTC (PCF8563) ------------------------------------------------------------
PCF8563_ADDRESS = 0x51

# --- Network time (NTP) -------------------------------------------------------
# After a successful Wi-Fi connect the demo fetches the time from this server
# and writes it to the PCF8563 so the on-screen clock is accurate.
NTP_HOST = "pool.ntp.org"
# Local timezone offset from UTC, in hours (e.g. 1 = CET, 2 = CEST, -5 = EST).
TZ_OFFSET_HOURS = 2

# --- Buttons ------------------------------------------------------------------
PIN_BUTTON = 21              # onboard BOOT/User tactile button

# --- Battery monitor ----------------------------------------------------------
# GPIO14 is on ADC2 which CONFLICTS with active Wi-Fi. battery.py enforces this.
PIN_BATTERY_ADC = 14
BATTERY_ADC_DIVIDER = 2.0    # on-board resistor divider ratio
BATTERY_FULL_V = 4.2
BATTERY_EMPTY_V = 3.3

# --- SD / TF card (SPI) -------------------------------------------------------
PIN_SD_MISO = 16
PIN_SD_MOSI = 15
PIN_SD_SCK = 11
PIN_SD_CS = 42

# --- Free / unrouted pins (available for expansion) ---------------------------
FREE_PINS = (10, 39, 45, 48)

# --- Deep-sleep touch wake ----------------------------------------------------
# GPIO47 is NOT RTC-capable, so touch-to-wake requires soldering a bridge from
# GPIO10 (RTC-capable) to GPIO47. Set True only after the bridge is installed.
TOUCH_WAKE_BRIDGE = False
PIN_TOUCH_WAKE = 10

# --- Performance / native acceleration ----------------------------------------
# Use the native C GT911 touch poll (firmware `touch` module) when available.
# Falls back to the pure-Python driver automatically if the module is missing.
USE_NATIVE_TOUCH = False
# Emit input/refresh timing samples to debug.log (averaged, ~once/2s). Turn off
# in normal use; it adds a little overhead and noise to the log.
PROFILE = False
