#!/usr/bin/env python3
import can
import time

bus = can.interface.Bus(channel="can0", interface="socketcan")

msg = can.Message(
    arbitration_id=0x100,
    data=[0x01, 0x02],
    is_extended_id=False
)

print("Sending frame: ID=0x100, data=[0x01, 0x02]")
bus.send(msg)
time.sleep(0.1)
print("Done.")
