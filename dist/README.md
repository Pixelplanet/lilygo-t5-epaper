# LilyGo T5 4.7" e-paper starter kit (MicroPython)

A complete, ready-to-run starter for the **LilyGo T5 4.7" Plus** e-paper board.
It ships a working custom MicroPython firmware plus a touch-driven demo app, so
you can flash it, upload the Python, and have a usable grayscale UI with an
on-screen keyboard, Wi-Fi setup, and an NTP-synced clock in a few minutes.

> Everything here has been verified on real hardware. The trickiest parts of this
> board are the **e-paper refresh behavior** and the **multiple serial ports** —
> both are documented in detail below and in [`docs/`](docs).

## What's in the box

```
dist/
├─ firmware-epd.bin        ← the MicroPython firmware (flash this once)
├─ flash.ps1 / flash.sh    ← flash the firmware
├─ deploy.ps1 / deploy.sh  ← upload the Python app to the board
├─ device/                 ← the Python that runs on the board
│  ├─ boot.py, main.py, config.py
│  ├─ lib/                 ← display driver, touch, RTC, UI toolkit, helpers
│  └─ apps/wifi_demo.py    ← the demo app
└─ docs/
   ├─ screen-refresh.md    ← MUST READ: how e-paper refresh works here
   ├─ editing-with-thonny.md ← drag-and-drop style file editing (no USB drive)
   ├─ troubleshooting.md   ← debugging + common problems
   └─ pinmap.md            ← full GPIO map and constraints
```

## Hardware

- **Board:** LilyGo T5 4.7" Plus (V2.4)
- **MCU:** ESP32-S3-WROOM-1-**N16R8** — 16 MB flash, **8 MB Octal PSRAM**
- **Display:** ED047TC1, 960×540, 16-level grayscale, *controllerless* e-paper
- **Touch:** GT911 capacitive
- **RTC:** PCF8563
- Onboard BOOT/User button (GPIO21), battery monitor, microSD slot

The **Octal PSRAM** detail matters: a wrong firmware build will boot-loop. The
included `firmware-epd.bin` is built correctly.

## Prerequisites

Install Python 3, then:

```bash
pip install esptool mpremote
```

- `esptool` flashes the firmware.
- `mpremote` uploads the Python files and gives you a REPL.

## Quick start

### 1. Find your serial ports

This board enumerates **more than one** COM port and they **change after
flashing**. See [docs/troubleshooting.md → Find the ports](docs/troubleshooting.md#find-the-ports).
Briefly: the **download/ROM port** is for `esptool`, the **app port** (native
USB-CDC) is for `mpremote`.

### 2. Flash the firmware (once)

Put the board into **download mode**: hold **BOOT**, tap **RST**, release **BOOT**.

Windows:
```powershell
.\flash.ps1 -Port COM7
```
Linux/macOS:
```bash
./flash.sh /dev/ttyACM0
```

What the script runs under the hood:
```
python -m esptool --chip esp32s3 --port <DL_PORT> erase_flash
python -m esptool --chip esp32s3 --port <DL_PORT> --baud 460800 write_flash 0x0 firmware-epd.bin
```

Then **tap RST**. The board re-enumerates — note the new app port.

### 3. Upload the Python app

Windows:
```powershell
.\deploy.ps1 -Port COM5 -Reset
```
Linux/macOS:
```bash
./deploy.sh /dev/ttyACM0 --reset
```

This copies the whole `device/` tree (`main.py`, `config.py`, `lib/`, `apps/`) to
the flash root and resets the board. The demo starts automatically.

> **Prefer a GUI?** This board does **not** appear as a USB drive, so you can't
> drag files onto it in a file explorer. For a drag-and-drop style workflow
> (browse the device files, upload/edit them, run `main.py`) use **Thonny** —
> see [docs/editing-with-thonny.md](docs/editing-with-thonny.md).

### 4. Use the demo

On power-on you get the **home screen** — an icon grid of apps. Tap a tile to open it:

- **Wi-Fi** → **Scan Wi-Fi** → pick a network → type the password on the on-screen
  keyboard → **Connect**. On success it saves the network, syncs the clock over NTP,
  and shows an IP/status screen. After that the board **auto-connects** to the saved
  network at boot, so online features are ready without reconnecting. (This screen
  also has **Refresh** = clean full refresh, **Repair** = ghosting sweep, and
  **Touch test**.)
- **Calendar** → trash-collection calendar parsed from `device/trash.ics`.
- **Prices** → electricity prices (needs a Tibber token, see below).

Every screen has a uniform title bar with a top-right **Back** button to return home.

#### Electricity prices (Tibber)

Copy `device/secrets.example.py` to `device/secrets.py`, paste your Tibber token
into `TIBBER_TOKEN`, and redeploy. Without a token the Prices app just says so.
`secrets.py` is gitignored so your token is never committed.

#### Build your own apps/screens

The home grid and any custom screens are defined in `device/ui.json`. Design them
by hand or with the offline **web builder** (`tools/ui-builder.html`) — full guide
in [docs/ui-builder.md](docs/ui-builder.md).

Set your timezone first if the clock is off: edit `TZ_OFFSET_HOURS` in
[`device/config.py`](device/config.py) (`1` = CET, `2` = CEST), then redeploy.

## You can't lock yourself out

`main.py` auto-runs the app but always leaves a ~2 s escape window:

- Hold **BOOT** during reset → skip the app, land in the REPL.
- Or press **Ctrl-C** while connected to the REPL.

A crash also drops to the REPL with a traceback instead of hanging. So edit
freely — reconnect, fix, redeploy.

## Read this before you build your own screens

**[docs/screen-refresh.md](docs/screen-refresh.md)** explains the one thing that
trips everyone up: because this panel is *controllerless*, the firmware chooses
the refresh waveform, and the wrong choice causes vertical streaks, ghosting, or
distracting full-screen flashes. Short version:

- **FULL** (clean, ~1 s flash) is the **only** mode that removes streaks/ghosting.
- **PARTIAL** can erase but leaves streaks; **ADD** is instant but only darkens.
- Prefer instant **additive** updates for small darkening changes (like typing),
  and let screen transitions / the periodic auto-FULL clean up streaks. Don't force
  a FULL refresh on a fast, repeated interaction (that's the "keyboard flashing"
  mistake).

## Debugging

`print()` over USB-CDC is unreliable on this board. The dependable probe is the
on-device, fsync'd, append-only `debug.log`:

```powershell
python -m mpremote connect COM5 fs cat :debug.log
```

It records a `reset_cause` line every boot, so resets/brownouts are visible in the
history. Full guide + a table of common problems: **[docs/troubleshooting.md](docs/troubleshooting.md)**.

## Configuration reference

All hardware pins and flags live in [`device/config.py`](device/config.py) — you
shouldn't need to touch GPIOs, but these are the user-facing knobs:

| Setting | Purpose |
|---------|---------|
| `TZ_OFFSET_HOURS` | Local timezone offset for the NTP clock |
| `NTP_HOST` | Time server (default `pool.ntp.org`) |
| `TOUCH_SWAP_XY` / `TOUCH_FLIP_X` / `TOUCH_FLIP_Y` | Touch orientation calibration |
| `BOARD_REV` | `"V2.3"` / `"V2.4"` |

## Rebuilding the firmware

You only need this if you change the **C** firmware — Python app changes just need
`deploy`. The firmware is a custom MicroPython build with a native `epd` module
(IDF 5, Octal-PSRAM / `SPIRAM_OCT`). Build instructions live in the main project
repo (`firmware/build_epd_firmware.sh`); they're out of scope for this starter kit.
