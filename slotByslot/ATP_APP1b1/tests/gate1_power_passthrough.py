# tests/gate1_power_passthrough.py
import time
from slot_config import SlotConfig
from tests.power_PT.relay import relay_on
from tests.power_PT.power import read_power_state

def run_gate1_power_test(slot_cfg: SlotConfig, log_cb=None) -> bool:
    """
    Gate 1 — Power pass-through detect

    NEW behavior (for "power all RUPs at startup"):
    - Does NOT relay_off() / power-cycle.
    - Ensures relay is ON (idempotent), waits briefly, reads power GPIO.
    """
    def log(msg: str):
        (log_cb or print)(msg)

    log(f"[GATE1] Starting power pass-through test | slot={slot_cfg.slot}")

    # Ensure relay is ON (no power-cycle)
    relay_on(slot_cfg)
    log(f"[HW] relay ON (GPIO {slot_cfg.relay_gpio})")

    # Let power stabilize
    time.sleep(0.25)

    # Read power detect
    power_ok = read_power_state(slot_cfg, active_high=True)
    log(f"[GATE1] slot={slot_cfg.slot} {'PASS' if power_ok else 'FAIL'}")
    return bool(power_ok)
