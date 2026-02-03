# tests/CAN/can_bus.py
import can
from typing import Optional

_bus: Optional[can.BusABC] = None

def get_can_bus(channel: str = "can0") -> can.BusABC:
    """
    Return a shared SocketCAN bus instance.
    All gates/UI should use the SAME bus.
    """
    global _bus
    if _bus is None:
        _bus = can.interface.Bus(channel=channel, bustype="socketcan")
    return _bus

def shutdown_can_bus():
    global _bus
    if _bus is not None:
        try:
            _bus.shutdown()
        except Exception:
            pass
        _bus = None
