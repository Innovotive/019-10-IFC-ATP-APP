"""
=========================================================
GATE 5 – IUL (Indicator User Light) FUNCTIONAL TEST
=========================================================

Test logic:
- Send CAN command IUL_ON  → GPIO must go LOW  (LED ON)
- Send CAN command IUL_OFF → GPIO must go HIGH (LED OFF)

Returns:
- True  → PASS
- False → FAIL
"""

import time
import lgpio

from tests.CAN.can_commands import iul_on, iul_off

# ==============================
# GPIO CONFIG
# ==============================
GPIO_IUL = 23 #18 for slot1
GPIO_CHIP = 0

# Timing (tweak if needed)
IUL_SETTLE_TIME = 3 # seconds
READ_RETRIES = 3
READ_DELAY = 3   # seconds


# ==============================
# GPIO HELPERS
# ==============================
def read_gpio_stable(h, gpio):
    """
    Read GPIO multiple times to avoid glitches.
    Returns last read value (0 or 1).
    """
    val = None
    for _ in range(READ_RETRIES):
        val = lgpio.gpio_read(h, gpio)
        time.sleep(READ_DELAY)
    return val


# =========================================================
# PUBLIC API — CALLED BY UI LATER
# =========================================================
def run_gate4_iul_check(log_cb=None):

    def log(msg):
        if log_cb:
            log_cb(msg)
        else:
            print(msg)

    log("=" * 50)
    log("[ GATE4] Starting IUL (Indicator Light) test")
    log("[ GATE4] Expectations:")
    log("        IUL_ON  → GPIO LOW  (LED ON)")
    log("        IUL_OFF → GPIO HIGH (LED OFF)")

    try:
        h = lgpio.gpiochip_open(GPIO_CHIP)
        lgpio.gpio_claim_input(h, GPIO_IUL)
        log(f"[ GATE4] GPIO{GPIO_IUL} configured as INPUT")
    except Exception as e:
        log(f"[ GATE4][ERROR] GPIO init failed: {e}")
        return False

    try:
        # ------------------------------
        # IUL ON
        # ------------------------------
        log("[ GATE4] → Sending IUL_ON (0xE1)")
        iul_on()
        log(f"[ GATE4] Waiting {IUL_SETTLE_TIME}s for LED to settle")
        time.sleep(IUL_SETTLE_TIME)

        reads = []
        for i in range(READ_RETRIES):
            val = lgpio.gpio_read(h, GPIO_IUL)
            reads.append(val)
            log(f"[ GATE4] GPIO read {i+1}: {val}")
            time.sleep(READ_DELAY)

        state = reads[-1]
        if state != 0:
            log("[ GATE4][FAIL] IUL_ON but GPIO is not LOW")
            return False

        log("[ GATE4] IUL_ON PASS (GPIO LOW)")

        # ------------------------------
        # IUL OFF
        # ------------------------------
        log("[ GATE4] → Sending IUL_OFF (0xE0)")
        iul_off()
        log(f"[ GATE4] Waiting {IUL_SETTLE_TIME}s for LED to settle")
        time.sleep(IUL_SETTLE_TIME)

        reads = []
        for i in range(READ_RETRIES):
            val = lgpio.gpio_read(h, GPIO_IUL)
            reads.append(val)
            log(f"[ GATE4] GPIO read {i+1}: {val}")
            time.sleep(READ_DELAY)

        state = reads[-1]
        if state != 1:
            log("[ GATE4][FAIL] IUL_OFF but GPIO is not HIGH")
            return False

        log("[ GATE4] IUL_OFF PASS (GPIO HIGH)")
        log("[ GATE4] PASS — IUL functional test OK")
        return True

    finally:
        log("[ GATE4] Cleaning up GPIO")
        try:
            lgpio.gpiochip_close(h)
        except Exception:
            pass
        log("=" * 50)
