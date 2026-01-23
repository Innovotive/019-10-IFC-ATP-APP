# tests/CAN/can_utils.py
import time
from .can_bus import get_can_bus

bus = get_can_bus()

# Firmware replies with: send_can(..., 99) → 99 dec = 0x63
RUP_RESPONSE_ID = 0x63

ID_READ_REPORT_BASE = 0x40  # 0x40..0x47 encodes idconfig 0..7

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
    """Clear pending CAN frames."""
    for _ in range(max_drain):
        if bus.recv(timeout=0.0) is None:
            break


def normalize_idpins(byte_val: int):
    """
    Accept:
      - raw: 0x00..0x07
      - reported: 0x40..0x47  (0x40 + raw)
    Return raw 0..7 or None.
    """
    if 0x00 <= byte_val <= 0x07:
        return byte_val
    if ID_READ_REPORT_BASE <= byte_val <= ID_READ_REPORT_BASE + 7:
        return byte_val - ID_READ_REPORT_BASE
    return None


def extract_idpins_from_payload(data):
    """
    IMPORTANT FIX:
    -------------
    Old logic returned the FIRST byte that looks like 0..7 or 0x40..0x47.
    That can be wrong because payloads often contain 0x00 padding, and 0x00
    is a valid raw idconfig, so we could accidentally return 0 even when the
    real answer is elsewhere.

    New logic:
    - Prefer "reported" bytes 0x40..0x47 first (unambiguous)
    - Only if none exist, fall back to raw 0x00..0x07
    """
    # 1) Prefer reported encoding first (0x40..0x47)
    for b in data:
        b = int(b)
        if ID_READ_REPORT_BASE <= b <= ID_READ_REPORT_BASE + 7:
            return b - ID_READ_REPORT_BASE

    # 2) Fallback to raw only if no reported byte found
    for b in data:
        b = int(b)
        if 0x00 <= b <= 0x07:
            return b

    return None


def wait_for_idpins(timeout_s: float, expected: int = None, accept_float: bool = False):
    """
    Wait for ID-pins response from RUP.
    Returns raw idconfig (0..7) or None.

    EXTRA FIX:
    ----------
    If expected is provided, we ONLY accept that value (or floating 0x07 if
    accept_float=True). Otherwise we keep waiting until timeout.

    This prevents:
    - accidentally accepting a wrong value from a weird/early frame
    - accepting a padding-derived "fake" value
    """
    deadline = time.time() + timeout_s
    best_raw_candidate = None

    while time.time() < deadline:
        msg = bus.recv(timeout=0.1)
        if msg is None:
            continue

        if msg.arbitration_id != RUP_RESPONSE_ID:
            continue

        data = msg.data or []
        print(f"📥 RX | ID=0x{msg.arbitration_id:03X} | DATA={[f'0x{b:02X}' for b in data]}")

        val = extract_idpins_from_payload(data)
        if val is None:
            continue

        # If caller gave expected, enforce it
        if expected is not None:
            if val == expected:
                return val
            if accept_float and val == 0x07:
                return val
            # Not what we want → keep waiting for a better frame
            continue

        # No expected: if frame contains a reported byte, it's strong → return
        has_reported = any(ID_READ_REPORT_BASE <= int(b) <= ID_READ_REPORT_BASE + 7 for b in data)
        if has_reported:
            return val

        # Otherwise store raw as fallback and keep searching
        best_raw_candidate = val

    return best_raw_candidate
