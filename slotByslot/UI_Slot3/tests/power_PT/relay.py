# tests/power_PT/relay.py
from gpiozero import LED

_relay = None

def _get():
    global _relay
    if _relay is None:
        _relay = LED(6)  # default active_high=True
        _relay.on()       # start OFF (GPIO HIGH)
    return _relay

def relay_on():
    _get().off()  # ON
    print("[HW] relay ON")

def relay_off():
    _get().on()   # OFF
    print("[HW] relay OFF")

def relay_close():
    global _relay
    if _relay is not None:
        _relay.close()
        _relay = None
