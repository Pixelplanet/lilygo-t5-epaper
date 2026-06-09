# main.py - device entry point.
#
# Builds the board (display + touch + RTC + battery), then runs the Wi-Fi
# touch-showcase app. The SAME code path is exercised by the desktop simulator
# (sim/run_sim.py) so this can be developed and demoed without hardware.
#
# SAFETY: this file auto-runs at power-on. To keep the board recoverable for
# anyone who flashes it, there is a startup escape hatch:
#   * Hold the BOOT button (GPIO21) during reset -> skip the app, drop to REPL.
#   * Or press Ctrl-C in the ~2s startup window -> drop to REPL.
# This prevents a bad app build from locking you out of the REPL.
import sys
import time

import asyncio


def _skip_requested():
    """True if the user is holding the BOOT button to bypass auto-start."""
    try:
        from machine import Pin
        import config
        btn = Pin(config.PIN_BUTTON, Pin.IN, Pin.PULL_UP)
        # BOOT/User button is active-low. Sample briefly to debounce.
        for _ in range(5):
            if btn.value() != 0:
                return False
            time.sleep_ms(10)
        return True
    except Exception:
        return False


async def main():
    from apps import launcher
    from lib.board import Board
    from lib.ui.core import App

    try:
        from lib import debuglog
        import machine
        # Do NOT clear: we want history across reboots so a reset during the
        # Wi-Fi connect is visible. reset_cause() tells us WHY we (re)booted.
        debuglog.log("==== boot reset_cause=" + str(machine.reset_cause()))
    except Exception:
        pass

    board = await Board().begin()
    app = App(board.display, board.input, board)
    # Register any user-defined hooks for declarative (ui.json) screens.
    try:
        import user_hooks
        user_hooks.register_all()
    except Exception as e:  # noqa: BLE001
        try:
            from lib import debuglog
            debuglog.log("hooks: register failed " + str(e))
        except Exception:
            pass
    # If a network is already configured, auto-connect in the background so
    # online features (e.g. prices) are ready without a manual reconnect.
    try:
        from lib import netconn, wifistore
        if wifistore.load()[0]:
            asyncio.create_task(netconn.auto_connect())
    except Exception:
        pass
    await app.run(launcher.build_app(app))


def run():
    # Give native USB-CDC time to enumerate and let the user break in before
    # any heavy display/Wi-Fi work starts.
    print("Starting app in ~2s. Hold BOOT or press Ctrl-C for REPL.")
    for _ in range(20):
        time.sleep_ms(100)

    if _skip_requested():
        print("BOOT held - skipping app, dropping to REPL.")
        return

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Halted - back to REPL.")
    except Exception as e:  # noqa: BLE001
        # Never leave the user stuck: report and fall back to the REPL.
        sys.print_exception(e)
        print("App crashed - dropping to REPL.")


run()
