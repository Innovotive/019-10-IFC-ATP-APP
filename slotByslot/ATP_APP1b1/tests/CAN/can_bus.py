# tests/CAN/can_bus.py
import threading
import can

# One shared CAN bus for the entire app
_LOCK = threading.Lock()
_BUS = None


def _is_bus_alive(bus) -> bool:
    """
    SocketCAN bus is 'dead' when its underlying socket FD is -1.
    """
    try:
        sock = getattr(bus, "socket", None)
        if sock is None:
            return True  # can't verify, assume OK
        return sock.fileno() >= 0
    except Exception:
        return False


def get_can_bus(channel="can0", bitrate=500000, force_reopen=False):
    """
    Returns a singleton python-can Bus.
    - Never create per-gate buses.
    - Reopen automatically if bus was shutdown or dead.
    """
    global _BUS

    with _LOCK:
        if _BUS is None:
            _BUS = can.Bus(interface="socketcan", channel=channel, bitrate=bitrate)
            return _BUS

        # If someone shut it down or it's dead, reopen
        if force_reopen or (not _is_bus_alive(_BUS)):
            try:
                _BUS.shutdown()
            except Exception:
                pass
            _BUS = can.Bus(interface="socketcan", channel=channel, bitrate=bitrate)

        return _BUS


def shutdown_can_bus():
    """
    Call only on app exit if you want.
    Do NOT call this inside gates.
    """
    global _BUS
    with _LOCK:
        if _BUS is not None:
            try:
                _BUS.shutdown()
            except Exception:
                pass
            _BUS = None
