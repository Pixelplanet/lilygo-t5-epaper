import os


def _w(msg):
    with open("/diag3.txt", "a") as f:
        f.write(str(msg) + "\n")
    os.sync()


def run():
    open("/diag3.txt", "w").close()
    _w("before import")
    import epd
    _w("after import")
    try:
        r = epd.init()
        _w("init returned " + repr(r))
    except Exception as e:
        import sys
        with open("/diag3.txt", "a") as f:
            sys.print_exception(e, f)
        os.sync()
        return
    _w("init done")
