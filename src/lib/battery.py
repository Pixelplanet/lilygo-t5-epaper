# battery.py - Battery voltage on GPIO14 (ADC2).
#
# CRITICAL: GPIO14 is on ADC2, which the ESP32-S3 shares with the Wi-Fi radio.
# Reading it while Wi-Fi is active causes failed reads or brownout resets.
# This module refuses to sample when the WLAN radio is up, and the Wi-Fi code
# is written to sample the battery BEFORE enabling the radio.
from machine import ADC, Pin

import config


class Battery:
    def __init__(self, pin_num=config.PIN_BATTERY_ADC):
        self.adc = ADC(Pin(pin_num))
        try:
            self.adc.atten(ADC.ATTN_11DB)  # full ~0-3.3V range
        except Exception:
            pass

    @staticmethod
    def _wifi_active():
        try:
            import network
            return network.WLAN(network.STA_IF).active()
        except Exception:
            return False

    def voltage(self):
        """Battery volts, or None if Wi-Fi is active (ADC2 conflict)."""
        if self._wifi_active():
            print("battery: refused - Wi-Fi (ADC2) active")
            return None
        raw = 0
        for _ in range(8):
            raw += self.adc.read_uv() if hasattr(self.adc, "read_uv") else self.adc.read()
        avg = raw / 8
        # read_uv() returns microvolts at the pin; read() returns 0..4095.
        if hasattr(self.adc, "read_uv"):
            pin_v = avg / 1_000_000
        else:
            pin_v = avg / 4095 * 3.3
        return pin_v * config.BATTERY_ADC_DIVIDER

    def percent(self):
        v = self.voltage()
        if v is None:
            return None
        span = config.BATTERY_FULL_V - config.BATTERY_EMPTY_V
        pct = (v - config.BATTERY_EMPTY_V) / span * 100
        return max(0, min(100, int(pct)))
