"""Render key screens to PNG files without opening a window.

Useful for validating the rendering pipeline in CI / headless environments and
for previewing the UI. Outputs to build/snapshots/*.png.

    pip install pillow
    python sim/snapshot.py
"""
import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)

if not hasattr(asyncio, "sleep_ms"):
    async def _sleep_ms(ms):
        await asyncio.sleep(ms / 1000)
    asyncio.sleep_ms = _sleep_ms

from apps import wifi_demo  # noqa: E402
from lib.board import Board  # noqa: E402
from lib.ui.core import App  # noqa: E402

OUT = os.path.join(ROOT, "build", "snapshots")


async def snap(app, screen, name):
    screen.build()
    screen.on_show()
    screen.draw(app.display)
    await screen.task()           # let it populate data (no navigation saved)
    screen.draw(app.display)
    app.display.fb.image.save(os.path.join(OUT, name))
    print("wrote", name)


async def main():
    os.makedirs(OUT, exist_ok=True)
    board = await Board().begin()
    app = App(board.display, board.input, board)

    fake_nets = [
        {"ssid": "HomeNet_5G", "rssi": -48, "secured": True},
        {"ssid": "CoffeeShop_Free", "rssi": -57, "secured": False},
        {"ssid": "Neighbour_2.4", "rssi": -67, "secured": True},
        {"ssid": "LilyGoLab", "rssi": -72, "secured": True},
    ]

    await snap(app, wifi_demo.HomeScreen(app), "01_home.png")
    await snap(app, wifi_demo.NetworkListScreen(app, fake_nets), "02_networks.png")
    pw = wifi_demo.PasswordScreen(app, "HomeNet_5G")
    pw.build()
    pw.draw(app.display)
    for ch in "secret12":
        pw._on_key(ch)
    pw.draw(app.display)
    app.display.fb.image.save(os.path.join(OUT, "03_password.png"))
    print("wrote 03_password.png")
    await snap(app, wifi_demo.ResultScreen(app, "HomeNet_5G", True, "192.168.1.42"),
               "04_result.png")
    await snap(app, wifi_demo.TouchTestScreen(app), "05_touch.png")


if __name__ == "__main__":
    asyncio.run(main())
