import can

bus = can.interface.Bus(channel='can0', bustype='socketcan')

print("Listening on CAN...")

while True:
    msg = bus.recv()
    if msg is not None:
        print(f"ID: 0x{msg.arbitration_id:X}   DLC: {msg.dlc}   DATA: {msg.data.hex(' ').upper()}")
