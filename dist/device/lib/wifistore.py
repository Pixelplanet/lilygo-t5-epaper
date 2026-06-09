# wifistore.py - remember the last Wi-Fi network so the user need not retype it.
#
# Stores the most recently *successfully connected* SSID/password as JSON in the
# filesystem. Kept deliberately tiny so it is easy to audit and to clear.
import json

_PATH = "wifi.json"


def save(ssid, password):
    """Persist the last good credentials. Returns True on success."""
    try:
        with open(_PATH, "w") as f:
            json.dump({"ssid": ssid, "password": password}, f)
        try:
            import os
            os.sync()
        except Exception:
            pass
        return True
    except Exception as e:  # noqa: BLE001
        print("wifistore: save failed:", e)
        return False


def load():
    """Return (ssid, password) for the saved network, or (None, None)."""
    try:
        with open(_PATH) as f:
            data = json.load(f)
        return data.get("ssid"), data.get("password")
    except Exception:
        return None, None


def clear():
    """Forget the saved network."""
    try:
        import os
        os.remove(_PATH)
    except Exception:
        pass
