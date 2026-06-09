# shared_i2c.py - Thread/task-safe I2C wrapper for the shared bus.
#
# The GT911 touch controller and the PCF8563 RTC sit on the SAME physical I2C
# bus (GPIO18/SDA, GPIO17/SCL). The GT911 clock-stretches between scan cycles;
# bit-banged SoftI2C cannot service that reliably (most reads time out), so we
# use the ESP32-S3 hardware I2C peripheral, which handles clock stretching in
# silicon. An asyncio.Lock serialises concurrent access from the touch task and
# any clock/RTC updates.
import asyncio
import time
from machine import Pin, I2C

import config


def _recover_bus(sda_pin, scl_pin):
    """Free a stuck I2C bus before handing the pins to the I2C peripheral.

    At power-on the GT911 can hold SDA low (or be left mid-transaction),
    which makes the whole shared bus appear dead - even the RTC stops
    ACKing. Clocking SCL up to 9 times lets any slave finish its byte and
    release SDA, then we issue a STOP. This is the documented I2C recovery
    sequence and is harmless when the bus is already idle.
    """
    scl = Pin(scl_pin, Pin.OUT, value=1)
    sda = Pin(sda_pin, Pin.IN, Pin.PULL_UP)
    for _ in range(9):
        scl.value(0)
        time.sleep_us(5)
        scl.value(1)
        time.sleep_us(5)
        if sda.value():
            break
    # Generate a STOP condition: SDA low->high while SCL high.
    sda_out = Pin(sda_pin, Pin.OUT, value=0)
    time.sleep_us(5)
    scl.value(1)
    time.sleep_us(5)
    sda_out.value(1)
    time.sleep_us(5)


class SharedI2CBus:
    def __init__(self, sda_pin=config.PIN_I2C_SDA, scl_pin=config.PIN_I2C_SCL,
                 freq=config.I2C_FREQ):
        _recover_bus(sda_pin, scl_pin)
        self.i2c = I2C(0, sda=Pin(sda_pin), scl=Pin(scl_pin), freq=freq)
        self.lock = asyncio.Lock()

    def scan(self):
        return self.i2c.scan()

    async def read_mem(self, addr, mem_addr, num_bytes, addr_size=16, quiet=False):
        async with self.lock:
            for attempt in range(3):
                try:
                    return self.i2c.readfrom_mem(addr, mem_addr, num_bytes,
                                                 addrsize=addr_size)
                except OSError as e:  # noqa: PERF203
                    # The GT911 intermittently clock-stretches/NACKs while it
                    # latches a new frame; a quick retry recovers it.
                    last = e
                    time.sleep_ms(2)
            if not quiet:
                print("I2C read error @", hex(addr), ":", last)
            return None

    async def write_mem(self, addr, mem_addr, data, addr_size=16):
        async with self.lock:
            for attempt in range(3):
                try:
                    self.i2c.writeto_mem(addr, mem_addr, data, addrsize=addr_size)
                    return True
                except OSError as e:
                    last = e
                    time.sleep_ms(2)
            print("I2C write error @", hex(addr), ":", last)
            return False

    async def probe(self, addr):
        """Return True if a device ACKs at `addr`."""
        async with self.lock:
            try:
                self.i2c.writeto(addr, b"")
                return True
            except Exception:
                return False
