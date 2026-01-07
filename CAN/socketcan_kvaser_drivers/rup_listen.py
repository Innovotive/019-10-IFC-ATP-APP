#!/usr/bin/env python3
import can

bus = can.interface.Bus(channel='can0', interface='socketcan')

print("Listening…")
while True:
    msg = bus.recv()
    if msg:
        print(msg)
