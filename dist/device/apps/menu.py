# menu.py - kept for backward compatibility. The home screen is now the
# icon-grid launcher (apps/launcher.py); MenuScreen forwards to it so existing
# "Menu" buttons in the demo apps still return to the new home screen.
from apps.launcher import LauncherScreen


def MenuScreen(app):  # noqa: N802 - kept callable for existing call sites
    return LauncherScreen(app)


def build_app(app):
    return LauncherScreen(app)
