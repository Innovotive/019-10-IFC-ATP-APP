import can
import time

CHANNEL = "can0"
CAN_ID = 0x004

ATP_COMMANDS = 0x07

START_ATP = 0x02
END_ATP   = 0xC2

GUIDELIGHT_ON  = 0x61
GUIDELIGHT_OFF = 0x60
TERMINATION_ON  = 0x81
TERMINATION_OFF = 0x80
READ_ID_PINS_REQUEST = 0x42
POWER_REPORT_REQUEST = 0xA2
POWER_TO_60W   = 0x21
POWER_TO_45W   = 0x22
POWER_TO_30W   = 0x23
POWER_TO_22_5W = 0x24
POWER_TO_15W   = 0x25
IUL_ON  = 0xE1
IUL_OFF = 0xE0

bus = can.interface.Bus(channel=CHANNEL, bustype="socketcan")


def send_atp_command(cmd: int, desc: str = ""):
    # NEW protocol: [ATP_COMMANDS, cmd]
    data = [ATP_COMMANDS, cmd]

    msg = can.Message(
        arbitration_id=CAN_ID,
        data=data,
        is_extended_id=False
    )

    try:
        bus.send(msg)
        print(f"TX {desc or hex(cmd)}: {[hex(b) for b in data]}")
    except can.CanError as e:
        print("CAN send failed:", e)

def listen(duration_s: float = 2.0, timeout_s: float = 0.2):
    t_end = time.time() + duration_s
    while time.time() < t_end:
        msg = bus.recv(timeout=timeout_s)
        if msg and msg.dlc:
            data_hex = " ".join(f"{b:02X}" for b in msg.data)
            print(f"RX id=0x{msg.arbitration_id:03X} dlc={msg.dlc} data=[{data_hex}]")

if __name__ == "__main__":
    """
    # Enter ATP mode
    send_atp_command(START_ATP, "START_ATP")
    #listen(1.5)

    # Now ATP commands will be accepted
    #send_atp_command(READ_ID_PINS_REQUEST, "READ_ID_PINS_REQUEST")
    listen(1.5)
    send_atp_command(IUL_ON, "IUL_ON")
    #send_atp_command(IUL_OFF, "IUL_OFF")
    


    # Exit ATP mode
    send_atp_command(END_ATP, "END_ATP")
    listen(1.5)
"""
    send_atp_command(START_ATP, "START_ATP")
    # send_atp_command(END_ATP, "END_ATP")
    # Turn IUL ON GPIO Reads 0
    # send_atp_command(IUL_ON, "IUL_ON")
    #time.sleep(2)
    #send_atp_command(IUL_OFF, "IUL_OFF")
    # send_atp_command(GUIDELIGHT_OFF, "GUIDELIGHT_OFF")

    # send_atp_command(TERMINATION_ON , "TERMINATION_ON 83 ")
    #send_atp_command(TERMINATION_OFF , "TERMINATION_OFF ")
    send_atp_command(READ_ID_PINS_REQUEST, "READ_ID_PINS_REQUEST")
    send_atp_command(POWER_TO_60W,"POWER_TO_60W")
    #send_atp_command(POWER_TO_45W,"POWER_TO_45W")
    #send_atp_command(POWER_TO_30W,"POWER_TO_30W") #12v doesnt appear on the menu
    #send_atp_command(POWER_TO_22_5W,"POWER_TO_22_5W")
    # send_atp_command(POWER_TO_15W,"POWER_TO_15W")
    # time.sleep(2)
    # send_atp_command(POWER_REPORT_REQUEST,"POWER_REPORT_REQUEST")
    bus.shutdown()

    



