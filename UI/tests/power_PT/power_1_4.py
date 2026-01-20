# tests/power_PT/power.py
"""
Power detect reader for ATP (RUP1..RUP4).

Power detect is ACTIVE-HIGH:
    GPIO HIGH -> Power present  -> return True
    GPIO LOW  -> Power missing  -> return False
"""

import time
import RPi.GPIO as GPIO

POWER_GPIO_RUP1 = 21
POWER_GPIO_RUP2 = 20
POWER_GPIO_RUP3 = 16
POWER_GPIO_RUP4 = 12

STARTUP_DELAY = 1  # seconds


def _gpio_init_once() -> None:
    """Initialize BCM mode once."""
    if GPIO.getmode() is None:
        GPIO.setmode(GPIO.BCM)


def _read_power_gpio(power_gpio: int, label: str) -> bool:
    _gpio_init_once()

    GPIO.setup(power_gpio, GPIO.IN)

    print(f"[HW] ({label}) Waiting {STARTUP_DELAY}s for power to stabilize...")
    time.sleep(STARTUP_DELAY)

    raw = GPIO.input(power_gpio)
    print(f"[HW] ({label}) Power GPIO raw state (GPIO {power_gpio}) = {raw}")

    power_present = (raw == GPIO.HIGH)  # ACTIVE-HIGH
    print(f"[HW] ({label}) Power detected = {power_present}")

    return power_present


def read_power_state_rup1() -> bool:
    return _read_power_gpio(POWER_GPIO_RUP1, "RUP1")


def read_power_state_rup2() -> bool:
    return _read_power_gpio(POWER_GPIO_RUP2, "RUP2")


def read_power_state_rup3() -> bool:
    return _read_power_gpio(POWER_GPIO_RUP3, "RUP3")


def read_power_state_rup4() -> bool:
    return _read_power_gpio(POWER_GPIO_RUP4, "RUP4")


def cleanup_gpio() -> None:
    """Call once when your whole app exits."""
    GPIO.cleanup()
