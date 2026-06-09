# clock_app.py - full-screen digital clock (community catalog example).
#
# Demonstrates a self-contained installable app: one file, an `open_<x>(app)`
# entry point returning a Screen, and a periodic on_tick() update. Drop this in
# apps/ and add a launcher tile with entry "clock_app:open_clock".
from lib.ui import theme
from lib.ui.core import Screen
from lib.ui.widgets import Label


def open_clock(app):
    return ClockScreen(app)


class ClockScreen(Screen):
    def __init__(self, app):
        super().__init__(app, "Clock")
        self.tick_ms = 15000          # check every 15s; repaint on minute change
        self._last_min = -1
        self._mins_since_full = 0
        self.time_lbl = None
        self.date_lbl = None

    def build(self):
        self.add_back_button()
        d = self.app.display
        # Big centered time, date below.
        self.time_lbl = self.add(Label(0, d.height // 2 - 60, "--:--",
                                        theme.TITLE_SCALE))
        self.date_lbl = self.add(Label(0, d.height // 2 + 30, "",
                                       theme.H1_SCALE, theme.FG_MUTED))

    async def task(self):
        await self._update(force=True)

    async def on_tick(self):
        await self._update()

    async def _update(self, force=False):
        dt = await self.app.board.rtc.datetime()
        if not dt:
            return
        minute = dt[5]
        if not force and minute == self._last_min:
            return
        self._last_min = minute
        self._center(self.time_lbl, "{:02d}:{:02d}".format(dt[4], minute))
        days = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
        wd = dt[3] if 0 <= dt[3] <= 6 else 0
        self._center(self.date_lbl, "{} {:02d}.{:02d}.{:04d}".format(
            days[wd], dt[2], dt[1], dt[0]))
        if not force:
            self._mins_since_full += 1
            if self._mins_since_full >= 10:
                self._mins_since_full = 0
                self.app.refresh_now()

    def _center(self, lbl, text):
        d = self.app.display
        lbl.set_text(text)
        lbl.x = (d.width - len(text) * 8 * lbl.scale) // 2
