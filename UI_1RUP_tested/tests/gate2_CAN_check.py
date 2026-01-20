import time
from tests.CAN.can_commands import start_atp, read_id_pins_request
from tests.CAN.can_utils import flush_rx, wait_for_idpins, IDPINS_MAP

EXPECTED_IDPINS = {0x00,0x06}
TIMEOUT_S = 2.0
POST_START_DELAY_S = 3   # ← IMPORTANT (300 ms)

def gate2_can_check() -> bool:
    """
    Gate 2:
    - Send START_ATP ONCE
    - Wait a short time for RUP to switch mode
    - Listen for ID-pins response
    """

    print("\n========== GATE 2 ==========")

    flush_rx()
    start_atp()
    read_id_pins_request()

    # ✅ Give RUP time to enter ATP mode
    time.sleep(POST_START_DELAY_S)

    val = wait_for_idpins(TIMEOUT_S)

    if val is None:
        print("❌ GATE 2 FAIL: no ID-pins response")
        return False

    desc = IDPINS_MAP.get(val, "UNKNOWN")
    print(f"🔎 ID-pins = 0x{val:02X} ({desc})")

    if val in EXPECTED_IDPINS:
        print("✅ GATE 2 PASS")
        return True

    print("❌ GATE 2 FAIL: wrong ID-pins")
    return False
