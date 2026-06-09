"""Pillow-backed CPython shim of MicroPython's `framebuf` module.

Implements just enough of the FrameBuffer API for the UI, plus a `text_scaled`
helper that the display layer uses for crisp scaled text in the simulator.
Requires Pillow:  pip install pillow
"""
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:  # pragma: no cover
    raise ImportError("The simulator needs Pillow. Run: pip install pillow") from e

# Format constants (values are arbitrary; only identity matters here)
GS4_HMSB = 1
MONO_HLSB = 2
MONO_VLSB = 3
RGB565 = 4

_FONT_CACHE = {}
_FONT_CANDIDATES = (
    "DejaVuSansMono.ttf",
    r"C:\Windows\Fonts\consola.ttf",
    r"C:\Windows\Fonts\cour.ttf",
    "DejaVuSans.ttf",
)


def _font(scale):
    if scale in _FONT_CACHE:
        return _FONT_CACHE[scale]
    size = max(8, 7 * scale)
    font = None
    for name in _FONT_CANDIDATES:
        try:
            font = ImageFont.truetype(name, size)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    _FONT_CACHE[scale] = font
    return font


def _g(color):
    """Map a GS4 value (0..15) to an 8-bit gray level."""
    return int(max(0, min(15, color)) * 17)


class FrameBuffer:
    def __init__(self, buffer, width, height, fmt=GS4_HMSB, stride=None):
        self.width = width
        self.height = height
        self.fmt = fmt
        self.image = Image.new("L", (width, height), 255)
        self.draw = ImageDraw.Draw(self.image)

    def fill(self, color):
        self.draw.rectangle((0, 0, self.width, self.height), fill=_g(color))

    def pixel(self, x, y, color=None):
        if color is None:
            try:
                return self.image.getpixel((x, y)) // 17
            except Exception:
                return 0
        self.image.putpixel((x, y), _g(color))

    def hline(self, x, y, w, color):
        self.draw.line((x, y, x + w - 1, y), fill=_g(color))

    def vline(self, x, y, h, color):
        self.draw.line((x, y, x, y + h - 1), fill=_g(color))

    def line(self, x1, y1, x2, y2, color):
        self.draw.line((x1, y1, x2, y2), fill=_g(color))

    def rect(self, x, y, w, h, color):
        self.draw.rectangle((x, y, x + w - 1, y + h - 1), outline=_g(color))

    def fill_rect(self, x, y, w, h, color):
        if w <= 0 or h <= 0:
            return
        self.draw.rectangle((x, y, x + w - 1, y + h - 1), fill=_g(color))

    def text(self, s, x, y, color=0):
        self.text_scaled(s, x, y, color, 1)

    def text_scaled(self, s, x, y, color=0, scale=1):
        font = _font(scale)
        fill = _g(color)
        cw = 8 * scale
        for i, ch in enumerate(s):
            self.draw.text((x + i * cw, y - scale), ch, fill=fill, font=font)
