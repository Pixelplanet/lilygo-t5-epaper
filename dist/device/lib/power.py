# power.py - Deep sleep + touch-wake helper.
#
# GPIO47 (touch INT) is NOT in the ESP32-S3 RTC power domain, so it cannot wake
# the chip from deep sleep with stock wiring. The research doc's hardware mod is
# to solder a bridge GPIO10 (RTC-capable) -> GPIO47. Only enable touch-wake when
# config.TOUCH_WAKE_BRIDGE is True (i.e. the bridge is physically installed).
import machine
from machine import Pin

import config


def deep_sleep(ms=0):
    """Enter deep sleep. Wakes on touch (if bridged) and/or after `ms`."""
    if config.TOUCH_WAKE_BRIDGE:
        try:
            import esp32
            wake = Pin(config.PIN_TOUCH_WAKE, Pin.IN, Pin.PULL_UP)
            # GT911 INT is active-low -> wake when it goes low.
            esp32.wake_on_ext0(pin=wake, level=esp32.WAKEUP_ALL_LOW)
        except Exception as e:  # noqa: BLE001
            print("power: touch-wake setup failed:", e)
    if ms:
        machine.deepsleep(ms)
    else:
        machine.deepsleep()


def wake_reason():
    try:
        import esp32
        return machine.wake_reason()
    except Exception:
        return None
