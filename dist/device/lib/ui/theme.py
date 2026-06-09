# theme.py - shared palette + metrics for the UI.
from lib.display import BLACK, DARK, GRAY, LIGHT, WHITE  # noqa: F401

# Semantic colors (grayscale)
FG = BLACK            # primary text / outlines
FG_MUTED = GRAY       # secondary text
BG = WHITE            # screen background
ACCENT = DARK         # selected / pressed fills
SURFACE = LIGHT       # panels / key faces

# Metrics (pixels)
PAD = 12
TITLE_SCALE = 4
H1_SCALE = 3
BODY_SCALE = 2
SMALL_SCALE = 1

BUTTON_H = 64
ROW_H = 56
KEY_GAP = 6

# Uniform title bar: a band at the top of every screen holding the title text,
# a full-width separator line, and an optional Wi-Fi indicator on the right.
TITLE_BAR_H = 58
