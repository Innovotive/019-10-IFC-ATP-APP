# tests/CAN/can_commands.py
import can
from typing import Optional, Sequence

from .can_bus import get_can_bus
from slot_config import SlotConfig

ATP_PREFIX = 0x07

# Command bytes
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

def can_send(slot_cfg: SlotConfig, cmd_byte: int, description: str = "", payload: Optional[Sequence[int]] = None):
    """
    Sends classic CAN frame:
      [0] = 0x07
      [1] = cmd
      [2..] optional payload
    """
    bus = get_can_bus()
    data = [ATP_PREFIX & 0xFF, cmd_byte & 0xFF]
    if payload:
        data += [int(b) & 0xFF for b in payload]
    data = data[:8]

    msg = can.Message(
        arbitration_id=int(slot_cfg.can_tx_id),
        data=data,
        is_extended_id=False
    )

    bus.send(msg)
    if description:
        print(f"📤 CAN TX | slot={slot_cfg.slot} id=0x{slot_cfg.can_tx_id:03X} | {description} | "
              f"[{len(data)}] " + " ".join(f"{b:02X}" for b in data))

# Convenience wrappers
def start_atp(slot_cfg: SlotConfig):            can_send(slot_cfg, START_ATP, "START_ATP")
def end_atp(slot_cfg: SlotConfig):              can_send(slot_cfg, END_ATP, "END_ATP")
def termination_on(slot_cfg: SlotConfig):       can_send(slot_cfg, TERMINATION_ON, "TERMINATION_ON")
def termination_off(slot_cfg: SlotConfig):      can_send(slot_cfg, TERMINATION_OFF, "TERMINATION_OFF")
def read_id_pins_request(slot_cfg: SlotConfig): can_send(slot_cfg, READ_ID_PINS_REQ, "READ_ID_PINS_REQUEST")
def iul_on(slot_cfg: SlotConfig):               can_send(slot_cfg, IUL_ON, "IUL_ON")
def iul_off(slot_cfg: SlotConfig):              can_send(slot_cfg, IUL_OFF, "IUL_OFF")
