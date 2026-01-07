#!/usr/bin/env python3
import time
import brainstem
from brainstem.stem import USBCSwitch
from brainstem.result import Result

MUX_CHANNEL = 0  # channel where your RUP/PM125 side is connected

sw = USBCSwitch()
r = sw.discoverAndConnect(brainstem.link.Spec.USB)
if r != Result.NO_ERROR:
    print("❌ Failed to connect:", r)
    raise SystemExit

print("✅ Connected, serial:", hex(sw.system.getSerialNumber().value))

# 1) SAFE RESET
print("\n[1] Resetting mux + port to safe state...")
sw.usb.setPortDisable(0)
sw.mux.setEnable(False)
time.sleep(0.1)

# 2) SELECT CHANNEL
print(f"[2] Selecting mux channel {MUX_CHANNEL}...")
sw.mux.setChannel(MUX_CHANNEL)
sw.mux.setEnable(True)
time.sleep(0.1)

# 3) FORCE GOOD CONNECT MODE + PORT MODE
print("[3] Enabling auto-connect and full CC/VBUS path...")

# enable automatic connection/orientation handling
sw.usb.setConnectMode(0, 1)

# Build a "good" portMode:
# bit 2  = keep-alive charging
# bit 6  = VBUS enable
# bit 11 = auto-connect enable
# bit 12 = CC1 enable
# bit 13 = CC2 enable
# bit 14 = SBU enable
port_mode = (
    (1 << 2)  |  # keep-alive charge
    (1 << 6)  |  # VBUS
    (1 << 11) |  # auto-connect
    (1 << 12) |  # CC1
    (1 << 13) |  # CC2
    (1 << 14)    # SBU
)

sw.usb.setPortMode(0, port_mode)
time.sleep(1)

# 4) ENABLE PORT
print("[4] Enabling port 0...")
sw.usb.setPortEnable(MUX_CHANNEL)
time.sleep(1)

# 5) READ BACK STATUS
print("\n[5] Reading back USB status...")
mode = sw.usb.getPortMode(0).value
state = sw.usb.getPortState(0).value

print(f"   PortMode  = 0x{mode:08X} (requested)")
print(f"   PortState = 0x{state:08X} (actual)")

cc1_en_state = (state >> 6) & 1
cc2_en_state = (state >> 7) & 1
conn_established = (state >> 23) & 1

print(f"   CC1 enable (state bit6): {cc1_en_state}")
print(f"   CC2 enable (state bit7): {cc2_en_state}")
print(f"   Connection Established (bit23): {conn_established}")

# Also show the direct CC enable API
try:
    cc1_en = sw.usb.getCC1Enable(0).value
    cc2_en = sw.usb.getCC2Enable(0).value
    print(f"   getCC1Enable(): {cc1_en}")
    print(f"   getCC2Enable(): {cc2_en}")
except Exception as e:
    print("   CC enable readback not supported:", e)

# 6) MEASURE CC VOLTAGES/CURRENTS
print("\n[6] CC voltages/currents (µV / µA):")
try:
    cc1_v = sw.usb.getCC1Voltage(0).value
    cc2_v = sw.usb.getCC2Voltage(0).value
    cc1_i = sw.usb.getCC1Current(0).value
    cc2_i = sw.usb.getCC2Current(0).value
    print(f"   CC1: {cc1_v} µV, {cc1_i} µA")
    print(f"   CC2: {cc2_v} µV, {cc2_i} µA")
except Exception as e:
    print("   CC voltage/current readback not supported:", e)

print("\n✅ Diagnostic done. Make sure RUP and PM125 are both powered and connected during this test.")
