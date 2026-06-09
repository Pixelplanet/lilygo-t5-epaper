import asyncio


def log(msg):
    try:
        with open("/diag.txt", "a") as f:
            f.write(str(msg) + "\n")
    except Exception:
        pass
    print(msg)


async def go():
    log("--- DIAG START ---")
    try:
        from lib.board import Board
        log("import board ok")
        board = await Board().begin()
        log("board.begin ok")
        from apps import wifi_demo
        from lib.ui.core import App
        log("import app ok")
        app = App(board.display, board.input, board)
        log("App() ok")
        screen = wifi_demo.build_app(app)
        log("build_app ok " + repr(screen))
        await app._activate(screen)
        log("activate ok - home drawn")
        # Pump a few input cycles
        for i in range(20):
            evs = await app.input.poll_events()
            if evs:
                log("EV " + str([(e.type, e.x, e.y) for e in evs]))
            await asyncio.sleep_ms(50)
        log("--- DIAG DONE ---")
    except Exception as e:
        import sys
        with open("/diag.txt", "a") as f:
            sys.print_exception(e, f)
        sys.print_exception(e)


def run():
    try:
        open("/diag.txt", "w").close()
    except Exception:
        pass
    asyncio.run(go())
