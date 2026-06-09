#!/usr/bin/env bash
# flash.sh - Erase the ESP32-S3 and write mainline MicroPython (SPIRAM_OCT build).
#   Usage: ./tools/flash.sh /dev/ttyACM0 ./firmware/ESP32_GENERIC_S3-SPIRAM_OCT.bin
set -euo pipefail
PORT="${1:?usage: flash.sh <port> <firmware.bin>}"
FW="${2:?usage: flash.sh <port> <firmware.bin>}"
[ -f "$FW" ] || { echo "Firmware not found: $FW" >&2; exit 1; }

echo "Erasing flash on $PORT ..."
python -m esptool --chip esp32s3 --port "$PORT" erase_flash
echo "Writing $FW at 0x0 ..."
python -m esptool --chip esp32s3 --port "$PORT" --baud 921600 write_flash -z 0x0 "$FW"
echo "Done. Now run: ./tools/deploy.sh $PORT"
