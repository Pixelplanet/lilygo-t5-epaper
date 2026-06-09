"""Desktop simulator for the LilyGo T5 4.7" Plus UI.

Runs the *exact* device application (src/main.py's app) on CPython, rendering the
framebuffer into a Tk window. Mouse clicks/drags are injected as touch events,
so the full touch flow - home -> scan Wi-Fi -> pick network -> on-screen keyboard
-> connect - can be demonstrated and tested without the board.

Usage:
    pip install pillow
    python sim/run_sim.py
"""
import asyncio
import os
import sys
import tkinter as tk

# --- import resolution: shims first, then the device source tree -------------
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "src")
sys.path.insert(0, SRC)   # config, lib, apps
sys.path.insert(0, HERE)  # framebuf, machine, network, epd shims

# MicroPython's asyncio has sleep_ms; CPython's does not.
if not hasattr(asyncio, "sleep_ms"):
    async def _sleep_ms(ms):
        await asyncio.sleep(ms / 1000)
    asyncio.sleep_ms = _sleep_ms

from PIL import ImageTk  # noqa: E402  (after path setup)

import config  # noqa: E402
from apps import wifi_demo  # noqa: E402
from lib.board import Board  # noqa: E402
from lib.ui.core import DOWN, MOVE, UP, Event, InputSource  # noqa: E402

SCALE = 1.0


class SimInput(InputSource):
    """Collects Tk mouse events and serves them to the App loop."""

    def __init__(self):
        self._queue = []

    def push(self, etype, x, y):
        self._queue.append(Event(etype, int(x / SCALE), int(y / SCALE)))

    async def poll_events(self):
        evs, self._queue = self._queue, []
        return evs


async def amain():
    board = await Board().begin()
    sim_input = SimInput()
    board.input = sim_input

    from lib.ui.core import App
    app = App(board.display, sim_input, board)

    root = tk.Tk()
    root.title("LilyGo T5 4.7\" Plus - simulator (mouse = touch)")
    cw, ch = int(config.DISPLAY_WIDTH * SCALE), int(config.DISPLAY_HEIGHT * SCALE)
    canvas = tk.Canvas(root, width=cw, height=ch, highlightthickness=0)
    canvas.pack()

    canvas.bind("<ButtonPress-1>", lambda e: sim_input.push(DOWN, e.x, e.y))
    canvas.bind("<B1-Motion>", lambda e: sim_input.push(MOVE, e.x, e.y))
    canvas.bind("<ButtonRelease-1>", lambda e: sim_input.push(UP, e.x, e.y))
    root.protocol("WM_DELETE_WINDOW", lambda: setattr(app, "running", False))

    img_item = canvas.create_image(0, 0, anchor="nw")
    photo_ref = [None]

    runner = asyncio.create_task(app.run(wifi_demo.build_app(app)))

    while app.running:
        try:
            root.update()
        except tk.TclError:
            break
        img = board.display.fb.image
        if SCALE != 1.0:
            img = img.resize((cw, ch))
        photo = ImageTk.PhotoImage(img)
        canvas.itemconfig(img_item, image=photo)
        photo_ref[0] = photo
        await asyncio.sleep(0.03)

    runner.cancel()
    try:
        root.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass
