"""Simulator stub for the LilyGo `epd` C module.

On the device this module drives the ED047TC1 panel. In the simulator the panel
contents are mirrored straight from the framebuffer's Pillow image by run_sim.py,
so these calls are no-ops that simply keep the display backend happy.
"""


def init():
    print("sim epd: init")


def clear():
    pass


def display(buffer):
    pass


def display_partial(buffer, x, y, w, h, clear=True):
    pass


def repair(cycles=4, delay=50):
    print("sim epd: repair", cycles, "cycles")


def power_off():
    pass
