# wifi_demo.py - Touch showcase: scan Wi-Fi, pick a network, type the password
# on the on-screen keyboard, and connect. Demonstrates the full touch stack on
# the e-paper display.
import asyncio

import config
from lib import debuglog, wifistore
from lib.ui import theme
from lib.ui.core import Screen
from lib.ui.keyboard import BACK, ENTER, Keyboard
from lib.ui.widgets import Button, Label, ListView, ProgressBar, TextField


def _try_import_network():
    try:
        import network
        return network
    except Exception:
        return None


def _ntp_localtime():
    """Fetch the current time over NTP and return a localtime tuple, or None.

    The result is `time.localtime(...)`: (year, month, mday, hour, minute,
    second, weekday, yearday) already adjusted to config.TZ_OFFSET_HOURS.
    Requires an active Wi-Fi connection with internet access.
    """
    try:
        import ntptime
        import time
    except Exception:
        return None
    try:
        ntptime.host = config.NTP_HOST
    except Exception:
        pass
    try:
        secs = ntptime.time()  # seconds since 2000-01-01 UTC
    except Exception as e:  # noqa: BLE001
        print("ntp error:", e)
        return None
    return time.localtime(secs + int(config.TZ_OFFSET_HOURS * 3600))


# --------------------------------------------------------------------------- #
# Home
# --------------------------------------------------------------------------- #
class HomeScreen(Screen):
    def __init__(self, app):
        super().__init__(app, "LilyGo T5 Dashboard")
        self.batt = None
        self.tick_ms = 0   # title bar clock is handled by Screen base class

    def build(self):
        d = self.app.display
        self.add_back_button()
        self.batt = self.add(Label(theme.PAD, 80, "Battery: --", theme.BODY_SCALE,
                                   theme.FG_MUTED))
        self.add(Button(d.width - 384, 70, 180, 64, "Refresh",
                        self._refresh, theme.H1_SCALE))
        self.add(Button(d.width - 192, 70, 180, 64, "Repair",
                        self._repair, theme.H1_SCALE))
        cy = 170
        bw = d.width - 2 * theme.PAD
        # Show all saved networks with one-tap reconnect.
        networks = wifistore.load_networks()
        if networks:
            self.add(Label(theme.PAD, cy, "Saved networks:",
                           theme.BODY_SCALE, theme.FG_MUTED))
            cy += 36
            # Most recent first (reverse).
            for net in reversed(networks[:3]):  # max 3 visible
                ssid = net.get("ssid", "?")
                self.add(Button(theme.PAD, cy, bw - 120, 64,
                                "Reconnect: " + ssid,
                                lambda s=ssid: self._reconnect_to(s),
                                theme.H1_SCALE))
                # Forget button next to each reconnect.
                self.add(Button(theme.PAD + bw - 110, cy, 98, 64, "Forget",
                                lambda s=ssid: self._forget(s),
                                theme.BODY_SCALE))
                cy += 76
            if len(networks) > 3:
                self.add(Label(theme.PAD, cy,
                               "+{} more saved".format(len(networks) - 3),
                               theme.BODY_SCALE, theme.FG_MUTED))
                cy += 30
            cy += 12
        self.add(Button(theme.PAD, cy, bw, 90, "Scan Wi-Fi networks",
                        self._scan, theme.TITLE_SCALE))
        self.add(Button(theme.PAD, cy + 110, bw, 90, "Touch test",
                        self._touch_test, theme.TITLE_SCALE))
        self.add(Label(theme.PAD, d.height - 48,
                       "Tap a button. Mouse = touch in the simulator.",
                       theme.BODY_SCALE, theme.FG_MUTED))

    async def task(self):
        # Wi-Fi is off here, so the ADC2 battery read is safe.
        pct = self.app.board.battery.percent()
        if pct is not None:
            self.batt.set_text("Battery: {}%".format(pct))

    def _refresh(self):
        self.app.refresh_now()

    def _repair(self):
        self.app.repair_now()

    def _menu(self):
        from apps import launcher
        self.app.go(launcher.LauncherScreen(self.app))

    def _reconnect_to(self, ssid):
        net = wifistore.find_network(ssid)
        if net:
            self.app.go(ConnectScreen(self.app, ssid, net.get("password", "")))

    def _forget(self, ssid):
        wifistore.remove(ssid)
        # Rebuild the home screen to reflect the change.
        self.app.go(HomeScreen(self.app))

    def _scan(self):
        self.app.go(ScanScreen(self.app))

    def _touch_test(self):
        self.app.go(TouchTestScreen(self.app))


# --------------------------------------------------------------------------- #
# Scanning
# --------------------------------------------------------------------------- #
class ScanScreen(Screen):
    def __init__(self, app):
        super().__init__(app, "Scanning for networks...")

    def build(self):
        d = self.app.display
        self.add(Label(theme.PAD, 140, "Enabling Wi-Fi radio and scanning",
                       theme.BODY_SCALE))
        self.bar = self.add(ProgressBar(theme.PAD, 200, d.width - 2 * theme.PAD, 40))

    async def task(self):
        self.bar.set_value(20)
        net = _try_import_network()
        results = []
        if net:
            sta = net.WLAN(net.STA_IF)
            sta.active(True)
            # If a background auto-connect is in progress, the radio is busy and
            # scan() returns nothing. Disconnect first to free the radio, then
            # wait for the interface to settle before scanning.
            try:
                if sta.status() not in (0, 1001):   # 0=IDLE, 1001=WRONG_PASSWORD
                    sta.disconnect()
                    await asyncio.sleep_ms(400)
            except Exception:
                pass
            await asyncio.sleep_ms(150)
            try:
                results = sta.scan()
            except Exception as e:  # noqa: BLE001
                print("wifi scan error:", e)
        self.bar.set_value(100)
        # Normalise to (ssid, rssi, secured)
        nets = []
        for r in results:
            ssid = r[0]
            if isinstance(ssid, (bytes, bytearray)):
                ssid = ssid.decode("utf-8", "replace")
            if not ssid:
                continue
            rssi = r[3]
            secured = r[4] != 0
            nets.append({"ssid": ssid, "rssi": rssi, "secured": secured})
        nets.sort(key=lambda n: n["rssi"], reverse=True)
        self.app.go(NetworkListScreen(self.app, nets))


# --------------------------------------------------------------------------- #
# Network list
# --------------------------------------------------------------------------- #
class NetworkListScreen(Screen):
    def __init__(self, app, nets):
        super().__init__(app, "Select a network")
        self.nets = nets

    def build(self):
        d = self.app.display
        top = 70
        self.add_back_button(self._back)
        if not self.nets:
            self.add(Label(theme.PAD, top + 20, "No networks found. Tap Back.",
                           theme.BODY_SCALE))
            return
        lv = ListView(theme.PAD, top, d.width - 2 * theme.PAD,
                      d.height - top - theme.PAD, self.nets, self._row, self._pick)
        self.add(lv)

    def _row(self, disp, net, idx, x, y, w, h):
        lock = "[L] " if net["secured"] else "[ ] "
        ssid = net["ssid"]
        known = wifistore.find_network(ssid) is not None
        prefix = "* " if known else "  "
        disp.text(prefix + lock + ssid, x + 10, y + (h - 16) // 2, theme.FG,
                  theme.BODY_SCALE)
        if known:
            disp.text("saved", x + w - 130, y + (h - 16) // 2,
                      theme.ACCENT, theme.SMALL_SCALE)
        # RSSI bars (right aligned)
        bars = self._bars(net["rssi"])
        bx = x + w - 90
        for i in range(4):
            bh = 8 + i * 8
            color = theme.ACCENT if i < bars else theme.LIGHT
            disp.fill_rect(bx + i * 18, y + h - 10 - bh, 12, bh, color)

    @staticmethod
    def _bars(rssi):
        if rssi >= -55:
            return 4
        if rssi >= -65:
            return 3
        if rssi >= -75:
            return 2
        if rssi >= -85:
            return 1
        return 0

    def _pick(self, idx):
        net = self.nets[idx]
        if net["secured"]:
            self.app.go(PasswordScreen(self.app, net["ssid"]))
        else:
            self.app.go(ConnectScreen(self.app, net["ssid"], ""))

    def _back(self):
        self.app.go(HomeScreen(self.app))


# --------------------------------------------------------------------------- #
# Password entry + keyboard
# --------------------------------------------------------------------------- #
class PasswordScreen(Screen):
    def __init__(self, app, ssid):
        super().__init__(app, "Enter password")
        self.ssid = ssid
        self.password = ""

    def build(self):
        d = self.app.display
        self.add(Label(theme.PAD, 60, self.ssid, theme.BODY_SCALE, theme.FG_MUTED))
        self.field = self.add(TextField(theme.PAD, 92, d.width - 2 * theme.PAD, 54,
                                        masked=True, scale=theme.H1_SCALE))
        # Explicit Connect button so the user doesn't have to discover the small
        # "OK" key on the keyboard. ENTER on the keyboard does the same thing.
        self.connect_btn = self.add(Button(theme.PAD, 156, 240, 60, "Connect",
                                           self._connect, theme.H1_SCALE))
        self.show = self.add(Button(theme.PAD + 256, 156, 150, 60, "Show",
                                    self._toggle_show, theme.H1_SCALE))
        self.cancel = self.add(Button(theme.PAD + 422, 156, 170, 60, "Cancel",
                                      self._cancel, theme.H1_SCALE))
        kb_h = 300
        self.kb = self.add(Keyboard(0, d.height - kb_h, d.width, kb_h, self._on_key))

    def _connect(self):
        debuglog.log("pw: connect button -> go ConnectScreen")
        self.app.go(ConnectScreen(self.app, self.ssid, self.password))

    def _on_key(self, key):
        if key == BACK:
            self.password = self.password[:-1]
        elif key == ENTER:
            debuglog.log("pw: ENTER key -> go ConnectScreen")
            self.app.go(ConnectScreen(self.app, self.ssid, self.password))
            return
        else:
            self.password += key
        self.field.set_text(self.password)

    def _toggle_show(self):
        self.field.masked = not self.field.masked
        self.field.invalidate()

    def _cancel(self):
        self.app.go(HomeScreen(self.app))


# --------------------------------------------------------------------------- #
# Connecting + result
# --------------------------------------------------------------------------- #
class ConnectScreen(Screen):
    def __init__(self, app, ssid, password):
        super().__init__(app, "Connecting...")
        self.ssid = ssid
        self.password = password

    def build(self):
        d = self.app.display
        self.add(Label(theme.PAD, 120, "Connecting to:", theme.BODY_SCALE))
        self.add(Label(theme.PAD, 160, self.ssid, theme.H1_SCALE))
        self.status = self.add(Label(theme.PAD, 230, "Associating...",
                                     theme.BODY_SCALE, theme.FG_MUTED))
        debuglog.log("connect: screen built ssid=" + self.ssid)

    async def task(self):
        net = _try_import_network()
        ok, ip = False, ""
        debuglog.log("connect: start ssid=" + self.ssid)
        if net is None:
            self.status.set_text("No network support")
            await self.app.flush()
            await asyncio.sleep_ms(800)
        else:
            sta = net.WLAN(net.STA_IF)
            sta.active(True)
            # Reduce peak TX current so full association doesn't brown out the
            # e-paper boost converter (the reason a *correct* password could make
            # the board reset while a wrong one - never associating - looked OK).
            try:
                sta.config(txpower=8)
            except Exception as e:  # noqa: BLE001
                print("txpower set skipped:", e)
            try:
                print("wifi: connecting to", self.ssid)
                sta.connect(self.ssid, self.password)
                for i in range(120):  # ~12s timeout
                    if sta.isconnected():
                        ok = True
                        break
                    if i % 5 == 0:
                        self.status.set_text("Connecting... {}s".format(i // 10))
                        await self.app.flush()
                    await asyncio.sleep_ms(100)
            except Exception as e:  # noqa: BLE001
                print("connect error:", e)
                debuglog.log("connect: exception " + repr(e))
                self.status.set_text("Error - check password")
                await self.app.flush()
                await asyncio.sleep_ms(800)
            if ok:
                debuglog.log("connect: associated")
                # Show success on THIS screen first (light partial update), then
                # let the radio settle before the heavier ResultScreen refresh.
                self.status.set_text("Connected! Loading details...")
                await self.app.flush()
                await asyncio.sleep_ms(1000)
                try:
                    ip = sta.ifconfig()[0]
                    debuglog.log("connect: ip=" + str(ip))
                except Exception as e:  # noqa: BLE001
                    print("ifconfig error:", e)
                    debuglog.log("connect: ifconfig err " + repr(e))
                try:
                    wifistore.save(self.ssid, self.password)
                    debuglog.log("connect: creds saved")
                except Exception as e:  # noqa: BLE001
                    print("save error:", e)
                    debuglog.log("connect: save err " + repr(e))
            else:
                debuglog.log("connect: timeout/failed")
        print("wifi:", "connected" if ok else "failed", "ip=", ip)
        debuglog.log("connect: -> result ok=" + str(ok))
        self.app.go(ResultScreen(self.app, self.ssid, ok, ip))


class ResultScreen(Screen):
    def __init__(self, app, ssid, ok, ip):
        super().__init__(app, "Wi-Fi status")
        self.ssid = ssid
        self.ok = ok
        self.ip = ip
        self.time_status = None

    def build(self):
        d = self.app.display
        self.add_back_button(self._home, "Home")
        msg = "Connected" if self.ok else "Not connected"
        mark = "OK" if self.ok else "X"
        self.add(Label(theme.PAD, 120, "[{}]  {}".format(mark, msg),
                       theme.TITLE_SCALE))
        self.add(Label(theme.PAD, 200, "Network:  " + self.ssid, theme.BODY_SCALE))
        if self.ok:
            self.add(Label(theme.PAD, 244, "IP address:  " + self.ip,
                           theme.BODY_SCALE))
            self.time_status = self.add(
                Label(theme.PAD, 288, "Syncing clock over Wi-Fi...",
                      theme.BODY_SCALE, theme.FG_MUTED))
        else:
            self.add(Label(theme.PAD, 244, "Check the password and try again.",
                           theme.BODY_SCALE, theme.FG_MUTED))
        self.add(Button(theme.PAD, d.height - 100, d.width - 2 * theme.PAD, 80,
                        "Back to home", self._home, theme.H1_SCALE))

    async def task(self):
        debuglog.log("result: shown ok=" + str(self.ok) + " ip=" + str(self.ip))
        if not self.ok or self.time_status is None:
            return
        print("ntp: syncing clock...")
        tm = _ntp_localtime()
        if tm is None:
            print("ntp: failed")
            self.time_status.set_text("Clock sync failed (no internet)")
            await self.app.flush()
            return
        # tm = (year, month, mday, hour, minute, second, weekday, yearday)
        try:
            await self.app.board.rtc.set_datetime(
                tm[0], tm[1], tm[2], tm[6], tm[3], tm[4], tm[5])
        except Exception as e:  # noqa: BLE001
            print("rtc set error:", e)
            self.time_status.set_text("Clock sync got time but RTC write failed")
            await self.app.flush()
            return
        self.time_status.set_text(
            "Clock synced:  {:04d}-{:02d}-{:02d}  {:02d}:{:02d}".format(
                tm[0], tm[1], tm[2], tm[3], tm[4]))
        print("ntp: synced", tm)
        await self.app.flush()

    def _home(self):
        self.app.go(HomeScreen(self.app))


# --------------------------------------------------------------------------- #
# Touch test (draw where you touch)
# --------------------------------------------------------------------------- #
class TouchTestScreen(Screen):
    def __init__(self, app):
        super().__init__(app, "Touch test")

    def build(self):
        d = self.app.display
        self.add_back_button(self._back)
        self.add(Label(theme.PAD, 70, "Touch the screen - a dot follows your finger.",
                       theme.BODY_SCALE, theme.FG_MUTED))
        self.coord = self.add(Label(theme.PAD, 110, "x: ---  y: ---",
                                    theme.BODY_SCALE))
        self.canvas = TouchCanvas(theme.PAD, 150, d.width - 2 * theme.PAD,
                                  d.height - 170, self.coord)
        self.add(self.canvas)

    def _back(self):
        self.app.go(HomeScreen(self.app))


class TouchCanvas(ListView):
    """Reuses Widget plumbing to capture raw touches and draw a marker."""

    DOT = 16  # marker half-extent is DOT//2

    def __init__(self, x, y, w, h, coord_label):
        from lib.ui.core import Widget
        Widget.__init__(self, x, y, w, h)
        self.coord = coord_label
        self.mark = None

    def draw(self, disp):
        disp.rect(self.x, self.y, self.w, self.h, theme.FG_MUTED)
        if self.mark:
            mx, my = self.mark
            disp.fill_rect(mx - 8, my - 8, 16, 16, theme.ACCENT)

    def _dot_rect(self, pt):
        """Bounding box of the dot at pt, clipped into the canvas border."""
        mx, my = pt
        x0 = max(self.x + 1, mx - 8)
        y0 = max(self.y + 1, my - 8)
        x1 = min(self.x + self.w - 1, mx + 8)
        y1 = min(self.y + self.h - 1, my + 8)
        return x0, y0, max(0, x1 - x0), max(0, y1 - y0)

    def handle(self, ev):
        from lib.ui.core import UP
        if ev.type != UP and self.contains(ev):
            old = self.mark
            self.mark = (ev.x, ev.y)
            self.coord.set_text("x: {}  y: {}".format(ev.x, ev.y))
            # Erase the old marker (dark->white needs a clear), then draw the
            # new marker additively (white->black) so it appears instantly.
            if old:
                self.screen.mark_dirty(*self._dot_rect(old))
            self.screen.mark_dirty(*self._dot_rect(self.mark), fast=True)
            return True
        return False


def build_app(app):
    """Entry helper: return the first screen for the demo."""
    return HomeScreen(app)
