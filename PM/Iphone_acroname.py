#!/usr/bin/env python3
import time
import brainstem
from brainstem.stem import USBCSwitch
from brainstem.result import Result

sw = USBCSwitch()
r = sw.discoverAndConnect(brainstem.link.Spec.USB)

if r != Result.NO_ERROR:
    print("Error:", r)
    exit(1)

print("Connected:", hex(sw.system.getSerialNumber().value))

PORT = 3   


# 1. Disable power + port on common
sw.usb.setPowerDisable(0)
sw.usb.setPortDisable(0)
time.sleep(0.1)

# 2. Disable mux
sw.mux.setEnable(False)
time.sleep(0.05)

# 3. Select port
sw.mux.setChannel(PORT)
time.sleep(0.05)

# 4. Enable mux
sw.mux.setEnable(True)
time.sleep(0.05)

# 5. Enable power to COMMON
sw.usb.setPowerEnable(1)
time.sleep(0.2)

print(f"COMMON → PORT {PORT} ACTIVE ✓ (Power + MUX enabled)")

print("Now plug iPhone into COMMON → It should charge.")
sw.disconnect()
