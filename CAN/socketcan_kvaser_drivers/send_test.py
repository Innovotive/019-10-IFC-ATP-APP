#!/usr/bin/env python3
import can
import time

bus = can.interface.Bus(channel="can0", interface="socketcan")

msg = can.Message(
    arbitration_id=0x100,
    data=[0x01, 0x02],
    is_extended_id=False
)

print("Sending CAN messages (Ctrl+C to stop)")

try:
    while True:
        try:
            bus.send(msg)
        except can.CanOperationError:
            # TX buffer full → wait a bit and continue
            time.sleep(0.02) #50Hz

except KeyboardInterrupt:
    print("\nStopped")

finally:
    bus.shutdown()
