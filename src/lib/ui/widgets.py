# widgets.py - reusable UI widgets.
from lib.ui import theme
from lib.ui.core import DOWN, MOVE, UP, Widget


class Label(Widget):
    def __init__(self, x, y, text, scale=theme.BODY_SCALE, color=theme.FG):
        super().__init__(x, y, len(text) * 8 * scale, 8 * scale)
        self.text = text
        self.scale = scale
        self.color = color

    def set_text(self, text):
        old_w = self.w
        self.text = text
        self.w = len(text) * 8 * self.scale
        # Erase the union of the old and new extents so shrinking text doesn't
        # leave leftover glyphs from a previous, longer value.
        if self.screen:
            w = old_w if old_w > self.w else self.w
            self.screen.mark_dirty(self.x, self.y, w, self.h, False)

    def draw(self, disp):
        disp.text(self.text, self.x, self.y, self.color, self.scale)


class Button(Widget):
    def __init__(self, x, y, w, h, text, on_press=None, scale=theme.BODY_SCALE):
        super().__init__(x, y, w, h)
        self.text = text
        self.on_press = on_press
        self.scale = scale
        self.pressed = False

    def draw(self, disp):
        # Pressed = darken the face only (text stays dark and visible). Because
        # this is a pure darkening change, the press can be shown with a fast
        # additive refresh (~0.3s) instead of a slow clearing one (~1s).
        face = theme.FG_MUTED if self.pressed else theme.SURFACE
        disp.rounded_rect(self.x, self.y, self.w, self.h, face, r=10, fill=True)
        disp.rounded_rect(self.x, self.y, self.w, self.h, theme.FG, r=10)
        tw = len(self.text) * 8 * self.scale
        disp.text(self.text, self.x + (self.w - tw) // 2,
                  self.y + (self.h - 8 * self.scale) // 2, theme.FG, self.scale)

    def handle(self, ev):
        if ev.type == DOWN and self.contains(ev):
            self.pressed = True
            # Additive => the press registers instantly instead of waiting on a
            # full clearing refresh.
            self.invalidate(fast=True)
            return True
        if ev.type == UP:
            if self.pressed:
                self.pressed = False
                self.invalidate()
                if self.contains(ev) and self.on_press:
                    self.on_press()
                return True
        return False


class ProgressBar(Widget):
    def __init__(self, x, y, w, h, value=0):
        super().__init__(x, y, w, h)
        self.value = value  # 0..100

    def set_value(self, v):
        old = self.value
        self.value = max(0, min(100, v))
        # Increasing = only adds dark pixels → additive (instant, no flash).
        # Decreasing = old dark pixels must be erased → full clear.
        self.invalidate(fast=(self.value >= old))

    def draw(self, disp):
        disp.rect(self.x, self.y, self.w, self.h, theme.FG)
        fill_w = (self.w - 4) * self.value // 100
        disp.fill_rect(self.x + 2, self.y + 2, fill_w, self.h - 4, theme.ACCENT)


class TextField(Widget):
    def __init__(self, x, y, w, h, masked=False, scale=theme.BODY_SCALE):
        super().__init__(x, y, w, h)
        self.text = ""
        self.masked = masked
        self.scale = scale

    def _maxchars(self):
        return (self.w - 16) // (8 * self.scale)

    def set_text(self, text):
        old = self.text
        self.text = text
        # Pure append that still fits without scrolling = additive (instant):
        # we only ever add dark glyph pixels onto the existing white field.
        # Backspace / scrolling / mask toggle must erase, so fall back to clear.
        fast = (len(text) > len(old)
                and text[:len(old)] == old
                and len(text) <= self._maxchars())
        self.invalidate(fast=fast)

    def draw(self, disp):
        disp.rect(self.x, self.y, self.w, self.h, theme.FG)
        shown = ("*" * len(self.text)) if self.masked else self.text
        # clip to width
        maxchars = self._maxchars()
        if len(shown) > maxchars:
            shown = shown[-maxchars:]
        disp.text(shown, self.x + 8, self.y + (self.h - 8 * self.scale) // 2,
                  theme.FG, self.scale)


class ListView(Widget):
    """Vertical scrollable list. Renderer draws one row; tap selects it."""

    def __init__(self, x, y, w, h, items, render_row, on_select=None,
                 row_h=theme.ROW_H):
        super().__init__(x, y, w, h)
        self.items = items
        self.render_row = render_row
        self.on_select = on_select
        self.row_h = row_h
        self.offset = 0
        self._drag_start = None
        self._start_off = 0
        self._moved = False

    def set_items(self, items):
        self.items = items
        self.offset = 0
        self.invalidate()

    @property
    def max_offset(self):
        total = len(self.items) * self.row_h
        return max(0, total - self.h)

    def draw(self, disp):
        disp.fill_rect(self.x, self.y, self.w, self.h, theme.BG)
        disp.rect(self.x, self.y, self.w, self.h, theme.FG_MUTED)
        first = self.offset // self.row_h
        y = self.y - (self.offset % self.row_h)
        i = first
        while y < self.y + self.h and i < len(self.items):
            if y + self.row_h > self.y:
                self.render_row(disp, self.items[i], i, self.x, y, self.w, self.row_h)
                disp.hline(self.x, y + self.row_h - 1, self.w, theme.LIGHT)
            y += self.row_h
            i += 1
        # scrollbar
        if self.max_offset > 0:
            track = self.h
            knob = max(20, track * self.h // (len(self.items) * self.row_h))
            pos = self.y + (track - knob) * self.offset // self.max_offset
            disp.fill_rect(self.x + self.w - 5, pos, 4, knob, theme.GRAY)

    def handle(self, ev):
        if ev.type == DOWN and self.contains(ev):
            self._drag_start = ev.y
            self._start_off = self.offset
            self._moved = False
            return True
        if ev.type == MOVE and self._drag_start is not None:
            dy = self._drag_start - ev.y
            if abs(dy) > 6:
                self._moved = True
            self.offset = max(0, min(self.max_offset, self._start_off + dy))
            self.invalidate()
            return True
        if ev.type == UP and self._drag_start is not None:
            tapped = not self._moved and self.contains(ev)
            self._drag_start = None
            if tapped and self.on_select:
                idx = (self.offset + (ev.y - self.y)) // self.row_h
                if 0 <= idx < len(self.items):
                    self.on_select(idx)
            return True
        return False


class WifiIcon(Widget):
    """Small signal-bars indicator. state: "on" | "off" | "wait"."""

    def __init__(self, x, y, state="off", size=36):
        super().__init__(x, y, size, size)
        self.state = state

    def set_state(self, state):
        if state != self.state:
            self.state = state
            self.invalidate()

    def draw(self, disp):
        bw = max(5, self.w // 6)
        gap = (self.w - 4 * bw) // 3
        base = self.y + self.h
        heights = (self.h // 4, self.h // 2, self.h * 3 // 4, self.h)
        for i, bh in enumerate(heights):
            bx = self.x + i * (bw + gap)
            by = base - bh
            if self.state == "on":
                disp.fill_rect(bx, by, bw, bh, theme.FG)
            elif self.state == "wait":
                disp.rect(bx, by, bw, bh, theme.FG)
            else:
                disp.rect(bx, by, bw, bh, theme.FG_MUTED)
        if self.state == "off":
            # Diagonal slash to signal "no connection".
            disp.line(self.x, self.y, self.x + self.w, self.y + self.h,
                      theme.FG_MUTED)
