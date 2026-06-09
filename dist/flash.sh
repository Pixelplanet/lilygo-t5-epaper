#!/usr/bin/env bash
# flash.sh - One-shot firmware flasher for the LilyGo T5 4.7" Plus (Linux/macOS).
#
#   ./flash.sh /dev/ttyACM0
#
# Erases the chip and writes firmware-epd.bin at offset 0x0.
set -euo pipefail
PORT="${1:?Usage: ./flash.sh <port> [firmware.bin]}"
FW="${2:-$(dirname "$0")/firmware-epd.bin}"

[ -f "$FW" ] || { echo "Firmware not found: $FW" >&2; exit 1; }

echo "Erasing flash on $PORT ..."
python3 -m esptool --chip esp32s3 --port "$PORT" erase_flash

echo "Writing $FW to $PORT ..."
python3 -m esptool --chip esp32s3 --port "$PORT" --baud 460800 write_flash 0x0 "$FW"

echo "Done. Tap RST on the board, then deploy the app with deploy.sh."
