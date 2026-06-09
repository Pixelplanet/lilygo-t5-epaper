# repair.py - Standalone e-paper screen maintenance / particle-dispersal tool.
#
# Repeated partial refreshes on the controllerless ED047TC1 panel build up an
# asymmetric charge that leaves ghost-boundary lines and gray "burn-in". This
# routine drives the WHOLE panel through alternating full-voltage white<->black
# cycles, pulling trapped electrophoretic particles off the glass and dispersing
# them evenly to restore a clean white display.
#
# Run from the REPL:  import repair  (or mpremote run tools/repair.py)
import time

import epd

CYCLES = 15   # 4 = routine maintenance, 10-15 = heavily ghosted panel
DELAY_MS = 50  # dwell per voltage inversion; 50ms matches the panel curve

print("Screen repair: initializing...")
epd.init()
epd.power_on()

# 1. Clean white baseline.
epd.clear()
time.sleep(1)

# 2. Deep neutralization sweep across the full panel.
print("Screen repair: neutralizing trapped particles ({} cycles)...".format(CYCLES))
epd.repair(CYCLES, DELAY_MS)

# 3. Final clean clear, then power down the rails to avoid static stress.
epd.clear()
epd.power_off()
print("Screen repair: complete - display restored.")
