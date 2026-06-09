# boot.py - runs once at power-on before main.py.
# Keep this minimal and fast; heavy work belongs in main.py / the app.
import gc

gc.enable()

try:
    import esp
    esp.osdebug(None)  # silence native debug noise on the REPL
except Exception:
    pass

gc.collect()
