# pcf8563.py - NXP PCF8563 real-time clock on the shared I2C bus (8-bit regs).
import config

REG_SECONDS = 0x02  # seconds register; date/time block follows


def _bcd2dec(b):
    return (b >> 4) * 10 + (b & 0x0F)


def _dec2bcd(d):
    return ((d // 10) << 4) | (d % 10)


class PCF8563:
    def __init__(self, shared_i2c, address=config.PCF8563_ADDRESS):
        self.bus = shared_i2c
        self.address = address

    async def datetime(self):
        """Return (year, month, day, weekday, hour, minute, second) or None."""
        data = await self.bus.read_mem(self.address, REG_SECONDS, 7, addr_size=8)
        if not data:
            return None
        second = _bcd2dec(data[0] & 0x7F)
        minute = _bcd2dec(data[1] & 0x7F)
        hour = _bcd2dec(data[2] & 0x3F)
        day = _bcd2dec(data[3] & 0x3F)
        weekday = data[4] & 0x07
        month = _bcd2dec(data[5] & 0x1F)
        year = 2000 + _bcd2dec(data[6])
        return (year, month, day, weekday, hour, minute, second)

    async def set_datetime(self, year, month, day, weekday, hour, minute, second):
        buf = bytes((
            _dec2bcd(second), _dec2bcd(minute), _dec2bcd(hour),
            _dec2bcd(day), weekday & 0x07, _dec2bcd(month),
            _dec2bcd(year % 100),
        ))
        return await self.bus.write_mem(self.address, REG_SECONDS, buf, addr_size=8)

    async def time_string(self):
        dt = await self.datetime()
        if not dt:
            return "--:--"
        return "{:02d}:{:02d}".format(dt[4], dt[5])
