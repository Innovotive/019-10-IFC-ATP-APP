# tests/power_PT/relay.py
"""
Relay control for Gate1 (multi-RUP).

We have 2 real relays we care about right now:
- RUP1 relay GPIO = 22
- RUP4 relay GPIO = 13

Relays are ACTIVE-LOW:
    GPIO LOW  -> Relay ON
    GPIO HIGH -> Relay OFF

We provide:
- relay_on_rup1(), relay_off_rup1()
- relay_on_rup4(), relay_off_rup4()

These are explicit and easy to read/debug.
"""

from gpiozero import LED

# ---------------------------------------------------------
# Relay GPIO mapping (ACTIVE-LOW)
# ---------------------------------------------------------
RELAY_GPIO_RUP1 = 22
RELAY_GPIO_RUP4 = 13

# Create relay objects once (cached)
# initial_value=False -> OFF (GPIO HIGH for active-low LED)
_relay_rup1 = LED(RELAY_GPIO_RUP1, active_high=False, initial_value=False)
_relay_rup4 = LED(RELAY_GPIO_RUP4, active_high=False, initial_value=False)


# -------------------------
# RUP1 relay functions
# -------------------------
def relay_on_rup1() -> None:
    """Turn ON relay for RUP1 (GPIO 22, active-low)."""
    _relay_rup1.on()  # active_low -> drives GPIO LOW
    print(f"[HW] Relay ON  - RUP1 (GPIO {RELAY_GPIO_RUP1}, ACTIVE-LOW)")


def relay_off_rup1() -> None:
    """Turn OFF relay for RUP1 (GPIO 22, active-low)."""
    _relay_rup1.off()  # active_low -> drives GPIO HIGH
    print(f"[HW] Relay OFF - RUP1 (GPIO {RELAY_GPIO_RUP1}, ACTIVE-LOW)")


# -------------------------
# RUP4 relay functions
# -------------------------
def relay_on_rup4() -> None:
    """Turn ON relay for RUP4 (GPIO 13, active-low)."""
    _relay_rup4.on()
    print(f"[HW] Relay ON  - RUP4 (GPIO {RELAY_GPIO_RUP4}, ACTIVE-LOW)")


def relay_off_rup4() -> None:
    """Turn OFF relay for RUP4 (GPIO 13, active-low)."""
    _relay_rup4.off()
    print(f"[HW] Relay OFF - RUP4 (GPIO {RELAY_GPIO_RUP4}, ACTIVE-LOW)")
