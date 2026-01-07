from RPiMCP23S17.MCP23S17 import MCP23S17
import time

# MCP23S17(bus, cs, device_id=0)
# bus = 0
# cs  = 0  → CE0
m = MCP23S17(0, 0, device_id=0)

# ✅ REQUIRED initialization
m.open()

# A0 = GPA0 → INPUT
m.setDirection(0, m.DIR_INPUT)

# Enable pull-up
m.setPullupMode(0, m.PULLUP_ENABLED)

print("Reading A0 (GPA0). Tie A0 to GND to see 0")

try:
    while True:
        print("A0 =", m.digitalRead(0))
        time.sleep(0.5)
except KeyboardInterrupt:
    m.close()
    print("\nClosed")
