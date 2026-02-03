# tests/power_PT/power.py
import RPi.GPIO as GPIO
from slot_config import SlotConfig

_gpio_inited = False
_power_pins_configured = set()

def _init_gpio_mode():
    global _gpio_inited
    if not _gpio_inited:
        GPIO.setmode(GPIO.BCM)
        _gpio_inited = True

def ensure_power_gpio(slot_cfg: SlotConfig):
    """
    Configure the slot's power detect pin as input once.
    """
    _init_gpio_mode()
    pin = int(slot_cfg.power_gpio)
    if pin not in _power_pins_configured:
        GPIO.setup(pin, GPIO.IN)
        _power_pins_configured.add(pin)

def read_power_state(slot_cfg: SlotConfig, active_high: bool = True) -> bool:
    """
    Reads power detect for a slot.
    If your wiring is active-high (HIGH means power present), leave active_high=True.
    """
    ensure_power_gpio(slot_cfg)
    raw = GPIO.input(int(slot_cfg.power_gpio))
    power_present = (raw == GPIO.HIGH) if active_high else (raw == GPIO.LOW)
    print(f"[HW] slot={slot_cfg.slot} PowerGPIO={slot_cfg.power_gpio} raw={raw} -> present={power_present}")
    return bool(power_present)
