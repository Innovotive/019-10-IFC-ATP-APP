import can
import time

# ==============================
# CAN BUS SETUP
# ==============================
# Interface: can0
# Bitrate already configured at OS level (e.g. 125k / 500k)
bus = can.interface.Bus(
    channel="can0",
    bustype="socketcan"
)



CAN_ID = 0x002   # Standard CAN ID

# ==============================
# COMMAND DEFINITIONS
# ==============================
START_ATP              = 0x02
END_ATP                = 0xC2

GUIDELIGHT_ON           = 0x61
GUIDELIGHT_OFF          = 0x60

TERMINATION_ON          = 0x81
TERMINATION_OFF         = 0x80

READ_ID_PINS_REQUEST    = 0x42

POWER_TO_60W            = 0x21
POWER_TO_45W            = 0x22
POWER_TO_30W            = 0x23
POWER_TO_22_5W          = 0x24
POWER_TO_15W            = 0x25

IUL_ON                  = 0xE1
IUL_OFF                 = 0xE0

# ==============================
# SEND FUNCTION
# ==============================
def send_command(command_byte, description):
    """
    Sends one CAN frame with:
    - ID = 0x002
    - First byte = command_byte
    """
    data = [command_byte] 

    msg = can.Message(
        arbitration_id=CAN_ID,
        data=data,
        is_extended_id=False
    )

    try:
        bus.send(msg)
        print(f"Sent {description}: {[hex(b) for b in data]}")
    except can.CanError as e:
        print("CAN send failed:", e)

# ==============================
# SEQUENCE EXAMPLE
# ==============================

# start ATP
send_command(START_ATP, "START_ATP")
#send_command(END_ATP, "END_ATP")
# Turn IUL ON GPIO Reads 0
#send_command(IUL_ON, "IUL_ON")
#send_command(IUL_OFF, "IUL_OFF")
#time.sleep(5)
#send_command(TERMINATION_ON , "TERMINATION_ON 83 ")
#send_command(TERMINATION_OFF , "TERMINATION_OFF ")
#send_command(READ_ID_PINS_REQUEST, "READ_ID_PINS_REQUEST")


"""



# Turn IUL Off Reads 1
send_command(IUL_OFF, "IUL_OFF")
time.sleep(0.2)

# End ATP
send_command(END_ATP, "END_ATP")



# Turn guide light ON
send_command(GUIDELIGHT_ON, "GUIDELIGHT_ON")
time.sleep(0.2)

# Request ID pins
send_command(READ_ID_PINS_REQUEST, "READ_ID_PINS_REQUEST")
time.sleep(0.2)



# Turn guide light ON
send_command(GUIDELIGHT_ON, "GUIDELIGHT_ON")
time.sleep(0.2)

# Request ID pins
send_command(READ_ID_PINS_REQUEST, "READ_ID_PINS_REQUEST")
time.sleep(0.2)

# Set power to 60W
send_command(POWER_TO_60W, "POWER_TO_60W")
time.sleep(0.2)

# Turn IUL ON
send_command(IUL_ON, "IUL_ON")
time.sleep(0.2)

# End ATP
send_command(END_ATP, "END_ATP")"""
