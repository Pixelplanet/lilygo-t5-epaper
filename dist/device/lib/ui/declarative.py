# declarative.py - build UI screens from plain-data (JSON) descriptions.
#
# This lets people lay out screens in the web builder (or by hand-editing
# ui.json) without writing Python, while still allowing hobbyist coders to wire
# custom behaviour via "hooks" - named Python callables they register.
#
# Schema (see docs/ui-builder.md):
#   {
#     "apps":   [ {id,name,icon, kind:"builtin"|"screen", entry|screen}, ... ],
#     "screens": { "<id>": { "title": str, "widgets": [ <widget>, ... ] } }
#   }
#
# A <widget> is a dict: {"type": "...", "x":, "y":, ...}. Supported types map to
# lib.ui.widgets. An "action" string on a button is one of:
#   "menu"            -> back to the launcher home
#   "screen:<id>"     -> navigate to another declared screen
#   "hook:<name>"     -> call hooks[name](app) (registered in Python)
import json

from lib.ui import theme
from lib.ui.core import Screen
from lib.ui.widgets import Button, Label, ProgressBar

CONFIG_PATH = "ui.json"

# Registry of custom Python callbacks usable from "hook:<name>" actions.
# Populate it from your own code, e.g.:
#     from lib.ui import declarative
#     declarative.register_hook("say_hi", lambda app: ...)
_HOOKS = {}


def register_hook(name, fn):
    """Register a Python callable for a 'hook:<name>' button action."""
    _HOOKS[name] = fn


def load_config(path=CONFIG_PATH):
    """Read and parse the UI config. Returns {} if missing/invalid."""
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


# Named grayscale shades so config can use words instead of magic numbers.
_COLORS = {
    "fg": theme.FG, "muted": theme.FG_MUTED, "bg": theme.BG,
    "accent": theme.ACCENT, "surface": theme.SURFACE,
    "black": theme.BLACK, "dark": theme.DARK, "gray": theme.GRAY,
    "light": theme.LIGHT, "white": theme.WHITE,
}
# Named text scales.
_SCALES = {
    "title": theme.TITLE_SCALE, "h1": theme.H1_SCALE,
    "body": theme.BODY_SCALE, "small": theme.SMALL_SCALE,
}


def _scale(v, default=theme.BODY_SCALE):
    if v is None:
        return default
    if isinstance(v, str):
        return _SCALES.get(v, default)
    return int(v)


def _color(v, default=theme.FG):
    if v is None:
        return default
    if isinstance(v, str):
        return _COLORS.get(v, default)
    return int(v)


class ConfigScreen(Screen):
    """A Screen whose widgets come from a config dict."""

    def __init__(self, app, screen_id, config):
        spec = (config.get("screens", {}) or {}).get(screen_id, {})
        super().__init__(app, spec.get("title", screen_id))
        self._spec = spec
        self._config = config
        self._screen_id = screen_id
        self._by_id = {}      # widget "id" -> widget, for hook lookups

    def find(self, wid):
        """Return a widget previously given "id": wid in the config, or None.

        Lets a hook update declared widgets, e.g.:
            app._screen.find("msg").set_text("Hi!")
        """
        return self._by_id.get(wid)

    def build(self):
        d = self.app.display
        for w in self._spec.get("widgets", []) or []:
            wid = self._make_widget(d, w)
            if wid is not None:
                self.add(wid)
                if w.get("id"):
                    self._by_id[w["id"]] = wid
        # Always offer a way back to the launcher unless the screen opts out.
        if self._spec.get("back", True):
            self.add_back_button()

    def _make_widget(self, d, w):
        t = w.get("type")
        x = int(w.get("x", theme.PAD))
        y = int(w.get("y", theme.PAD))
        if t == "label":
            return Label(x, y, str(w.get("text", "")),
                         _scale(w.get("scale")), _color(w.get("color")))
        if t == "button":
            return Button(x, y, int(w.get("w", 300)), int(w.get("h", 72)),
                          str(w.get("text", "Button")),
                          self._action(w.get("action")), _scale(w.get("scale")))
        if t == "progress":
            pb = ProgressBar(x, y, int(w.get("w", 400)), int(w.get("h", 40)),
                             int(w.get("value", 0)))
            return pb
        # Unknown type -> render a muted placeholder label so mistakes are
        # visible on-device rather than silently dropped.
        return Label(x, y, "?" + str(t), theme.SMALL_SCALE, theme.FG_MUTED)

    def _action(self, action):
        if not action:
            return None
        if action == "menu":
            return self._go_home
        if action.startswith("screen:"):
            target = action[7:]

            def go_screen():
                self.app.go(ConfigScreen(self.app, target, self._config))
            return go_screen
        if action.startswith("hook:"):
            name = action[5:]

            def run_hook():
                fn = _HOOKS.get(name)
                if fn:
                    fn(self.app)
            return run_hook
        return None

    def _go_home(self):
        from apps import launcher
        self.app.go(launcher.LauncherScreen(self.app))
