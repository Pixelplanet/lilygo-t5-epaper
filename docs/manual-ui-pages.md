# Building UI Pages by Hand

You can build screens for the LilyGo T5 **without writing Python** by editing
`ui.json` directly or using the [UI Builder](../tools/ui-builder.html). This
guide covers the full `ui.json` schema, all widget types, colors, actions, and
everything you need to build screens by hand.

---

## Table of Contents

1. [ui.json structure](#uijson-structure)
2. [The apps array](#the-apps-array)
3. [The screens object](#the-screens-object)
4. [Widget reference](#widget-reference)
   - [Label](#label)
   - [Button](#button)
   - [ProgressBar](#progressbar)
5. [Button actions](#button-actions)
6. [Colors and scales](#colors-and-scales)
7. [Coordinate system](#coordinate-system)
8. [Widget IDs and hooks](#widget-ids-and-hooks)
9. [Complete example](#complete-example)
10. [Using the UI Builder](#using-the-ui-builder)
11. [Integration with Python apps](#integration-with-python-apps)

---

## ui.json structure

```json
{
  "apps": [
    /* ... app tile declarations ... */
  ],
  "screens": {
    "screen_id_1": {
      "title": "My Screen",
      "back": true,
      "widgets": [
        /* ... widget objects ... */
      ]
    },
    "screen_id_2": { /* ... */ }
  }
}
```

- **`apps`** — defines tiles on the launcher home screen.
- **`screens`** — one entry per custom screen. The key (e.g. `"screen_id_1"`)
  is used to reference the screen from app tiles and button actions.

---

## The apps array

Each app tile in `apps` links to either a built-in Python app or a declarative
screen.

```json
{
  "id": "my_screen",
  "name": "My Screen",
  "icon": "star",
  "kind": "screen",
  "screen": "screen_id_1"
}
```

| Field | Description |
|---|---|
| `id` | Unique identifier (lowercase, no spaces). |
| `name` | Text shown under the icon on the home tile. |
| `icon` | One of: `wifi`, `calendar`, `bolt`, `star`, `gear`, `help`, `app`. |
| `kind` | `"builtin"` for Python apps, `"screen"` for declarative screens. |
| `entry` | (for `"builtin"`) Module:function, e.g. `"clock_app:open_clock"`. |
| `screen` | (for `"screen"`) The screen ID to open. |
| `slot` | (optional) Fixed grid slot 0-7. 0=top-left, 3=top-right, 4=bottom-left, 7=bottom-right. Omit for auto-placement. |

**Built-in app tile example:**
```json
{
  "id": "clock",
  "name": "Big Clock",
  "icon": "gear",
  "kind": "builtin",
  "entry": "clock_app:open_clock"
}
```

**Declarative screen tile example:**
```json
{
  "id": "counter",
  "name": "Counter",
  "icon": "star",
  "kind": "screen",
  "screen": "counter_demo"
}
```

---

## The screens object

Each screen has:

| Field | Required | Description |
|---|---|---|
| `title` | Yes | Text in the title bar (top of screen). |
| `back` | No | Show a back button? Default `true`. Set `false` for screens that are navigated to programmatically. |
| `widgets` | Yes | Array of widget objects (can be empty `[]`). |

---

## Widget reference

Every widget has these common fields:

```json
{
  "type": "label",
  "x": 0,
  "y": 0,
  "id": "optional_id_for_hooks"
}
```

| Common field | Description |
|---|---|
| `type` | `"label"`, `"button"`, or `"progress"`. |
| `x` | Left edge in pixels (0-959). |
| `y` | Top edge in pixels (0-539). Title bar occupies y=0..57. |
| `id` | (optional) Identifier for hook callbacks to find this widget. |

---

### Label

Displays static or updatable text.

```json
{
  "type": "label",
  "x": 12,
  "y": 80,
  "text": "Hello, world!",
  "scale": "h1",
  "color": "fg"
}
```

| Field | Required | Default | Description |
|---|---|---|---|
| `text` | Yes | — | The text to display. |
| `scale` | No | `"body"` | Text size: `"small"`, `"body"`, `"h1"`, `"title"`. |
| `color` | No | `"fg"` | Text color: see [Colors](#colors-and-scales). |

Labels auto-size their width based on text length × scale. Only invalidate the
horizontal extent when text changes.

---

### Button

Tappable rounded button. Supports several action types.

```json
{
  "type": "button",
  "x": 12,
  "y": 200,
  "w": 400,
  "h": 72,
  "text": "Click me",
  "scale": "h1",
  "action": "menu"
}
```

| Field | Required | Default | Description |
|---|---|---|---|
| `text` | Yes | — | Button label text. |
| `w` | Yes | — | Width in pixels. |
| `h` | Yes | — | Height in pixels. |
| `scale` | No | `"body"` | Text size. |
| `action` | No | — | What happens on press. See [Button actions](#button-actions). |

Press feedback is automatic: the button face darkens instantly (additive
refresh, ~0.3s) and the callback fires on release if still inside the rect.

---

### ProgressBar

Horizontal progress indicator.

```json
{
  "type": "progress",
  "x": 12,
  "y": 300,
  "w": 400,
  "h": 40,
  "value": 75
}
```

| Field | Required | Default | Description |
|---|---|---|---|
| `w` | Yes | — | Width in pixels. |
| `h` | Yes | — | Height in pixels. |
| `value` | No | `0` | Progress 0-100. |

Progress bars are static in pure declarative mode unless updated by a Python
hook. To make them dynamic, give them an `"id"` and update via a hook callback.

---

## Button actions

The `action` field on a button tells the framework what to do on press:

| Action value | Behavior |
|---|---|
| `"menu"` | Go back to the launcher home screen. |
| `"screen:my_screen_id"` | Navigate to the screen with key `"my_screen_id"` in `screens`. |
| `"hook:my_hook_name"` | Call the Python function registered as `"my_hook_name"`. See [Widget IDs and hooks](#widget-ids-and-hooks). |
| (omitted) | Button is inert (visual only). |

**Examples:**

```json
{ "action": "menu" }
{ "action": "screen:settings" }
{ "action": "hook:save_data" }
```

---

## Colors and scales

### Text scales

| Scale name | Pixel height | Use for |
|---|---|---|
| `"small"` | 8px | Captions, footnotes, debug messages. |
| `"body"` | 16px | Body text, list items, descriptions. |
| `"h1"` | 24px | Button labels, section headings. |
| `"title"` | 32px | Main titles, clock faces. |

### Grayscale colors

The display has 16 grayscale levels (0-15). The named colors are:

| Color name | Value | Appearance |
|---|---|---|
| `"fg"` | 0 (black) | Primary text, outlines, icons. |
| `"dark"` | 4 | Filled areas, accent fills. |
| `"accent"` | 4 | Same as dark — selected/pressed fills. |
| `"gray"` | 8 | Secondary text, muted elements. |
| `"muted"` | 8 | Same as gray — subtle text. |
| `"light"` | 12 | Panel backgrounds. |
| `"surface"` | 12 | Button faces, card backgrounds. |
| `"white"` | 15 | Screen background. |
| `"bg"` | 15 | Same as white. |

---

## Coordinate system

- Display: **960 × 540 pixels landscape**.
- Origin `(0, 0)` is **top-left**.
- X increases to the **right**, Y increases **down**.
- Title bar: **0..57** on Y axis. Place your widgets at `y >= 58` unless you
  want them behind the title bar.
- Back button: auto-placed at the top-right (`x=810`, `y=4`, `150×50`).
  If your rightmost widget overlaps `x=810..960` and `y=0..57`, it will
  appear behind the back button.

### Safe layout area

```
┌────────────────────────────────────────────────────────────┬──┐
│  Title bar (y=0..57)                            [Back btn]│  │
├────────────────────────────────────────────────────────────┘  │
│                                                                │
│  Usable area: x=0..959, y=58..539                              │
│                                                                │
│                                                                │
│                                                                │
│                                                                │
└────────────────────────────────────────────────────────────────┘
  960px wide × 540px tall
```

---

## Widget IDs and hooks

Any widget can have an `"id"` field. This lets Python hook callbacks find and
update widgets at runtime:

```json
{
  "type": "label",
  "id": "status_msg",
  "x": 200,
  "y": 150,
  "text": "Waiting...",
  "scale": "h1"
}
```

In your hook (registered in `src/user_hooks.py`):

```python
def _update_status(app):
    scr = app._screen
    lbl = scr.find("status_msg")
    if lbl:
        lbl.set_text("Done!")
```

This is how you make declarative screens interactive without writing a full
Python Screen class.

---

## Complete example

Here's a complete `ui.json` with a counter screen that updates via a Python
hook:

```json
{
  "apps": [
    {
      "id": "counter",
      "name": "Counter",
      "icon": "star",
      "kind": "screen",
      "screen": "counter_demo"
    }
  ],
  "screens": {
    "counter_demo": {
      "title": "Counter",
      "back": true,
      "widgets": [
        {
          "type": "label",
          "id": "counter",
          "x": 400,
          "y": 150,
          "text": "0",
          "scale": "title",
          "color": "fg"
        },
        {
          "type": "button",
          "x": 12,
          "y": 250,
          "w": 280,
          "h": 80,
          "text": "Increment",
          "scale": "h1",
          "action": "hook:increment"
        },
        {
          "type": "button",
          "x": 310,
          "y": 250,
          "w": 280,
          "h": 80,
          "text": "Reset",
          "scale": "h1",
          "action": "hook:reset"
        }
      ]
    }
  }
}
```

With `src/user_hooks.py`:
```python
from lib.ui import declarative

def _increment(app):
    lbl = app._screen.find("counter")
    if lbl:
        try:
            n = int(lbl.text) + 1
        except ValueError:
            n = 1
        lbl.set_text(str(n))

def _reset(app):
    lbl = app._screen.find("counter")
    if lbl:
        lbl.set_text("0")

def register_all():
    declarative.register_hook("increment", _increment)
    declarative.register_hook("reset", _reset)
```

---

## Using the UI Builder

The [UI Builder](../tools/ui-builder.html) is a web-based editor for `ui.json`.
Open it in your browser — no server needed, it works offline.

**Key features:**
- Drag widgets on a 960×540 canvas
- Edit properties in the right panel
- Configure app tiles with icons and screen links
- Browse the community app catalog and add apps to your config
- Export `ui.json` + catalog app files for deployment
- Import existing `ui.json` to edit

**Limitations:**
- The UI Builder only edits `ui.json` — it cannot create Python apps.
- Currently supported widget types: Label, Button, ProgressBar.
- For TextField, ListView, Keyboard, and custom widgets, write Python apps
  instead (see [Creating Custom Apps](./custom-apps.md)).

---

## Integration with Python apps

Declarative screens can coexist with Python apps. Use cases:

1. **Simple screens** — info pages, settings menus, status displays — build
   them declaratively.
2. **Complex apps** — anything needing ListView, TextField, Keyboard, or async
   `task()` — write a Python Screen class.
3. **Hybrid** — add your Python app's entry to the `apps` array with
   `"kind": "builtin"` and reference your Python module.

Example hybrid `ui.json`:
```json
{
  "apps": [
    { "id": "clock", "name": "Clock", "icon": "gear",
      "kind": "builtin", "entry": "clock_app:open_clock" },
    { "id": "about", "name": "About", "icon": "help",
      "kind": "screen", "screen": "about_page" }
  ],
  "screens": {
    "about_page": {
      "title": "About",
      "widgets": [
        { "type": "label", "x": 200, "y": 120,
          "text": "LilyGo T5 E-Paper Platform", "scale": "h1" },
        { "type": "label", "x": 200, "y": 170,
          "text": "Built with MicroPython", "scale": "body", "color": "muted" }
      ]
    }
  }
}
```
