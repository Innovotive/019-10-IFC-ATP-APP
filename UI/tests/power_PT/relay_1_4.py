# tests/power_PT/relay_1_4.py   (or relay.py, but match your imports)
"""
Relay control for ATP (RUP1..RUP4).

Relays are ACTIVE-LOW:
    GPIO LOW  -> Relay ON
    GPIO HIGH -> Relay OFF

We also ensure MCP23S17 ID pins are initialized ONCE before powering any RUP.
This makes sure ID-pin hardware is ready before startup/power-on.
"""

from gpiozero import LED

# ---------------------------------------------------------
# OPTIONAL: ID PINS INIT (MCP23S17)
# ---------------------------------------------------------
try:
    from tests.ID.id_pins_init import init_id_pins_active_high

except Exception as e:
    init_id_pins_active_high = None
    print(f"[RELAY][WARN] Could not import init_id_pins_active_high: {e}")

_id_pins_initialized = False


def ensure_id_pins_initialized() -> bool:
    """
    Initialize MCP23S17 ID pins exactly once.
    Returns True if initialized (or already initialized), False otherwise.
    """
    global _id_pins_initialized

    if _id_pins_initialized:
        return True

    if init_id_pins_active_high is None:
        print("[RELAY][ERROR] ID pins init function not available (import failed).")
        return False

    try:
        ok = bool(init_id_pins_active_high())
        if ok:
            _id_pins_initialized = True
            print("[RELAY][INIT] ID pins initialized (ACTIVE-HIGH, ID3 OFF)")
        else:
            print("[RELAY][WARN] ID pin initialization returned False")
        return ok
    except Exception as e:
        print(f"[RELAY][ERROR] MCP23S17 init failed: {e}")
        return False


# ---------------------------------------------------------
# Relay GPIO mapping (ACTIVE-LOW)
# ---------------------------------------------------------
RELAY_GPIO_RUP1 = 22
RELAY_GPIO_RUP2 = 27
RELAY_GPIO_RUP3 = 6
RELAY_GPIO_RUP4 = 13

# Create relay objects once (cached)
# active_high=False => active-low behavior
# initial_value=False => logical OFF at start
_relay_rup1 = LED(RELAY_GPIO_RUP1, active_high=False, initial_value=False)
_relay_rup2 = LED(RELAY_GPIO_RUP2, active_high=False, initial_value=False)
_relay_rup3 = LED(RELAY_GPIO_RUP3, active_high=False, initial_value=False)
_relay_rup4 = LED(RELAY_GPIO_RUP4, active_high=False, initial_value=False)


# -------------------------
# RUP1 relay functions
# -------------------------
def relay_on_rup1() -> None:
    if not ensure_id_pins_initialized():
        print("[HW][FAIL] Refusing to power RUP1 because ID pins init failed.")
        return
    _relay_rup1.on()
    print(f"[HW] Relay ON  - RUP1 (GPIO {RELAY_GPIO_RUP1}, ACTIVE-LOW)")


def relay_off_rup1() -> None:
    _relay_rup1.off()
    print(f"[HW] Relay OFF - RUP1 (GPIO {RELAY_GPIO_RUP1}, ACTIVE-LOW)")


# -------------------------
# RUP2 relay functions
# -------------------------
def relay_on_rup2() -> None:
    if not ensure_id_pins_initialized():
        print("[HW][FAIL] Refusing to power RUP2 because ID pins init failed.")
        return
    _relay_rup2.on()
    print(f"[HW] Relay ON  - RUP2 (GPIO {RELAY_GPIO_RUP2}, ACTIVE-LOW)")


def relay_off_rup2() -> None:
    _relay_rup2.off()
    print(f"[HW] Relay OFF - RUP2 (GPIO {RELAY_GPIO_RUP2}, ACTIVE-LOW)")


# -------------------------
# RUP3 relay functions
# -------------------------
def relay_on_rup3() -> None:
    if not ensure_id_pins_initialized():
        print("[HW][FAIL] Refusing to power RUP3 because ID pins init failed.")
        return
    _relay_rup3.on()
    print(f"[HW] Relay ON  - RUP3 (GPIO {RELAY_GPIO_RUP3}, ACTIVE-LOW)")


def relay_off_rup3() -> None:
    _relay_rup3.off()
    print(f"[HW] Relay OFF - RUP3 (GPIO {RELAY_GPIO_RUP3}, ACTIVE-LOW)")


# -------------------------
# RUP4 relay functions
# -------------------------
def relay_on_rup4() -> None:
    if not ensure_id_pins_initialized():
        print("[HW][FAIL] Refusing to power RUP4 because ID pins init failed.")
        return
    _relay_rup4.on()
    print(f"[HW] Relay ON  - RUP4 (GPIO {RELAY_GPIO_RUP4}, ACTIVE-LOW)")


def relay_off_rup4() -> None:
    _relay_rup4.off()
    print(f"[HW] Relay OFF - RUP4 (GPIO {RELAY_GPIO_RUP4}, ACTIVE-LOW)")
