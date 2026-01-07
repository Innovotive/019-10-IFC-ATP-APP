import can
from .can_bus import get_can_bus

# ==============================
# CAN CONFIG
# ==============================
CAN_TX_ID = 0x002
bus = get_can_bus()

# ==============================
# COMMAND BYTES
# ==============================
START_ATP           = 0x02
END_ATP             = 0xC2

GUIDELIGHT_ON       = 0x61
GUIDELIGHT_OFF      = 0x60

TERMINATION_ON      = 0x81
TERMINATION_OFF     = 0x80

READ_ID_PINS_REQ    = 0x42

POWER_60W           = 0x21
POWER_45W           = 0x22
POWER_30W           = 0x23
POWER_22_5W         = 0x24
POWER_15W           = 0x25

IUL_ON              = 0xE1
IUL_OFF             = 0xE0


# ==============================
# GENERIC SEND
# ==============================
def _send(cmd_byte: int, description: str):
    """
    Low-level CAN TX helper.
    Sends exactly ONE standard CAN frame.
    """
    msg = can.Message(
        arbitration_id=CAN_TX_ID,
        data=[cmd_byte],
        is_extended_id=False
    )

    try:
        bus.send(msg)
        print(f"📤 CAN TX | {description} | 0x{cmd_byte:02X}")
    except can.CanError as e:
        print(f"❌ CAN TX FAILED | {description} | {e}")


# ==============================
# ATP MODE
# ==============================
def start_atp():
    _send(START_ATP, "START_ATP")

def end_atp():
    _send(END_ATP, "END_ATP")


# ==============================
# GUIDE LIGHT
# ==============================
def guidelight_on():
    _send(GUIDELIGHT_ON, "GUIDELIGHT_ON")

def guidelight_off():
    _send(GUIDELIGHT_OFF, "GUIDELIGHT_OFF")


# ==============================
# TERMINATION RESISTOR
# ==============================
def termination_on():
    _send(TERMINATION_ON, "TERMINATION_ON")

def termination_off():
    _send(TERMINATION_OFF, "TERMINATION_OFF")


# ==============================
# ID PINS
# ==============================
def read_id_pins_request():
    _send(READ_ID_PINS_REQ, "READ_ID_PINS_REQUEST")


# ==============================
# POWER LEVELS
# ==============================
def power_60w():
    _send(POWER_60W, "POWER_TO_60W")

def power_45w():
    _send(POWER_45W, "POWER_TO_45W")

def power_30w():
    _send(POWER_30W, "POWER_TO_30W")

def power_22_5w():
    _send(POWER_22_5W, "POWER_TO_22_5W")

def power_15w():
    _send(POWER_15W, "POWER_TO_15W")


# ==============================
# IUL (Indicator / Load)
# ==============================
def iul_on():
    _send(IUL_ON, "IUL_ON")

def iul_off():
    _send(IUL_OFF, "IUL_OFF")
