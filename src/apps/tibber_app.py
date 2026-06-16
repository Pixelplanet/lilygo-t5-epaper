# tibber_app.py - show today's (and tomorrow's) electricity prices as a bar
# chart. Prices change only once per day, so we fetch at most once per day and
# cache the result to flash; subsequent opens render straight from the cache.
#
# Requires a Tibber personal access token in secrets.py:
#     TIBBER_TOKEN = "xxxxxxxx..."
# Get one at https://developer.tibber.com/ (Account -> access token).
import json

from lib import debuglog, wifistore
from lib.ui import theme
from lib.ui.core import UP, Screen, Widget
from lib.ui.widgets import Button, Label

CACHE_PATH = "tibber_cache.json"
API_HOST = "api.tibber.com"
API_PATH = "/v1-beta/gql"

_QUERY = ("{viewer{homes{currentSubscription{priceInfo{"
          "today{total startsAt}tomorrow{total startsAt}}}}}}")


def _token():
    try:
        from secrets import TIBBER_TOKEN
        return TIBBER_TOKEN or ""
    except Exception:
        return ""


def open_prices(app):
    return PricesScreen(app)


# --------------------------------------------------------------------------- #
# Networking (small HTTPS POST without a urequests dependency)
# --------------------------------------------------------------------------- #
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


def _https_post_graphql(token, query, timeout=15):
    import socket
    import ssl
    addr = socket.getaddrinfo(API_HOST, 443)[0][-1]
    s = socket.socket()
    s.settimeout(timeout)
    s.connect(addr)
    s = ssl.wrap_socket(s, server_hostname=API_HOST)
    payload = json.dumps({"query": query})
    req = ("POST " + API_PATH + " HTTP/1.1\r\n"
           "Host: " + API_HOST + "\r\n"
           "Authorization: Bearer " + token + "\r\n"
           "Content-Type: application/json\r\n"
           "Content-Length: " + str(len(payload)) + "\r\n"
           "Connection: close\r\n\r\n" + payload)
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
    return json.loads(body)


def _extract_prices(data):
    """Pull today/tomorrow price lists out of the GraphQL response.

    Returns (today, tomorrow) where each is a list of (hour, total_float).
    """
    info = (data["data"]["viewer"]["homes"][0]
            ["currentSubscription"]["priceInfo"])

    def conv(rows):
        out = []
        for r in rows or ():
            sa = r.get("startsAt", "")
            hour = int(sa[11:13]) if len(sa) >= 13 else 0
            out.append((hour, float(r["total"])))
        return out

    return conv(info.get("today")), conv(info.get("tomorrow"))


def _wifi_connected():
    """True if the station interface currently has a Wi-Fi connection."""
    from lib import netconn
    return netconn.is_connected()


def _ensure_wifi(timeout=12):
    """Bring up Wi-Fi using the saved credentials. Returns True on success."""
    from lib import netconn
    return netconn.connect_blocking(timeout)


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #
def _load_cache():
    try:
        with open(CACHE_PATH) as f:
            return json.load(f)
    except Exception:
        return None


def _save_cache(obj):
    try:
        import os
        with open(CACHE_PATH, "w") as f:
            json.dump(obj, f)
        os.sync()
    except Exception as e:  # noqa: BLE001
        debuglog.log("tibber: cache save failed " + str(e))


# --------------------------------------------------------------------------- #
# Chart widget
# --------------------------------------------------------------------------- #
class PriceChart(Widget):
    def __init__(self, x, y, w, h, prices, current_hour=None, on_select=None):
        super().__init__(x, y, w, h)
        self.prices = prices            # list of (hour, total)
        self.current_hour = current_hour
        self.on_select = on_select
        self.selected = None            # index of a tapped bar, or None
        self._bars = []                 # cached (bx, bw) per bar for hit-testing

    def draw(self, disp):
        disp.rect(self.x, self.y, self.w, self.h, theme.FG_MUTED)
        self._bars = []
        if not self.prices:
            disp.text("No price data", self.x + 16, self.y + self.h // 2 - 8,
                      theme.FG_MUTED, theme.BODY_SCALE)
            return
        vals = [p[1] for p in self.prices]
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1.0
        n = len(self.prices)
        plot_h = self.h - 36          # leave room for larger hour labels
        gap = 2
        bw = (self.w - 2 - (n - 1) * gap) // n
        for i, (hour, total) in enumerate(self.prices):
            bx = self.x + 1 + i * (bw + gap)
            self._bars.append((bx, bw))
            bh = int((total - lo) / span * (plot_h - 10)) + 6
            by = self.y + plot_h - bh
            is_now = (self.current_hour is not None and hour == self.current_hour)
            is_sel = (i == self.selected)
            if is_sel:
                fill = theme.LIGHT          # lighter shade = clearly selected
            elif is_now:
                fill = theme.FG
            else:
                fill = theme.GRAY
            disp.fill_rect(bx, by, bw, bh, fill)
            if is_sel:
                # Bold double outline so the lighter bar still reads as picked.
                disp.rect(bx - 1, by - 1, bw + 2, bh + 2, theme.FG)
                disp.rect(bx - 2, by - 2, bw + 4, bh + 4, theme.FG)
            elif is_now:
                disp.rect(bx - 1, by - 1, bw + 2, bh + 2, theme.FG)
            # hour label every 3 hours to avoid clutter
            if hour % 3 == 0:
                disp.text("{:02d}".format(hour), bx, self.y + plot_h + 10,
                          theme.FG_MUTED, theme.BODY_SCALE)

    def handle(self, ev):
        if ev.type != UP or not self.contains(ev) or not self._bars:
            return False
        for i, (bx, bw) in enumerate(self._bars):
            if bx <= ev.x < bx + bw + 2:
                # Tapping the already-selected bar deselects (back to average).
                self.selected = None if i == self.selected else i
                self.invalidate()
                if self.on_select:
                    self.on_select(self.selected)
                return True
        return False


# --------------------------------------------------------------------------- #
# Screen
# --------------------------------------------------------------------------- #
class PricesScreen(Screen):
    def __init__(self, app):
        super().__init__(app, "Electricity prices")
        self.today = []
        self.tomorrow = []
        self.showing = "today"
        self.status = None
        self.chart = None
        self.toggle = None
        self.readout = None
        self.dateline = None

    def build(self):
        d = self.app.display
        self.add_back_button()
        # Toggle sits below the title bar so the chart can fill to the bottom edge.
        self.toggle = Button(d.width - 420, theme.TITLE_BAR_H + 8, 228, 50,
                             "Show tomorrow", self._toggle, theme.BODY_SCALE)
        self.toggle.visible = False
        self.add(self.toggle)
        # Price readout directly under the title bar: tapped bar or daily avg.
        ry = theme.TITLE_BAR_H + 14
        self.readout = self.add(Label(theme.PAD, ry, "", theme.H1_SCALE))
        # Date / status line over the graph.
        self.dateline = self.add(Label(theme.PAD, ry + 44, "Loading prices...",
                                       theme.BODY_SCALE, theme.FG_MUTED))
        self.status = self.dateline
        chart_y = ry + 84
        self.chart = PriceChart(theme.PAD, chart_y, d.width - 2 * theme.PAD,
                                d.height - chart_y - theme.PAD, [],
                                self._now_hour(), self._on_bar)
        self.add(self.chart)

    def _now_hour(self):
        t = getattr(self.app.board, "today", None)
        return t[4] if t else None

    def _today_str(self):
        t = getattr(self.app.board, "today", None)
        if t:
            return "{:04d}-{:02d}-{:02d}".format(t[0], t[1], t[2])
        return ""

    async def task(self):
        import asyncio
        today_str = self._today_str()
        cache = _load_cache()
        if cache and cache.get("date") == today_str and cache.get("today"):
            self.set_wifi_state("on" if _wifi_connected() else "off")
            self._apply(cache)
            await self.app.flush()
            return

        if not _token():
            self.set_wifi_state("off")
            self.status.set_text("No Tibber token - add it to secrets.py")
            await self.app.flush()
            return

        self.set_wifi_state("wait")
        self.status.set_text("Connecting Wi-Fi...")
        await self.app.flush()
        await asyncio.sleep_ms(50)
        if not _ensure_wifi():
            self.set_wifi_state("off")
            self.status.set_text("Wi-Fi failed - connect once in Wi-Fi Setup")
            await self.app.flush()
            return

        self.set_wifi_state("on")
        self.status.set_text("Fetching prices...")
        await self.app.flush()
        await asyncio.sleep_ms(50)
        try:
            data = _https_post_graphql(_token(), _QUERY)
            today, tomorrow = _extract_prices(data)
        except Exception as e:  # noqa: BLE001
            debuglog.log("tibber: fetch failed " + str(e))
            self.status.set_text("Fetch failed - see debug.log")
            await self.app.flush()
            return
        obj = {"date": today_str, "today": today, "tomorrow": tomorrow}
        _save_cache(obj)
        self._apply(obj)
        await self.app.flush()

    def _apply(self, obj):
        self.today = obj.get("today") or []
        self.tomorrow = obj.get("tomorrow") or []
        self._render_chart()
        self.toggle.visible = bool(self.tomorrow)
        self.toggle.invalidate()

    def _render_chart(self):
        if self.showing == "today":
            self.chart.prices = self.today
            self.chart.current_hour = self._now_hour()
        else:
            self.chart.prices = self.tomorrow
            self.chart.current_hour = None
        self.chart.selected = None
        self.chart.invalidate()
        self._set_dateline()
        self._show_average()

    def _current_series(self):
        return self.today if self.showing == "today" else self.tomorrow

    def _displayed_date(self):
        t = getattr(self.app.board, "today", None)
        if not t:
            return None
        y, m, d = t[0], t[1], t[2]
        if self.showing == "tomorrow":
            from lib import ics
            if d >= ics.days_in_month(y, m):
                d, m = 1, m + 1
                if m > 12:
                    m, y = 1, y + 1
            else:
                d += 1
        return (y, m, d)

    def _set_dateline(self):
        dt = self._displayed_date()
        if not dt:
            self.dateline.set_text("")
            return
        from lib import ics
        y, m, d = dt
        name = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                "Saturday", "Sunday")[ics.weekday(y, m, d)]
        self.dateline.set_text("{} {:02d}.{:02d}.{:04d}".format(name, d, m, y))

    def _show_average(self):
        series = self._current_series()
        if not series:
            self.readout.set_text("")
            return
        avg = sum(p[1] for p in series) / len(series)
        label = "Avg" if self.showing == "today" else "Avg tomorrow"
        self.readout.set_text("{}: {:.4f} EUR/kWh".format(label, avg))

    def _on_bar(self, index):
        if index is None:
            # Deselected - go back to showing the daily average.
            self._show_average()
            return
        series = self._current_series()
        if not (0 <= index < len(series)):
            return
        hour, total = series[index]
        self.readout.set_text("{:02d}:00  {:.4f} EUR/kWh".format(hour, total))

    def _toggle(self):
        self.showing = "tomorrow" if self.showing == "today" else "today"
        self.toggle.text = ("Show today" if self.showing == "tomorrow"
                            else "Show tomorrow")
        self.toggle.invalidate()
        self._render_chart()

    def _menu(self):
        from apps import launcher
        self.app.go(launcher.LauncherScreen(self.app))
