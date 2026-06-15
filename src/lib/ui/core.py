# core.py - UI framework: events, widgets, screens, and the App loop.
import asyncio
import time

from lib import display as d
from lib import profile
from lib.ui import theme

# Event types
DOWN = "down"
MOVE = "move"
UP = "up"


def _rects_overlap(a, b):
    """True if rectangles a=(x,y,w,h) and b=(x,y,w,h) intersect."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw <= bx or bx + bw <= ax
                or ay + ah <= by or by + bh <= ay)


def _merge_rects(rects, gap=8):
    """Coalesce rects that overlap or sit within `gap` px of each other.

    Each panel push costs ~0.3-1.7s, so fewer regions = a far snappier UI. We
    only merge rects that are actually near one another (on BOTH axes), so two
    far-apart updates (e.g. a top label and the bottom chart) stay separate
    instead of fusing into one giant, slow full-height push.
    """
    if len(rects) <= 1:
        return list(rects)
    boxes = list(rects)
    changed = True
    while changed:
        changed = False
        out = []
        while boxes:
            ax, ay, aw, ah = boxes.pop()
            i = 0
            while i < len(out):
                bx, by, bw, bh = out[i]
                near = not (ax + aw + gap <= bx or bx + bw + gap <= ax
                            or ay + ah + gap <= by or by + bh + gap <= ay)
                if near:
                    nx = ax if ax < bx else bx
                    ny = ay if ay < by else by
                    ex = ax + aw if ax + aw > bx + bw else bx + bw
                    ey = ay + ah if ay + ah > by + bh else by + bh
                    ax, ay, aw, ah = nx, ny, ex - nx, ey - ny
                    out.pop(i)
                    changed = True
                    i = 0
                    continue
                i += 1
            out.append((ax, ay, aw, ah))
        boxes = out
    return boxes



def _draw_wifi(disp, x, y, size, state):
    """Draw a small signal-bars Wi-Fi indicator.

    state: "on" (filled bars), "wait" (outlined bars), "off" (muted + slash).
    """
    bw = max(4, size // 6)
    gap = (size - 4 * bw) // 3
    base = y + size
    heights = (size // 4, size // 2, size * 3 // 4, size)
    for i, bh in enumerate(heights):
        bx = x + i * (bw + gap)
        by = base - bh
        if state == "on":
            disp.fill_rect(bx, by, bw, bh, theme.FG)
        elif state == "wait":
            disp.rect(bx, by, bw, bh, theme.FG)
        else:
            disp.rect(bx, by, bw, bh, theme.FG_MUTED)
    if state == "off":
        disp.line(x, y, x + size, y + size, theme.FG_MUTED)


class Event:
    __slots__ = ("type", "x", "y")

    def __init__(self, etype, x, y):
        self.type = etype
        self.x = x
        self.y = y


class InputSource:
    """Base input source. Subclasses return a list of Events per poll."""

    async def poll_events(self):
        return []


class GT911Input(InputSource):
    """Turns GT911 contact polling into down/move/up events."""

    def __init__(self, touch):
        self.touch = touch
        self._was_down = False
        self._last = (0, 0)

    async def poll_events(self):
        # Poll the controller's status register directly every cycle rather than
        # gating on the INT pin (GPIO47). The INT line is not reliably wired on
        # all T5 Plus revisions, so status-register polling is the robust path.
        events = []
        _t = profile.start()
        pts = await self.touch.poll()
        profile.add("touch_poll", _t)
        if pts:
            p = pts[0]
            xy = (p["x"], p["y"])
            if not self._was_down:
                events.append(Event(DOWN, *xy))
                self._was_down = True
            elif xy != self._last:
                events.append(Event(MOVE, *xy))
            self._last = xy
            return events
        if self._was_down:
            events.append(Event(UP, *self._last))
            self._was_down = False
        return events


class Widget:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.visible = True
        self.screen = None

    def contains(self, ev):
        return (self.x <= ev.x < self.x + self.w
                and self.y <= ev.y < self.y + self.h)

    def draw(self, disp):
        pass

    def handle(self, ev):
        """Return True if the event was consumed."""
        return False

    def invalidate(self, fast=False):
        """Mark this widget's area for repaint.

        fast=True requests an *additive* refresh (white->black only, instant,
        no clear flash). Use it when the repaint only adds dark pixels over the
        existing image (e.g. a new character, a new marker). Leave fast=False
        when pixels must return to white (erasing old content).
        """
        if self.screen:
            self.screen.mark_dirty(self.x, self.y, self.w, self.h, fast)


class Screen:
    def __init__(self, app, title=""):
        self.app = app
        self.title = title
        self.widgets = []
        self._dirty_clear = []  # rects needing a clear+draw (can erase)
        self._dirty_add = []    # rects needing additive draw only (instant)
        # Periodic tick: if > 0, the App loop calls on_tick() every tick_ms
        # milliseconds while this screen is active (used e.g. for the clock).
        self.tick_ms = 15000    # update title-bar status every 15s by default
        self._cached_clock = "--:--"
        self._mins_since_full = 0

    def add(self, widget):
        widget.screen = self
        self.widgets.append(widget)
        return widget

    def build(self):
        """Override: create widgets. Called when the screen is shown."""
        pass

    def on_show(self):
        pass

    async def task(self):
        """Override: async work to run once, after the screen is first drawn
        (e.g. fetch RTC time, run a Wi-Fi scan, attempt a connection)."""
        pass

    async def on_tick(self):
        """Override: called every tick_ms while this screen is active.

        Only invoked when tick_ms > 0. Keep it light and non-blocking."""
        pass

    async def _tick_status(self):
        """Update the cached clock and invalidate the title-bar status area.

        Called automatically by the App loop every 15s, separate from on_tick,
        so every screen gets a title-bar status update without having to
        override anything."""
        from lib import netconn

        if self.app.board is None:
            return
        try:
            dt = await self.app.board.rtc.datetime()
            if dt:
                self._cached_clock = "{:02d}:{:02d}".format(dt[4], dt[5])
        except Exception:
            pass

        # Invalidate the status area so it redraws on next flush.
        self.mark_dirty(*self._status_rect(self.app.display), False)

    # dirty-rect tracking ------------------------------------------------------
    def mark_dirty(self, x, y, w, h, fast=False):
        (self._dirty_add if fast else self._dirty_clear).append((x, y, w, h))

    def take_dirty(self):
        clear, add = self._dirty_clear, self._dirty_add
        self._dirty_clear, self._dirty_add = [], []
        return clear, add

    # rendering ---------------------------------------------------------------
    def _wifi_rect(self, disp):
        """Geometry of the title-bar Wi-Fi indicator (right of the title text)."""
        tw = len(self.title) * 8 * theme.H1_SCALE
        size = 30
        x = theme.PAD + tw + 28
        y = (theme.TITLE_BAR_H - size) // 2
        return (x, y, size, size)

    def _title_band(self, disp):
        return (0, 0, disp.width, theme.TITLE_BAR_H + 4)

    def _draw_title_bar(self, disp):
        if not self.title:
            return
        ty = (theme.TITLE_BAR_H - 8 * theme.H1_SCALE) // 2
        disp.text(self.title, theme.PAD, ty, theme.FG, theme.H1_SCALE)
        disp.hline(theme.PAD, theme.TITLE_BAR_H,
                   disp.width - 2 * theme.PAD, theme.FG_MUTED)

        # Clock + Wi-Fi status on every page, to the left of the back button.
        self._draw_status(disp)

    def _draw_status(self, disp):
        """Draw clock + Wi-Fi icon + SSID in the title bar (right side)."""
        from lib import netconn

        # Back button occupies x = d.w - 150 - 12 = 798..948.
        # Put status area to the left of that: x=480..790.
        status_x = disp.width - 320   # 960 - 320 = 640
        status_w = 180                # total width for clock + icon + SSID
        status_h = theme.TITLE_BAR_H - 4

        # Clock.
        dt = None
        try:
            if self.app.board:
                import asyncio
                # Can't await in draw(), use cached time or RTC sync read.
                pass
        except Exception:
            pass

        # Use the launcher's cached clock if available, otherwise "--:--".
        clock = getattr(self, "_cached_clock", None)
        if clock is None:
            clock = "--:--"

        cs = theme.H1_SCALE
        ctw = len(clock) * 8 * cs
        cx = status_x + status_w - ctw
        cy = (theme.TITLE_BAR_H - 8 * cs) // 2
        disp.text(clock, cx, cy, theme.FG, cs)

        # Wi-Fi icon.
        isize = 24
        ix = cx - 8 - isize
        iy = (theme.TITLE_BAR_H - isize) // 2

        ssid = None
        try:
            ssid = netconn.connected_ssid()
        except Exception:
            pass

        state = "on" if ssid else "off"
        _draw_wifi(disp, ix, iy, isize, state)

        # SSID text left of icon.
        if ssid:
            def _trim(t, mx):
                return t if len(t) <= mx else t[:mx - 1] + "~"
            ss = _trim(ssid, 12)
            stw = len(ss) * 8 * theme.BODY_SCALE
            sx = ix - 6 - stw
            sy = (theme.TITLE_BAR_H - 8 * theme.BODY_SCALE) // 2
            disp.text(ss, sx, sy, theme.FG_MUTED, theme.BODY_SCALE)

    def _status_rect(self, disp):
        """Bounding rect of the status area for dirty-rect tracking."""
        status_x = disp.width - 320
        return (status_x - 4, 0, 324, theme.TITLE_BAR_H + 4)

    def add_back_button(self, on_press=None, label="Back"):
        """Add a uniform Back button in the top-right of the title bar.

        Gives every screen the same return affordance so navigation feels
        consistent. Defaults to returning to the launcher home.
        """
        from lib.ui.widgets import Button
        d = self.app.display
        w, h = 150, 50
        y = (theme.TITLE_BAR_H - h) // 2
        return self.add(Button(d.width - w - theme.PAD, y, w, h, label,
                               on_press or self._default_back, theme.BODY_SCALE))

    def _default_back(self):
        from apps import launcher
        self.app.go(launcher.LauncherScreen(self.app))

    def draw(self, disp):
        disp.fill(theme.BG)
        self._draw_title_bar(disp)
        for wgt in self.widgets:
            if wgt.visible:
                wgt.draw(disp)

    def redraw_regions(self, disp, clear, add):
        """Re-render only the parts of the framebuffer covered by dirty rects.

        This is the fast path used between full refreshes: instead of redrawing
        every widget (each scaled-text glyph is expensive), we erase the rects
        that must return to background and redraw only the widgets that actually
        intersect a dirty rect. The unchanged framebuffer pixels are reused.
        """
        rects = clear + add
        # Erase areas that need to go back to background (partial/clear rects).
        for x, y, w, h in clear:
            disp.fill_rect(x, y, w, h, theme.BG)
        # Redraw the title band only if a dirty rect reaches into it.
        if self.title:
            band = self._title_band(disp)
            for r in rects:
                if _rects_overlap(band, r):
                    self._draw_title_bar(disp)
                    break
        # Redraw only widgets that overlap a dirty rect.
        for wgt in self.widgets:
            if not wgt.visible:
                continue
            wb = (wgt.x, wgt.y, wgt.w, wgt.h)
            for r in rects:
                if _rects_overlap(wb, r):
                    wgt.draw(disp)
                    break

    def dispatch(self, ev):
        for wgt in reversed(self.widgets):
            if wgt.visible and (wgt.contains(ev) or ev.type == UP):
                if wgt.handle(ev):
                    return True
        return False


class App:
    def __init__(self, display, input_source, board=None):
        self.display = display
        self.input = input_source
        self.board = board
        self._screen = None
        self._next = None
        self.running = True
        # E-paper maintenance: repeated partial updates build up charge and leave
        # ghost-boundary lines, so force a clean full refresh after this many
        # partial/additive region pushes (manufacturer recommends <= 30).
        self.maint_every = 30
        self._partial_count = 0
        # Events captured by _latch_input() during a long blocking flush, so a
        # tap that lands mid-refresh is dispatched on the next loop pass instead
        # of being lost.
        self._pending = []

    def go(self, screen):
        """Queue a screen transition (full refresh)."""
        self._next = screen

    async def _activate(self, screen):
        self._screen = screen
        screen.build()
        screen.on_show()
        # E-paper holds its previous image; flush to clean white first so the
        # new screen renders with full contrast instead of over dark residue.
        self.display.clear()
        screen.draw(self.display)
        self.display.refresh(d.FULL)
        self._partial_count = 0
        await screen.task()

    def refresh_now(self):
        """Manually clear the panel and redraw the current screen (full refresh).

        Useful when accumulated ghosting makes the display hard to read.
        """
        if self._screen is not None:
            self.display.clear()
            self._screen.draw(self.display)
            self.display.refresh(d.FULL)
            self._screen.take_dirty()  # discard pending partials; we just redrew
            self._partial_count = 0

    def repair_now(self, cycles=10):
        """Run the manufacturer screen-repair sweep, then redraw the screen.

        Use to clear stubborn ghosting / gray burn-in left by partial updates.
        """
        if self._screen is None:
            return
        if not self.display.repair(cycles):
            # No hardware repair available (e.g. simulator) - fall back to clear.
            self.display.clear()
        self._screen.draw(self.display)
        self.display.refresh(d.FULL)
        self._partial_count = 0

    async def _latch_input(self):
        """Poll touch during a multi-push flush and buffer any events.

        The e-paper push is a blocking C call the event loop can't interrupt, so
        without this a tap landing during a slow flush would be dropped. We just
        capture it here and let the run loop dispatch it next pass.
        """
        try:
            evs = await self.input.poll_events()
        except Exception:
            return
        if evs:
            self._pending.extend(evs)

    async def flush(self):
        """Push any pending dirty regions to the panel immediately.

        Normally the run loop does this, but blocking screen tasks (e.g. a Wi-Fi
        connect) can call it to make live status updates appear mid-task.
        """
        clear, add = self._screen.take_dirty()
        if not (clear or add):
            return
        # Coalesce nearby regions so we push as few times as possible.
        clear = _merge_rects(clear)
        add = _merge_rects(add)
        # Re-render only the dirty regions in RAM (not the whole screen).
        _t = profile.start()
        self._screen.redraw_regions(self.display, clear, add)
        profile.add("redraw_ram", _t)
        # Push the fast additive regions first (~0.3s) so darkening changes
        # (typing, selections, button presses) feel immediate, then the slower
        # clearing PARTIAL regions (~1s).
        regions = [(d.ADD, x, y, w, h) for (x, y, w, h) in add]
        regions += [(d.PARTIAL, x, y, w, h) for (x, y, w, h) in clear]
        n = len(regions)
        # Preferred path: push every region in ONE panel power cycle so they
        # update back-to-back with no inter-region gap.
        _t = profile.start()
        batched = self.display.refresh_batch(regions)
        if batched:
            profile.add("push_batch", _t)
        else:
            # Fallback (older firmware): push one region at a time, polling touch
            # between pushes so taps landing mid-refresh aren't dropped.
            for i in range(n):
                mode, x, y, w, h = regions[i]
                _t = profile.start()
                self.display.refresh(mode, x, y, w, h)
                profile.add("push_add" if mode == d.ADD else "push_partial", _t)
                if i < n - 1:
                    await self._latch_input()
        self._partial_count += n
        if self._partial_count >= self.maint_every:
            # Sweep accumulated ghosting with a clean full refresh.
            self.display.clear()
            self._screen.draw(self.display)
            self.display.refresh(d.FULL)
            self._partial_count = 0

    async def run(self, first_screen):
        await self._activate(first_screen)
        self._pending = []
        last_tick = time.ticks_ms()
        last_status = time.ticks_ms()
        while self.running:
            if self._next is not None:
                nxt, self._next = self._next, None
                await self._activate(nxt)
                self._pending = []
                last_tick = time.ticks_ms()
                last_status = time.ticks_ms()
                continue

            # Dispatch any taps buffered during the last (slow) flush first.
            if self._pending:
                pend, self._pending = self._pending, []
                for ev in pend:
                    self._screen.dispatch(ev)

            for ev in await self.input.poll_events():
                self._screen.dispatch(ev)

            # Periodic tick (e.g. clock update) without blocking input polling.
            tm = self._screen.tick_ms
            if tm and self._next is None:
                now = time.ticks_ms()
                if time.ticks_diff(now, last_tick) >= tm:
                    last_tick = now
                    await self._screen.on_tick()

            # Title-bar status (clock + Wi-Fi) updates every 15s on every screen.
            now = time.ticks_ms()
            if self._next is None and time.ticks_diff(now, last_status) >= 15000:
                last_status = now
                await self._screen._tick_status()

            if self._next is None:
                await self.flush()
            await asyncio.sleep_ms(20)
