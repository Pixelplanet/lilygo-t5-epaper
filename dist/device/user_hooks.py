# user_hooks.py - register your own Python callbacks for declarative screens.
#
# Screens defined in ui.json can trigger Python via a button "action" of
# "hook:<name>". Register those callbacks here. Each hook receives the running
# App, so it can navigate, read peripherals, or update widgets on the current
# screen by their config "id" (screen.find("<id>")).
#
# main.py imports this module once at startup so the hooks are available.
from lib.ui import declarative


def _say_hi(app):
    # Update the label declared with "id": "msg" on the hello screen.
    scr = app._screen
    lbl = getattr(scr, "find", lambda _id: None)("msg")
    if lbl is not None:
        lbl.set_text("Hi from Python!")


def register_all():
    declarative.register_hook("say_hi", _say_hi)
