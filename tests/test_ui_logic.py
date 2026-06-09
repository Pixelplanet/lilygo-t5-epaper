"""Headless logic tests - no display/Tk required (Pillow still needed for the
framebuf import chain). Run with:  python tests/test_ui_logic.py
or:  python -m pytest tests/
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "sim"))

from lib.ui.core import DOWN, UP, Event  # noqa: E402
from lib.ui.keyboard import BACK, ENTER, Keyboard  # noqa: E402
from lib.ui.widgets import Button, ListView  # noqa: E402


def test_keyboard_types_and_shifts():
    out = []
    kb = Keyboard(0, 0, 960, 300, on_key=out.append)
    # find the rect of letter 'a'
    rect = next(r for r, label, tok in kb.keys if tok == "a")
    cx, cy = rect[0] + 5, rect[1] + 5
    kb.handle(Event(DOWN, cx, cy))
    kb.handle(Event(UP, cx, cy))
    assert out == ["a"], out

    # toggle shift, then 'a' should produce 'A'
    sh = next(r for r, label, tok in kb.keys if tok == "shift")
    kb.handle(Event(DOWN, sh[0] + 5, sh[1] + 5))
    kb.handle(Event(UP, sh[0] + 5, sh[1] + 5))
    assert kb.shift is True
    rect = next(r for r, label, tok in kb.keys if tok == "a")
    kb.handle(Event(DOWN, rect[0] + 5, rect[1] + 5))
    kb.handle(Event(UP, rect[0] + 5, rect[1] + 5))
    assert out[-1] == "A", out
    assert kb.shift is False  # shift auto-releases after one char


def test_keyboard_backspace_and_enter_tokens():
    out = []
    kb = Keyboard(0, 0, 960, 300, on_key=out.append)
    back = next(r for r, label, tok in kb.keys if tok == "back")
    kb.handle(Event(DOWN, back[0] + 5, back[1] + 5))
    kb.handle(Event(UP, back[0] + 5, back[1] + 5))
    assert out[-1] == BACK
    ent = next(r for r, label, tok in kb.keys if tok == "enter")
    kb.handle(Event(DOWN, ent[0] + 5, ent[1] + 5))
    kb.handle(Event(UP, ent[0] + 5, ent[1] + 5))
    assert out[-1] == ENTER


def test_button_fires_only_on_release_inside():
    fired = []
    b = Button(10, 10, 200, 80, "Go", on_press=lambda: fired.append(1))
    b.handle(Event(DOWN, 50, 50))
    assert b.pressed
    b.handle(Event(UP, 50, 50))
    assert fired == [1]
    # press then release outside -> no fire
    b.handle(Event(DOWN, 50, 50))
    b.handle(Event(UP, 9000, 9000))
    assert fired == [1]


def test_listview_select_vs_scroll():
    picked = []
    items = list(range(20))
    lv = ListView(0, 0, 400, 200, items,
                  render_row=lambda *a: None, on_select=picked.append, row_h=50)
    # tap (no movement) on second row -> select index 1
    lv.handle(Event(DOWN, 10, 60))
    lv.handle(Event(UP, 10, 62))
    assert picked == [1], picked
    # drag up -> scrolls, no selection
    lv.handle(Event(DOWN, 10, 150))
    from lib.ui.core import MOVE
    lv.handle(Event(MOVE, 10, 50))
    lv.handle(Event(UP, 10, 50))
    assert lv.offset > 0
    assert picked == [1]


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print("\nAll %d tests passed." % len(fns))


if __name__ == "__main__":
    _run_all()
