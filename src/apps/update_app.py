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
from lib.ui.widgets import Button, Label
from lib import updater


def open_updater(app):
    return UpdaterScreen(app)


class UpdaterScreen(Screen):
    def __init__(self, app):
        super().__init__(app, "System update")
        self._status = None
        self._btn = None
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

        self._status = self.add(Label(theme.PAD, y, "Tap Check to look for updates.",
                                       theme.BODY_SCALE, theme.FG_MUTED))
        y += 50

        self._btn = self.add(Button(
            theme.PAD, y, d.width - 2 * theme.PAD, 72,
            "Check for updates", self._do_check, theme.H1_SCALE))

    async def _do_check(self):
        if self._busy:
            return
        self._busy = True
        self._btn.on_press = None

        self._status.set_text("Connecting...")
        self.set_wifi_state("wait")
        await self.app.flush()

        if not await netconn.auto_connect():
            self.set_wifi_state("off")
            self._status.set_text("Wi-Fi needed — connect in Wi-Fi app first.")
            self._busy = False
            await self.app.flush()
            return

        self.set_wifi_state("on")
        self._status.set_text("Checking for updates...")
        await self.app.flush()

        try:
            self._pending = await updater.check()
        except Exception as e:  # noqa: BLE001
            debuglog.log("updater: check failed " + str(e))
            self._status.set_text("Could not check — see debug.log")
            self._busy = False
            await self.app.flush()
            return

        if self._pending is None:
            self._status.set_text("You're up to date! No updates available.")
            self._busy = False
            await self.app.flush()
            return

        n = len(self._pending["files"])
        desc = self._pending.get("description", "")
        v = self._pending["version"]

        self._status.set_text(
            "v{} available ({} file{}). {}".format(
                v, n, "s" if n != 1 else "", desc))
        await self.app.flush()

        # Rebuild the button to be an "Update now" action.
        self.app.go(UpdateConfirmScreen(self.app, self._pending))


class UpdateConfirmScreen(Screen):
    def __init__(self, app, pending):
        super().__init__(app, "Update available")
        self._pending = pending
        self._status = None
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
                       "Update to v{} ({} files)".format(v, n),
                       theme.H1_SCALE))
        y += 40

        if desc:
            self.add(Label(theme.PAD, y, desc, theme.BODY_SCALE,
                           theme.FG_MUTED))
            y += 30

        # Show the first few changed files so the user knows what's affected.
        shown = self._files_list[:8]
        for f in shown:
            self.add(Label(theme.PAD + 8, y, f, theme.SMALL_SCALE,
                           theme.FG_MUTED))
            y += 14
        if len(self._files_list) > 8:
            self.add(Label(theme.PAD + 8, y,
                           "... and {} more".format(
                               len(self._files_list) - 8),
                           theme.SMALL_SCALE, theme.FG_MUTED))
            y += 14

        y += 16
        self._status = self.add(Label(theme.PAD, y, "",
                                       theme.BODY_SCALE, theme.FG_MUTED))
        y += 36

        self.add(Button(
            theme.PAD, y, d.width - 2 * theme.PAD, 72,
            "Download & install update", self._do_update,
            theme.H1_SCALE))

    async def _do_update(self):
        if self._busy:
            return
        self._busy = True

        def progress(path, done, total):
            self._status.set_text(
                "Downloading [{}/{}] {}".format(done, total,
                                                path.split("/")[-1]))

        self._status.set_text("Starting download...")
        self.set_wifi_state("on")
        await self.app.flush()

        try:
            n = await updater.download_updates(self._pending,
                                               on_progress=progress)
        except Exception as e:  # noqa: BLE001
            debuglog.log("updater: download failed " + str(e))
            self._status.set_text("Download failed — see debug.log")
            self._busy = False
            await self.app.flush()
            return

        self._status.set_text(
            "Updated {} file{}. Reset to apply.".format(
                n, "s" if n != 1 else ""))
        await self.app.flush()

        # Replace the button with a reset button.
        self.app.go(UpdateDoneScreen(self.app))


class UpdateDoneScreen(Screen):
    def __init__(self, app):
        super().__init__(app, "Update complete")

    def build(self):
        self.add_back_button()
        d = self.app.display

        y = theme.TITLE_BAR_H + 12
        self.add(Label(theme.PAD, y, "Update installed successfully!",
                       theme.H1_SCALE))
        y += 50
        self.add(Label(theme.PAD, y,
                       "The device will reset and boot the new version.",
                       theme.BODY_SCALE, theme.FG_MUTED))
        y += 60

        self.add(Button(theme.PAD, y,
                        d.width - 2 * theme.PAD, 80,
                        "Reset now", updater.do_reset, theme.TITLE_SCALE))
