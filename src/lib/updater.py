# updater.py — Over-the-air (OTA) update engine.
#
# Fetches a remote update manifest (update.json) over HTTPS, compares file
# hashes against the local version.json, downloads only changed files, and
# writes them to flash. After a successful update the user can reset to run
# the new code.
#
# Usage from an app:
#     from lib.updater import check, download_updates
#     pending = await check(UPDATE_URL)
#     if pending:
#         await download_updates(pending)
#
# The device needs Wi-Fi and enough free flash space for the largest updated
# file (downloaded whole, then atomically replaced).
import json
import os

try:
    import uhashlib as hashlib
    import ubinascii as binascii
except ImportError:
    import hashlib
    import binascii

VERSION_PATH = "version.json"
UPDATE_URL = "https://raw.githubusercontent.com/Pixelplanet/lilygo-t5-epaper/master/update.json"
SRC_BASE = "https://raw.githubusercontent.com/Pixelplanet/lilygo-t5-epaper/master/src/"


def _sha256_hex(data):
    """Return lowercase hex SHA-256 digest of a bytes or string."""
    if isinstance(data, str):
        data = data.encode()
    h = hashlib.sha256(data)
    # MicroPython uhashlib returns .digest() -> bytes; CPython has .hexdigest() -> str.
    # Use ubinascii.hexlify for portability.
    try:
        return h.hexdigest()
    except AttributeError:
        return binascii.hexlify(h.digest()).decode()


def _file_sha256(path):
    """SHA-256 hex digest of a file on flash, or None if missing."""
    try:
        with open(path, "rb") as f:
            return _sha256_hex(f.read())
    except Exception:
        return None


def _load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def _save_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f)
    os.sync()


def _mkdirs(path):
    """Ensure parent directories exist for a file path."""
    parts = path.split("/")[:-1]
    cur = ""
    for p in parts:
        cur = cur + "/" + p if cur else p
        try:
            os.mkdir(cur)
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# Minimal HTTPS GET (same pattern as appstore.py, avoids urequests dep)
# --------------------------------------------------------------------------- #
def _split_url(url):
    if url.startswith("https://"):
        url = url[8:]
    elif url.startswith("http://"):
        url = url[7:]
    slash = url.find("/")
    host = url[:slash] if slash >= 0 else url
    path = url[slash:] if slash >= 0 else "/"
    return host, path


def _dechunk(body):
    out = b""
    while body:
        j = body.find(b"\r\n")
        if j < 0:
            break
        try:
            size = int(body[:j], 16)
        except ValueError:
            break
        if size == 0:
            break
        start = j + 2
        out += body[start:start + size]
        body = body[start + size + 2:]
    return out


def _https_get(url, timeout=15):
    import socket
    import ssl
    host, path = _split_url(url)
    addr = socket.getaddrinfo(host, 443)[0][-1]
    s = socket.socket()
    s.settimeout(timeout)
    s.connect(addr)
    s = ssl.wrap_socket(s, server_hostname=host)
    req = ("GET " + path + " HTTP/1.1\r\n"
           "Host: " + host + "\r\n"
           "User-Agent: lilygo-t5-updater\r\n"
           "Connection: close\r\n\r\n")
    s.write(req.encode())
    chunks = []
    while True:
        try:
            d = s.read(512)
        except Exception:
            break
        if not d:
            break
        chunks.append(d)
    try:
        s.close()
    except Exception:
        pass
    raw = b"".join(chunks)
    i = raw.find(b"\r\n\r\n")
    if i < 0:
        raise ValueError("bad HTTP response")
    head, body = raw[:i], raw[i + 4:]
    if b"chunked" in head or b"Chunked" in head:
        body = _dechunk(body)
    return body


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def local_version():
    """Return (version_number, {path: sha256_hex, ...}) from version.json."""
    v = _load_json(VERSION_PATH, {"version": 0, "files": {}})
    return v.get("version", 0), v.get("files", {})


def local_file_hashes():
    """Compute SHA-256 hashes of all tracked files on flash. Used to generate
    version.json after a successful update or initial deploy."""
    _, tracked = local_version()
    result = {}
    for path in tracked:
        h = _file_sha256(path)
        if h:
            result[path] = h
    return result


async def check(update_url=UPDATE_URL):
    """Fetch the remote update manifest and return a dict of files that differ.

    Returns:
        None — no updates available or already up-to-date.
        {"version": N, "description": "...", "files": {"main.py": "sha256", ...}}
          — dict of changed files (path -> expected hash).
    Raises:
        OSError, ValueError, etc. on network / parse failures.
    """
    import asyncio

    body = _https_get(update_url)
    remote = json.loads(body)

    remote_version = remote.get("version", 0)
    remote_files = remote.get("files", {})
    description = remote.get("description", "")

    local_ver, local_files = local_version()

    if remote_version <= local_ver:
        return None  # already current

    # Find files that differ (or are new).
    changed = {}
    for path, rhash in remote_files.items():
        lhash = local_files.get(path)
        if lhash != rhash:
            changed[path] = rhash

    if not changed:
        return None

    return {
        "version": remote_version,
        "description": description,
        "files": changed,
    }


async def download_updates(pending, base_url=SRC_BASE,
                           on_progress=None):
    """Download each file in `pending["files"]` to flash and update version.json.

    `pending` is the dict returned by check().
    `on_progress(path, done, total)` is called after each file download.
    Returns the number of files successfully downloaded.
    """
    import asyncio

    files = pending["files"]
    total = len(files)
    done = 0
    ok = 0

    for path, expected_hash in files.items():
        url = base_url + path
        try:
            body = _https_get(url)
        except Exception as e:  # noqa: BLE001
            if on_progress:
                on_progress(path, done, total)
            raise

        # Verify hash before writing.
        actual = _sha256_hex(body)
        if actual != expected_hash:
            if on_progress:
                on_progress(path, done, total)
            raise ValueError(
                "hash mismatch for {}: expected {} got {}".format(
                    path, expected_hash[:12], actual[:12]))

        _mkdirs(path)
        # Write to a temp file first, then atomically rename so a power loss
        # mid-write doesn't leave a half-written file.
        tmp = path + ".tmp"
        try:
            with open(tmp, "wb") as f:
                f.write(body)
            os.sync()
            # MicroPython's os.rename is atomic on littlefs.
            os.rename(tmp, path)
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass

        done += 1
        ok += 1
        if on_progress:
            on_progress(path, done, total)

    # Update local version.json to match what we just wrote.
    _, tracked = local_version()
    new_files = {}
    for path in files:
        new_files[path] = files[path]
    # Keep hashes of unchanged tracked files that we didn't download.
    for path, h in tracked.items():
        if path not in new_files:
            new_files[path] = h

    _save_json(VERSION_PATH, {
        "version": pending["version"],
        "files": new_files,
    })

    return ok


def do_reset():
    """Trigger a soft reset to run the newly updated code."""
    import machine
    import time
    time.sleep_ms(500)
    machine.reset()
