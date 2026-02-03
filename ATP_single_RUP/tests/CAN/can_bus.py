import can

def get_can_bus():
    """
    Returns a SocketCAN bus instance.
    UI and tests all use the SAME bus.
    """
    return can.interface.Bus(
        channel="can0",
        bustype="socketcan"
    )

