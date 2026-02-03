# tests/gates/gate3_id_flip_check.py
import time

from tests.power_PT.relay import idcfg_off
from tests.CAN.can_commands import read_id_pins_request
from tests.CAN.can_utils import flush_rx, wait_for_idpins, IDPINS_MAP

TIMEOUT_S = 2.0
SETTLE_AFTER_FLIP_S = 0.4

def run_gate3_id_flip_check(expected_values_after_flip: set, log_cb=None) -> bool:
    def log(m): log_cb(m) if log_cb else print(m)

    log("========== GATE 3 ==========")
    log("[GATE3] Flip IDCFG: GPIO8 OFF")
    idcfg_off()
    time.sleep(SETTLE_AFTER_FLIP_S)

    # Clear stale frames, then request ID
    flush_rx()
    read_id_pins_request()

    val = wait_for_idpins(TIMEOUT_S)
    if val is None:
        log("❌ GATE 3 FAIL: no ID-pins response after flip")
        return False

    desc = IDPINS_MAP.get(val, "UNKNOWN")
    log(f"🔎 ID-pins after flip = 0x{val:02X} ({desc})")

    if val in expected_values_after_flip:
        log("✅ GATE 3 PASS")
        return True

    log(f"❌ GATE 3 FAIL: wrong ID-pins after flip (expected {sorted(expected_values_after_flip)})")
    return False
