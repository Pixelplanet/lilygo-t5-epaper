import asyncio
import os


def log(msg):
    try:
        with open("/diag.txt", "a") as f:
            f.write(str(msg) + "\n")
        os.sync()
    except Exception:
        pass
    print(msg)


async def go():
    log("start")
    import epd
    log("import epd ok")
    epd.init()
    log("epd.init ok")
    buf = bytearray(b"\xff" * (960 * 540 // 2))
    log("buf alloc ok")
    epd.display(buf)
    log("epd.display white ok")

    from lib.shared_i2c import SharedI2CBus
    i2c = SharedI2CBus()
    log("i2c ok " + str([hex(a) for a in i2c.scan()]))

    from lib.gt911 import GT911
    t = GT911(i2c)
    ok = await t.begin()
    log("touch begin " + str(ok))

    from lib.display import Display
    log("import Display ok")
    d = Display()
    log("Display() ok")
    d.fill(15)
    d.text("HELLO DIAG", 100, 100, 0)
    d.refresh()
    log("Display drawn+refresh ok")
    log("DONE")


def run():
    try:
        open("/diag.txt", "w").close()
    except Exception:
        pass
    try:
        asyncio.run(go())
    except Exception as e:
        import sys
        with open("/diag.txt", "a") as f:
            sys.print_exception(e, f)
        os.sync()
        sys.print_exception(e)
