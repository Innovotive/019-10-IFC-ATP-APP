# acroname_switch.py
import time
import brainstem
from brainstem.stem import USBCSwitch

# Initialize Acroname switch
sw = USBCSwitch()
sw.discoverAndConnect(brainstem.link.Spec.USB)

COMMON = 0  # common side index


def select_rup(port):
    """
    Safely switch Acroname COMMON to a RUP port (0–3)
    and enable CC routing for PD.
    """
    print(f"\n--- Switching to RUP PORT {port} ---")

    # 1. Disable VBUS + port on COMMON before switching
    sw.usb.setPowerDisable(COMMON)
    sw.usb.setPortDisable(COMMON)
    time.sleep(0.05)

    # 2. Disable mux before selecting channel
    sw.mux.setEnable(False)
    time.sleep(0.05)

    # 3. Select the channel (0,1,2,3)
    sw.mux.setChannel(port)
    time.sleep(0.05)

    # 4. Re-enable mux
    sw.mux.setEnable(True)
    time.sleep(0.05)

    # 5. Enable CC routing + passive mode for selected RUP port
    sw.usb.setPortMode(port, sw.usb.PORT_MODE_PASSIVE)
    sw.usb.setPortMode(port, sw.usb.PORT_MODE_CC1_ENABLE)
    sw.usb.setPortMode(port, sw.usb.PORT_MODE_CC2_ENABLE)
    time.sleep(0.05)

    # 6. Re-enable VBUS on COMMON
    sw.usb.setPortEnable(COMMON)
    sw.usb.setPowerEnable(COMMON)
    time.sleep(0.1)

    print(f"✓ COMMON → PORT {port} ACTIVE\n")

