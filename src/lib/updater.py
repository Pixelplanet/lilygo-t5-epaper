# updater.py — Over-the-air (OTA) update engine.
#
# Fetches a remote update manifest (update.json) over HTTPS, compares file
# hashes against the local version.json, downloads only changed files, and
# writes them to flash. After a successful update the user can reset to run
# the new code.
#
# The manifest includes a "commit" field (SHA of the git commit that generated
# it).  File downloads use the commit-specific URL to bypass GitHub's CDN
# cache, guaranteeing the file content matches the recorded hash.
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

# Commit that matches the hashes in update.json — set by gen_hashes.py.
# All fetches use this commit-specific URL to bypass CDN caching entirely.
PINNED_COMMIT = "094c0f94c2e117d0c6b879ca40300e918165db4f"

def _sha256_hex(data):
    """Return lowercase hex SHA-256 digest of a bytes or string."""
    if isinstance(data, str):
        data = data.encode()
    h = hashlib.sha256()
    h.update(data)
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
    parts = path.split("/")[:-1]
    cur = ""
    for p in parts:
        cur = cur + "/" + p if cur else p
        try:
            os.mkdir(cur)
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# Minimal HTTPS GET
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


def _https_get(url, timeout=30):
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
           "Cache-Control: no-cache\r\n"
           "Pragma: no-cache\r\n"
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


async def check(update_url=UPDATE_URL):
    """Fetch the remote update manifest and return changed files if any.

    Uses the pinned commit URL to completely bypass GitHub's CDN cache.
    """
    commit_url = update_url.replace("/master/", "/" + PINNED_COMMIT + "/")
    body = _https_get(commit_url)
    remote = json.loads(body)
    return _build_pending(remote)


def _build_pending(remote):
    """Build the pending-update dict from a parsed remote manifest."""
    remote_version = remote.get("version", 0)
    remote_files = remote.get("files", {})
    description = remote.get("description", "")
    commit = remote.get("commit", None)

    local_ver, local_files = local_version()

    if remote_version <= local_ver:
        return None

    changed = {}
    for path, rhash in remote_files.items():
        if local_files.get(path) != rhash:
            changed[path] = rhash

    if not changed:
        return None

    return {
        "version": remote_version,
        "description": description,
        "files": changed,
        "commit": commit,
    }


async def download_updates(pending, base_url=SRC_BASE, on_progress=None):
    """Download each changed file to flash and update version.json."""
    import asyncio
    import time

    # Use pinned commit URL so file content matches recorded hashes exactly.
    base_url = base_url.replace("/master/", "/" + PINNED_COMMIT + "/")

    files = pending["files"]
    total = len(files)
    done = 0
    ok = 0

    for path, expected_hash in files.items():
        url = base_url + path
        body = None
        for attempt in range(2):
            try:
                body = _https_get(url + "?t=" + str(int(time.time())))
                break
            except Exception:
                if attempt == 0:
                    await asyncio.sleep_ms(2000)
                    continue
                if on_progress:
                    on_progress(path, done, total)
                raise

        actual = _sha256_hex(body)
        if actual != expected_hash:
            if on_progress:
                on_progress(path, done, total)
            raise ValueError("hash mismatch: " + path.split("/")[-1])

        _mkdirs(path)
        tmp = path + ".tmp"
        try:
            with open(tmp, "wb") as f:
                f.write(body)
            os.sync()
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

    _, tracked = local_version()
    new_files = {}
    for path in files:
        new_files[path] = files[path]
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
