# tests/power_PT/relay.py
from gpiozero import LED
from slot_config import SlotConfig

# Cache LED objects per GPIO so we don't re-create them
_relays = {}

# Your relay boards were active-low in older tests:
#   ON  = drive LOW
#   OFF = drive HIGH
ACTIVE_LOW = True

def _get_relay(gpio: int) -> LED:
    if gpio not in _relays:
        r = LED(gpio)  # gpiozero LED uses "active_high=True" default
        _relays[gpio] = r
        # start OFF
        relay_off_gpio(gpio)
    return _relays[gpio]

def relay_on_gpio(gpio: int):
    r = _get_relay(gpio)
    if ACTIVE_LOW:
        r.off()  # drive LOW -> ON
    else:
        r.on()
    print(f"[HW] relay ON (GPIO {gpio})")

def relay_off_gpio(gpio: int):
    r = _get_relay(gpio)
    if ACTIVE_LOW:
        r.on()   # drive HIGH -> OFF
    else:
        r.off()
    print(f"[HW] relay OFF (GPIO {gpio})")

def relay_on(slot_cfg: SlotConfig):
    relay_on_gpio(slot_cfg.relay_gpio)

def relay_off(slot_cfg: SlotConfig):
    relay_off_gpio(slot_cfg.relay_gpio)

def relay_close_all():
    global _relays
    for gpio, r in list(_relays.items()):
        try:
            r.close()
        except Exception:
            pass
    _relays = {}
