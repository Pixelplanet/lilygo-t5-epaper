# Editing files with Thonny (drag-and-drop style)

Unlike a Raspberry Pi Pico or a micro:bit, this board **does not show up as a USB
drive** in Windows/macOS/Linux — so you can't just copy `.py` files onto it in a
file explorer. That's not a limitation of this project; it's how MicroPython works
on the **ESP32-S3**:

- The on-board Python filesystem lives in internal flash as a **littlefs**
  partition, not a FAT volume.
- The USB connection is a **serial port** (the REPL), which is what tools talk to.
- Standard ESP32-S3 MicroPython firmware doesn't expose a USB Mass-Storage
  interface, so the OS only ever sees a COM/tty port — never a drive letter.

The good news: **Thonny** gives you the same "see the files, drag them over, run
`main.py`" experience through a simple GUI, with no firmware changes. This is the
recommended way to poke at the board if you don't want to use the command line.

---

## 1. Install Thonny

Download it from <https://thonny.org> (Windows/macOS/Linux). Install and open it.

## 2. Point Thonny at the board

1. Plug the board in. Note its **app serial port** (the native USB-CDC port —
   the same one you use with `mpremote`). See
   [troubleshooting.md → Find the ports](troubleshooting.md#find-the-ports) if
   you're not sure which COM/tty it is.
2. In Thonny: **Tools → Options… → Interpreter**.
3. Set **interpreter** to *MicroPython (ESP32)*.
4. Set **Port** to the board's app port (e.g. `COM5`, or `/dev/ttyACM0`).
5. Click **OK**. The bottom **Shell** pane should show a MicroPython `>>>`
   prompt. If it doesn't, press the **Stop/Restart** button (or tap RST on the
   board) and re-check the port.

> If Thonny can't connect, close any other program using the port first — only
> one tool can own the serial port at a time (Thonny **or** `mpremote`, not both).

## 3. Show the device files

Turn on the file panels: **View → Files**.

You now get two stacked panes on the left:

- **This computer** — your PC's folders.
- **MicroPython device** — the files on the board's flash (`main.py`, `config.py`,
  `lib/`, `apps/`, …).

## 4. Upload / download files (drag-and-drop)

- **PC → board:** right-click a file in *This computer* → **Upload to /**.
  (You can also drag it onto the device pane.)
- **board → PC:** right-click a file in *MicroPython device* → **Download to…**.
- **Edit in place:** double-click a file in the device pane to open it, edit it,
  then **Ctrl-S** — Thonny saves it straight back to the board.

To upload a whole folder (e.g. `apps/`), select it on the PC side and **Upload**;
Thonny recreates the folder on the device.

## 5. Run it

- Press the green **Run** button (or **F5**) to execute the currently open file.
- To run the app the way it starts on boot, open the device's **`main.py`** and
  Run it, or just **tap RST** on the board — `main.py` auto-starts.
- **Ctrl-C** in the Shell (or the **Stop** button) interrupts a running program
  and drops you back to the `>>>` prompt — handy if a screen hangs.

## 6. You still can't lock yourself out

`main.py` always leaves an escape window (see the main README):

- Hold **BOOT** during reset → skip the app, land in the REPL.
- Or press **Ctrl-C** in Thonny's Shell.

So edit freely — if something breaks, interrupt, fix the file in the device pane,
save, and tap RST.

---

## Why not make it a real USB drive?

Technically the ESP32-S3 has native USB and *can* present a USB Mass-Storage
device, but it's a poor fit here:

- It needs a **separate FAT partition** plus a translation layer — you can't just
  share the existing littlefs filesystem.
- The PC's disk cache and the board writing the **same flash** at the same time
  corrupts the filesystem unless you eject perfectly every time.
- It's experimental on ESP32-S3 MicroPython and would mean shipping and
  maintaining a fragile custom firmware feature.

**Thonny** avoids all of that and gives you 95% of the convenience. If you prefer
no cable at all, WebREPL over Wi-Fi is another option — but Thonny is the simplest
reliable path.
