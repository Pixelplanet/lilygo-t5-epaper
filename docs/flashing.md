# Flashing & deploying (do this when the board arrives)

## 0. Host prerequisites

```powershell
python -m pip install -r tools/requirements.txt
```

## 1. Get the right firmware

Download **mainline MicroPython** for the ESP32-S3, **SPIRAM_OCT** variant:

- https://micropython.org/download/ESP32_GENERIC_S3/ → pick the build whose name contains
  **`SPIRAM_OCT`** (Octal PSRAM).

> ⚠️ The N16R8 module has **Octal** PSRAM. A standard quad-SPIRAM build will not map the 8 MB
> PSRAM and the board will kernel-panic / boot-loop. This is the single most common bring-up
> mistake on this board.

Put the `.bin` somewhere like `firmware/ESP32_GENERIC_S3-SPIRAM_OCT.bin`.

## 2. Put the board into download mode

1. Hold **BOOT**, tap **RST**, release **BOOT** (V2.3 boards especially need this on USB power).
2. Find the serial port: Device Manager (Windows, e.g. `COM5`) or `ls /dev/ttyACM*` (Linux).

## 3. Flash the firmware

```powershell
./tools/flash.ps1 -Port COM5 -Firmware .\firmware\ESP32_GENERIC_S3-SPIRAM_OCT.bin
```
```bash
./tools/flash.sh /dev/ttyACM0 ./firmware/ESP32_GENERIC_S3-SPIRAM_OCT.bin
```

This runs `erase_flash` then writes the image at offset `0x0`.

## 4. Upload the application

```powershell
./tools/deploy.ps1 -Port COM5
```
```bash
./tools/deploy.sh /dev/ttyACM0
```

This copies the whole `src/` tree (`main.py`, `config.py`, `lib/`, `apps/`) to the flash root.

## 5. About the e-paper driver (`epd` module)

The pure-Python layer in this repo drives **touch, I²C, RTC, battery, power and the entire UI**.
The ED047TC1 *parallel pixel* path needs a native `epd` module. Two options:

- **Option A (recommended for the display):** flash the **LilyGo C-driver firmware** instead of
  mainline; it ships the `epd` / `framebuf_plus` modules. Build it per research-doc section 4:
  ```bash
  git clone --recursive https://github.com/Xinyuan-LilyGO/lilygo-micropython
  cd lilygo-micropython
  cp config_T5-4.7-Plus config
  make            # remove ninja-build first if you hit the Ninja subsystem error
  ```
  Then upload `src/` the same way. `lib/display.py` auto-detects the `epd` module.
- **Option B (mainline):** the UI still runs and all drawing happens in the framebuffer, but
  nothing reaches the panel until a native parallel driver is present. `lib/display.py` prints
  `no 'epd' backend - draw-only mode` and continues, which is fine for REPL/touch bring-up.

> When the real `epd` API differs from the assumed names, edit **only** the `# === HW BINDING ===`
> block (`_Backend`) in [`src/lib/display.py`](../src/lib/display.py).

## 6. Bring-up checklist

1. `python -m mpremote connect COM5 repl` → `import config` then `from lib.board import Board`.
2. `apps/touch_test.py` route in the app → verify the dot tracks your finger.
3. If touch is mirrored/rotated, flip `TOUCH_*` flags in `config.py`.
4. Run the Wi-Fi demo, connect to a real AP.
5. (Optional) solder GPIO10→GPIO47 and set `TOUCH_WAKE_BRIDGE = True` for touch-wake.
