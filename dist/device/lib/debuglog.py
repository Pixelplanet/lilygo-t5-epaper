# debuglog.py - tiny append-only on-device log (survives resets/brownouts).
#
# CDC serial output is lost on reset/brownout, so milestones are written to a
# file and fsync'd. Read it back with: mpremote fs cat :debug.log
_PATH = "debug.log"


def log(msg):
    try:
        with open(_PATH, "a") as f:
            f.write(str(msg))
            f.write("\n")
        try:
            import os
            os.sync()
        except Exception:
            pass
    except Exception:
        pass


def clear():
    try:
        import os
        os.remove(_PATH)
    except Exception:
        pass
