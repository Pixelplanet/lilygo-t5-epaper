# LilyGo T5 4.7" Plus — MicroPython Implementation Plan

Target board: **LilyGo T5 4.7" Plus** (ESP32-S3-WROOM-1-N16R8, 16 MB Flash / 8 MB Octal
PSRAM), **ED047TC1** 540×960 16-level grayscale e-paper, **GT911** capacitive touch,
**PCF8563** RTC. Both **V2.3** and **V2.4** hardware revisions are supported.

This document is the engineering plan derived from `Research plan.docx`. The goal is to have
**everything ready to flash the moment the board arrives**, plus a **desktop simulator** so the
UI and application logic can be developed and demonstrated *today* without hardware.

---

## 1. Strategy & key decisions

### 1.1 Firmware path

The research doc describes two paths:

- **Option A — LilyGo C-driver firmware** (`epd`, `framebuf_plus` C modules). This is the only
  realistic way to drive the ED047TC1 *parallel* panel from MicroPython at usable speed, because
  pushing pixel data through the 8-bit bus with precise timing cannot be done fast enough in pure
  Python.
- **Option B — Upstream mainline MicroPython** + pure-Python drivers. Excellent for touch / I²C /
  RTC / power, but the parallel **pixel** path is effectively incomplete (the doc's
  `parallel_bypass.py` only latches the shift-register *config* byte, not the high-speed pixel
  clocking).

**Decision:** Use **Option A firmware** as the supported runtime for the display, and layer **our
own pure-Python application, drivers and UI on top**. All touch / I²C / RTC / battery code is
firmware-agnostic and works on either path. The display layer is isolated behind a single
adapter (`lib/display.py`) so that if a better mainline parallel driver appears, only that one
file changes.

> The exact symbol names of the LilyGo `epd` / `framebuf_plus` C modules vary between firmware
> builds (the repo is fragmented/unmaintained). Every hardware-specific call is therefore
> centralised in `lib/display.py` inside a clearly marked **`# === HW BINDING ===`** block. When
> the board is in hand, confirm the installed firmware's API and adjust only that block.

### 1.2 Testability without hardware

We ship a **desktop simulator** (`sim/`) that provides CPython shims for `machine`, `framebuf`,
`network`, `epd`, and `time.sleep_ms`, and renders the framebuffer to a **Tkinter** window where
**mouse clicks act as touch events**. The *same* application and UI code runs unmodified on the
simulator and on the device. This is how we validate the touch UX, the on-screen keyboard, and
the Wi-Fi flow right now.

### 1.3 Async model

Mainline MicroPython ≥ 1.28 aliases `uasyncio` as `asyncio`, so we `import asyncio` everywhere.
The app runs a cooperative loop: a touch task polls the GT911 `INT` line (active-low), dispatches
events to the UI, and a render task flushes dirty regions to the panel.

---

## 2. Hardware constraints baked into the code

| Constraint (from research doc) | How the code handles it |
|---|---|
| Octal PSRAM needs `SPIRAM_OCT` firmware | Documented in `docs/flashing.md`; flashing script uses the OCT variant. |
| GT911 address floats `0x14`/`0x5D` (esp. V2.4) | `gt911.py` auto-probes both addresses at startup. |
| GT911 status reg `0x814E` must be cleared after read | Driver always writes `0x00` back to `0x814E`. |
| Shared I²C (GT911 + PCF8563) lockups | `SoftI2C` + an `asyncio.Lock` wrapper (`shared_i2c.py`). |
| Battery ADC (GPIO14 / ADC2) conflicts with Wi-Fi | `battery.py` refuses to sample while `WLAN` is active; Wi-Fi code samples *before* enabling the radio. |
| Touch-to-wake needs GPIO10↔GPIO47 solder bridge | `power.py` deep-sleep helper is gated behind a `TOUCH_WAKE_BRIDGE` config flag. |
| Shift-register config too slow via `Pin.value()` | `parallel_bypass.py` (SPI @ 20 MHz) included for the Option-B/experimental path. |
| V2.3 vs V2.4 differences | `config.py` `BOARD_REV` flag; address scan covers both regardless. |

Pin map is encoded once in `config.py` and documented in `docs/pinmap.md`.

---

## 3. Project structure

```
src/                      # → uploaded to the device flash root
  boot.py                 # minimal, fast boot
  main.py                 # entry point: builds Board + launches WifiDemoApp
  config.py               # pin map, board revision, feature flags
  lib/
    shared_i2c.py         # SoftI2C + async lock (from doc, hardened)
    gt911.py              # GT911 touch: dynamic address, sync + async poll
    pcf8563.py            # RTC read/set
    battery.py            # ADC2-safe battery voltage
    power.py              # deep sleep / touch-wake helper
    parallel_bypass.py    # SPI shift-register accelerator (experimental)
    display.py            # display abstraction + HW binding block
    board.py              # wires all peripherals together
    ui/
      core.py             # Widget/Screen base, event + rect types, App loop
      theme.py            # grayscale palette, metrics
      widgets.py          # Label, Button, Panel, ListView, ProgressBar, TextField
      keyboard.py         # on-screen QWERTY keyboard
  apps/
    wifi_demo.py          # showcase: scan Wi-Fi, pick SSID, type password, connect
    touch_test.py         # draw-where-you-touch diagnostic
sim/                      # desktop simulator (CPython, stdlib only)
  framebuf.py  machine.py  network.py  epd.py  font8x8.py  run_sim.py
tools/
  flash.ps1  flash.sh     # erase + write firmware
  deploy.ps1  deploy.sh    # upload src/ with mpremote
  requirements.txt
docs/
  implementation_plan.md  pinmap.md  flashing.md
tests/
  test_ui_logic.py        # headless logic tests (no display)
```

---

## 4. Showcase application — `wifi_demo.py`

Demonstrates touch end-to-end on the e-paper:

1. **Home screen** — title, RTC clock, battery %, two big buttons: **“Scan Wi-Fi”** and
   **“Touch Test”**.
2. **Scanning screen** — samples battery first, enables `WLAN`, runs `scan()`, shows a spinner.
3. **Network list** — scrollable `ListView` of SSIDs with RSSI bars and a lock icon for secured
   networks; tap to select.
4. **Password screen** — selected SSID, a masked `TextField`, and the on-screen **keyboard**
   (letters / numbers / symbols layers, Shift, Backspace, Space, Connect).
5. **Result screen** — “Connected ✓ / Failed ✗”, assigned IP, button back to home.

Open networks skip the password screen. e-paper updates use partial refresh for key feedback and
full refresh on screen transitions.

---

## 5. Bring-up order when the board arrives (handoff)

1. Flash firmware: `tools/flash.ps1` (erase + `ESP32_GENERIC_S3` **SPIRAM_OCT** build).
2. Upload code: `tools/deploy.ps1` (mpremote copies `src/` to flash root).
3. Open REPL, confirm `import config` and `Board()` init prints detected GT911 address.
4. Run `apps/touch_test.py` → verify coordinates track finger and orientation/mapping.
5. Calibrate touch→panel mapping in `config.py` (`TOUCH_FLIP_X/Y`, `TOUCH_SWAP_XY`) if needed.
6. Launch `main.py` → run the Wi-Fi demo, connect to a real AP.
7. (Optional) If GPIO10↔GPIO47 bridge is soldered, set `TOUCH_WAKE_BRIDGE = True` for deep-sleep
   touch-wake.

The only steps that *require* the physical board are 4–7; everything else is verified now in the
simulator.

---

## 6. What is verifiable today (no board)

- Full UI flow (home → scan → list → keyboard → connect → result) via `python sim/run_sim.py`.
- On-screen keyboard input, masking, layer switching, backspace.
- Wi-Fi list rendering & selection (simulator returns a fake scan list).
- Headless logic tests: `python -m pytest tests/` (keyboard state, list scrolling, event hit-test).
