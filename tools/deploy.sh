#!/usr/bin/env bash
# deploy.sh - Upload src/ to the board flash root via mpremote.
#   Usage: ./tools/deploy.sh /dev/ttyACM0
set -euo pipefail
PORT="${1:?usage: deploy.sh <port>}"
SRC="$(cd "$(dirname "$0")/../src" && pwd)"

echo "Uploading $SRC -> $PORT :/"
cd "$SRC"
find . -type d ! -path . | sed 's#^\./##' | while read -r d; do
    python -m mpremote connect "$PORT" fs mkdir ":$d" 2>/dev/null || true
done
find . -type f -name '*.py' | sed 's#^\./##' | while read -r f; do
    echo "  + $f"
    python -m mpremote connect "$PORT" fs cp "$f" ":$f"
done
echo "Done. Reset the board to run main.py."
