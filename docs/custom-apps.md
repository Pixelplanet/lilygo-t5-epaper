# Creating Custom Apps for LilyGo T5

This guide covers everything you need to know to create, test, and publish
custom apps for the LilyGo T5 4.7" Plus e-paper platform.

---

## Table of Contents

1. [Architecture overview](#architecture-overview)
2. [Minimal app template](#minimal-app-template)
3. [Screen lifecycle](#screen-lifecycle)
4. [Available widgets](#available-widgets)
5. [Working with touch events](#working-with-touch-events)
6. [E-paper refresh model](#e-paper-refresh-model)
7. [Periodic updates (on_tick)](#periodic-updates-on_tick)
8. [Navigation and going back](#navigation-and-going-back)
9. [RTC, Wi-Fi, and battery](#rtc-wi-fi-and-battery)
10. [OTA system updates](#ota-system-updates)
11. [Declarative screens (ui.json)](#declarative-screens-uijson)
12. [Declarative hooks (Python callbacks)](#declarative-hooks-python-callbacks)
12. [Testing in the simulator](#testing-in-the-simulator)
13. [Publishing to the app catalog](#publishing-to-the-app-catalog)
14. [App catalog manifest reference](#app-catalog-manifest-reference)
15. [Troubleshooting](#troubleshooting)

---

## Architecture overview

```
main.py
  └─ App (core.py)            ← main event loop, render loop
       ├─ Board (board.py)    ← display, touch, RTC, battery
       └─ CURRENT Screen       ← only one screen visible at a time
            ├─ Widget A
            ├─ Widget B
            └─ Widget C
```

- **`App`** runs the cooperative `asyncio` loop: polls touch → dispatches events →
  redraws dirty areas.
- **`Screen`** owns a list of `Widget` instances. Only ONE screen is active.
- **`Widget`** knows its bounding rect, draws itself, and handles touch events.
- **`Board`** gives access to hardware: `display`, `rtc`, `battery`, etc.

---

## Minimal app template

Every app lives as a Python file in `src/apps/` (or just `apps/` on the device).
It must expose an entry-point function that receives `app` and returns a `Screen`.

```python
# src/apps/my_app.py
from lib.ui import theme
from lib.ui.core import Screen
from lib.ui.widgets import Label, Button


def open_my_app(app):
    """Entry point: called when the user taps the app tile."""
    return MyScreen(app)


class MyScreen(Screen):
    def __init__(self, app):
        super().__init__(app, "My App")  # title shown in the title bar

    def build(self):
        """Create and add widgets. Called once when the screen is shown."""
        d = self.app.display

        # Always provide a way back to the launcher.
        self.add_back_button()

        # Add a centered label.
        x = (d.width - 200) // 2
        self.add(Label(x, 120, "Hello, world!", theme.H1_SCALE))

        # Add a button that does something.
        self.add(Button(
            theme.PAD, 300,              # x, y
            d.width - 2 * theme.PAD, 72, # w, h
            "Tap me!",                    # text
            self._on_tap,                 # callback
            theme.H1_SCALE                # text scale
        ))

    def _on_tap(self):
        print("Button tapped!")
```

**To add your app to the launcher**, open `tools/ui-builder.html`, go to the
Apps tab, and add a tile with:
- **ID**: `my_app`
- **Name**: `My App`
- **Icon**: pick one
- **Opens**: Built-in app → entry: `my_app:open_my_app`

Or edit `ui.json` by hand:
```json
{
  "apps": [
    {
      "id": "my_app",
      "name": "My App",
      "icon": "star",
      "kind": "builtin",
      "entry": "my_app:open_my_app"
    }
  ]
}
```

The entry format `my_app:open_my_app` means "import `apps.my_app` and call
`open_my_app(app)`".

---

## Screen lifecycle

```
Screen.__init__()     → store state, set self.tick_ms if needed
Screen.build()        → create widgets via self.add()
Screen.on_show()      → (optional) called right after build
Screen.task()         → (optional) async work after first draw
Screen.on_tick()      → (optional) periodic callback if tick_ms > 0
```

**Important:** `build()` is called exactly once per screen instance. If you
navigate away and come back, a *new* Screen instance is created, so `build()`
runs again. Use `__init__` to save state that should persist across navigations.

---

## Available widgets

All widgets are in `lib.ui.widgets`. Each takes `(x, y, ...)` in pixels.

| Widget | Constructor | Description |
|---|---|---|
| `Label` | `Label(x, y, text, scale, color)` | Static text. `scale` is 1-4, `color` is a theme constant. |
| `Button` | `Button(x, y, w, h, text, callback, scale)` | Tappable rounded button. Press triggers `callback()`. |
| `ProgressBar` | `ProgressBar(x, y, w, h, value)` | Horizontal bar 0-100. Call `.set_value(v)` to update. |
| `TextField` | `TextField(x, y, w, h, masked, scale)` | Single-line text entry. `masked=True` shows `*`. |
| `ListView` | `ListView(x, y, w, h, items, render_fn, on_select, row_h)` | Scrollable list. See [ListView details](#listview). |
| `Keyboard` | `Keyboard(x, y, w, h, on_key)` | On-screen QWERTY keyboard. Used with `TextField`. |
| `WifiIcon` | `WifiIcon(x, y, state, size)` | Signal-bars indicator. State: `"on"`, `"off"`, `"wait"`. |

### Label

```python
from lib.ui.widgets import Label
from lib.ui import theme

Label(12, 100, "Hello", theme.H1_SCALE, theme.FG)

# Update text after creation:
label.set_text("New text")

# Text scales:
# theme.SMALL_SCALE = 1  →  8px characters
# theme.BODY_SCALE  = 2  → 16px characters
# theme.H1_SCALE    = 3  → 24px characters
# theme.TITLE_SCALE = 4  → 32px characters

# Grayscale colors:
# theme.FG        = black
# theme.FG_MUTED  = gray
# theme.ACCENT    = dark gray
# theme.SURFACE   = light gray
```

### Button

```python
def my_callback():
    print("Pressed!")

Button(12, 200, 300, 72, "Click me", my_callback, theme.H1_SCALE)

# Press feedback is automatic (the button face darkens instantly via additive
# refresh, ~0.3s). Release fires the callback if still inside the button rect.
```

### ProgressBar

```python
pb = ProgressBar(12, 100, 400, 40, 0)  # width, height, initial value 0-100
self.add(pb)

# Later:
pb.set_value(75)  # updates the bar and invalidates for redraw
```

### ListView

```python
items = ["Wi-Fi A", "Wi-Fi B", "Guest Network"]

def render_row(disp, item, idx, x, y, w, h):
    """Called once per visible row to draw it."""
    disp.text(str(item), x + 12, y + 10, theme.FG, theme.BODY_SCALE)

def on_select(idx):
    print("User picked:", items[idx])

list_view = ListView(12, 100, 400, 300, items, render_row, on_select, row_h=56)
self.add(list_view)

# Update items later:
list_view.set_items(["New item 1", "New item 2"])
```

### TextField + Keyboard

```python
from lib.ui.widgets import TextField
from lib.ui.keyboard import Keyboard, ENTER, BACK

tf = TextField(12, 100, 400, 64, masked=False, scale=theme.BODY_SCALE)
self.add(tf)

def on_key(key):
    if key == ENTER:
        print("User entered:", tf.text)
        # Navigate or submit here
    elif key == BACK:
        tf.set_text(tf.text[:-1])  # delete last character
    else:
        tf.set_text(tf.text + key)
        # set_text handles buffering automatically

kb = Keyboard(12, 180, 400, 300, on_key)
self.add(kb)
```

---

## Working with touch events

For most cases, use `Button` widgets — they handle touch automatically.

For custom touch handling, override `handle(self, ev)` on a Widget:

```python
from lib.ui.core import DOWN, MOVE, UP, Widget


class MyCustomWidget(Widget):
    def __init__(self, x, y, w, h):
        super().__init__(x, y, w, h)
        self._drag_start = None

    def draw(self, disp):
        """Draw the widget."""
        disp.fill_rect(self.x, self.y, self.w, self.h, theme.SURFACE)
        disp.rect(self.x, self.y, self.w, self.h, theme.FG)

    def handle(self, ev):
        # ev.type is one of DOWN, MOVE, UP
        # ev.x, ev.y are touch coordinates in display pixels
        if ev.type == DOWN and self.contains(ev):
            self._drag_start = (ev.x, ev.y)
            self.invalidate()  # schedule redraw
            return True        # consumed the event

        if ev.type == MOVE and self._drag_start:
            # Handle drag...
            self.invalidate()
            return True

        if ev.type == UP and self._drag_start:
            self._drag_start = None
            self.invalidate()
            return True

        return False  # event not handled, passes to next widget
```

**Event routing order:** The App loop dispatches events to widgets in
reverse-add order (last added = top-most). The first widget whose `handle()`
returns `True` consumes the event.

---

## E-paper refresh model

The LilyGo T5 has a grayscale e-paper panel. Refreshing is SLOW compared to LCDs.

| Mode | Method | Speed | Effect |
|---|---|---|---|
| Full | `self.invalidate()` | ~1-2s | Flickers, clears all ghosts. Good for screen transitions. |
| Partial clear | `self.invalidate()` (default) | ~1s | Clears white in region, redraws. Good for text changes. |
| Additive | `self.invalidate(fast=True)` | ~0.3s | Only adds dark pixels. Instant, no flash. Use for press feedback. |

### Guidelines

1. **Call `invalidate()` whenever a widget's appearance changes.** The framework
   batches dirty rects and pushes them to the panel in one refresh cycle.

2. **Use `fast=True` for instant darkening changes** (button press, adding a
   character to a TextField). Never use it when you need to erase old pixels.

3. **Every ~10 partial updates, do a full refresh** to clear accumulated
   ghosting. Use `self.app.refresh_now()` in your periodic tick:

   ```python
   async def on_tick(self):
       self._mins_since_full += 1
       if self._mins_since_full >= 10:
           self._mins_since_full = 0
           self.app.refresh_now()  # full sweep
   ```

4. **The display is 960×540 landscape, 4-bit grayscale (16 shades).**
   Coordinates are `(x, y)` with `(0, 0)` at the top-left.

---

## Periodic updates (on_tick)

For screens that need a clock or status refresh:

```python
class MyScreen(Screen):
    def __init__(self, app):
        super().__init__(app, "My App")
        self.tick_ms = 15000       # callback every 15 seconds

    async def on_tick(self):
        """Called every tick_ms while this screen is visible."""
        dt = await self.app.board.rtc.datetime()
        if dt:
            self.clock_label.set_text("{:02d}:{:02d}".format(dt[4], dt[5]))
```

Keep `on_tick()` light and non-blocking. It runs in the main event loop.

---

## Navigation and going back

```python
# Navigate to another screen:
self.app.go(AnotherScreen(self.app))

# Add a back button (returns to the launcher):
self.add_back_button()

# Add a custom back button:
self.add_back_button(callback=my_custom_back_fn)

# The back button is positioned at the top-right of the title bar.
# If your screen has no title bar (rare), you can disable it:
# Set self.title = None in __init__ and don't call add_back_button.
```

The title bar is 58px tall. Place your first widget at `y >= theme.TITLE_BAR_H`
(58px) to avoid overlap.

---

## RTC, Wi-Fi, and battery

### Reading the real-time clock
```python
dt = await self.app.board.rtc.datetime()
# Returns (year, month, day, weekday, hour, minute, second, subsecond)
# or None if the RTC is not available.

# weekday is 0=Monday .. 6=Sunday (MicroPython convention)
```

### Wi-Fi connectivity
```python
from lib import netconn

# Check if we're connected:
ssid = netconn.connected_ssid()  # returns None if not connected

# Auto-connect (uses saved credentials):
connected = await netconn.auto_connect()

# The launcher auto-connects at startup. By the time your app opens,
# Wi-Fi is usually already up.
```

### Battery level
```python
pct = self.app.board.battery.percent()
# Returns 0-100 or None if reading failed.
# NOTE: Battery ADC conflicts with active Wi-Fi. Read battery BEFORE
# enabling Wi-Fi, or the reading will fail.
```
---

## OTA system updates

The platform supports over-the-air updates so users don't need to reflash
the board for every change. The Update app (`apps/update_app.py`) handles
this through a simple manifest-based diff.

### How it works

1. The device has a `version.json` file listing every platform file and its
   SHA-256 hash.
2. A remote `update.json` (hosted on GitHub) lists the latest file hashes.
3. The Update app fetches the remote manifest, diffs it against the local
   `version.json`, and downloads only changed files.
4. Files are written atomically (temp file → rename) to avoid corruption.
5. After all downloads, `version.json` is updated and the user resets.

### Adding your app to the update manifest

When you contribute an app that becomes part of the platform (not the catalog),
add its files to the deploy so `version.json` tracks them:

1. Place your `.py` files in `src/apps/` or `src/lib/`.
2. Run `tools/deploy.ps1` — it auto-generates `version.json` and `update.json`
   with SHA-256 hashes.
3. Commit and push `update.json` to publish the update.

For catalog apps (installed via the App Store), the catalog system handles
updates separately — users re-install from the store to get new versions.

### Version numbering

The `version` field in `update.json` is an integer. Increment it when you
push a platform update. The device only downloads when the remote version
is strictly greater than the local version.

### Programmatic use

Your app can also trigger update checks:
```python
from lib import updater

pending = await updater.check()
if pending:
    print("Update available: v" + str(pending["version"]))
    print("Changed files:", list(pending["files"].keys()))
```
---

## Declarative screens (ui.json)

Instead of writing Python, you can describe screens in `ui.json` using the
[UI Builder](../tools/ui-builder.html) or by hand. See
[Building UI Pages by Hand](./manual-ui-pages.md) for the full schema.

Declarative screens support three button action types:
- `"menu"` → back to launcher home
- `"screen:<id>"` → navigate to another declared screen
- `"hook:<name>"` → call a Python callback (see below)

---

## Declarative hooks (Python callbacks)

When a declarative screen button has `"action": "hook:my_hook"`, the framework
calls `my_hook(app)` from the hook registry. Register hooks in
`src/user_hooks.py`:

```python
# src/user_hooks.py
from lib.ui import declarative


def _update_counter(app):
    """Find the 'counter' label on the current screen and update it."""
    scr = app._screen
    lbl = scr.find("counter")
    if lbl:
        # Parse current value, increment, update.
        try:
            n = int(lbl.text) + 1
        except ValueError:
            n = 1
        lbl.set_text(str(n))


def register_all():
    declarative.register_hook("increment", _update_counter)
```

In your `ui.json`, give the label an `"id"` and create a button with a hook:
```json
{
  "screens": {
    "counter_demo": {
      "title": "Counter",
      "widgets": [
        {"type": "label", "id": "counter", "x": 400, "y": 200,
         "text": "0", "scale": "title"},
        {"type": "button", "x": 300, "y": 300, "w": 360, "h": 80,
         "text": "+1", "action": "hook:increment"}
      ]
    }
  }
}
```

---

## Testing in the simulator

You CANNOT test custom Python apps in the web UI Builder. The builder only
edits `ui.json` (declarative screens).

To test Python apps without hardware:
1. Place your app in `src/apps/my_app.py`
2. Add a launcher tile via `ui.json` or the UI Builder
3. Run the desktop simulator:

```powershell
python sim/run_sim.py
```

The simulator uses the **same** `src/` code as the device. Mouse clicks act as
touch events. See [README.md](../README.md) for setup.

> **Tip:** Write your app against the simulator first, then flash to hardware.
> The simulator is faster to iterate on and catches most logic bugs.

---

## Publishing to the app catalog

Once your app is tested, you can publish it so others can install it from the
on-device App Store.

### Step 1: Host your app files

Your app files must be publicly accessible via HTTPS. GitHub raw URLs work
great:

```
https://raw.githubusercontent.com/<user>/<repo>/main/apps/my_app.py
```

### Step 2: Add an entry to the catalog index

The catalog is `apps-catalog/index.json`. Add your app to the `apps` array:

```json
{
  "version": 1,
  "name": "LilyGo T5 community app catalog",
  "apps": [
    {
      "id": "my_app",
      "name": "My Awesome App",
      "icon": "star",
      "author": "your-github-username",
      "description": "Does something cool on your e-paper display.",
      "entry": "my_app:open_my_app",
      "files": [
        "apps/my_app.py",
        "lib/my_extra_lib.py"
      ]
    }
  ]
}
```

### Step 3: Open a pull request

1. Fork the [lilygo-t5-epaper](https://github.com/Pixelplanet/lilygo-t5-epaper) repo.
2. Add your entry to `apps-catalog/index.json`.
3. Place your app files in `apps-catalog/apps/` (or link to your own repo).
4. Open a PR.

### Step 4: Users install your app

Users open the App Store on their device, see your app in the catalog, tap to
view details, and tap **Install**. The app store downloads each file in the
`files` list and adds a launcher tile automatically.

---

## App catalog manifest reference

Each app entry in `apps-catalog/index.json`:

| Field | Required | Description |
|---|---|---|
| `id` | Yes | Unique identifier. Use lowercase snake_case. Must match across catalog versions. |
| `name` | Yes | Human-readable name shown on the tile and in the store. |
| `icon` | Yes | Icon name: `wifi`, `calendar`, `bolt`, `star`, `gear`, `help`, `app`. |
| `author` | Yes | Your name or GitHub handle. |
| `description` | Yes | One sentence (max ~110 chars). Shown in the store listing. |
| `entry` | Yes | `"module:function"` — imports `apps.<module>` and calls `function(app)`. |
| `files` | Yes | Array of device paths. Relative to flash root. Each file is downloaded on install. |

**Important:** The `files` array tells the installer which files to download.
All paths are relative to the device flash root. Common patterns:

- `apps/my_app.py` — a single-file app
- `apps/my_app.py`, `lib/my_extra.py` — app with a helper library
- `apps/my_app/__init__.py`, `apps/my_app/data.json` — app in a subdirectory

---

## Troubleshooting

### "My app doesn't appear in the launcher"
- Check that `entry` in `ui.json` matches `my_module:my_function`.
- Ensure the file is at `apps/my_module.py` (not `src/apps/` — the device sees only the flash root).
- Run `tools/deploy.ps1` to upload files to the device.

### "ImportError: no module named 'apps.xxx'"
- The file is missing from flash. Deploy with `tools/deploy.ps1`.
- Check the filename matches the `entry` field exactly (case-sensitive).

### "The screen is blank / widgets don't appear"
- Are you calling `self.add(widget)` in `build()`?
- Is the widget's `y` coordinate within 0-539? (The display is 960×540.)

### "Touch doesn't work in my custom widget"
- Does your `handle()` return `True` when it consumes the event?
- Is `self.contains(ev)` true for the touch coordinates?

### "The e-paper is ghosting badly"
- Call `self.app.refresh_now()` periodically (every ~10 partial updates).
- For severe burn-in, use the Repair button in the Wi-Fi app or call `self.app.board.display.repair()`.
- See [E-paper refresh model](#e-paper-refresh-model).
