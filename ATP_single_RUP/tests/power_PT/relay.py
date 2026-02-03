# tests/power_PT/relay.py
from gpiozero import LED

_power = None   # GPIO25
_idcfg = None   # GPIO8

def _get_power():
    global _power
    if _power is None:
        _power = LED(25)   # active_high=True default
        _power.on()        # start OFF (GPIO HIGH)
    return _power

def _get_idcfg():
    global _idcfg
    if _idcfg is None:
        _idcfg = LED(8)
        _idcfg.on()        # start OFF (GPIO HIGH)
    return _idcfg

# POWER relay (GPIO25) — active-low board
def power_on():
    _get_power().off()     # ON
    print("[HW] POWER relay ON (GPIO25)")

def power_off():
    _get_power().on()      # OFF
    print("[HW] POWER relay OFF (GPIO25)")

# IDCFG relay (GPIO8) — active-low board
def idcfg_on():
    _get_idcfg().off()     # ON (select initial config)
    print("[HW] IDCFG relay ON (GPIO8)")

def idcfg_off():
    _get_idcfg().on()      # OFF (flip config)
    print("[HW] IDCFG relay OFF (GPIO8)")

def relay_close():
    global _power, _idcfg
    if _power is not None:
        _power.close()
        _power = None
    if _idcfg is not None:
        _idcfg.close()
        _idcfg = None
