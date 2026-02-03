# tests/gates/gate1_can_check.py
import time
from tests.CAN.can_commands import start_atp, read_id_pins_request
from tests.CAN.can_utils import flush_rx, wait_for_idpins, IDPINS_MAP

TIMEOUT_S = 2.0
POST_START_DELAY_S = 3.0  # keep as you use now

def run_gate1_can_check(expected_values: set, log_cb=None) -> bool:
    def log(m): log_cb(m) if log_cb else print(m)

    log("========== GATE 1 ==========")

    flush_rx()

    # enter ATP mode + request id pins
    start_atp()
    read_id_pins_request()

    time.sleep(POST_START_DELAY_S)

    val = wait_for_idpins(TIMEOUT_S)
    if val is None:
        log("❌ GATE 1 FAIL: no ID-pins response")
        return False

    desc = IDPINS_MAP.get(val, "UNKNOWN")
    log(f"🔎 ID-pins = 0x{val:02X} ({desc})")

    if val in expected_values:
        log("✅ GATE 1 PASS")
        return True

    log(f"❌ GATE 1 FAIL: wrong ID-pins (expected {sorted(expected_values)})")
    return False
