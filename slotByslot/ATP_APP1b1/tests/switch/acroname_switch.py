# tests/switch/acroname_switch.py
import time
import brainstem
from brainstem.stem import USBCSwitch

# Initialize Acroname switch (global, connected once)
COMMON = 0  # common side index
_sw = None


def init_switch(log_cb=None):
    """
    Connect to the Acroname USBCSwitch once.
    Safe to call multiple times.
    """
    global _sw

    def log(msg: str):
        (log_cb or print)(msg)

    if _sw is not None:
        return _sw

    log("[ACRONAME] discoverAndConnect(USB)...")
    sw = USBCSwitch()
    sw.discoverAndConnect(brainstem.link.Spec.USB)
    _sw = sw
    log("[ACRONAME] connected ✅")
    return _sw


def select_rup(port: int, log_cb=None):
    """
    Safely switch Acroname COMMON to a RUP port (0–3)
    and enable CC routing for PD.
    """
    port = int(port)
    if port < 0 or port > 3:
        raise ValueError(f"select_rup(port) expects 0..3, got {port}")

    def log(msg: str):
        (log_cb or print)(msg)

    sw = init_switch(log_cb=log)

    log(f"\n--- [ACRONAME] Switching COMMON → RUP PORT {port} ---")

    # 1) Disable VBUS + port on COMMON before switching
    sw.usb.setPowerDisable(COMMON)
    sw.usb.setPortDisable(COMMON)
    time.sleep(0.05)

    # 2) Disable mux before selecting channel
    sw.mux.setEnable(False)
    time.sleep(0.05)

    # 3) Select the channel (0,1,2,3)
    sw.mux.setChannel(port)
    time.sleep(0.05)

    # 4) Re-enable mux
    sw.mux.setEnable(True)
    time.sleep(0.05)

    # 5) Enable CC routing + passive mode for selected RUP port
    # (keep exactly like your previous working setup)
    sw.usb.setPortMode(port, sw.usb.PORT_MODE_PASSIVE)
    sw.usb.setPortMode(port, sw.usb.PORT_MODE_CC1_ENABLE)
    sw.usb.setPortMode(port, sw.usb.PORT_MODE_CC2_ENABLE)
    time.sleep(0.05)

    # 6) Re-enable VBUS on COMMON
    sw.usb.setPortEnable(COMMON)
    sw.usb.setPowerEnable(COMMON)

    # 7) Settle time for PD to stabilize (important)
    time.sleep(0.35)

    log(f"✓ [ACRONAME] COMMON → PORT {port} ACTIVE\n")


def select_rup_port_for_slot(slot: int, log_cb=None) -> int:
    """
    Slot 1..4 -> Acroname port 0..3 (slot-1).
    Returns the selected port.
    """
    slot = int(slot)
    if slot < 1 or slot > 4:
        raise ValueError(f"slot must be 1..4, got {slot}")

    port = slot - 1
    select_rup(port, log_cb=log_cb)
    return port
