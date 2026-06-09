"""CPython shim of MicroPython's `network` module for the simulator.

Returns a fixed fake scan list and simulates association: open networks always
connect; secured networks connect only if the password is >= 8 characters
(mirrors WPA2 minimum length) so the keyboard flow can be demonstrated.
"""
STA_IF = 0
AP_IF = 1

# (ssid, bssid, channel, rssi, authmode, hidden) - authmode 0 == open
_FAKE = [
    (b"HomeNet_5G", b"\x00\x11\x22\x33\x44\x55", 36, -48, 3, False),
    (b"CoffeeShop_Free", b"\x00\xaa\xbb\xcc\xdd\xee", 6, -57, 0, False),
    (b"Neighbour_2.4", b"\x00\x12\x34\x56\x78\x9a", 11, -67, 3, False),
    (b"LilyGoLab", b"\x00\xde\xad\xbe\xef\x00", 1, -72, 4, False),
    (b"Guest", b"\x00\x01\x02\x03\x04\x05", 9, -80, 0, False),
    (b"IoT_Sensors", b"\x00\x99\x88\x77\x66\x55", 3, -85, 3, True),
]


class WLAN:
    def __init__(self, iface=STA_IF):
        self.iface = iface
        self._active = False
        self._connected = False
        self._ssid = None

    def active(self, state=None):
        if state is None:
            return self._active
        self._active = bool(state)
        return self._active

    def scan(self):
        return list(_FAKE)

    def connect(self, ssid, password=""):
        self._ssid = ssid
        # Find authmode for the ssid
        secured = True
        for r in _FAKE:
            if r[0] == (ssid.encode() if isinstance(ssid, str) else ssid):
                secured = r[4] != 0
                break
        self._connected = (not secured) or (len(password) >= 8)
        print("sim wifi: connect '%s' -> %s" % (ssid, self._connected))

    def isconnected(self):
        return self._connected

    def ifconfig(self):
        return ("192.168.1.42", "255.255.255.0", "192.168.1.1", "1.1.1.1")
