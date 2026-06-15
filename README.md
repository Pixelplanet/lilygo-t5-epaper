# LilyGo T5 4.7" Plus — MicroPython UI Platform

MicroPython project for the [LilyGo T5 4.7" Plus](https://www.lilygo.cc/products/t5-v2-3-1)
e-paper board (ESP32-S3, 960×540 16-level grayscale panel, GT911 capacitive touch,
PCF8563 RTC).

**This project has been tested for multiple days on real hardware.**
Everything in this repo — the UI framework, touch stack, Wi-Fi, calendar, app launcher,
keyboard, and app store — has been verified on-device with repeated full cycles (flash →
deploy → use → reset).

## What's included

- **Touch-optimized UI framework** with e-paper partial refresh (additive/clearing/full).
- **App launcher** with an 8-slot icon grid, clock, and Wi-Fi status.
- **Built-in apps:** Wi-Fi setup (scan, connect, keyboard), trash calendar (ICS parser),
  Tibber electricity prices, help screen, and on-device app store.
- **App store** — install community apps over Wi-Fi from a hosted catalog.
- **OTA system updates** — check for and install platform updates over Wi-Fi without reflashing.
- **Desktop simulator** — develop and test the UI without hardware.
- **Offline web UI Builder** — drag-and-drop editor for `ui.json` (launcher + screens).
- **Full documentation** — custom app development, manual UI building, and flashing guides.

## Quick start

### Simulator (no board required)

```powershell
python -m pip install -r tools/requirements.txt
python sim/run_sim.py
```

### Hardware (tested on V2.3 & V2.4)

1. Put the board in bootloader mode (hold BOOT, tap RST, release BOOT).
2. Flash firmware:

```powershell
./tools/flash.ps1 -Port COM5 -Firmware .\firmware\ESP32_GENERIC_S3-SPIRAM_OCT.bin
```

3. Deploy app files:

```powershell
./tools/deploy.ps1 -Port COM5
```

4. Reset the board.
5. Open the Wi-Fi app → connect → then use the App Store to install community apps.

Detailed flashing notes: [docs/flashing.md](docs/flashing.md)

## Documentation

| Guide | Description |
|---|---|
| [docs/flashing.md](docs/flashing.md) | Flash firmware, deploy apps, first boot. |
| [docs/pinmap.md](docs/pinmap.md) | Pin map and hardware constraints. |
| [docs/custom-apps.md](docs/custom-apps.md) | **Create your own Python apps** — widgets, touch, navigation, RTC, Wi-Fi, catalog publishing. |
| [docs/manual-ui-pages.md](docs/manual-ui-pages.md) | **Build screens without Python** — ui.json schema, all widget types, hooks, coordinate system. |
| [tools/ui-builder.html](tools/ui-builder.html) | **Drag-and-drop UI editor** (open in browser, works offline). |

## Project layout

```text
src/                  Device source (main.py, apps/, lib/, config.py)
sim/                  Desktop simulator (CPython shims, run_sim.py)
tools/                Flash/deploy scripts, offline UI builder, serial monitor
apps-catalog/         Community app catalog index + installable example apps
docs/                 Hardware, flashing, developer guides
tests/                Headless logic tests
firmware/             Build scripts and test helpers for the e-paper driver
```

## Main user flows

- **Home launcher** — icon grid, clock, Wi-Fi status. Tap any tile to open an app.
- **Wi-Fi app** — scan, connect, type password on on-screen keyboard, sync RTC via NTP.
- **Calendar app** — month grid with tappable collection days, day detail view.
- **Prices app** — Tibber electricity prices (requires API token in `secrets.py`).
- **App Store** — browse community catalog, view details, install/uninstall apps.
- **System Update** — check for platform updates over Wi-Fi, download changed files, reset to apply.
- **UI Builder** — edit launcher tiles and screens in your browser, export `ui.json`.
- **Help screen** — on-device quick reference.

## Notes

- Pin and feature flags: [src/config.py](src/config.py)
- Architecture and design decisions: [docs/implementation_plan.md](docs/implementation_plan.md)
- Recovery: hold the BOOT button during reset to skip the app and drop to the REPL.
- **OTA updates:** The Update app checks `update.json` on GitHub, downloads only changed
  files, and writes them to flash. After a successful update, reset the board to run the
  new version. The first deploy (via USB) seeds `version.json` on flash so future updates
  can diff against it.
- To publish an OTA update: bump the version in `update.json`, run `tools/deploy.ps1`
  (which regenerates the manifest with current file hashes), commit & push.
