# appstore.py - on-device app installer (pulls apps from a Wi-Fi catalog).
#
# Fetches a catalog index.json over HTTPS, lists the apps, and installs the
# selected one: downloads its files to flash, appends a launcher tile to
# ui.json, and saves. Requires Wi-Fi (auto-connects via netconn).
#
# Set CATALOG_URL to your hosted apps-catalog/index.json (raw GitHub URL, etc).
import json

from lib import debuglog, netconn
from lib.ui import theme
from lib.ui.core import Screen
from lib.ui.widgets import Button, Label, ListView

CATALOG_URL = "https://raw.githubusercontent.com/Pixelplanet/lilygo-t5-epaper/main/apps-catalog/index.json"
UI_PATH = "ui.json"


def open_store(app):
    return StoreScreen(app)


# --------------------------------------------------------------------------- #
# Minimal HTTPS GET (no urequests dependency)
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
           "User-Agent: lilygo-t5\r\n"
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


def _catalog_base(url):
    # Strip the trailing "index.json" to resolve relative file paths.
    j = url.rfind("/")
    return url[:j + 1] if j >= 0 else url


def _load_ui():
    try:
        with open(UI_PATH) as f:
            return json.load(f)
    except Exception:
        return {"apps": [], "screens": {}}


def _save_ui(cfg):
    import os
    with open(UI_PATH, "w") as f:
        json.dump(cfg, f)
    os.sync()


def _mkdirs(path):
    # Ensure parent dirs of a device path exist (e.g. "apps/foo.py").
    import os
    parts = path.split("/")[:-1]
    cur = ""
    for p in parts:
        cur = cur + "/" + p if cur else p
        try:
            os.mkdir(cur)
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# Screen
# --------------------------------------------------------------------------- #
class StoreScreen(Screen):
    def __init__(self, app):
        super().__init__(app, "App store")
        self.status = None
        self.listv = None
        self.apps = []

    def build(self):
        self.add_back_button()
        d = self.app.display
        self.status = self.add(Label(theme.PAD, theme.TITLE_BAR_H + 12,
                                     "Connecting...", theme.BODY_SCALE,
                                     theme.FG_MUTED))
        self.listv = ListView(theme.PAD, theme.TITLE_BAR_H + 48,
                              d.width - 2 * theme.PAD,
                              d.height - theme.TITLE_BAR_H - 60,
                              [], self._row, self._pick)
        self.add(self.listv)

    async def task(self):
        import asyncio
        self.set_wifi_state("wait")
        await self.app.flush()
        if not await netconn.auto_connect():
            self.set_wifi_state("off")
            self.status.set_text("Wi-Fi needed - connect in Wi-Fi app first")
            await self.app.flush()
            return
        self.set_wifi_state("on")
        self.status.set_text("Loading catalog...")
        await self.app.flush()
        await asyncio.sleep_ms(50)
        try:
            body = _https_get(CATALOG_URL)
            cat = json.loads(body)
            self.apps = cat.get("apps", [])
        except Exception as e:  # noqa: BLE001
            debuglog.log("store: catalog load failed " + str(e))
            self.status.set_text("Could not load catalog - see debug.log")
            await self.app.flush()
            return
        self.status.set_text("Tap an app to install ({} available)".format(
            len(self.apps)))
        self.listv.set_items(self.apps)
        await self.app.flush()

    def _row(self, disp, item, idx, x, y, w, h):
        disp.text(item.get("name", "?"), x + 8, y + 8, theme.FG, theme.BODY_SCALE)
        desc = item.get("description", "")
        if desc:
            disp.text(desc[:46], x + 8, y + 30, theme.FG_MUTED, theme.SMALL_SCALE)

    def _pick(self, idx):
        if 0 <= idx < len(self.apps):
            self.app.go(InstallScreen(self.app, self.apps[idx]))


class InstallScreen(Screen):
    def __init__(self, app, manifest):
        super().__init__(app, "Install")
        self.manifest = manifest
        self.status = None

    def build(self):
        self.add_back_button(self._back)
        self.add(Label(theme.PAD, theme.TITLE_BAR_H + 12,
                       self.manifest.get("name", "App"), theme.H1_SCALE))
        self.status = self.add(Label(theme.PAD, theme.TITLE_BAR_H + 60,
                                     "Installing...", theme.BODY_SCALE,
                                     theme.FG_MUTED))

    async def task(self):
        import asyncio
        await asyncio.sleep_ms(50)
        files = self.manifest.get("files", [])
        base = _catalog_base(CATALOG_URL)
        try:
            for i, f in enumerate(files):
                self.status.set_text("Downloading {}/{}: {}".format(
                    i + 1, len(files), f))
                await self.app.flush()
                data = _https_get(base + f)
                _mkdirs(f)
                with open(f, "wb") as out:
                    out.write(data)
            # Append the launcher tile to ui.json (if not already present).
            cfg = _load_ui()
            apps = cfg.setdefault("apps", [])
            aid = self.manifest.get("id")
            if not any(a.get("id") == aid for a in apps):
                apps.append({
                    "id": aid,
                    "name": self.manifest.get("name", aid),
                    "icon": self.manifest.get("icon", "app"),
                    "kind": "builtin",
                    "entry": self.manifest.get("entry", ""),
                })
            _save_ui(cfg)
        except Exception as e:  # noqa: BLE001
            debuglog.log("store: install failed " + str(e))
            self.status.set_text("Install failed - see debug.log")
            await self.app.flush()
            return
        import os
        os.sync()
        self.status.set_text("Installed! Reset the device to see it.")
        await self.app.flush()

    def _back(self):
        from apps import appstore
        self.app.go(appstore.StoreScreen(self.app))
