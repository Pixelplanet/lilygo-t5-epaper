# LilyGo T5 4.7" Plus — MicroPython + Touch UI

MicroPython firmware project for the **LilyGo T5 4.7" Plus** e-paper board
(ESP32-S3-WROOM-1-N16R8, ED047TC1 540×960 grayscale panel, GT911 touch, PCF8563 RTC).

## What's included

- **Flash-ready device code** (`src/`): hardware drivers + a small touch UI toolkit + a Wi-Fi
  showcase app.
- **A touch showcase**: home screen → scan Wi-Fi → pick a network → type the password on an
  **on-screen keyboard** → connect → result. Plus a draw-where-you-touch diagnostic.
- **A desktop simulator** (`sim/`): runs the *same* app on your PC, mouse = touch, so the UX is
  verifiable now without the board.

![home](build/snapshots/01_home.png)
![password keyboard](build/snapshots/03_password.png)

## Try it now (no board needed)

```powershell
python -m pip install -r tools/requirements.txt   # Pillow
python sim/run_sim.py                              # interactive window, mouse = touch
python sim/snapshot.py                             # render screens to build/snapshots/
python tests/test_ui_logic.py                      # headless logic tests
```

## Project layout

```
src/      device code (uploaded to flash root): main.py, config.py, lib/, apps/
sim/      CPython shims (machine/framebuf/network/epd) + Tk runner + snapshots
tools/    flash.ps1/.sh (firmware) and deploy.ps1/.sh (upload src/)
docs/     implementation_plan.md, pinmap.md, flashing.md
tests/    headless UI logic tests
```

## When the board arrives

See **[docs/flashing.md](docs/flashing.md)**. Summary:

1. Flash mainline MicroPython **SPIRAM_OCT** build (or LilyGo C-driver firmware for the panel —
   see flashing doc) → `tools/flash.ps1`.
2. Upload the app → `tools/deploy.ps1`.
3. Run touch test, calibrate `TOUCH_*` flags in `config.py`, then run the Wi-Fi demo.

## Key engineering notes

- All pins/flags live in [`src/config.py`](src/config.py); see [docs/pinmap.md](docs/pinmap.md).
- GT911 touch address is auto-probed (`0x14`/`0x5D`); status reg `0x814E` is cleared each read.
- Battery ADC (GPIO14/ADC2) is never read while Wi-Fi is active (radio conflict).
- The e-paper hardware binding is isolated in one block of
  [`src/lib/display.py`](src/lib/display.py) (`# === HW BINDING ===`) for easy adaptation to the
  installed firmware's `epd` API.

Full rationale: **[docs/implementation_plan.md](docs/implementation_plan.md)**.
