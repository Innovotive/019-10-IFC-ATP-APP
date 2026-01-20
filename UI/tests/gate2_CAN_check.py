# tests/gate2_CAN_check.py
import time
from tests.CAN.can_commands import start_atp, read_id_pins_request
from tests.CAN.can_utils import flush_rx, wait_for_idpins, IDPINS_MAP

TIMEOUT_S = 2.0
POST_START_DELAY_S = 1
POST_READ_DELAY_S = 1
RETRY_DELAY_S = 0.5
MAX_ATTEMPTS = 3

# ✅ expected “ID config” per slot (your desired configs)
EXPECTED_PER_SLOT = {
    1: 0x06,  # slot1 0x06
    2: 0x05,  # slot2 0x03
    3: 0x03,  # slot3
    4: 0x04,  # slot4
}

# optional: accept floating as warning-pass if you want
PASS_WEAK_FLOAT = 0x07


def gate2_can_check(slot: int) -> bool:
    expected = EXPECTED_PER_SLOT.get(slot, None)
    if expected is None:
        raise ValueError(f"No expected ID config for slot {slot}")

    print("\n========== GATE 2 ==========")
    print(f"[GATE2] Slot={slot} expected=0x{expected:02X}")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"[GATE2] Attempt {attempt}/{MAX_ATTEMPTS}")

        flush_rx()

        start_atp()
        time.sleep(POST_START_DELAY_S)

        read_id_pins_request()
        time.sleep(POST_READ_DELAY_S)

        val = wait_for_idpins(TIMEOUT_S)

        if val is None:
            print("[GATE2][WARN] No ID-pins response")
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_S)
                continue
            print("❌ GATE 2 FAIL: no ID-pins response")
            return False

        desc = IDPINS_MAP.get(val, "UNKNOWN")
        print(f"🔎 ID-pins raw = 0x{val:02X} ({desc})")

        if val == expected:
            print("✅ GATE 2 PASS")
            return True

        if val == PASS_WEAK_FLOAT:
            print("⚠️ GATE 2 PASS (WARNING): floating (0x07)")
            return True

        print("❌ GATE 2 FAIL: wrong ID-pins")
        return False

    return False
