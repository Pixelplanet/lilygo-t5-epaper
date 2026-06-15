# Building your own UI (apps, screens, and the web builder)

The home screen is an **icon grid of apps**, and every app is either a built-in
Python screen or a **screen you design as data** in `ui.json`. You can edit that
file by hand, or use the offline **web builder** to drag it together visually.

```
device flash
├─ ui.json          ← apps + custom screens (this file drives the home grid)
├─ user_hooks.py    ← optional Python callbacks for custom button logic
├─ main.py, apps/, lib/ …
```

If `ui.json` is missing, the launcher falls back to the three built-in demos.

---

## The web builder (no install)

Open `tools/ui-builder.html` in any browser (double-click it — it runs fully
offline, nothing is uploaded).

- **Apps (home) tab** — add/rename app tiles, pick an icon, and choose what each
  tile opens: a **built-in app** (Wi-Fi / Calendar / Prices / Help) or one of your
  **custom screens**. Each tile can be **Auto (next free slot)** or **Fixed slot** —
  set it to Fixed and drag it on the home preview; it **snaps to the nearest of the
  8 grid slots** (4×2). All tiles are the same size. (Wi-Fi and Help ship pinned to
  the bottom-right slots 6 and 7.)
- **Screens tab** — create screens and drag **Label / Button / Progress**
  widgets onto the 960×540 canvas. Click a widget to edit its text, size, scale,
  color, and (for buttons) its action.
- **Export ui.json** — downloads the config. **Import ui.json** — reloads an
  existing one to keep editing.

Then copy the exported `ui.json` to the device flash root (via the deploy
script, `mpremote`, or Thonny — see [editing-with-thonny.md](editing-with-thonny.md))
and reset the board.

---

## ui.json schema

```jsonc
{
  "apps": [
    // Opens a built-in Python app:
    {"id":"wifi","name":"Wi-Fi","icon":"wifi","kind":"builtin","entry":"wifi_demo:HomeScreen"},
    // Opens a screen you defined below:
    {"id":"hello","name":"Hello","icon":"star","kind":"screen","screen":"hello"}
  ],
  "screens": {
    "hello": {
      "title": "Hello screen",
      "back": true,                       // show the top-right Back button
      "widgets": [
        {"type":"label","x":12,"y":90,"text":"Built from ui.json","scale":"h1"},
        {"type":"button","x":12,"y":220,"w":360,"h":84,"text":"Say hi",
         "scale":"h1","action":"hook:say_hi"},
        {"type":"label","id":"msg","x":12,"y":330,"text":"","scale":"h1"}
      ]
    }
  }
}
```

**Icons:** `wifi`, `calendar`, `bolt`, `star`, `gear`, `help`, `app`.
**Scales:** `title`, `h1`, `body`, `small`.
**Colors:** `fg`, `muted`, `accent`, `surface`, `black`, `dark`, `gray`, `light`.

**Pinning a tile:** add `"slot": <0-7>` (row-major: 0-3 top row, 4-7 bottom row)
to pin an app to a fixed grid slot (e.g. Wi-Fi `"slot":6`, Help `"slot":7` in the
bottom-right). Tiles without a slot fill the remaining slots in order. All tiles
are the same size.

**Button actions:**
| action | effect |
|--------|--------|
| *(none)* | does nothing |
| `menu` | return to the home grid |
| `screen:<id>` | open another declared screen |
| `hook:<name>` | call your Python function `<name>` |

> Text is ASCII-only — the e-paper font has no umlaut/symbol glyphs, so use
> `EUR` instead of `€`, `ae` instead of `ä`, etc.

---

## Custom logic with hooks (for coders)

A button `"action": "hook:say_hi"` calls a Python function you register in
`user_hooks.py`:

```python
from lib.ui import declarative

def _say_hi(app):
    # update a widget that has "id": "msg" on the current screen
    lbl = app._screen.find("msg")
    if lbl is not None:
        lbl.set_text("Hi from Python!")

def register_all():
    declarative.register_hook("say_hi", _say_hi)
```

`main.py` calls `register_all()` at boot. Each hook receives the running `App`,
so it can read peripherals (`app.board`), navigate (`app.go(...)`), or update
declared widgets by their config `id` via `app._screen.find("<id>")`.

That's the full escape hatch: lay the screen out visually, wire the behaviour in
a few lines of Python.

---

## App store (sharing apps)

A community **app catalog** lets people share installable apps. Each app is a
small folder with a manifest entry in `apps-catalog/index.json` plus its Python
file(s). See `apps-catalog/README.md` for the format.

Two ways to install from a catalog:

- **Web builder → Catalog tab:** enter the catalog URL (a raw GitHub link to
  `index.json`) and **Load URL**, or **Load file…** for a local copy. Pick an app
  and **Add to device** — it adds the launcher tile and, on **Export bundle**,
  downloads the app's `.py` files alongside `ui.json` (copy each to its listed
  device path).
- **On the device → Apps tile:** the App Store app connects over Wi-Fi, fetches
  the catalog, and opens a details page when you tap an app. From there you can
  **Install** (or **Uninstall** if already installed). Install downloads files
  to flash and adds/updates the launcher tile. Set the catalog URL in
  `apps/appstore.py` (`CATALOG_URL`). Reset the device to refresh the launcher.
