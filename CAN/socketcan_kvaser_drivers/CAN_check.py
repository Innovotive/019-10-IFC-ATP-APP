import can
import time

# ==============================
# CONFIG
# ==============================
CAN_CHANNEL = "can0"

START_ATP_CAN_ID = 0x002
START_ATP = 0x02

# In your capture, the RUP sends the response on ID 0x065
RESPONSE_CAN_ID = 0x065      # set to None if you want to accept any ID

TIMEOUT_S = 2.0              # how long to wait after sending START_ATP

# ------------------------------
# ID pins report mapping
# ------------------------------
# Your doc:
#  - ALL OPEN            -> 0x40 + 0x00
#  - ID3 only shorted    -> 0x40 + 0x01
#  - ID2 only shorted    -> 0x40 + 0x02
#  - ID3+ID2 shorted     -> 0x40 + 0x03
#  - ID1 only shorted    -> 0x40 + 0x04
#  - ID3+ID1 shorted     -> 0x40 + 0x05
#  - ID2+ID1 shorted     -> 0x40 + 0x06
#  - ID3+ID2+ID1 shorted -> 0x40 + 0x07
#
# But on your bus you’re seeing only 0x00..0x07 (no +0x40).
# This script supports BOTH.

IDPINS_VALUE_TO_DESC = {
    0x00: "ALL OPEN (no shorts)",
    0x01: "ID3 only shorted",
    0x02: "ID2 only shorted",
    0x03: "ID3 + ID2 shorted",
    0x04: "ID1 only shorted",
    0x05: "ID3 + ID1 shorted",
    0x06: "ID2 + ID1 shorted",
    0x07: "ID3 + ID2 + ID1 shorted",
}

# ✅ Choose what you expect for this RUP (can be 1 value or a list of allowed values)
EXPECTED_IDPINS_VALUES = {0x00}   # Example: expecting ALL OPEN

# If your RUP sometimes reports 0x40..0x47 instead, you do NOT need to change anything.


# ==============================
# CAN setup
# ==============================
bus = can.interface.Bus(channel=CAN_CHANNEL, bustype="socketcan")


def send_start_atp():
    msg = can.Message(
        arbitration_id=START_ATP_CAN_ID,
        data=[START_ATP],
        is_extended_id=False
    )
    bus.send(msg)
    print(f"✅ Sent START_ATP: ID=0x{START_ATP_CAN_ID:X}, DATA=[0x{START_ATP:02X}]")


def normalize_idpins_byte(b: int):
    """
    Accept BOTH formats:
      - raw value: 0x00..0x07
      - packed value: 0x40..0x47  (0x40 + value)
    Return (value_0_to_7, format_str) or (None, None) if not recognized.
    """
    if 0x00 <= b <= 0x07:
        return b, "raw(0x00..0x07)"
    if 0x40 <= b <= 0x47:
        return (b - 0x40), "packed(0x40+value)"
    return None, None


def gate2_check():
    print("\n==============================")
    print("   GATE 2 – START ATP + ID PINS")
    print("==============================")

    send_start_atp()

    deadline = time.time() + TIMEOUT_S
    print(f"⏳ Waiting up to {TIMEOUT_S:.1f}s for ID-pins report...")

    while time.time() < deadline:
        msg = bus.recv(timeout=0.1)
        if msg is None:
            continue

        # Optional filtering on response CAN ID
        if RESPONSE_CAN_ID is not None and msg.arbitration_id != RESPONSE_CAN_ID:
            # Still print for debug if you want:
            # print(f"(ignore) RX ID=0x{msg.arbitration_id:X} DATA={[hex(x) for x in msg.data]}")
            continue

        if len(msg.data) < 1:
            continue

        raw_byte = msg.data[0]
        val, fmt = normalize_idpins_byte(raw_byte)

        print(f"📥 RX: ID=0x{msg.arbitration_id:X} DLC={msg.dlc} DATA={[hex(x) for x in msg.data]}")

        if val is None:
            print(f"⚠️ Got byte 0x{raw_byte:02X} but it doesn't match ID-pins formats (0x00..0x07 or 0x40..0x47).")
            continue

        desc = IDPINS_VALUE_TO_DESC.get(val, "Unknown")
        print(f"🔎 ID-pins report = 0x{val:02X} ({desc})   [{fmt}]")

        if val in EXPECTED_IDPINS_VALUES:
            print("✅ GATE 2 PASS: ID-pins value is acceptable")
            return True
        else:
            exp_desc = ", ".join([f"0x{x:02X}({IDPINS_VALUE_TO_DESC.get(x,'?')})" for x in sorted(EXPECTED_IDPINS_VALUES)])
            print("❌ GATE 2 FAIL: wrong ID-pins value")
            print(f"   Expected one of: {exp_desc}")
            return False

    print("❌ GATE 2 FAIL: No ID-pins report received within timeout")
    return False


if __name__ == "__main__":
    gate2_check()
