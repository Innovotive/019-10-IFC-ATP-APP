"""
=========================================================
GATE 5 – IUL (Indicator User Light) FUNCTIONAL TEST (slot-aware)
=========================================================

Per slot:
- Address the correct RUP via CAN (set_target_slot(slot))
- Read the correct GPIO input pin for that slot

IUL expectations:
- IUL_ON  → GPIO LOW  (LED ON)
- IUL_OFF → GPIO HIGH (LED OFF)

Returns:
- True  → PASS (for this slot)
- False → FAIL (for this slot)
"""

import time
import lgpio

from tests.CAN.can_commands import set_target_slot, iul_on, iul_off

GPIO_CHIP = 0

# Slot -> GPIO input pin mapping (your wiring)
SLOT_TO_GPIO_IUL = {
    1: 18,
    2: 23,
    3: 24,
    4: 25,
}

# Timing (tweak if needed)
IUL_SETTLE_TIME = 4   # seconds
READ_RETRIES = 4
READ_DELAY = 4        # seconds


def run_gate5_iul_check(slot: int, log_cb=None) -> bool:
    def log(msg: str):
        if log_cb:
            log_cb(msg)
        else:
            print(msg)

    if slot not in SLOT_TO_GPIO_IUL:
        raise ValueError(f"[GATE5] Invalid slot={slot} (expected 1..4)")

    gpio_iul = SLOT_TO_GPIO_IUL[slot]

    log("=" * 50)
    log(f"[GATE5] Slot={slot} — IUL test using GPIO{gpio_iul}")
    log("[GATE5] Expectations:")
    log("        IUL_ON  → GPIO LOW  (LED ON)")
    log("        IUL_OFF → GPIO HIGH (LED OFF)")

    h = None
    try:
        # Ensure CAN is addressed to the correct RUP
        set_target_slot(slot)

        # Init GPIO input for this slot
        h = lgpio.gpiochip_open(GPIO_CHIP)
        lgpio.gpio_claim_input(h, gpio_iul)
        log(f"[GATE5] GPIO{gpio_iul} configured as INPUT")

        # ------------------------------
        # IUL ON
        # ------------------------------
        log("[GATE5] → Sending IUL_ON (0xE1)")
        set_target_slot(slot)  # extra safety
        iul_on()

        log(f"[GATE5] Waiting {IUL_SETTLE_TIME}s for LED to settle")
        time.sleep(IUL_SETTLE_TIME)

        reads = []
        for i in range(READ_RETRIES):
            val = lgpio.gpio_read(h, gpio_iul)
            reads.append(val)
            log(f"[GATE5] GPIO read {i+1}: {val}")
            time.sleep(READ_DELAY)

        if reads[-1] != 0:
            log("[GATE5][FAIL] IUL_ON but GPIO is not LOW")
            return False

        log("[GATE5] IUL_ON PASS (GPIO LOW)")

        # ------------------------------
        # IUL OFF
        # ------------------------------
        log("[GATE5] → Sending IUL_OFF (0xE0)")
        set_target_slot(slot)  # extra safety
        iul_off()

        log(f"[GATE5] Waiting {IUL_SETTLE_TIME}s for LED to settle")
        time.sleep(IUL_SETTLE_TIME)

        reads = []
        for i in range(READ_RETRIES):
            val = lgpio.gpio_read(h, gpio_iul)
            reads.append(val)
            log(f"[GATE5] GPIO read {i+1}: {val}")
            time.sleep(READ_DELAY)

        if reads[-1] != 1:
            log("[GATE5][FAIL] IUL_OFF but GPIO is not HIGH")
            return False

        log("[GATE5] IUL_OFF PASS (GPIO HIGH)")
        log("[GATE5] PASS — IUL functional test OK")
        return True

    except Exception as e:
        log(f"[GATE5][ERROR] {e}")
        return False

    finally:
        log("[GATE5] Cleaning up GPIO")
        try:
            if h is not None:
                lgpio.gpiochip_close(h)
        except Exception:
            pass
        log("=" * 50)
