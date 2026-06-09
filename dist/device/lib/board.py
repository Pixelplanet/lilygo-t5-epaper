# board.py - wires together all peripherals for the T5 4.7" Plus.
from lib.battery import Battery
from lib.display import Display
from lib.gt911 import GT911
from lib.pcf8563 import PCF8563
from lib.shared_i2c import SharedI2CBus
from lib.ui.core import GT911Input


class Board:
    def __init__(self):
        self.display = Display()
        self.i2c = SharedI2CBus()
        self.touch = GT911(self.i2c)
        self.rtc = PCF8563(self.i2c)
        self.battery = Battery()
        # Default input source: physical touch panel. The simulator swaps this.
        self.input = GT911Input(self.touch)
        # Cached (year, month, day, weekday, hour, minute, second) read once at
        # begin() so screens can default to "today" without an async RTC call.
        self.today = None

    async def begin(self):
        ok = await self.touch.begin()
        if not ok:
            print("board: continuing without touch (check FFC connector)")
        print("board: I2C devices:", [hex(a) for a in self.i2c.scan()])
        try:
            self.today = await self.rtc.datetime()
        except Exception:
            self.today = None
        return self
