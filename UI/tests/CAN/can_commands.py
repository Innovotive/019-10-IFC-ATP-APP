# tests/CAN/can_commands.py
import can
from .can_bus import get_can_bus

bus = get_can_bus()

# ==============================
# NEW FW: ATP COMMAND FRAMING
# ==============================
ATP_COMMANDS = 0x07  # data[0]

# ==============================
# Default TX target (slot 1)
# ==============================
_CURRENT_TX_ID = 0x001  # will be updated by set_target_slot()

# Map slot -> CAN TX arbitration id
# You said: slot1 id=0x001, slot2=0x002, slot3=0x003, slot4=0x004
SLOT_TO_CAN_ID = {
    1: 0x001,
    2: 0x002,
    3: 0x000,
    4: 0x003,
}

def set_target_slot(slot: int) -> None:
    """Select which RUP will receive commands (by CAN arbitration ID)."""
    global _CURRENT_TX_ID
    if slot not in SLOT_TO_CAN_ID:
        raise ValueError(f"Invalid slot for CAN target: {slot}")
    _CURRENT_TX_ID = SLOT_TO_CAN_ID[slot]
    print(f"[CAN] Target slot={slot} => TX_ID=0x{_CURRENT_TX_ID:03X}")

def set_tx_id(arbitration_id: int) -> None:
    """Manual override if needed."""
    global _CURRENT_TX_ID
    _CURRENT_TX_ID = int(arbitration_id) & 0x7FF
    print(f"[CAN] TX_ID set to 0x{_CURRENT_TX_ID:03X}")

# ==============================
# COMMAND BYTES
# ==============================
START_ATP            = 0x02
END_ATP              = 0xC2
GUIDELIGHT_ON        = 0x61
GUIDELIGHT_OFF       = 0x60
TERMINATION_ON       = 0x81
TERMINATION_OFF      = 0x80
READ_ID_PINS_REQ     = 0x42
POWER_60W            = 0x21
POWER_45W            = 0x22
POWER_30W            = 0x23
POWER_22_5W          = 0x24
POWER_15W            = 0x25
POWER_REPORT_REQUEST = 0xA2
IUL_ON               = 0xE1
IUL_OFF              = 0xE0

# ==============================
# GENERIC SEND
# ==============================
def _send(cmd_byte: int, description: str):
    payload = [ATP_COMMANDS, cmd_byte]

    msg = can.Message(
        arbitration_id=_CURRENT_TX_ID,
        data=payload,
        is_extended_id=False
    )

    try:
        bus.send(msg)
        print(
            f"📤 CAN TX | {description} | "
            f"ID=0x{_CURRENT_TX_ID:03X} | "
            f"DATA={[f'0x{b:02X}' for b in payload]}"
        )
    except can.CanError as e:
        print(f"❌ CAN TX FAILED | {description} | {e}")

# ==============================
# Commands
# ==============================
def start_atp(): _send(START_ATP, "START_ATP")
def end_atp(): _send(END_ATP, "END_ATP")

def guidelight_on(): _send(GUIDELIGHT_ON, "GUIDELIGHT_ON")
def guidelight_off(): _send(GUIDELIGHT_OFF, "GUIDELIGHT_OFF")

def termination_on(): _send(TERMINATION_ON, "TERMINATION_ON")
def termination_off(): _send(TERMINATION_OFF, "TERMINATION_OFF")

def read_id_pins_request(): _send(READ_ID_PINS_REQ, "READ_ID_PINS_REQUEST")

def power_60w(): _send(POWER_60W, "POWER_TO_60W")
def power_45w(): _send(POWER_45W, "POWER_TO_45W")
def power_30w(): _send(POWER_30W, "POWER_TO_30W")
def power_22_5w(): _send(POWER_22_5W, "POWER_TO_22_5W")
def power_15w(): _send(POWER_15W, "POWER_TO_15W")
def power_report_request(): _send(POWER_REPORT_REQUEST, "POWER_REPORT_REQUEST")

def iul_on(): _send(IUL_ON, "IUL_ON")
def iul_off(): _send(IUL_OFF, "IUL_OFF")
