# switch_controller.py

import brainstem
from brainstem import link
from brainstem.result import Result


class AcronameSwitch:
    def __init__(self):
        self.dev = brainstem.stem.USBCSwitch()
        r = self.dev.discoverAndConnect(link.Spec.USB)
        if r != Result.NO_ERROR:
            raise RuntimeError(f"Could not connect to USBCSwitch, error {r}")
        self.usb = self.dev.usb
        print("✅ Connected to Acroname USBCSwitch")

    def select_port(self, port: int):
        """Connect COMMON ↔ given port, in PASSIVE PD-transparent mode."""
        print(f"\n🔀 Selecting port {port}")

        # Turn everything off first
        for p in range(4):
            self.usb.setPortDisable(p)
            self.usb.setPowerDisable(p)

        # Make selected port passive (transparent PD path)
        self.usb.setPortMode(port, self.usb.PORT_MODE_PASSIVE)

        # Enable data + VBUS path on that port
        self.usb.setPortEnable(port)
        self.usb.setPowerEnable(port)

        print(f"✅ Port {port} enabled in PASSIVE mode")

    def disconnect(self):
        self.dev.disconnect()
        print("🔌 USBCSwitch disconnected")
