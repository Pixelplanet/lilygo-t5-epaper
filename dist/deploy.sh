#!/usr/bin/env bash
# deploy.sh - Upload the device/ Python tree to the board's flash (Linux/macOS).
#
#   ./deploy.sh /dev/ttyACM0 [--reset]
#
set -euo pipefail
PORT="${1:?Usage: ./deploy.sh <port> [--reset]}"
DEV="$(dirname "$0")/device"

python3 -m mpremote connect "$PORT" fs mkdir :lib 2>/dev/null || true
python3 -m mpremote connect "$PORT" fs mkdir :lib/ui 2>/dev/null || true
python3 -m mpremote connect "$PORT" fs mkdir :apps 2>/dev/null || true

cd "$DEV"
find . -type f | sed 's|^\./||' | while read -r rel; do
    echo "  -> :$rel"
    python3 -m mpremote connect "$PORT" fs cp "$rel" ":$rel"
done

if [ "${2:-}" = "--reset" ]; then
    echo "Resetting board..."
    python3 -m mpremote connect "$PORT" reset
fi

echo "Deploy complete."
