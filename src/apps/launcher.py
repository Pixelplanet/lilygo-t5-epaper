# launcher.py - icon-grid home screen driven by the UI config (ui.json).
#
# Apps are declared in ui.json under "apps". Each entry is one of:
#   builtin: {"id","name","icon","kind":"builtin","entry":"module:callable"}
#            -> imports apps.<module> and calls callable(app) to get a Screen
#               (or a Screen subclass, which is instantiated with (app)).
#   screen:  {"id","name","icon","kind":"screen","screen":"<screen-id>"}
#            -> opens the declarative ConfigScreen with that id.
#
# If ui.json is missing, a sensible default registry (the built-in demos) is
# used so the device still boots into a usable launcher.
from lib import netconn
from lib.ui import declarative, icons, theme
from lib.ui.core import DOWN, UP, Screen, Widget

DEFAULT_APPS = [
    {"id": "trash", "name": "Calendar", "icon": "calendar", "slot": 0,
     "kind": "builtin", "entry": "calendar_app:open_calendar"},
    {"id": "prices", "name": "Prices", "icon": "bolt", "slot": 1,
     "kind": "builtin", "entry": "tibber_app:open_prices"},
    {"id": "store", "name": "Apps", "icon": "gear", "slot": 2,
     "kind": "builtin", "entry": "appstore:open_store"},
    # Bottom row: Update | Wi-Fi | Help (rightmost).
    {"id": "update", "name": "Update", "icon": "gear", "slot": 5,
     "kind": "builtin", "entry": "update_app:open_updater"},
    {"id": "wifi", "name": "Wi-Fi", "icon": "wifi", "slot": 6,
     "kind": "builtin", "entry": "wifi_demo:HomeScreen"},
    {"id": "help", "name": "Help", "icon": "help", "slot": 7,
     "kind": "builtin", "entry": "help:open_help"},
]

# Home grid: 4 columns x 2 rows = 8 slots (index 0..7, row-major).
GRID_COLS = 4
GRID_ROWS = 2
GRID_SLOTS = GRID_COLS * GRID_ROWS


def _trim(text, max_len):
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "~"


def build_app(app):
    return LauncherScreen(app)


def _open_app(app, entry):
    """Resolve an app registry entry to a Screen and navigate to it."""
    kind = entry.get("kind", "builtin")
    if kind == "screen":
        app.go(declarative.ConfigScreen(app, entry.get("screen", ""),
                                        app._ui_config))
        return
    spec = entry.get("entry", "")
    if ":" not in spec:
        return
    mod_name, attr = spec.split(":", 1)
    try:
        mod = __import__("apps." + mod_name, None, None, (mod_name,))
        fn = getattr(mod, attr)
    except Exception as e:  # noqa: BLE001
        from lib import debuglog
        debuglog.log("launcher: cannot open " + spec + " " + str(e))
        return
    res = fn(app)
    # fn may return a Screen instance, or be a Screen class needing (app).
    if isinstance(res, Screen):
        app.go(res)
    else:
        try:
            app.go(res(app))
        except Exception:
            pass


class AppTile(Widget):
    """One icon + label cell in the launcher grid."""

    def __init__(self, x, y, w, h, entry, on_open):
        super().__init__(x, y, w, h)
        self.entry = entry
        self.on_open = on_open
        self._pressed = False

    def draw(self, disp):
        # Card.
        face = theme.FG_MUTED if self._pressed else theme.SURFACE
        disp.rounded_rect(self.x, self.y, self.w, self.h, face, r=14, fill=True)
        disp.rounded_rect(self.x, self.y, self.w, self.h, theme.FG, r=14)
        # Large icon centered in the upper area for visibility.
        isize = int(self.w * 0.46)
        ix = self.x + (self.w - isize) // 2
        iy = self.y + (self.h - isize) // 2 - 16
        icons.draw(disp, self.entry.get("icon", "app"), ix, iy, isize)
        # Label centered near the bottom.
        name = self.entry.get("name", "App")
        if self.entry.get("id") == "wifi":
            ssid = netconn.connected_ssid()
            if ssid:
                name = _trim(ssid, 12)
        tw = len(name) * 8 * theme.BODY_SCALE
        disp.text(name, self.x + (self.w - tw) // 2,
                  self.y + self.h - 8 * theme.BODY_SCALE - 14,
                  theme.FG, theme.BODY_SCALE)

    def handle(self, ev):
        if ev.type == DOWN and self.contains(ev):
            self._pressed = True
            self.invalidate(fast=True)
            return True
        if ev.type == UP:
            if self._pressed:
                self._pressed = False
                self.invalidate()
                if self.contains(ev) and self.on_open:
                    self.on_open(self.entry)
                return True
        return False


class LauncherScreen(Screen):
    def __init__(self, app):
        super().__init__(app, "LilyGo T5 4.7\" Plus")
        self.tick_ms = 5000           # fast polls to catch auto-connect result
        self._fast_ticks = 3          # first 3 ticks at 5s, then slow to 15s
        self.status = None
        # Cache the parsed config on the app so screens can reach it.
        if not hasattr(app, "_ui_config"):
            app._ui_config = declarative.load_config()

    def build(self):
        d = self.app.display
        self.status = self.add(HomeStatus(d.width - 360, 6, 348,
                          theme.TITLE_BAR_H - 8))
        apps = (self.app._ui_config.get("apps") if self.app._ui_config
                else None) or DEFAULT_APPS
        gap = theme.PAD
        top = theme.TITLE_BAR_H + theme.PAD
        bottom = 14
        # Uniform tile size for an 8-slot (4x2) grid, centered.
        tile_w = (d.width - (GRID_COLS + 1) * gap) // GRID_COLS
        avail_h = d.height - top - bottom
        row_h = (avail_h - (GRID_ROWS - 1) * gap) // GRID_ROWS
        tile = min(tile_w, row_h)
        grid_w = GRID_COLS * tile + (GRID_COLS - 1) * gap
        left = (d.width - grid_w) // 2

        def slot_xy(slot):
            r, c = slot // GRID_COLS, slot % GRID_COLS
            return left + c * (tile + gap), top + r * (tile + gap)

        # Apps with an explicit slot are pinned there; the rest fill the free
        # slots in order. Everything is the same tile size and grid-aligned.
        pinned = {}
        flow = []
        for a in apps:
            s = a.get("slot")
            if isinstance(s, int) and 0 <= s < GRID_SLOTS and s not in pinned:
                pinned[s] = a
            else:
                flow.append(a)
        free = [s for s in range(GRID_SLOTS) if s not in pinned]
        for slot, entry in pinned.items():
            tx, ty = slot_xy(slot)
            self.add(AppTile(tx, ty, tile, tile, entry, self._open))
        for entry, slot in zip(flow, free):
            tx, ty = slot_xy(slot)
            self.add(AppTile(tx, ty, tile, tile, entry, self._open))

    async def task(self):
        await self._update_status()

    async def on_tick(self):
        await self._update_status()
        # After a few fast polls, slow down to save power and reduce refresh wear.
        if self._fast_ticks > 0:
            self._fast_ticks -= 1
            if self._fast_ticks == 0:
                self.tick_ms = 15000

    async def _update_status(self):
        dt = await self.app.board.rtc.datetime()
        if dt:
            clock = "{:02d}:{:02d}".format(dt[4], dt[5])
        else:
            clock = "--:--"
        self.status.set_status(clock, netconn.connected_ssid())

    def _open(self, entry):
        _open_app(self.app, entry)


class HomeStatus(Widget):
    """Top-right status strip: clock + Wi-Fi icon + SSID (if connected)."""

    def __init__(self, x, y, w, h):
        super().__init__(x, y, w, h)
        self.clock = "--:--"
        self.ssid = None

    def set_status(self, clock, ssid):
        if clock == self.clock and ssid == self.ssid:
            return
        self.clock = clock
        self.ssid = ssid
        self.invalidate(False)

    def draw(self, disp):
        # Clock right-aligned.
        cs = theme.BODY_SCALE
        ctw = len(self.clock) * 8 * cs
        cx = self.x + self.w - ctw
        cy = self.y + (self.h - 8 * cs) // 2
        disp.text(self.clock, cx, cy, theme.FG, cs)

        # Wi-Fi icon just left of the time.
        isize = 20
        ix = cx - 12 - isize
        iy = self.y + (self.h - isize) // 2
        icons.draw(disp, "wifi", ix, iy, isize)

        # Connected SSID (truncated) to the left of the icon.
        if self.ssid:
            ss = _trim(self.ssid, 14)
            stw = len(ss) * 8 * theme.SMALL_SCALE
            sx = ix - 10 - stw
            sy = self.y + (self.h - 8 * theme.SMALL_SCALE) // 2
            disp.text(ss, sx, sy, theme.FG_MUTED, theme.SMALL_SCALE)
