import time
import brainstem
from brainstem.stem import USBCSwitch
from brainstem.result import Result

sw = USBCSwitch()
r = sw.discoverAndConnect(brainstem.link.Spec.USB)

if r != Result.NO_ERROR:
    print("Cannot connect:", r)
    exit(1)

print("Connected — performing FACTORY RESET state...")

# Disable USB2/USB3 data paths
for p in range(4):
    sw.usb.setDataDisable(p)  
    sw.usb.setSuperSpeedDataDisable(p)
    sw.usb.setPortDisable(p)
    sw.usb.setPowerDisable(p)
    sw.usb.clearPortErrorStatus(p)

# Disable upstream power too
sw.usb.setPowerDisable(0)
sw.usb.setPortDisable(0)

# Reset MUX
sw.mux.setEnable(False)
sw.mux.setChannel(0)

# Reset hub mode
sw.usb.setHubMode(0)

time.sleep(0.2)
print("Factory reset complete.")
sw.disconnect()
