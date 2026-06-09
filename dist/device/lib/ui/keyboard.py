# keyboard.py - on-screen touch keyboard widget.
from lib.ui import theme
from lib.ui.core import DOWN, UP, Widget

# Special key tokens
SHIFT, BACK, SYM, ABC, SPACE, ENTER = "shift", "back", "sym", "abc", "space", "enter"

# Each key: (label, token, weight)
_LETTERS = [
    [(c, c, 1) for c in "qwertyuiop"],
    [(c, c, 1) for c in "asdfghjkl"],
    [("Sh", SHIFT, 1.5)] + [(c, c, 1) for c in "zxcvbnm"] + [("<-", BACK, 1.5)],
    [("?123", SYM, 2), (" ", SPACE, 5), ("OK", ENTER, 2)],
]
_SYMBOLS = [
    [(c, c, 1) for c in "1234567890"],
    [(c, c, 1) for c in "-/:;()$&@\""],
    [("#+=", SYM, 1.5)] + [(c, c, 1) for c in ".,?!'"] + [("<-", BACK, 1.5)],
    [("ABC", ABC, 2), (" ", SPACE, 5), ("OK", ENTER, 2)],
]


class Keyboard(Widget):
    # On this controllerless e-paper panel, any per-key partial/additive refresh
    # leaves vertical streaks, and forcing periodic FULL refreshes to wipe them
    # is too distracting. So the keyboard is drawn ONCE (on screen activation)
    # and never repaints individual keys while typing. Press feedback comes from
    # the password field updating immediately instead.
    def __init__(self, x, y, w, h, on_key=None):
        super().__init__(x, y, w, h)
        self.on_key = on_key
        self.shift = False
        self.symbols = False
        self._pressed = None  # index of key currently held (state only)
        self._rebuild()

    def _layout(self):
        return _SYMBOLS if self.symbols else _LETTERS

    def _rebuild(self):
        """Compute pixel rects for every key."""
        self.keys = []  # list of (rect, label, token)
        rows = self._layout()
        n = len(rows)
        row_h = (self.h - (n + 1) * theme.KEY_GAP) // n
        ry = self.y + theme.KEY_GAP
        for row in rows:
            total_w = sum(k[2] for k in row)
            avail = self.w - (len(row) + 1) * theme.KEY_GAP
            rx = self.x + theme.KEY_GAP
            for label, token, weight in row:
                kw = int(avail * weight / total_w)
                disp_label = label.upper() if (self.shift and len(label) == 1
                                               and label.isalpha()) else label
                self.keys.append(((rx, ry, kw, row_h), disp_label, token))
                rx += kw + theme.KEY_GAP
            ry += row_h + theme.KEY_GAP

    def draw(self, disp):
        disp.fill_rect(self.x, self.y, self.w, self.h, theme.BG)
        disp.hline(self.x, self.y, self.w, theme.FG_MUTED)
        for i, (rect, label, token) in enumerate(self.keys):
            kx, ky, kw, kh = rect
            pressed = self._pressed == i
            active = (token == SHIFT and self.shift)
            face = theme.ACCENT if (pressed or active) else theme.SURFACE
            txt = theme.BG if (pressed or active) else theme.FG
            disp.rounded_rect(kx, ky, kw, kh, face, r=6, fill=True)
            disp.rounded_rect(kx, ky, kw, kh, theme.FG_MUTED, r=6)
            tw = len(label) * 8 * theme.BODY_SCALE
            disp.text(label, kx + (kw - tw) // 2,
                      ky + (kh - 8 * theme.BODY_SCALE) // 2, txt, theme.BODY_SCALE)

    def _key_at(self, ev):
        for i, (rect, _, _) in enumerate(self.keys):
            kx, ky, kw, kh = rect
            if kx <= ev.x < kx + kw and ky <= ev.y < ky + kh:
                return i
        return None

    def handle(self, ev):
        # Note: presses intentionally do NOT repaint keys (no per-key partial
        # refresh => no streaks). Feedback is the password field updating.
        if ev.type == DOWN:
            i = self._key_at(ev)
            if i is not None:
                self._pressed = i
                return True
        elif ev.type == UP:
            if self._pressed is not None:
                i, self._pressed = self._pressed, None
                _, _, token = self.keys[i]
                self._emit(token)
                return True
        return False

    def _full_redraw(self):
        """Repaint the keyboard with a clean FULL refresh (no streaks).

        Used only when the key labels actually change (shift / symbol toggle),
        which is infrequent, so the full-screen refresh is not distracting.
        """
        app = getattr(self.screen, "app", None) if self.screen else None
        if app is not None and app._next is None:
            app.refresh_now()
        else:
            self.invalidate()

    def _emit(self, token):
        if token == SHIFT:
            self.shift = not self.shift
            self._rebuild()
            self._full_redraw()  # labels/active state changed
            return
        if token in (SYM, ABC):
            self.symbols = not self.symbols
            self._rebuild()
            self._full_redraw()  # whole layout changed
            return
        if token == SPACE:
            char = " "
        elif token in (BACK, ENTER):
            char = token
        else:
            char = token.upper() if self.shift else token
            if self.shift and len(char) == 1:
                self.shift = False
                self._rebuild()
                self._full_redraw()  # shift auto-released
        if self.on_key:
            self.on_key(char)
