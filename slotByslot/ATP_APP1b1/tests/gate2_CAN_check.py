# tests/gate2_CAN_check.py
import time
from slot_config import SlotConfig
from tests.CAN.can_commands import start_atp, read_id_pins_request
from tests.CAN.can_utils import flush_rx, wait_for_idpins, IDPINS_MAP

TIMEOUT_S = 2.0
POST_START_DELAY_S = 3.0

def gate2_can_check(slot_cfg: SlotConfig, log_cb=None) -> bool:
    """
    Gate 2:
    - flush RX
    - START_ATP once
    - READ_ID_PINS_REQUEST
    - wait for response
    - compare vs slot_cfg.expected_idpins_gate2 (set of allowed values)
    """
    def log(msg: str):
        (log_cb or print)(msg)

    log(f"\n========== GATE 2 | slot={slot_cfg.slot} ==========")

    flush_rx()
    start_atp(slot_cfg)

    # Some firmwares need a short settle after START_ATP before answering requests
    time.sleep(0.05)

    read_id_pins_request(slot_cfg)

    # Your original delay (keep it if your firmware really needs it)
    time.sleep(POST_START_DELAY_S)

    val = wait_for_idpins(slot_cfg, TIMEOUT_S)

    if val is None:
        log("❌ GATE 2 FAIL: no ID-pins response")
        return False

    desc = IDPINS_MAP.get(val, "UNKNOWN")
    log(f"🔎 ID-pins = 0x{val:02X} ({desc})")

    # ✅ correct attribute name from slot_config.py
    expected = set(getattr(slot_cfg, "expected_idpins_gate2", set()))

    if not expected:
        log("⚠️ [GATE2][WARN] expected_idpins_gate2 is empty in slot_config; failing safe.")
        return False

    if val in expected:
        log(f"✅ GATE 2 PASS (matched {', '.join([f'0x{x:02X}' for x in expected])})")
        return True

    log(f"❌ GATE 2 FAIL: expected one of {[f'0x{x:02X}' for x in expected]}")
    return False
