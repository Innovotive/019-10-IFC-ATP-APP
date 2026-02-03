# tests/power_PT/power.py
"""
Power detect reader for Gate1 (multi-RUP).

You have two REAL power-detect GPIO inputs:
- RUP1 power detect GPIO = 21
- RUP4 power detect GPIO = 12

Power detect is ACTIVE-HIGH:
    GPIO HIGH -> Power present  -> return True
    GPIO LOW  -> Power missing  -> return False

We provide:
- read_power_state_rup1()
- read_power_state_rup4()

Important:
- We init GPIO safely (BCM mode) once.
- We do NOT cleanup GPIO inside these functions (cleanup should be done at app exit).
"""

import time
import RPi.GPIO as GPIO

POWER_GPIO_RUP1 = 21
POWER_GPIO_RUP4 = 12

STARTUP_DELAY = 8  # seconds (your requirement)


def _gpio_init_once() -> None:
    """Initialize BCM mode once."""
    if GPIO.getmode() is None:
        GPIO.setmode(GPIO.BCM)


def _read_power_gpio(power_gpio: int, label: str) -> bool:
    """
    Common helper that reads a given power detect pin after a delay.

    Args:
        power_gpio: BCM GPIO number
        label: string label for logs (ex: "RUP1")

    Returns:
        True if GPIO HIGH, else False
    """
    _gpio_init_once()

    # Configure pin as input
    GPIO.setup(power_gpio, GPIO.IN)

    print(f"[HW] ({label}) Waiting {STARTUP_DELAY}s for power to stabilize...")
    time.sleep(STARTUP_DELAY)

    raw = GPIO.input(power_gpio)
    print(f"[HW] ({label}) Power GPIO raw state (GPIO {power_gpio}) = {raw}")

    power_present = (raw == GPIO.HIGH)  # ✅ ACTIVE-HIGH
    print(f"[HW] ({label}) Power detected = {power_present}")

    return power_present


def read_power_state_rup1() -> bool:
    """Read power detect for RUP1 (GPIO 21)."""
    return _read_power_gpio(POWER_GPIO_RUP1, "RUP1")


def read_power_state_rup4() -> bool:
    """Read power detect for RUP4 (GPIO 12)."""
    return _read_power_gpio(POWER_GPIO_RUP4, "RUP4")


def cleanup_gpio() -> None:
    """
    Optional: call once when your whole app exits.
    Don't call this after each gate.
    """
    GPIO.cleanup()
