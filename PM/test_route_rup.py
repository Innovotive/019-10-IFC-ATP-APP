#!/usr/bin/env python3
import time
import brainstem
from brainstem.stem import USBCSwitch
from brainstem.result import Result

# --------- CONFIG: which RUP port? 0..3 ----------
RUP_PORT = 0   # change to 1,2,3 later for other RUPs
# -------------------------------------------------


def main():
    sw = USBCSwitch()
    r = sw.discoverAndConnect(brainstem.link.Spec.USB)

    if r != Result.NO_ERROR:
        print("❌ Error connecting to USBCSwitch:", r)
        return

    serial = sw.system.getSerialNumber().value
    print(f"✅ Connected to USBCSwitch, serial = 0x{serial:08X}")

    # 1) Make sure USB channel and power are OFF
    print("→ Disabling USB channel and power...")
    sw.usb.setPortDisable(0)    # channel index is always 0
    sw.usb.setPowerDisable(0)
    time.sleep(0.1)

    # 2) Disable mux, select RUP port, then enable mux
    print(f"→ Routing COMMON ⇄ PORT {RUP_PORT} via mux...")
    sw.mux.setEnable(False)
    time.sleep(0.05)
    sw.mux.setChannel(RUP_PORT)
    time.sleep(0.05)
    sw.mux.setEnable(True)
    time.sleep(0.05)

    # 3) Set port mode to fully enable VBUS + CC1/CC2 + data + SBU + auto-connect
    # Bits: keep-alive, HS A/B, VBUS, SS1/SS2, AutoConnect, CC1, CC2, SBU
    # mask = (1<<2)|(1<<4)|(1<<5)|(1<<6)|(1<<7)|(1<<8)|(1<<11)|(1<<12)|(1<<13)|(1<<14)
    PORT_MODE_FULL_PD = 31220  # decimal value of mask above

    print("→ Setting port mode for full PD (VBUS + CC1/CC2 + data + SBU)...")
    sw.usb.setPortMode(0, PORT_MODE_FULL_PD)

    # 4) Turn power + USB channel back on
    print("→ Enabling power and USB channel...")
    sw.usb.setPowerEnable(0)
    sw.usb.setPortEnable(0)
    time.sleep(0.2)

    # 5) Print a quick status snapshot
    mode = sw.usb.getPortMode(0).value
    v = sw.usb.getPortVoltage(0).value
    cc1_v = sw.usb.getCC1Voltage(0).value
    cc2_v = sw.usb.getCC2Voltage(0).value

    print("\n=== USB Channel Status ===")
    print(f"PortMode = 0x{mode:04X}")
    print(f"VBUS    = {v} mV")
    print(f"CC1     = {cc1_v} mV")
    print(f"CC2     = {cc2_v} mV")
    print("==========================\n")

    print(f"✅ COMMON is now routed to RUP on PORT {RUP_PORT} with PD lines enabled.")
    print("Now run your PM125 script (e.g. test_negotiation.py).")

    sw.disconnect()


if __name__ == "__main__":
    main()
