# tests/gate4_iul_check.py
import time
import lgpio

from slot_config import SlotConfig
from tests.CAN.can_commands import iul_on, iul_off

GPIO_CHIP = 0
IUL_SETTLE_TIME = 3
READ_RETRIES = 3
READ_DELAY = 1.0

def run_gate4_iul_check(slot_cfg: SlotConfig, log_cb=None) -> bool:
    def log(msg: str):
        (log_cb or print)(msg)

    gpio_iul = int(slot_cfg.iul_gpio)

    log("=" * 50)
    log(f"[GATE4] IUL test | slot={slot_cfg.slot} GPIO={gpio_iul}")
    log("Expect: IUL_ON  -> GPIO LOW ; IUL_OFF -> GPIO HIGH")

    h = None
    try:
        h = lgpio.gpiochip_open(GPIO_CHIP)
        lgpio.gpio_claim_input(h, gpio_iul)

        log("[GATE4] → IUL_ON")
        iul_on(slot_cfg)
        time.sleep(IUL_SETTLE_TIME)

        reads = []
        for i in range(READ_RETRIES):
            val = lgpio.gpio_read(h, gpio_iul)
            reads.append(val)
            log(f"[GATE4] read {i+1}: {val}")
            time.sleep(READ_DELAY)

        if reads[-1] != 0:
            log("[GATE4][FAIL] IUL_ON but GPIO not LOW")
            return False

        log("[GATE4] → IUL_OFF")
        iul_off(slot_cfg)
        time.sleep(IUL_SETTLE_TIME)

        reads = []
        for i in range(READ_RETRIES):
            val = lgpio.gpio_read(h, gpio_iul)
            reads.append(val)
            log(f"[GATE4] read {i+1}: {val}")
            time.sleep(READ_DELAY)

        if reads[-1] != 1:
            log("[GATE4][FAIL] IUL_OFF but GPIO not HIGH")
            return False

        log("[GATE4] PASS")
        return True

    except Exception as e:
        log(f"[GATE4][ERROR] {e}")
        return False

    finally:
        try:
            if h is not None:
                lgpio.gpiochip_close(h)
        except Exception:
            pass
