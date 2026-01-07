import time
from .can_bus import get_can_bus

bus = get_can_bus()

# RUP response ID (from your sniff)
RUP_RESPONSE_ID = 0x065

IDPINS_MAP = {
    0x00: "ALL OPEN",
    0x01: "ID3 only",
    0x02: "ID2 only",
    0x03: "ID3 + ID2",
    0x04: "ID1 only",
    0x05: "ID3 + ID1",
    0x06: "ID2 + ID1",
    0x07: "ID3 + ID2 + ID1",
}

def flush_rx():
    """Clear old CAN frames before starting a test"""
    while bus.recv(timeout=0.0):
        pass

def normalize_idpins(byte):
    """
    Accept:
      - 0x00..0x07
      - 0x40..0x47
    """
    if 0x00 <= byte <= 0x07:
        return byte
    if 0x40 <= byte <= 0x47:
        return byte - 0x40
    return None

def wait_for_idpins(timeout_s: float):
    """
    Waits for ID-pins report.
    Returns value 0x00..0x07 or None.
    """
    deadline = time.time() + timeout_s

    while time.time() < deadline:
        msg = bus.recv(timeout=0.1)
        if not msg:
            continue

        if msg.arbitration_id != RUP_RESPONSE_ID:
            continue

        if not msg.data:
            continue

        raw = msg.data[0]
        val = normalize_idpins(raw)

        print(f"📥 RX | ID=0x{msg.arbitration_id:X} | DATA={[hex(b) for b in msg.data]}")

        return val

    return None
