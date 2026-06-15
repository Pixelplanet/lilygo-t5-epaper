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


def _path_exists(path):
    try:
        with open(path, "rb"):
            return True
    except Exception:
        return False


def _is_installed(manifest, cfg=None):
    if cfg is None:
        cfg = _load_ui()
    aid = manifest.get("id")
    if not aid:
        return False
    apps = cfg.get("apps", [])
    if not any(a.get("id") == aid for a in apps):
        return False
    for f in manifest.get("files", []):
        if not _path_exists(f):
            return False
    return True


def _upsert_launcher_tile(cfg, manifest):
    apps = cfg.setdefault("apps", [])
    aid = manifest.get("id")
    entry = {
        "id": aid,
        "name": manifest.get("name", aid),
        "icon": manifest.get("icon", "app"),
        "kind": "builtin",
        "entry": manifest.get("entry", ""),
    }
    for i, a in enumerate(apps):
        if a.get("id") == aid:
            apps[i] = entry
            return
    apps.append(entry)


def _remove_launcher_tile(cfg, app_id):
    apps = cfg.setdefault("apps", [])
    cfg["apps"] = [a for a in apps if a.get("id") != app_id]


def _delete_file(path):
    import os
    try:
        os.remove(path)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Screen
# --------------------------------------------------------------------------- #
class StoreScreen(Screen):
    def __init__(self, app):
        super().__init__(app, "App store")
        self.status = None
        self.listv = None
        self.apps = []
        self.installed_ids = set()

    def build(self):
        self.add_back_button()
        d = self.app.display
        self.status = self.add(Label(theme.PAD, theme.TITLE_BAR_H + 12,
                                     "Connecting...", theme.BODY_SCALE,
                                     theme.FG_MUTED))
        self.listv = ListView(theme.PAD, theme.TITLE_BAR_H + 48,
                              d.width - 2 * theme.PAD,
                              d.height - theme.TITLE_BAR_H - 60,
                      [], self._row, self._pick, row_h=84)
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
            cfg = _load_ui()
            self.installed_ids = set(
                a.get("id") for a in self.apps if _is_installed(a, cfg)
            )
        except Exception as e:  # noqa: BLE001
            debuglog.log("store: catalog load failed " + str(e))
            self.status.set_text("Could not load catalog - see debug.log")
            await self.app.flush()
            return
        self.status.set_text("Tap an app to view details ({} available)".format(
            len(self.apps)))
        self.listv.set_items(self.apps)
        await self.app.flush()

    def _row(self, disp, item, idx, x, y, w, h):
        installed = item.get("id") in self.installed_ids
        disp.rounded_rect(x + 4, y + 6, w - 12, h - 12, theme.SURFACE,
                          r=10, fill=True)
        disp.rounded_rect(x + 4, y + 6, w - 12, h - 12, theme.FG, r=10)
        disp.text(item.get("name", "?"), x + 14, y + 16, theme.FG,
                  theme.BODY_SCALE)
        meta = "Installed" if installed else "Not installed"
        disp.text(meta, x + 14, y + 44,
                  theme.ACCENT if installed else theme.FG_MUTED,
                  theme.SMALL_SCALE)
        author = item.get("author", "unknown")
        disp.text("by " + author, x + w - 130, y + 44, theme.FG_MUTED,
                  theme.SMALL_SCALE)

    def _pick(self, idx):
        if 0 <= idx < len(self.apps):
            self.app.go(AppDetailsScreen(self.app, self.apps[idx]))


class AppDetailsScreen(Screen):
    def __init__(self, app, manifest):
        super().__init__(app, "App details")
        self.manifest = manifest
        self.status = None
        self.action_btn = None
        self._busy = False
        self._installed = False

    def build(self):
        self.add_back_button(self._back)
        self._installed = _is_installed(self.manifest)
        name = self.manifest.get("name", "App")
        author = self.manifest.get("author", "unknown")
        desc = self.manifest.get("description", "")
        files = self.manifest.get("files", [])

        self.add(Label(theme.PAD, theme.TITLE_BAR_H + 12,
                       name, theme.H1_SCALE))
        self.add(Label(theme.PAD, theme.TITLE_BAR_H + 54,
                       "Author: " + author, theme.BODY_SCALE,
                       theme.FG_MUTED))
        self.add(Label(theme.PAD, theme.TITLE_BAR_H + 84,
                       "Files: {}".format(len(files)), theme.BODY_SCALE,
                       theme.FG_MUTED))
        if desc:
            self.add(Label(theme.PAD, theme.TITLE_BAR_H + 124,
                           desc[:56], theme.BODY_SCALE))
            if len(desc) > 56:
                self.add(Label(theme.PAD, theme.TITLE_BAR_H + 152,
                               desc[56:112], theme.BODY_SCALE,
                               theme.FG_MUTED))

        self.action_btn = self.add(Button(
            theme.PAD,
            self.app.display.height - 142,
            self.app.display.width - 2 * theme.PAD,
            64,
            "Install",
            self._start_action,
            theme.H1_SCALE,
        ))

        self.status = self.add(Label(theme.PAD, self.app.display.height - 70,
                                     "", theme.BODY_SCALE,
                                     theme.FG_MUTED))
        self._sync_action_ui()

    async def task(self):
        await self.app.flush()

    def _sync_action_ui(self):
        if self.action_btn is not None:
            self.action_btn.text = "Uninstall" if self._installed else "Install"
            self.action_btn.invalidate()
        self.status.set_text("Installed" if self._installed else "Not installed")

    def _start_action(self):
        if self._busy:
            return
        import asyncio
        self._busy = True
        self.action_btn.text = "Working..."
        self.action_btn.invalidate()
        asyncio.create_task(self._run_action())

    async def _run_action(self):
        import os
        import asyncio

        files = self.manifest.get("files", [])
        base = _catalog_base(CATALOG_URL)
        try:
            cfg = _load_ui()
            if self._installed:
                # Uninstall: remove launcher tile and delete listed app files.
                self.status.set_text("Removing app...")
                await self.app.flush()
                _remove_launcher_tile(cfg, self.manifest.get("id"))
                for i, f in enumerate(files):
                    self.status.set_text("Removing {}/{}: {}".format(
                        i + 1, len(files), f))
                    await self.app.flush()
                    _delete_file(f)
                    await asyncio.sleep_ms(10)
                _save_ui(cfg)
                os.sync()
                self.status.set_text("Uninstalled. Reset to refresh launcher.")
            else:
                # Install: download files and add/update launcher tile.
                for i, f in enumerate(files):
                    self.status.set_text("Downloading {}/{}: {}".format(
                        i + 1, len(files), f))
                    await self.app.flush()
                    data = _https_get(base + f)
                    _mkdirs(f)
                    with open(f, "wb") as out:
                        out.write(data)
                _upsert_launcher_tile(cfg, self.manifest)
                _save_ui(cfg)
                os.sync()
                self.status.set_text("Installed. Reset to refresh launcher.")

            self._installed = _is_installed(self.manifest)
            self._sync_action_ui()
            await self.app.flush()
            return

        except Exception as e:  # noqa: BLE001
            debuglog.log("store: action failed " + str(e))
            self.status.set_text("Action failed - see debug.log")
            await self.app.flush()
        finally:
            self._busy = False

    def _back(self):
        from apps import appstore
        self.app.go(appstore.StoreScreen(self.app))
