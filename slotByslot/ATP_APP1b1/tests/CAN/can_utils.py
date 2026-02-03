# tests/CAN/can_utils.py
import time
from .can_bus import get_can_bus

IDPINS_MAP = {
    0x00: "SLOT 1",
    0x01: "SLOT 2",
    0x02: "SLOT 3",
    0x03: "SLOT 4",
    0x04: "ID1 only",
    0x05: "ID3 + ID1",
    0x06: "ID2 + ID1",
    0x07: "ID3 + ID2 + ID1",
}


def flush_rx():
    """
    Flush RX safely. If bus was dead, force reopen.
    """
    bus = get_can_bus()
    try:
        while bus.recv(timeout=0.0):
            pass
    except ValueError:
        # FD is dead -> reopen and try once more
        bus = get_can_bus(force_reopen=True)
        while bus.recv(timeout=0.0):
            pass


def normalize_idpins(byte):
    # Accept 0x00..0x07 or 0x40..0x47
    if 0x00 <= byte <= 0x07:
        return byte
    if 0x40 <= byte <= 0x47:
        return byte - 0x40
    return None


def extract_idpins_from_payload(data):
    for b in data:
        v = normalize_idpins(b)
        if v is not None:
            return v
    return None


def wait_for_idpins(slot_cfg, timeout_s: float):
    """
    Wait for ID-pins report for a specific slot response ID.
    Returns 0x00..0x07 or None.
    """
    bus = get_can_bus()
    deadline = time.time() + float(timeout_s)

    while time.time() < deadline:
        try:
            msg = bus.recv(timeout=0.1)
        except ValueError:
            # FD dead -> reopen and continue
            bus = get_can_bus(force_reopen=True)
            continue

        if not msg or not msg.data:
            continue

        # slot-specific response ID
        if msg.arbitration_id != int(slot_cfg.can_rsp_id):
            continue

        val = extract_idpins_from_payload(msg.data)

        print(
            f"📥 CAN RX | ID=0x{msg.arbitration_id:03X} "
            f"DATA={' '.join(f'{b:02X}' for b in msg.data)}"
        )

        if val is not None:
            return val

    return None
