# icons.py - vector icon set drawn with framebuf primitives, using the panel's
# 16-level grayscale for depth so icons read clearly at a glance.
#
# Each icon fills a `size` x `size` box at (x, y). Add a new icon by writing a
# _draw_<name>(disp, x, y, s) function and listing it in _ICONS.
from lib.ui import theme

# Grayscale ramp (GS4: 0=black .. 15=white). Mid-tones give the icons shading.
G0 = theme.BLACK     # 0
G2 = 2
G4 = theme.DARK      # 4
G6 = 6
G8 = theme.GRAY      # 8
G10 = 10
G12 = theme.LIGHT    # 12
GW = theme.WHITE     # 15


# --------------------------------------------------------------------------- #
# Drawing helpers
# --------------------------------------------------------------------------- #
def _disc(disp, cx, cy, r, color):
    """Filled circle via horizontal spans."""
    r2 = r * r
    for dy in range(-r, r + 1):
        dx = int((r2 - dy * dy) ** 0.5)
        disp.hline(cx - dx, cy + dy, 2 * dx + 1, color)


def _ring(disp, cx, cy, r, thick, color):
    """Filled annulus (outer disc minus inner disc) drawn span-wise."""
    ro2 = r * r
    ri = r - thick
    ri2 = ri * ri
    for dy in range(-r, r + 1):
        ox = int((ro2 - dy * dy) ** 0.5) if dy * dy <= ro2 else 0
        if dy * dy < ri2:
            ix = int((ri2 - dy * dy) ** 0.5)
            disp.hline(cx - ox, cy + dy, ox - ix + 1, color)
            disp.hline(cx + ix, cy + dy, ox - ix + 1, color)
        else:
            disp.hline(cx - ox, cy + dy, 2 * ox + 1, color)


def _fill_poly(disp, pts, color):
    """Scanline polygon fill for an arbitrary closed polygon."""
    ys = [p[1] for p in pts]
    ymin, ymax = min(ys), max(ys)
    n = len(pts)
    for y in range(ymin, ymax + 1):
        xs = []
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            if (y1 <= y < y2) or (y2 <= y < y1):
                t = (y - y1) / (y2 - y1)
                xs.append(int(x1 + t * (x2 - x1)))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            disp.hline(xs[i], y, xs[i + 1] - xs[i] + 1, color)


def _thick_rect(disp, x, y, w, h, color, t=3):
    """Rectangle outline with adjustable thickness."""
    for i in range(t):
        disp.rect(x + i, y + i, w - 2 * i, h - 2 * i, color)


# --------------------------------------------------------------------------- #
# Icons (size-relative geometry, bold + shaded)
# --------------------------------------------------------------------------- #
def _wifi(disp, x, y, s):
    # Signal bars rising left->right, shaded light->dark (matches the title-bar
    # indicator). Bold and instantly readable.
    n = 4
    gap = max(3, s // 16)
    bw = (s - (n - 1) * gap) // n
    base = y + s
    shades = (G10, G8, G4, G0)
    for i in range(n):
        bh = int(s * (i + 1) / n)
        bx = x + i * (bw + gap)
        disp.fill_rect(bx, base - bh, bw, bh, shades[i])
        disp.rect(bx, base - bh, bw, bh, G0)


def _calendar(disp, x, y, s):
    top = y + s // 8
    body_h = s - s // 8
    disp.fill_rect(x, top, s, body_h, GW)
    _thick_rect(disp, x, top, s, body_h, G0, 3)
    hh = s // 4
    disp.fill_rect(x, top, s, hh, G4)
    rw = max(4, s // 12)
    disp.fill_rect(x + s // 4, y, rw, hh, G0)
    disp.fill_rect(x + 3 * s // 4 - rw, y, rw, hh, G0)
    cell = s // 6
    gy = top + hh + cell // 2
    for r in range(2):
        for c in range(3):
            cx = x + s // 6 + c * (s // 4)
            disp.fill_rect(cx, gy + r * (cell + 6), cell, cell, G8)


def _bolt(disp, x, y, s):
    pts = [
        (x + int(s * 0.55), y),
        (x + int(s * 0.18), y + int(s * 0.58)),
        (x + int(s * 0.46), y + int(s * 0.58)),
        (x + int(s * 0.34), y + s),
        (x + int(s * 0.82), y + int(s * 0.38)),
        (x + int(s * 0.52), y + int(s * 0.38)),
        (x + int(s * 0.66), y),
    ]
    _fill_poly(disp, pts, G0)


def _star(disp, x, y, s):
    import math
    cx, cy = x + s // 2, y + s // 2
    ro = s // 2
    ri = int(ro * 0.42)
    pts = []
    for k in range(10):
        ang = -math.pi / 2 + k * math.pi / 5
        r = ro if k % 2 == 0 else ri
        pts.append((int(cx + r * math.cos(ang)), int(cy + r * math.sin(ang))))
    _fill_poly(disp, pts, G4)
    for i in range(len(pts)):
        disp.line(pts[i][0], pts[i][1], pts[(i + 1) % len(pts)][0],
                  pts[(i + 1) % len(pts)][1], G0)


def _gear(disp, x, y, s):
    import math
    cx, cy = x + s // 2, y + s // 2
    r = int(s * 0.34)
    tw = max(6, s // 7)
    tl = max(6, s // 6)
    for k in range(8):
        ang = k * math.pi / 4
        tx = int(cx + (r + tl // 2) * math.cos(ang)) - tw // 2
        ty = int(cy + (r + tl // 2) * math.sin(ang)) - tw // 2
        disp.fill_rect(tx, ty, tw, tw, G4)
    _disc(disp, cx, cy, r, G8)
    _ring(disp, cx, cy, r, 3, G0)
    _disc(disp, cx, cy, max(4, s // 8), GW)
    _ring(disp, cx, cy, max(4, s // 8), 2, G0)


def _app(disp, x, y, s):
    m = s // 8
    disp.rounded_rect(x + m, y + m, s - 2 * m, s - 2 * m, G12, r=10, fill=True)
    disp.rounded_rect(x + m, y + m, s - 2 * m, s - 2 * m, G0, r=10)
    d = max(6, s // 9)
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        px = x + s // 2 - d - 2 + dx * (d + 4)
        py = y + s // 2 - d - 2 + dy * (d + 4)
        disp.fill_rect(px, py, d, d, G4)


def _help(disp, x, y, s):
    # Light disc with a dark ring and a big "?" in the centre.
    cx, cy = x + s // 2, y + s // 2
    r = s // 2
    _disc(disp, cx, cy, r, G12)
    _ring(disp, cx, cy, r, 3, G0)
    sc = max(2, s // 11)
    qw = 8 * sc
    disp.text("?", cx - qw // 2, cy - qw // 2, G0, sc)


_ICONS = {
    "wifi": _wifi,
    "calendar": _calendar,
    "bolt": _bolt,
    "star": _star,
    "gear": _gear,
    "help": _help,
    "app": _app,
}


def names():
    return tuple(_ICONS.keys())


def draw(disp, name, x, y, size):
    fn = _ICONS.get(name, _app)
    fn(disp, x, y, size)
