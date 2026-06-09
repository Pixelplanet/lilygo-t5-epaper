# Troubleshooting & debugging

Practical fixes for the problems you're most likely to hit, plus how to use the
on-device log to diagnose anything else.

## Find the ports

This board exposes more than one serial port. On Windows, open **Device Manager →
Ports (COM & LPT)**; on Linux/macOS run `ls /dev/ttyACM* /dev/ttyUSB*`.

| Port (typical) | What it is | Used for |
|----------------|------------|----------|
| **COM5** (varies) | Native USB-CDC of the running app | `mpremote` deploy, REPL, reset |
| **COM7** (varies) | ROM/USB-JTAG download port | `esptool` firmware flashing |
| COM3 (varies) | Bluetooth, if present | ignore |

The numbers differ per machine and **change after flashing** (the app re-enumerates
as a new port). Always re-check which port is which after a flash.

## The recovery escape hatch (you can't brick the app)

`main.py` auto-runs at power-on but always gives you ~2 seconds to break in:

- **Hold the BOOT button (GPIO21) during reset** → the app is skipped and you land
  in the REPL.
- **Or press Ctrl-C** in the startup window (while connected to the REPL).

If the app ever crashes it also prints the traceback and drops to the REPL instead
of locking up. So a bad edit can never lock you out — reconnect, fix, redeploy.

## On-device debug log (the reliable probe)

Capturing `print()` output over the native USB-CDC port is **unreliable** on this
board (the CDC link drops during heavy display/Wi-Fi work). The dependable probe
is the on-device file log:

- [`device/lib/debuglog.py`](../device/lib/debuglog.py) appends to `debug.log` on
  flash and `os.sync()`s each line, so **entries survive a reset/brownout**.
- It is **append-only** and is *not* cleared at boot — each boot writes a
  `==== boot reset_cause=<n>` line, so a reset during an operation is visible in
  the history (you'll see the boot line appear mid-sequence).

Read it back after testing:

```powershell
python -m mpremote connect COM5 fs cat :debug.log
```

Clear it when it gets noisy:

```powershell
python -m mpremote connect COM5 exec "from lib import debuglog; debuglog.clear()"
```

Add your own markers anywhere:

```python
from lib import debuglog
debuglog.log("myscreen: got here x=" + str(x))
```

### Reading `reset_cause`

`machine.reset_cause()` values you'll see most:

| Value | Meaning |
|-------|---------|
| `1` | Power-on reset (cold boot) |
| `2` | Hard reset (RST / `mpremote reset`) — **normal** |
| `3` | Soft reset (Ctrl-D / `mpremote exec`) — **normal**, not a crash |
| `4` | Watchdog |
| `5` | Deep-sleep wake |
| brownout | A power dip (e.g. a current spike) reset the chip |

If you suspect an operation resets the board, look for an **extra boot line in the
middle** of your log sequence. If there's no extra boot line and your code's log
markers just stop, it's a hang/exception, not a reset — and the *last* marker tells
you exactly which line was reached.

> Real example from this project: "connecting with the correct Wi-Fi password did
> nothing." The log showed no `connect: start` marker and **no** extra boot line —
> proving the board never reset and the connect routine was never even reached. The
> real cause was a missing UI trigger, not the suspected brownout. The log settled
> it in one test.

## Common problems

### Board boot-loops or kernel-panics right after flashing
You flashed the wrong PSRAM variant. This module (N16R8) has **Octal** PSRAM. The
shipped `firmware-epd.bin` is built correctly; if you build your own, use the
`SPIRAM_OCT` variant. A quad-SPIRAM build will not map the 8 MB PSRAM and panics.

### `esptool` can't connect / times out
- Put the board in **download mode**: hold **BOOT**, tap **RST**, release **BOOT**.
- Use the **ROM/download port** (often COM7), not the app port.
- Close anything holding the port (`Get-Process python | Stop-Process -Force`).

### `mpremote` says the port is busy / access denied
A previous `python`/`mpremote` still holds it. Kill it first:
```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force; Start-Sleep 2
```

### Nothing reaches the screen / "no `epd` backend - draw-only mode"
The firmware doesn't expose the native `epd` module (e.g. you flashed plain
mainline MicroPython instead of `firmware-epd.bin`). Flash `firmware-epd.bin`. The
UI still runs headless in draw-only mode, which is fine for REPL/touch bring-up.

### Touch is mirrored, rotated, or offset
Adjust the `TOUCH_*` flags in [`device/config.py`](../device/config.py):
`TOUCH_SWAP_XY`, `TOUCH_FLIP_X`, `TOUCH_FLIP_Y`. The values there are calibrated
for V2.4 hardware; a different revision may need different flips.

### The screen has faint vertical lines / ghosting
That's accumulated partial-refresh residue. Press **Refresh** (FULL refresh) or
**Repair** (charge-neutralization sweep) on the home screen. See
[screen-refresh.md](screen-refresh.md) for why and how to avoid it in new screens.

### The clock is off by a few hours
Set your timezone in [`device/config.py`](../device/config.py):
`TZ_OFFSET_HOURS` (e.g. `1` = CET, `2` = CEST). The clock syncs over NTP after a
Wi-Fi connect.

### Wi-Fi connects but the device "forgets" the network
Credentials are saved by [`device/lib/wifistore.py`](../device/lib/wifistore.py)
to `wifi.json` only **after a successful connect**. If the Reconnect button never
appears, the connect never fully succeeded — check `debug.log` for `creds saved`.
