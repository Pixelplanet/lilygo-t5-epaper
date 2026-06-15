# update_app.py — on-device OTA system updater.
#
# Checks a remote manifest (update.json) for newer versions of the platform
# files, shows what changed, and downloads + applies the update. After a
# successful update the user can reset to run the new code.
#
# Add to your launcher with entry: "update_app:open_updater"
from lib import debuglog, netconn
from lib.ui import theme
from lib.ui.core import Screen
from lib.ui.widgets import Button, Label, ProgressBar
from lib import updater


def open_updater(app):
    return UpdaterScreen(app)


class UpdaterScreen(Screen):
    def __init__(self, app):
        super().__init__(app, "System update")
        self._status = None
        self._btn = None
        self._bar = None
        self._pending = None
        self._busy = False

    def build(self):
        self.add_back_button()
        d = self.app.display

        local_ver, local_files = updater.local_version()
        nfiles = len(local_files)

        y = theme.TITLE_BAR_H + 12
        self.add(Label(theme.PAD, y,
                       "Installed: v{} ({} files)".format(local_ver, nfiles),
                       theme.BODY_SCALE))
        y += 36

        self._status = self.add(Label(theme.PAD, y,
                                       "Checks GitHub for newer platform versions.",
                                       theme.BODY_SCALE, theme.FG_MUTED))
        y += 50

        self._btn = self.add(Button(
            theme.PAD, y, d.width - 2 * theme.PAD, 72,
            "Check for updates", self._start_check, theme.H1_SCALE))
        y += 90
        self._bar = self.add(ProgressBar(theme.PAD, y,
                                         d.width - 2 * theme.PAD, 30, 0))

    def _start_check(self):
        """Called by the button press (sync). Kick off the async check."""
        if self._busy:
            return
        import asyncio
        self._busy = True
        self._btn.on_press = None  # disable button during check
        asyncio.create_task(self._do_check())

    async def _do_check(self):
        self._bar.set_value(10)
        self._status.set_text("Checking Wi-Fi...")
        await self.app.flush()

        # If already connected, skip the slow auto_connect scan.
        if not netconn.is_connected():
            if not await netconn.auto_connect():
                self._status.set_text("No Wi-Fi — connect in Wi-Fi app first.")
                self._bar.set_value(0)
                self._busy = False
                await self.app.flush()
                return

        self._bar.set_value(40)
        self._status.set_text("Fetching update manifest from GitHub...")
        await self.app.flush()

        try:
            self._pending = await updater.check()
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            debuglog.log("updater: check failed " + msg)
            if len(msg) > 100:
                msg = msg[:97] + "..."
            self._status.set_text("Network error: " + msg)
            self._bar.set_value(0)
            self._busy = False
            await self.app.flush()
            return

        self._bar.set_value(100)

        if self._pending is None:
            local_ver, _ = updater.local_version()
            self._status.set_text(
                "Up to date (v{}). No newer version found.".format(local_ver))
            self._busy = False
            await self.app.flush()
            return

        # Show what was found, then navigate to the detail screen.
        n = len(self._pending["files"])
        v = self._pending["version"]
        desc = self._pending.get("description", "")

        self._status.set_text(
            "Found v{} — {} changed file{}. Opening details...".format(
                v, n, "s" if n != 1 else ""))
        await self.app.flush()

        self.app.go(UpdateConfirmScreen(self.app, self._pending))


class UpdateConfirmScreen(Screen):
    def __init__(self, app, pending):
        super().__init__(app, "Update available")
        self._pending = pending
        self._status = None
        self._bar = None
        self._busy = False
        self._files_list = sorted(pending["files"].keys())

    def build(self):
        self.add_back_button()
        d = self.app.display

        v = self._pending["version"]
        desc = self._pending.get("description", "")
        n = len(self._files_list)

        y = theme.TITLE_BAR_H + 12
        self.add(Label(theme.PAD, y,
                       "v{}  —  {} changed file{}".format(
                           v, n, "s" if n != 1 else ""),
                       theme.H1_SCALE))
        y += 36

        if desc:
            self.add(Label(theme.PAD, y, "Changes: " + desc,
                           theme.BODY_SCALE, theme.FG_MUTED))
            y += 28

        # File list header.
        self.add(Label(theme.PAD, y, "Files to update:",
                       theme.BODY_SCALE, theme.FG_MUTED))
        y += 22

        # Show all changed files (up to 10, then truncate).
        shown = self._files_list[:10]
        for f in shown:
            short = f.split("/")[-1]
            dirs = "/".join(f.split("/")[:-1])
            label = "  " + short
            if dirs:
                label = dirs + "/" + short
            self.add(Label(theme.PAD + 4, y, label, theme.BODY_SCALE,
                           theme.FG_MUTED))
            y += 20
        if len(self._files_list) > 10:
            self.add(Label(theme.PAD + 4, y,
                           "  ... and {} more".format(
                               len(self._files_list) - 10),
                           theme.BODY_SCALE, theme.FG_MUTED))
            y += 20

        y += 14
        self._status = self.add(Label(theme.PAD, y, "",
                                       theme.BODY_SCALE, theme.FG_MUTED))
        y += 32

        self._bar = self.add(ProgressBar(theme.PAD, y,
                                         d.width - 2 * theme.PAD, 30, 0))
        y += 46

        self.add(Button(
            theme.PAD, y, d.width - 2 * theme.PAD, 72,
            "Download & install update", self._start_download,
            theme.H1_SCALE))

    def _start_download(self):
        if self._busy:
            return
        import asyncio
        self._busy = True
        asyncio.create_task(self._do_update())

    async def _do_update(self):
        nfiles = len(self._pending["files"])

        def progress(path, done, total):
            pct = int(done * 100 / total) if total else 100
            self._bar.set_value(pct)
            self._status.set_text(
                "[{}/{}] {}".format(done, total, path.split("/")[-1]))

        self._status.set_text("Starting download ({} files)...".format(nfiles))
        self._bar.set_value(0)
        await self.app.flush()

        try:
            n = await updater.download_updates(self._pending,
                                               on_progress=progress)
        except Exception as e:  # noqa: BLE001
            debuglog.log("updater: download failed " + str(e))
            msg = str(e)
            if len(msg) > 100:
                msg = msg[:97] + "..."
            self._status.set_text("Failed: " + msg)
            self._bar.set_value(0)
            self._busy = False
            await self.app.flush()
            return

        self._bar.set_value(100)
        self._status.set_text(
            "{} file{} updated. Ready to reset.".format(
                n, "s" if n != 1 else ""))
        await self.app.flush()

        self.app.go(UpdateDoneScreen(self.app))


class UpdateDoneScreen(Screen):
    def __init__(self, app):
        super().__init__(app, "Update complete")

    def build(self):
        self.add_back_button()
        d = self.app.display

        y = theme.TITLE_BAR_H + 20
        self.add(Label(theme.PAD, y, "Update installed successfully!",
                       theme.H1_SCALE))
        y += 48
        self.add(Label(theme.PAD, y,
                       "The device will restart and boot the new version.",
                       theme.BODY_SCALE, theme.FG_MUTED))
        y += 80

        self.add(Button(theme.PAD, y,
                        d.width - 2 * theme.PAD, 80,
                        "Reset now", updater.do_reset, theme.TITLE_SCALE))

