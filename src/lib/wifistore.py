# wifistore.py — remember multiple Wi-Fi networks so the user need not retype.
#
# Stores successfully-connected SSID/password pairs as a JSON array in the
# filesystem. The most recently used network is always last in the list and
# tried first during auto-connect. Kept deliberately tiny for easy audit.
import json

_PATH = "wifi.json"


def save(ssid, password):
    """Add or move a network to the top of the saved list. Returns True."""
    networks = _load_list()
    # Remove any existing entry for this SSID.
    networks = [n for n in networks if n.get("ssid") != ssid]
    networks.append({"ssid": ssid, "password": password})
    return _write(networks)


def load():
    """Return (ssid, password) for the *most recently used* saved network,
    or (None, None) if the store is empty. Kept for backward compat."""
    networks = _load_list()
    if not networks:
        return None, None
    last = networks[-1]
    return last.get("ssid"), last.get("password")


def load_networks():
    """Return the full list of saved networks, newest last."""
    return _load_list()


def find_network(ssid):
    """Return {"ssid", "password"} for a specific SSID, or None."""
    for n in _load_list():
        if n.get("ssid") == ssid:
            return n
    return None


def remove(ssid):
    """Forget a specific network. Returns True if it was found."""
    networks = _load_list()
    new = [n for n in networks if n.get("ssid") != ssid]
    if len(new) != len(networks):
        return _write(new)
    return False


def clear():
    """Forget ALL saved networks."""
    try:
        import os
        os.remove(_PATH)
    except Exception:
        pass


def _load_list():
    """Return list of {"ssid": ..., "password": ...} dicts."""
    try:
        with open(_PATH) as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        # Backward compat: old format {"ssid": ..., "password": ...}
        if isinstance(data, dict) and data.get("ssid"):
            return [{"ssid": data["ssid"], "password": data.get("password", "")}]
    except Exception:
        pass
    return []


def _write(networks):
    """Save the network list to flash. Returns True on success."""
    try:
        with open(_PATH, "w") as f:
            json.dump(networks, f)
        try:
            import os
            os.sync()
        except Exception:
            pass
        return True
    except Exception as e:  # noqa: BLE001
        print("wifistore: save failed:", e)
        return False
