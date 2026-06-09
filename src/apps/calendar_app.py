# calendar_app.py - Trash-collection calendar from an .ics export.
#
# Month grid view: days that have a collection are boxed and tappable; tapping
# one opens a day-detail screen listing the waste types. Prev/next switch months.
# Days without data are not clickable.
from lib import ics
from lib.ui import theme
from lib.ui.core import UP, Screen, Widget
from lib.ui.widgets import Button, Label

# Where the calendar file lives on the device flash.
ICS_PATH = "trash.ics"

# Grayscale marker per waste type (outlined so even light shades stay visible).
COLORS = {
    "rest": theme.BLACK,
    "bio": theme.DARK,
    "papier": theme.GRAY,
    "wert": theme.LIGHT,
    "other": theme.GRAY,
}


def open_calendar(app):
    """Parse the .ics and return the calendar screen for the current month."""
    events = ics.load_events(ICS_PATH)
    today = getattr(app.board, "today", None)
    if today:
        year, month = today[0], today[1]
    else:
        year, month = 2026, 6
    return CalendarScreen(app, year, month, events)


def _marker(disp, x, y, size, color):
    disp.fill_rect(x, y, size, size, color)
    disp.rect(x, y, size, size, theme.FG)


# --------------------------------------------------------------------------- #
# Month grid widget
# --------------------------------------------------------------------------- #
class MonthGrid(Widget):
    HEADER_H = 28

    def __init__(self, x, y, w, h, year, month, events, on_day, today=None):
        super().__init__(x, y, w, h)
        self.year = year
        self.month = month
        self.events = events
        self.on_day = on_day
        self.today = today
        self.cell_w = w // 7
        self.cell_h = (h - self.HEADER_H) // 6

    def _cell_origin(self, day):
        first_wd = ics.weekday(self.year, self.month, 1)
        idx = first_wd + (day - 1)
        row, col = idx // 7, idx % 7
        cx = self.x + col * self.cell_w
        cy = self.y + self.HEADER_H + row * self.cell_h
        return cx, cy

    def draw(self, disp):
        # Weekday header (Mo..Su).
        for c in range(7):
            cx = self.x + c * self.cell_w
            lbl = ics._WEEKDAY_ABBR[c]
            disp.text(lbl, cx + (self.cell_w - len(lbl) * 16) // 2, self.y,
                      theme.FG_MUTED, theme.BODY_SCALE)
        ndays = ics.days_in_month(self.year, self.month)
        is_today = (self.today and self.today[0] == self.year
                    and self.today[1] == self.month)
        for day in range(1, ndays + 1):
            cx, cy = self._cell_origin(day)
            keys = self.events.get((self.year, self.month, day))
            disp.rect(cx, cy, self.cell_w, self.cell_h, theme.LIGHT)
            disp.text(str(day), cx + 8, cy + 6, theme.FG, theme.BODY_SCALE)
            if is_today and self.today[2] == day:
                # Outline today's cell so it stands out at a glance.
                disp.rect(cx + 2, cy + 2, self.cell_w - 4, self.cell_h - 4,
                          theme.FG_MUTED)
            if keys:
                # Boxed = has data = tappable.
                disp.rect(cx + 1, cy + 1, self.cell_w - 2, self.cell_h - 2,
                          theme.FG)
                # Larger markers (never more than 3 per day) for readability.
                msize = 22
                mx = cx + 8
                my = cy + self.cell_h - msize - 8
                for k in keys:
                    _marker(disp, mx, my, msize, COLORS.get(k, theme.GRAY))
                    mx += msize + 8

    def handle(self, ev):
        if ev.type != UP or not self.contains(ev):
            return False
        gy = self.y + self.HEADER_H
        if ev.y < gy:
            return False
        col = (ev.x - self.x) // self.cell_w
        row = (ev.y - gy) // self.cell_h
        if not (0 <= col <= 6 and 0 <= row <= 5):
            return False
        first_wd = ics.weekday(self.year, self.month, 1)
        day = row * 7 + col - first_wd + 1
        ndays = ics.days_in_month(self.year, self.month)
        if 1 <= day <= ndays and (self.year, self.month, day) in self.events:
            if self.on_day:
                self.on_day(day)
            return True
        return False


# --------------------------------------------------------------------------- #
# Screens
# --------------------------------------------------------------------------- #
class CalendarScreen(Screen):
    def __init__(self, app, year, month, events):
        super().__init__(app, ics.month_name(month) + " " + str(year))
        self.year = year
        self.month = month
        self.events = events

    def build(self):
        d = self.app.display
        self.add_back_button()
        self.add(Button(d.width - 238, theme.PAD, 64, 50, ">",
                        self._next, theme.H1_SCALE))
        self.add(Button(d.width - 314, theme.PAD, 64, 50, "<",
                        self._prev, theme.H1_SCALE))
        today = getattr(self.app.board, "today", None)
        self.add(MonthGrid(theme.PAD, 78, d.width - 2 * theme.PAD,
                           d.height - 90, self.year, self.month, self.events,
                           self._open_day, today))
        if not self.events:
            self.add(Label(theme.PAD, d.height - 40,
                           "No " + ICS_PATH + " on device - upload it to flash.",
                           theme.SMALL_SCALE, theme.FG_MUTED))

    def _prev(self):
        y, m = ics.add_month(self.year, self.month, -1)
        self.app.go(CalendarScreen(self.app, y, m, self.events))

    def _next(self):
        y, m = ics.add_month(self.year, self.month, 1)
        self.app.go(CalendarScreen(self.app, y, m, self.events))

    def _open_day(self, day):
        keys = self.events.get((self.year, self.month, day), [])
        self.app.go(DayDetailScreen(self.app, self.year, self.month, day,
                                    keys, self.events))


class DayDetailScreen(Screen):
    def __init__(self, app, year, month, day, keys, events):
        super().__init__(app, "{:02d}.{:02d}.{}".format(day, month, year))
        self.year = year
        self.month = month
        self.day = day
        self.keys = keys
        self.events = events

    def build(self):
        d = self.app.display
        self.add_back_button(self._back)
        wd = ics.weekday(self.year, self.month, self.day)
        self.add(Label(theme.PAD, 90,
                       ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                        "Saturday", "Sunday")[wd],
                       theme.BODY_SCALE, theme.FG_MUTED))
        y = 150
        if not self.keys:
            self.add(Label(theme.PAD, y, "No collection on this day.",
                           theme.H1_SCALE))
            return
        self.add(Label(theme.PAD, y, "Collections:", theme.BODY_SCALE,
                       theme.FG_MUTED))
        y += 50
        for k in self.keys:
            self.add(_LegendRow(theme.PAD, y, k))
            y += 64

    def _back(self):
        self.app.go(CalendarScreen(self.app, self.year, self.month, self.events))


class _LegendRow(Widget):
    """A marker swatch followed by the waste-type label."""

    def __init__(self, x, y, key):
        super().__init__(x, y, 400, 48)
        self.key = key

    def draw(self, disp):
        _marker(disp, self.x, self.y, 44, COLORS.get(self.key, theme.GRAY))
        disp.text(ics.LABELS.get(self.key, self.key), self.x + 60,
                  self.y + 10, theme.FG, theme.H1_SCALE)
