# Screen refresh on the ED047TC1 e-paper — how it works and what to watch for

This is the single most important thing to understand when building UIs for this
panel. The ED047TC1 is a **controllerless** e-paper: there is no on-glass display
controller managing waveforms for you. The ESP32-S3 drives the pixel rows
directly, so the *quality* of every update depends entirely on the refresh mode
the firmware uses. Get this wrong and you get ghosting, streaks, or a panel that
flashes distractingly.

## The three refresh modes

Defined in [`device/lib/display.py`](../device/lib/display.py):

| Mode | Const | What it does | Speed | Side effects |
|------|-------|--------------|-------|--------------|
| **FULL** | `FULL = 0` | Clean full-panel waveform: every pixel is driven through a complete black↔white cycle. | ~1 s, visible flash | None. The **only** mode that removes ghosting/streaks. |
| **PARTIAL** | `PARTIAL = 1` | Partial-region update *with* clear — can change a pixel in either direction (darken **or** lighten). | Faster than FULL | Leaves faint vertical streaks at region boundaries that accumulate. |
| **ADD** | `ADD = 2` | Additive partial — only ever drives white→black (darkens). Instant, no flash. | Instant | Cannot erase. Leaves streaks. |

Key mental model:

- **Only FULL erases ghosting.** Partial and additive updates always leave some
  charge residue, which shows up as faint vertical lines at the edges of the
  updated rectangle. They never go away on their own.
- **ADD can only darken.** Use it when you're adding dark pixels onto white
  (e.g. typing a character onto a text field). It's instant and flash-free.
- **PARTIAL can erase** (needed for backspace, redrawing a changed region), but
  it's slower and still streaks.

## How the UI toolkit manages this

The app framework ([`device/lib/ui/core.py`](../device/lib/ui/core.py)) tracks
"dirty" rectangles in two lists and picks the cheapest correct mode:

- `mark_dirty(x, y, w, h, fast=False)` → **PARTIAL** (can erase).
- `mark_dirty(x, y, w, h, fast=True)` → **ADD** (instant, darken-only).

A widget calls `invalidate(fast=...)` when it changes. On each loop tick the app
flushes pending dirty rects with the right mode. To keep streaks from
accumulating, the app does a clean **FULL** refresh:

- On **every screen transition** (`_activate` → always FULL).
- Automatically after `maint_every` (30) partial pushes (`flush()` self-heals).
- On demand via `refresh_now()` (the **Refresh** button on the home screen).

### Worked example: the on-screen keyboard

The keyboard ([`device/lib/ui/keyboard.py`](../device/lib/ui/keyboard.py)) is the
canonical lesson. Early versions repainted each key on press (a partial refresh
per keystroke) and forced a periodic FULL refresh to wipe the resulting streaks.
Both were wrong:

- Per-key partial refresh → **vertical streaks** at every key edge.
- Periodic FULL refresh → **distracting full-screen flashes** while typing.

The fix: **the keyboard never repaints individual keys.** It's drawn once when
the screen opens. Press feedback comes entirely from the **password field
updating instantly** (an `ADD` refresh that only adds the new dark glyph). The
only time the keyboard repaints is when its labels actually change (Shift / symbol
toggle), and that uses a single clean FULL refresh — which is fine because it's
rare.

**Takeaway for new screens:** prefer additive (`fast=True`) updates for small,
darkening changes; let screen transitions and the periodic auto-FULL handle
streak cleanup; avoid forcing FULL refreshes on a fast, repeated interaction.

## Ghosting and the "repair" sweep

Repeated partial updates trap electrophoretic particles, leaving ghost-boundary
lines and a faint gray burn-in of old content. Two ways to clear it:

1. **A FULL refresh** clears normal ghosting (press the **Refresh** button, or
   just navigate between screens).
2. **The repair sweep** (`display.repair(cycles)`, the **Repair** button) drives
   the *whole panel* through several alternating white↔black cycles to disperse
   stubborn trapped particles. Use this if a FULL refresh isn't enough. It takes
   a few seconds and flashes several times — that's expected.

## Things to look out for

- **Cold boot shows dark residue.** E-paper holds its last image with no power.
  The app calls `display.clear()` (drive to clean white) before the first draw on
  every screen, so the new content has full contrast. If you write your own
  bring-up code, clear first.
- **Don't call `epd.init()` twice.** The firmware initializes the panel once at
  startup. Calling `epd.init()` again from the REPL while the app is running
  re-initializes the RMT driver and **aborts/reboots** the board. To test the
  panel from the REPL, disable auto-start first (hold BOOT during reset to reach
  the REPL) so the app never inits it.
- **Partial updates near the screen edge** streak the most. If a region streaks
  badly, a FULL refresh fixes it; consider whether that region really needs a
  partial update.
- **Grayscale is 4-bit (16 levels), packed 2 px/byte** (`framebuf.GS4_HMSB`).
  `0` = black, `15` = white. The palette helpers are `BLACK/DARK/GRAY/LIGHT/WHITE`.
- **Battery ADC conflicts with Wi-Fi.** GPIO14 is on ADC2, which the Wi-Fi radio
  also uses. Never read the battery while Wi-Fi is active (the driver enforces
  this) — unrelated to refresh, but a common bring-up surprise.
