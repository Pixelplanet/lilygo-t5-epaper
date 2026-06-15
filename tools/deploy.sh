#!/usr/bin/env bash
# deploy.sh - Upload src/ to the board flash root via mpremote.
# Also generates version.json with SHA-256 hashes for OTA update support.
#   Usage: ./tools/deploy.sh /dev/ttyACM0
set -euo pipefail
PORT="${1:?usage: deploy.sh <port>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/src"
VERSION_FILE="$ROOT/version.json"
UPDATE_FILE="$ROOT/update.json"

echo "Uploading $SRC -> $PORT :/"
cd "$SRC"

# Collect files once.
FILES=$(find . -type f -name '*.py' | sed 's#^\./##' | sort)

# Upload files individually (bash on Linux/macOS, one session per file).
echo "$FILES" | while read -r f; do
    echo "  + $f"
    python -m mpremote connect "$PORT" fs cp "$f" ":$f"
done

# --- Generate version.json with SHA-256 hashes ---
echo ""
echo "Generating version.json..."

python3 -c "
import json, hashlib, os, sys

src = sys.argv[1]
files = sys.argv[2].splitlines()
hashes = {}
for f in files:
    if not f: continue
    path = os.path.join(src, f)
    with open(path, 'rb') as fh:
        hashes[f] = hashlib.sha256(fh.read()).hexdigest()

# Read remote version.
remote_ver = 0
update_file = sys.argv[3]
desc = 'Update from deploy'
if os.path.exists(update_file):
    with open(update_file) as fh:
        r = json.load(fh)
        remote_ver = r.get('version', 0)
        desc = r.get('description', desc)

# Write local version.json.
ver = {'version': remote_ver, 'files': hashes}
with open(sys.argv[4], 'w') as fh:
    json.dump(ver, fh, indent=2)
print(f'  Wrote version.json (v{remote_ver}, {len(hashes)} files)')

# Also write update.json for GitHub.
update = {'version': remote_ver, 'description': desc, 'files': hashes}
with open(update_file, 'w') as fh:
    json.dump(update, fh, indent=2)
print(f'  Updated {update_file} for GitHub upload')
print('  -> Commit & push update.json to publish the OTA update')
" "$SRC" "$FILES" "$UPDATE_FILE" "$VERSION_FILE"

# Upload version.json to device.
echo ""
echo "Uploading version.json to device..."
python -m mpremote connect "$PORT" fs cp "$VERSION_FILE" ":version.json" || \
    echo "WARNING: version.json upload failed (OTA won't work until next deploy)"

echo ""
echo "Done. Reset the board to run main.py."

