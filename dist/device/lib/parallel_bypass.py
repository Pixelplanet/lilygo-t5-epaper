# parallel_bypass.py - SPI acceleration for the 74HCT4094D shift register.
#
# EXPERIMENTAL / Option-B path only. The shift register serialises the e-paper
# config controls (EPD_LE, EPD_OE, EPD_MODE, EPD_STV). Toggling them with
# Pin.value() in pure Python is far too slow and leaves the panel blank, so we
# map the S3 hardware SPI peripheral onto the register's DATA/CLK pins and push
# control bytes at 20 MHz, then pulse the strobe to latch.
#
# NOTE: this only latches the *config* byte. It does NOT clock pixel data across
# the 8-bit bus, which still needs the C driver (Option A). Kept for completeness
# and future mainline work.
from machine import Pin, SPI

import config


class ParallelBypass:
    def __init__(self, data_pin=config.PIN_CFG_DATA, clk_pin=config.PIN_CFG_CLK,
                 str_pin=config.PIN_CFG_STR):
        self.spi = SPI(1, baudrate=20_000_000, sck=Pin(clk_pin), mosi=Pin(data_pin))
        self.strobe = Pin(str_pin, Pin.OUT, value=0)

    def commit_state(self, control_byte):
        """Shift an 8-bit control byte and latch it to the register outputs."""
        self.spi.write(bytes((control_byte & 0xFF,)))
        self.strobe.value(1)
        self.strobe.value(0)
