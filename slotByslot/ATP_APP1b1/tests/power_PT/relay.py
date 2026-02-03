# tests/power_PT/relay.py
import time
import lgpio

# ---------------------------------------------------------
# Relay polarity
#   Active-low relay board:  ON = 0, OFF = 1   (MOST COMMON)
#   Active-high relay board: ON = 1, OFF = 0
# ---------------------------------------------------------
RELAY_ACTIVE_LOW = True

ON_LEVEL  = 0 if RELAY_ACTIVE_LOW else 1
OFF_LEVEL = 1 if RELAY_ACTIVE_LOW else 0

_CHIP = None

def _chip():
    global _CHIP
    if _CHIP is None:
        _CHIP = lgpio.gpiochip_open(0)  # gpiochip0
    return _CHIP

def _ensure_output(gpio: int, initial: int):
    h = _chip()
    try:
        lgpio.gpio_claim_output(h, gpio, initial)
    except Exception:
        # already claimed - just write
        lgpio.gpio_write(h, gpio, initial)

def _write_and_verify(gpio: int, level: int):
    h = _chip()
    lgpio.gpio_write(h, gpio, level)
    time.sleep(0.02)
    rb = lgpio.gpio_read(h, gpio)
    if rb != level:
        raise RuntimeError(f"GPIO{gpio} verify failed: want={level} got={rb}")

def relay_on(slot_cfg, log_cb=None):
    gpio = int(slot_cfg.relay_gpio)
    _ensure_output(gpio, OFF_LEVEL)
    _write_and_verify(gpio, ON_LEVEL)
    if log_cb:
        log_cb(f"[HW] relay ON  (slot={slot_cfg.slot} GPIO {gpio}) level={ON_LEVEL} active_low={RELAY_ACTIVE_LOW}")
    else:
        print(f"[HW] relay ON  (GPIO {gpio})")

def relay_off(slot_cfg, log_cb=None):
    gpio = int(slot_cfg.relay_gpio)
    _ensure_output(gpio, OFF_LEVEL)
    _write_and_verify(gpio, OFF_LEVEL)
    if log_cb:
        log_cb(f"[HW] relay OFF (slot={slot_cfg.slot} GPIO {gpio}) level={OFF_LEVEL} active_low={RELAY_ACTIVE_LOW}")
    else:
        print(f"[HW] relay OFF (GPIO {gpio})")

def relay_cleanup():
    global _CHIP
    if _CHIP is not None:
        try:
            lgpio.gpiochip_close(_CHIP)
        except Exception:
            pass
        _CHIP = None
