import can
import random
import time

# =====================================
# CONFIG
# =====================================
CAN_INTERFACE = "can0"
BITRATE = 125000        # must match your bus
SEND_PERIOD_S = 0.1     # 100 ms

ID_MIN = 0x100
ID_MAX = 0x7FF          # standard 11-bit IDs

# =====================================
# CAN BUS SETUP
# =====================================
bus = can.interface.Bus(
    channel=CAN_INTERFACE,
    bustype="socketcan"
)

print("🚀 Random CAN sender started (100 ms rate)")
print("Press Ctrl+C to stop\n")

try:
    while True:
        # Random arbitration ID (standard frame)
        arb_id = random.randint(ID_MIN, ID_MAX)

        # Random data length (0–8 bytes)
        dlc = random.randint(0, 8)

        # Random payload
        data = [random.randint(0, 255) for _ in range(dlc)]

        msg = can.Message(
            arbitration_id=arb_id,
            data=data,
            is_extended_id=False
        )

        try:
            bus.send(msg)
            print(f"TX  ID=0x{arb_id:03X}  DLC={dlc}  DATA={data}")
        except can.CanError as e:
            print("❌ CAN send failed:", e)

        time.sleep(SEND_PERIOD_S)

except KeyboardInterrupt:
    print("\n🛑 Stopped by user")

finally:
    bus.shutdown()
