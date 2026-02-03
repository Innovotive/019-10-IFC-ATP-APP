# tests/power_PT/relay_all.py
from slot_config import get_slot_config
from tests.power_PT.relay import relay_on, relay_off  # <-- use your working functions

def relay_on_all(log_cb=print):
    for s in (1, 2, 3, 4):
        sc = get_slot_config(s)
        relay_on(sc)  # <-- your proven relay control
        log_cb(f"[HW] relay ON  (slot={s} GPIO {sc.relay_gpio})")

def relay_off_all(log_cb=print):
    for s in (1, 2, 3, 4):
        sc = get_slot_config(s)
        relay_off(sc)
        log_cb(f"[HW] relay OFF (slot={s} GPIO {sc.relay_gpio})")
