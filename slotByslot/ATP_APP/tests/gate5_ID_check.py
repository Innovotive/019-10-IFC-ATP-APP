# tests/gate5_ID_check.py
import time

from slot_config import SlotConfig
from tests.CAN.can_commands import read_id_pins_request
from tests.CAN.can_utils import flush_rx, wait_for_idpins, IDPINS_MAP
from tests.ID.id_pins_mcp23s17 import IDPins

TIMEOUT_S = 2.0
SETTLE_DELAY_S = 0.5


def run_gate5_id_check(slot_cfg: SlotConfig, log_cb=None) -> bool:
    def log(msg: str):
        (log_cb or print)(msg)

    log("=" * 60)
    log(f"[GATE5] ID pins functional test | slot={slot_cfg.slot}")
    log(f"[GATE5] id_port={slot_cfg.id_port} id_pins={slot_cfg.id_pins} baseline_bits=0b{slot_cfg.id_baseline_bits:03b}")

    idpins = IDPins()

    try:
        # baseline
        log(f"[GATE5] Setting baseline pattern: 0b{slot_cfg.id_baseline_bits:03b}")
        idpins.set_slot_baseline(slot_cfg)
        time.sleep(SETTLE_DELAY_S)

        # test each pin bit for this slot
        for pin_bit in slot_cfg.id_pins:
            expected_val = slot_cfg.expected_after_clear.get(pin_bit)
            if expected_val is None:
                log(f"[GATE5][FAIL] expected_after_clear missing for pin_bit={pin_bit}")
                return False

            log(f"[GATE5] Clearing pin bit={pin_bit} (port {slot_cfg.id_port})")
            idpins.clear_slot_pin(slot_cfg, pin_bit)
            time.sleep(SETTLE_DELAY_S)

            flush_rx()
            read_id_pins_request(slot_cfg)

            # ✅ FIX: pass slot_cfg first
            val = wait_for_idpins(slot_cfg, TIMEOUT_S)

            if val is None:
                log(f"[GATE5][FAIL] No CAN response after clearing bit={pin_bit}")
                return False

            log(f"[GATE5] RX ID-pins=0x{val:02X} ({IDPINS_MAP.get(val, 'UNKNOWN')}) expected=0x{expected_val:02X}")

            if int(val) != int(expected_val):
                log(f"[GATE5][FAIL] bit={pin_bit} expected 0x{expected_val:02X} got 0x{val:02X}")
                return False

            log(f"[GATE5] ✅ bit={pin_bit} verified")

            # restore
            idpins.set_slot_pin(slot_cfg, pin_bit)
            time.sleep(SETTLE_DELAY_S)

        log("[GATE5] PASS")
        return True

    finally:
        try:
            idpins.set_slot_baseline(slot_cfg)
        except Exception:
            pass
        idpins.close()
        log("[GATE5] ID pins restored + closed")
