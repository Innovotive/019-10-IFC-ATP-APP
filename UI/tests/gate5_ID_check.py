"""
=========================================================
GATE 5 — ID PINS (slot-aware)
=========================================================

Per slot:
- Apply baseline ID strap pattern for the slot via MCP23S17 (set_slot_bits)
- Toggle each ID line LOW one-by-one
- Ask the RUP over CAN to report ID pins (read_id_pins_request)
- Verify you receive a response (and optionally validate expected value)

Returns:
- True  → PASS (for this slot)
- False → FAIL (for this slot)
"""

import time

from tests.CAN.can_commands import set_target_slot, read_id_pins_request
from tests.CAN.can_utils import flush_rx, wait_for_idpins

from tests.ID.id_pins_init import (
    init_id_pins_full_config,
    set_slot_bits,
)

# =========================================================
# CONFIG
# =========================================================
TIMEOUT_S = 2.0
SETTLE_DELAY_S = 0.5

# Convention: bits string is "ID3ID2ID1"
BASELINE_BITS = {
    1: "110",
    2: "101",
    3: "011",
    4: "100",
}


def gate5_id_check(slot: int, log_cb=None) -> bool:
    def log(msg: str):
        log_cb(msg) if log_cb else print(msg)

    if slot not in (1, 2, 3, 4):
        raise ValueError(f"[GATE5] Invalid slot={slot}")

    log(f"\n========== GATE 5 — ID PINS (Slot {slot}) ==========")

    # -------------------------------------------------
    # 1) Ensure baseline config for ALL slots (once per call is OK)
    # -------------------------------------------------
    if not init_id_pins_full_config():
        log("❌ [GATE5] Failed to init/apply full ID config (all slots)")
        return False

    # Ensure CAN targets correct RUP
    set_target_slot(slot)

    # -------------------------------------------------
    # 2) Start from baseline pattern for this slot
    # -------------------------------------------------
    baseline = BASELINE_BITS[slot]
    if not set_slot_bits(slot, baseline, settle_s=SETTLE_DELAY_S, verify=True):
        log(f"❌ [GATE5] Failed to set baseline bits for slot {slot}: {baseline}")
        return False

    log(f"[GATE5] Baseline for Slot{slot} = {baseline} (ID3ID2ID1)")

    # -------------------------------------------------
    # 3) Toggle each pin LOW one-by-one and read CAN response
    # -------------------------------------------------
    bit_names = [("ID3", 0), ("ID2", 1), ("ID1", 2)]  # index in string

    for name, idx in bit_names:
        test_bits = list(baseline)
        test_bits[idx] = "0"
        test_bits = "".join(test_bits)

        log(f"[GATE5] Forcing {name} LOW -> Slot{slot} bits = {test_bits}")
        if not set_slot_bits(slot, test_bits, settle_s=SETTLE_DELAY_S, verify=True):
            log(f"❌ [GATE5] Failed to apply test bits {test_bits} for {name}")
            return False

        flush_rx()
        set_target_slot(slot)
        read_id_pins_request()

        val = wait_for_idpins(TIMEOUT_S)
        if val is None:
            log(f"❌ [GATE5] No CAN response after forcing {name} LOW")
            # Restore baseline before exit
            set_slot_bits(slot, baseline, settle_s=SETTLE_DELAY_S, verify=False)
            return False

        log(f"🔎 [GATE5] CAN ID response = 0x{val:02X} after {name} LOW")

        # Restore baseline for next step
        if not set_slot_bits(slot, baseline, settle_s=SETTLE_DELAY_S, verify=True):
            log(f"❌ [GATE5] Failed to restore baseline after testing {name}")
            return False

    log("✅ [GATE5] PASS")
    return True
