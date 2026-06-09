# ics.py - minimal iCalendar reader for date-only VEVENTs (trash calendar).
#
# Only what we need: pull DTSTART (a VALUE=DATE day) and SUMMARY out of each
# VEVENT and group the waste types by date. No timezones, no recurrence - the
# RSAG export already lists every collection day as its own event.
#
# Waste-type classification maps the German SUMMARY text to a short type key.
# Labels are ASCII-only because the framebuffer font has no umlaut glyphs.

# type key -> short label shown to the user
LABELS = {
    "rest": "Restmuell",
    "bio": "Bio",
    "papier": "Papier",
    "wert": "Wertstoff",
    "other": "Abfuhr",
}

# Stable display order when a single day has several collections.
ORDER = ("rest", "bio", "papier", "wert", "other")


def classify(summary):
    """Map a SUMMARY string to one of the type keys above."""
    s = summary.lower()
    if "rest" in s:
        return "rest"
    if "bio" in s:
        return "bio"
    if "papier" in s:
        return "papier"
    if "wert" in s:
        return "wert"
    return "other"


def _parse_date(value):
    """'20260609' (optionally with a time suffix) -> (year, month, day)."""
    v = value.strip()
    if len(v) >= 8 and v[:8].isdigit():
        return (int(v[0:4]), int(v[4:6]), int(v[6:8]))
    return None


def load_events(path):
    """Parse the .ics at `path`.

    Returns a dict mapping (year, month, day) -> list of type keys, with the
    keys de-duplicated and sorted into ORDER. Returns {} if the file is missing.
    """
    events = {}
    try:
        f = open(path)
    except OSError:
        return events
    cur_date = None
    try:
        for raw in f:
            line = raw.rstrip("\r\n")
            if line.startswith("BEGIN:VEVENT"):
                cur_date = None
            elif line.startswith("DTSTART"):
                cur_date = _parse_date(line.split(":", 1)[-1])
            elif line.startswith("SUMMARY") and cur_date is not None:
                key = classify(line.split(":", 1)[-1])
                lst = events.get(cur_date)
                if lst is None:
                    events[cur_date] = [key]
                elif key not in lst:
                    lst.append(key)
    finally:
        f.close()
    # Normalise ordering within each day.
    for date, keys in events.items():
        keys.sort(key=lambda k: ORDER.index(k) if k in ORDER else 99)
    return events


# --- calendar date helpers (no `calendar`/`datetime` on the device) --------- #
_MONTH_NAMES = ("January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December")
_WEEKDAY_ABBR = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")


def month_name(month):
    return _MONTH_NAMES[month - 1]


def is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def days_in_month(year, month):
    if month == 2:
        return 29 if is_leap(year) else 28
    return (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[month - 1]


def weekday(year, month, day):
    """Day of week with 0=Monday .. 6=Sunday (Sakamoto's algorithm)."""
    t = (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)
    y = year
    if month < 3:
        y -= 1
    w = (y + y // 4 - y // 100 + y // 400 + t[month - 1] + day) % 7  # 0=Sunday
    return (w + 6) % 7  # shift to 0=Monday


def add_month(year, month, delta):
    """Return (year, month) moved by delta months (delta may be negative)."""
    idx = (year * 12 + (month - 1)) + delta
    return (idx // 12, idx % 12 + 1)
