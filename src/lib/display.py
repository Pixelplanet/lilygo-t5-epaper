# display.py - Display abstraction for the ED047TC1 e-paper (540x960, 16 gray).
#
# The drawing surface is a 4-bpp grayscale framebuffer (framebuf.GS4_HMSB).
# All drawing in the app/UI goes through this class so the hardware specifics
# live in exactly one place.
#
# === HW BINDING ===========================================================
# The actual panel push is delegated to a backend `epd` module:
#   * On the device this is the LilyGo C driver (Option A firmware).
#   * In the desktop simulator it is sim/epd.py, which renders to a Tk window.
# The LilyGo firmware's exact symbol names vary between builds; if `epd` is
# present but uses different names, adapt ONLY the _Backend class below.
# ==========================================================================
import framebuf

import config

# Grayscale palette (GS4: 0=black .. 15=white)
BLACK = 0
DARK = 4
GRAY = 8
LIGHT = 12
WHITE = 15

# Refresh modes
FULL = 0      # clean full update (slow, no ghosting)
PARTIAL = 1   # partial update WITH clear (black<->white, can erase, slower)
ADD = 2       # additive partial: only darkens (white->black), instant, no flash


class _Backend:
    """Thin wrapper around whatever `epd` module is available."""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.available = False
        try:
            import epd
            self._epd = epd
            if hasattr(epd, "init"):
                epd.init()
            self.available = True
        except Exception as e:  # noqa: BLE001
            print("display: no `epd` backend (", e, ") - draw-only mode")
            self._epd = None

    def push(self, buffer, mode, x=0, y=0, w=None, h=None):
        if not self.available:
            return
        w = self.width if w is None else w
        h = self.height if h is None else h
        try:
            if mode in (PARTIAL, ADD) and hasattr(self._epd, "display_partial"):
                # ADD = additive (no clear, white->black only, instant).
                self._epd.display_partial(buffer, x, y, w, h, mode == PARTIAL)
            elif hasattr(self._epd, "display"):
                self._epd.display(buffer)
        except Exception as e:  # noqa: BLE001
            print("display: push failed:", e)

    def push_many(self, buffer, regions):
        """Push several partial regions in ONE panel power cycle.

        `regions` is a list of (mode, x, y, w, h). Returns True if the batched
        firmware path ran, False if it isn't available (caller should fall back
        to per-region push()). Eliminates the inter-region power-on/off gap that
        makes separate partial refreshes look like they happen one-after-another.
        """
        if not self.available or not hasattr(self._epd, "display_partial_many"):
            return False
        specs = [(x, y, w, h, 1 if mode == PARTIAL else 0)
                 for (mode, x, y, w, h) in regions]
        try:
            self._epd.display_partial_many(buffer, specs)
            return True
        except Exception as e:  # noqa: BLE001
            print("display: push_many failed:", e)
            return False

    def clear(self):
        if self.available and hasattr(self._epd, "clear"):
            try:
                self._epd.clear()
            except Exception:
                pass

    def repair(self, cycles=4, delay=50):
        """Run the manufacturer charge-neutralization sweep over the whole panel.

        Drives every pixel through alternating full-voltage white<->black cycles
        to disperse trapped electrophoretic particles, removing the ghost
        boundary lines and gray burn-in that repeated partial updates cause.
        """
        if self.available and hasattr(self._epd, "repair"):
            try:
                self._epd.repair(cycles, delay)
                return True
            except Exception as e:  # noqa: BLE001
                print("display: repair failed:", e)
        return False

    def power_off(self):
        if not self.available:
            return
        for name in ("power_off", "deinit", "sleep"):
            if hasattr(self._epd, name):
                try:
                    getattr(self._epd, name)()
                except Exception:
                    pass
                break


class Display:
    def __init__(self, width=config.DISPLAY_WIDTH, height=config.DISPLAY_HEIGHT):
        self.width = width
        self.height = height
        stride_bytes = (width + 1) // 2  # GS4 packs 2 px / byte
        self.buffer = bytearray(stride_bytes * height)
        self.fb = framebuf.FrameBuffer(self.buffer, width, height, framebuf.GS4_HMSB)
        self.backend = _Backend(width, height)
        self.fill(WHITE)

    # --- primitives (delegate to framebuf) -----------------------------------
    def fill(self, color=WHITE):
        self.fb.fill(color)

    def pixel(self, x, y, color):
        self.fb.pixel(x, y, color)

    def hline(self, x, y, w, color):
        self.fb.hline(x, y, w, color)

    def vline(self, x, y, h, color):
        self.fb.vline(x, y, h, color)

    def line(self, x1, y1, x2, y2, color):
        self.fb.line(x1, y1, x2, y2, color)

    def rect(self, x, y, w, h, color):
        self.fb.rect(x, y, w, h, color)

    def fill_rect(self, x, y, w, h, color):
        self.fb.fill_rect(x, y, w, h, color)

    def rounded_rect(self, x, y, w, h, color, r=8, fill=False):
        if fill:
            self.fb.fill_rect(x + r, y, w - 2 * r, h, color)
            self.fb.fill_rect(x, y + r, w, h - 2 * r, color)
        else:
            self.fb.hline(x + r, y, w - 2 * r, color)
            self.fb.hline(x + r, y + h - 1, w - 2 * r, color)
            self.fb.vline(x, y + r, h - 2 * r, color)
            self.fb.vline(x + w - 1, y + r, h - 2 * r, color)
        # corners (quarter circles)
        for dx in range(r + 1):
            for dy in range(r + 1):
                inside = (r - dx) ** 2 + (r - dy) ** 2 <= r * r
                if fill and inside:
                    self.fb.pixel(x + dx, y + dy, color)
                    self.fb.pixel(x + w - 1 - dx, y + dy, color)
                    self.fb.pixel(x + dx, y + h - 1 - dy, color)
                    self.fb.pixel(x + w - 1 - dx, y + h - 1 - dy, color)

    # --- text with integer scaling (framebuf font is fixed 8x8) --------------
    def text(self, s, x, y, color=BLACK, scale=1):
        # Simulator framebuffers expose a native scaled-text path for crisp text.
        if hasattr(self.fb, "text_scaled"):
            self.fb.text_scaled(s, x, y, color, scale)
            return
        if scale <= 1:
            self.fb.text(s, x, y, color)
            return
        # Render each glyph to a temp mono buffer, then blow it up.
        gw, gh = 8, 8
        tmp = bytearray(gw * gh // 8)
        tfb = framebuf.FrameBuffer(tmp, gw, gh, framebuf.MONO_HLSB)
        cx = x
        fr = self.fb.fill_rect
        px = tfb.pixel
        for ch in s:
            tfb.fill(0)
            tfb.text(ch, 0, 0, 1)
            for yy in range(gh):
                ry = y + yy * scale
                xx = 0
                while xx < gw:
                    if px(xx, yy):
                        # Coalesce a horizontal run of set pixels into one
                        # fill_rect instead of one call per pixel.
                        run = 1
                        while xx + run < gw and px(xx + run, yy):
                            run += 1
                        fr(cx + xx * scale, ry, run * scale, scale, color)
                        xx += run
                    else:
                        xx += 1
            cx += gw * scale

    def text_width(self, s, scale=1):
        return len(s) * 8 * scale

    def text_centered(self, s, cx, y, color=BLACK, scale=1):
        self.text(s, cx - self.text_width(s, scale) // 2, y, color, scale)

    # --- panel refresh -------------------------------------------------------
    def refresh(self, mode=FULL, x=0, y=0, w=None, h=None):
        self.backend.push(self.buffer, mode, x, y, w, h)

    def refresh_batch(self, regions):
        """Push several partial regions in one panel power cycle.

        `regions` is a list of (mode, x, y, w, h). Returns True if the batched
        firmware path ran; False means the caller should push each region
        individually (older firmware without display_partial_many).
        """
        return self.backend.push_many(self.buffer, regions)

    def clear(self):
        """Flush the physical panel to clean white.

        E-paper retains its previous image, so on cold boot the panel holds
        random/dark content and a plain draw leaves dark residue (ghosting).
        Driving a full white clear first gives every following draw a clean,
        high-contrast background.
        """
        self.backend.clear()

    def repair(self, cycles=4, delay=50):
        """Run the panel screen-repair sweep (see _Backend.repair).

        Returns True if the hardware repair routine ran, False otherwise.
        """
        return self.backend.repair(cycles, delay)

    def power_off(self):
        self.backend.power_off()
