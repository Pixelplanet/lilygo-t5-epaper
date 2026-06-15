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


async def auto_connect(timeout=12):
    """Scan and connect to the first known network found in range.

    Tries saved networks in most-recently-used order. Waits for DHCP (IP
    assignment) after association. Non-blocking (awaits between polls).

    Returns True if a working connection (with IP) is established.
    """
    import asyncio
    import network

    sta = network.WLAN(network.STA_IF)
    sta.active(True)

    # Already connected with an IP — nothing to do.
    if sta.isconnected():
        try:
            ip = sta.ifconfig()[0]
            if ip and ip != "0.0.0.0":
                return True
        except Exception:
            pass

    networks = wifistore.load_networks()
    if not networks:
        return False

    # If we're in a transitional state (associating), wait for it to settle
    # rather than starting a new scan+connect cycle.
    status = sta.status()
    if status not in (0, 1001):  # not IDLE or WRONG_PASSWORD
        # Give it a moment to finish associating.
        for _ in range(30):
            if sta.isconnected():
                break
            await asyncio.sleep_ms(100)

    if sta.isconnected():
        try:
            ip = sta.ifconfig()[0]
            if ip and ip != "0.0.0.0":
                return True
        except Exception:
            pass
        # Connected but no IP yet — wait for DHCP.
        for _ in range(50):  # up to 5s
            try:
                ip = sta.ifconfig()[0]
                if ip and ip != "0.0.0.0":
                    return True
            except Exception:
                pass
            await asyncio.sleep_ms(100)

    # Scan for visible networks, then try each known one.
    visible = set()
    try:
        sta.disconnect()
        await asyncio.sleep_ms(400)
    except Exception:
        pass
    await asyncio.sleep_ms(150)
    try:
        for r in sta.scan():
            ssid = r[0]
            if isinstance(ssid, (bytes, bytearray)):
                ssid = ssid.decode("utf-8", "replace")
            if ssid:
                visible.add(ssid)
    except Exception:
        pass

    # Try networks in MRU order.
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
            # Wait for association.
            for _ in range(timeout * 10):
                if sta.isconnected():
                    break
                await asyncio.sleep_ms(100)
            if not sta.isconnected():
                continue
            # Wait for DHCP.
            for _ in range(50):
                try:
                    ip = sta.ifconfig()[0]
                    if ip and ip != "0.0.0.0":
                        return True
                except Exception:
                    pass
                await asyncio.sleep_ms(100)
        except Exception:
            pass

    return False


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
