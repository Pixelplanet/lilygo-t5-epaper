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
        self._time_x = 0
        self._date_x = 0

    def build(self):
        self.add_back_button()
        d = self.app.display
        # Use fixed centered anchors to keep dirty-rect math stable.
        self._time_x = (d.width - 5 * 8 * theme.TITLE_SCALE) // 2
        self._date_x = (d.width - 14 * 8 * theme.H1_SCALE) // 2
        # Big centered time, date below.
        self.time_lbl = self.add(Label(self._time_x, d.height // 2 - 60, "--:--",
                                        theme.TITLE_SCALE))
        self.date_lbl = self.add(Label(self._date_x, d.height // 2 + 30,
                                       "Mon 01.01.2000",
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
        self.time_lbl.set_text("{:02d}:{:02d}".format(dt[4], minute))
        days = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
        wd = dt[3] if 0 <= dt[3] <= 6 else 0
        self.date_lbl.set_text("{} {:02d}.{:02d}.{:04d}".format(
            days[wd], dt[2], dt[1], dt[0]))
        if not force:
            self._mins_since_full += 1
            if self._mins_since_full >= 10:
                self._mins_since_full = 0
                self.app.refresh_now()
