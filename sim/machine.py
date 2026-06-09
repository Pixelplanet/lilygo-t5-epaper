"""Minimal CPython shim of MicroPython's `machine` module for the simulator.

Only the surface used by the project is implemented. Touch input in the
simulator is injected via Tk mouse events (see run_sim.py), so the I2C/GT911
path here just degrades gracefully.
"""


class Pin:
    IN = 0
    OUT = 1
    PULL_UP = 2
    PULL_DOWN = 3

    def __init__(self, num, mode=-1, pull=-1, value=0):
        self.num = num
        self._value = value

    def value(self, v=None):
        if v is None:
            # INT/IRQ pins idle high (not touched) in the simulator
            return self._value if self._value else 1
        self._value = v

    def on(self):
        self._value = 1

    def off(self):
        self._value = 0


class SoftI2C:
    def __init__(self, sda=None, scl=None, freq=100000):
        pass

    def scan(self):
        return []

    def readfrom_mem(self, addr, mem, n, addrsize=8):
        raise OSError("sim: no I2C device")

    def writeto_mem(self, addr, mem, data, addrsize=8):
        raise OSError("sim: no I2C device")

    def writeto(self, addr, data):
        raise OSError("sim: no I2C device")


I2C = SoftI2C


class SPI:
    def __init__(self, *a, **k):
        pass

    def write(self, buf):
        pass


class ADC:
    ATTN_11DB = 3

    def __init__(self, pin):
        self.pin = pin

    def atten(self, db):
        pass

    def read(self):
        # ~1.95 V at the pin -> ~3.9 V battery after the /2 divider
        return 2420


def deepsleep(ms=0):
    print("sim: deepsleep(%s) - ignored" % ms)


def wake_reason():
    return 0


def reset():
    print("sim: reset() - ignored")
