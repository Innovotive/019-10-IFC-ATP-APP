import time
from .can_bus import get_can_bus

bus = get_can_bus()

# Firmware replies with: send_can(..., 99) → 99 dec = 0x63
RUP_RESPONSE_ID = 0x63

ID_READ_REPORT_BASE = 0x40  # 

# RAW idconfig interpretation (what the firmware actually reports)
IDPINS_MAP = {
    0x00: "000 (ID1, ID2, ID3 all shorted)",
    0x01: "001 (ID1+ID2 shorted)",
    0x02: "010 (ID1+ID3 shorted)",
    0x03: "011 (ID1 shorted)",
    0x04: "100 (ID2 + ID3 shorted)",
    0x05: "101 (ID2 shorted)",
    0x06: "110 (ID3 shorted)",
    0x07: "111 (no pins shorted / floating)",
}

def flush_rx(max_drain: int = 200):
    """Clear pending CAN frames"""
    for _ in range(max_drain):
        if bus.recv(timeout=0.0) is None:
            break

def normalize_idpins(byte_val: int):
    """
    Accept:
      - raw: 0x00..0x07
      - reported: 0x40..0x47
    Return raw 0..7 or None
    """
    if 0x00 <= byte_val <= 0x07:
        return byte_val
    if ID_READ_REPORT_BASE <= byte_val <= ID_READ_REPORT_BASE + 7:
        return byte_val - ID_READ_REPORT_BASE
    return None

def extract_idpins_from_payload(data):
    for b in data:
        val = normalize_idpins(int(b))
        if val is not None:
            return val
    return None

def wait_for_idpins(timeout_s: float):
    """
    Wait for ID-pins response from RUP.
    Returns raw idconfig (0..7) or None.
    """
    deadline = time.time() + timeout_s

    while time.time() < deadline:
        msg = bus.recv(timeout=0.1)
        if msg is None:
            continue

        if msg.arbitration_id != RUP_RESPONSE_ID:
            continue

        data = msg.data or []
        print(f"📥 RX | ID=0x{msg.arbitration_id:03X} | DATA={[f'0x{b:02X}' for b in data]}")

        val = extract_idpins_from_payload(data)
        if val is not None:
            return val

    return None
