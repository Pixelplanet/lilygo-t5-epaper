# Pin map — LilyGo T5 4.7" Plus (ESP32-S3-WROOM-1-N16R8)

Encoded in [`src/config.py`](../src/config.py). Source: research blueprint section 3.

| ESP32-S3 | Function | Notes / conflicts |
|---|---|---|
| GPIO13 | 74HCT4094D CFG_DATA (shift data) | display engine (SPI MOSI in bypass) |
| GPIO12 | 74HCT4094D CFG_CLK (shift clock) | display engine (SPI SCK in bypass) |
| GPIO0  | 74HCT4094D CFG_STR (strobe) | display engine; also boot strap |
| GPIO38 | E-Paper CKV (gate clock) | dedicated parallel line |
| GPIO40 | E-Paper STH (source start) | dedicated parallel line |
| GPIO41 | E-Paper CKH (source clock) | dedicated parallel line |
| GPIO8,1,2,3,4,5,6,7 | E-Paper data D0–D7 | dedicated 8-bit bus |
| GPIO18 | I²C SDA | shared: GT911 touch + PCF8563 RTC (pulled to 3V3) |
| GPIO17 | I²C SCL | shared: GT911 touch + PCF8563 RTC (pulled to 3V3) |
| GPIO47 | Touch INT / IRQ (active-low) | NOT RTC-capable (see deep-sleep note) |
| GPIO21 | Onboard BOOT/User button | tactile |
| GPIO14 | Battery voltage ADC | **ADC2 — conflicts with active Wi-Fi** |
| GPIO16 | TF card MISO | SPI storage |
| GPIO15 | TF card MOSI | SPI storage |
| GPIO11 | TF card SCK | SPI storage |
| GPIO42 | TF card CS | SPI storage |
| GPIO10,39,45,48 | Free / unrouted | available for expansion |

## Critical constraints baked into the code

- **Battery ADC (GPIO14 / ADC2)** — reading while Wi-Fi is active fails or browns out.
  `lib/battery.py` refuses to sample when the WLAN radio is up; the Wi-Fi flow samples the
  battery *before* enabling the radio.
- **Touch address floats 0x14 / 0x5D** — `lib/gt911.py` probes both at startup.
- **GT911 status reg 0x814E** — must be written back to `0x00` after every read.
- **Touch-to-wake** — GPIO47 is not RTC-capable. To wake from deep sleep on touch, solder a
  bridge **GPIO10 → GPIO47**, then set `TOUCH_WAKE_BRIDGE = True` in `config.py`.

## Touch orientation calibration

The GT911 reports portrait `540×960`. The UI runs landscape `960×540`. If touches land in the
wrong place during bring-up (step 5), flip the booleans in `config.py`:
`TOUCH_SWAP_XY`, `TOUCH_FLIP_X`, `TOUCH_FLIP_Y`.
