# gt911.py - Goodix GT911 capacitive touch driver (mainline-MicroPython, async).
#
# Handles the LilyGo T5 Plus quirks from the research blueprint:
#   * Dynamic I2C address: the chip answers on 0x14 OR 0x5D depending on the
#     cover-glass capacitance at power-on (the V2.4 board hardwires RST so the
#     MCU cannot force the address). We probe both.
#   * Status register 0x814E MUST be written back to 0x00 after every read or
#     the controller latches and stops reporting new contacts.
#
# Coordinates are returned already mapped into the active DISPLAY orientation
# using the flags in config.py (tuned during hardware bring-up).
import asyncio
from machine import Pin

import config

REG_STATUS = 0x814E
REG_POINT1 = 0x814F
REG_CONFIG_VERSION = 0x8047
REG_PRODUCT_ID = 0x8140


class GT911:
    def __init__(self, shared_i2c, int_pin_num=config.PIN_TOUCH_INT):
        self.bus = shared_i2c
        self.int_pin = Pin(int_pin_num, Pin.IN, Pin.PULL_UP)
        self.address = None
        self.points = []

    async def begin(self):
        """Discover the live I2C address. Returns True on success."""
        for attempt in range(3):
            for addr in config.GT911_ADDRESSES:
                pid = await self.bus.read_mem(addr, REG_PRODUCT_ID, 4,
                                              addr_size=16, quiet=True)
                if pid and pid[:3] == b"911":
                    self.address = addr
                    print("GT911 found @", hex(addr), "product:", pid)
                    return True
            await asyncio.sleep_ms(20)
        print("GT911: no touch controller acknowledged on the bus")
        return False

    def _map(self, x, y):
        """Map raw GT911 (portrait) coords into display orientation."""
        if config.TOUCH_SWAP_XY:
            x, y = y, x
        nw, nh = config.TOUCH_NATIVE_W, config.TOUCH_NATIVE_H
        if config.TOUCH_SWAP_XY:
            nw, nh = nh, nw
        if config.TOUCH_FLIP_X:
            x = nw - 1 - x
        if config.TOUCH_FLIP_Y:
            y = nh - 1 - y
        # Scale native -> active display resolution
        if nw and nh:
            x = x * config.DISPLAY_WIDTH // nw
            y = y * config.DISPLAY_HEIGHT // nh
        return x, y

    async def poll(self):
        """Read current contacts. Returns a list of dicts with x/y/id."""
        self.points = []
        if self.address is None:
            return self.points

        status_raw = await self.bus.read_mem(self.address, REG_STATUS, 1, addr_size=16)
        if not status_raw:
            return self.points
        status = status_raw[0]
        ready = status & 0x80
        n = status & 0x0F

        if not ready or n == 0 or n > 5:
            await self.bus.write_mem(self.address, REG_STATUS, b"\x00", addr_size=16)
            return self.points

        data = await self.bus.read_mem(self.address, REG_POINT1, 8 * n, addr_size=16)
        await self.bus.write_mem(self.address, REG_STATUS, b"\x00", addr_size=16)
        if not data:
            return self.points

        for i in range(n):
            o = i * 8
            if o + 6 > len(data):
                break
            fid = data[o]
            rx = data[o + 1] | (data[o + 2] << 8)
            ry = data[o + 3] | (data[o + 4] << 8)
            pressure = data[o + 5] | (data[o + 6] << 8)
            x, y = self._map(rx, ry)
            self.points.append({"id": fid, "x": x, "y": y, "pressure": pressure})
        return self.points

    @property
    def touched(self):
        # Active-low INT: low means a contact is present.
        return self.int_pin.value() == 0
