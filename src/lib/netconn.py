# netconn.py - shared Wi-Fi connection helpers.
#
# Centralises bringing up the station interface using saved credentials, so
# both the boot-time auto-connect and the apps (e.g. prices) behave the same.
# Uses a reduced TX power to avoid browning out the e-paper boost converter
# during association.
#
# auto_connect() scans for visible networks and tries every known network that
# is in range, most-recently-used first. It stops at the first successful one.
from lib import wifistore


def is_connected():
    """True if the station interface currently has a Wi-Fi connection."""
    try:
        import network
        return network.WLAN(network.STA_IF).isconnected()
    except Exception:
        return False


def connected_ssid():
    """Return connected SSID as text, or None when disconnected/unknown."""
    try:
        import network
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        if not sta.isconnected():
            return None
        val = sta.config("essid")
        if isinstance(val, (bytes, bytearray)):
            val = val.decode("utf-8", "replace")
        if not val:
            return None
        return str(val)
    except Exception:
        return None


def _begin(ssid, password):
    import network
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    if sta.isconnected():
        return sta, True
    try:
        sta.config(txpower=8)
    except Exception:
        pass
    sta.connect(ssid, password or "")
    return sta, False


async def auto_connect(timeout=10):
    """Connect to the first known network found in range.

    Tries saved networks in most-recently-used order. Returns True if
    Wi-Fi association succeeds. Simple and fast — no DHCP wait loops
    that can hang.
    """
    import asyncio
    import network

    sta = network.WLAN(network.STA_IF)
    sta.active(True)

    # Already connected — nothing to do.
    if sta.isconnected():
        return True

    networks = wifistore.load_networks()
    if not networks:
        return False

    # Quick scan.
    try:
        sta.disconnect()
        await asyncio.sleep_ms(300)
    except Exception:
        pass
    visible = set()
    try:
        for r in sta.scan():
            ssid = r[0]
            if isinstance(ssid, (bytes, bytearray)):
                ssid = ssid.decode("utf-8", "replace")
            if ssid:
                visible.add(ssid)
    except Exception:
        pass

    # Try each known network, MRU first. Stop at first success.
    for net in reversed(networks):
        ssid = net.get("ssid")
        password = net.get("password", "")
        if ssid not in visible:
            continue
        try:
            try:
                sta.config(txpower=8)
            except Exception:
                pass
            sta.connect(ssid, password)
            for _ in range(timeout * 10):
                if sta.isconnected():
                    return True
                await asyncio.sleep_ms(100)
        except Exception:
            pass

    return sta.isconnected()


def connect_blocking(timeout=12):
    """Blocking connect to the saved network. Returns True on success.

    For code paths that aren't async (kept for the apps' existing call sites).
    """
    import time
    ssid, password = wifistore.load()
    if not ssid:
        return False
    try:
        sta, already = _begin(ssid, password)
    except Exception:
        return False
    if already:
        return True
    for _ in range(timeout * 10):
        if sta.isconnected():
            return True
        time.sleep_ms(100)
    return sta.isconnected()
