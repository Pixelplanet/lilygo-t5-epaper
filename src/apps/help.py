# help.py - on-device help screen with short explanations.
#
# Opened from the launcher's Help tile. Plain, readable body text (no tiny
# fonts) covering the things that aren't obvious from the UI alone.
from lib.ui import theme
from lib.ui.core import Screen
from lib.ui.widgets import Label

# Each entry: (heading, body). Kept ASCII (the e-paper font has no umlauts).
SECTIONS = [
    ("Navigation",
     "Tap an app to open it. Back (top right) returns here."),
    ("Recovery / REPL",
     "Hold BOOT during reset to skip the app and get a Python prompt."),
    ("Wi-Fi",
     "Remembers multiple networks. Auto-reconnects to any in range."),
    ("System updates",
     "Use the Update app to get new platform versions over Wi-Fi."
     " Tested and working!"),
    ("Ghosting",
     "In Wi-Fi: Refresh cleans the screen, Repair clears ghosts."),
    ("Add your own apps",
     "Edit ui.json or use the web builder to add apps and screens."),
    ("Electricity prices",
     "Put a Tibber token in secrets.py to enable the Prices app."),
]


def open_help(app):
    return HelpScreen(app)


class HelpScreen(Screen):
    def __init__(self, app):
        super().__init__(app, "Help")

    def build(self):
        self.add_back_button()
        y = theme.TITLE_BAR_H + 16
        wrap = (self.app.display.width - 2 * theme.PAD) // (8 * theme.BODY_SCALE)
        for heading, body in SECTIONS:
            self.add(Label(theme.PAD, y, heading, theme.BODY_SCALE, theme.FG))
            y += 8 * theme.BODY_SCALE + 6
            for line in _wrap(body, wrap):
                self.add(Label(theme.PAD + 8, y, line, theme.BODY_SCALE,
                               theme.FG_MUTED))
                y += 8 * theme.BODY_SCALE + 6
            y += 12


def _wrap(text, width):
    """Greedy word-wrap into lines of at most `width` characters."""
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines
