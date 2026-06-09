# profile.py - tiny, low-overhead timing aggregator for on-device profiling.
#
# Accumulates named timing samples in RAM and flushes an averaged summary line
# to debug.log at most once every FLUSH_MS, so logging cost doesn't distort the
# measurements. Enable via config.PROFILE.
#
# Usage:
#     from lib import profile
#     t = profile.start()
#     ... work ...
#     profile.add("touch_idle", t)
#
# All calls are cheap no-ops when config.PROFILE is False.
import time

import config
from lib import debuglog

_ENABLED = bool(getattr(config, "PROFILE", False))
FLUSH_MS = 2000

_acc = {}          # name -> [count, total_us, max_us]
_last_flush = time.ticks_ms()


def start():
    return time.ticks_us()


def add(name, t_start):
    if not _ENABLED:
        return
    dt = time.ticks_diff(time.ticks_us(), t_start)
    rec = _acc.get(name)
    if rec is None:
        _acc[name] = [1, dt, dt]
    else:
        rec[0] += 1
        rec[1] += dt
        if dt > rec[2]:
            rec[2] = dt
    _maybe_flush()


def _maybe_flush():
    global _last_flush
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_flush) < FLUSH_MS:
        return
    _last_flush = now
    if not _acc:
        return
    parts = []
    for name in sorted(_acc):
        cnt, tot, mx = _acc[name]
        avg = tot // cnt
        parts.append("{}={}us(avg)/{}us(max)x{}".format(name, avg, mx, cnt))
    debuglog.log("PROF " + "  ".join(parts))
    _acc.clear()
