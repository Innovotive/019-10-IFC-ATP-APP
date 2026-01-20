# services/hardware.py
from typing import Callable

from tests.power_PT.relay_1_4 import (
    relay_on_rup1, relay_off_rup1,
    relay_on_rup2, relay_off_rup2,
    relay_on_rup3, relay_off_rup3,
    relay_on_rup4, relay_off_rup4,
)

from tests.power_PT.power_1_4 import (
    read_power_state_rup1,
    read_power_state_rup2,
    read_power_state_rup3,
    read_power_state_rup4,
    cleanup_gpio,
)

# ✅ ID-pins manager (MCP23S17) — absolute-per-slot patterns are inside id_pins_init.py
from tests.ID.id_pins_init import init_id_pins_active_high, set_slot_id_config

# ✅ CAN target selection (per-slot TX arbitration ID)
from tests.CAN.can_commands import set_target_slot


class HardwareController:
    """
    Hardware abstraction for:
      - Relays (power control)
      - Power detect
      - Per-slot selection:
          * sets CAN target arbitration ID (slot->CAN_TX_ID)
          * sets MCP23S17 ID-pin pattern for that slot

    IMPORTANT:
      - ID pins MUST be set BEFORE powering ON a RUP (boot/latch timing).
    """

    def __init__(self, log_cb: Callable[[str], None]):
        self.log = log_cb

        # Init MCP23S17 once at startup
        try:
            ok = bool(init_id_pins_active_high())
            self.log("[HW] MCP23S17 init OK" if ok else "[HW][WARN] MCP23S17 init returned False")
        except Exception as e:
            self.log(f"[HW][WARN] MCP23S17 init failed: {e}")

        # Default CAN target to slot 1
        try:
            set_target_slot(1)
            self.log("[HW] Default CAN target set to slot 1 (TX_ID=0x001)")
        except Exception as e:
            self.log(f"[HW][WARN] Default CAN target set failed: {e}")

    # -------------------------
    # ID PINS ONLY (for power-up timing)
    # -------------------------
    def _apply_id_only(self, slot: int) -> None:
        ok = bool(set_slot_id_config(slot))
        if not ok:
            raise RuntimeError(f"set_slot_id_config({slot}) returned False")

    # -------------------------
    # SLOT SELECT (CAN + ID PINS)
    # -------------------------
    def select_slot(self, slot: int) -> None:
        if slot not in (1, 2, 3, 4):
            raise ValueError(f"Invalid slot: {slot}")

        set_target_slot(slot)
        self._apply_id_only(slot)

        self.log(f"[HW] Selected slot {slot}: CAN target + ID pins configured")

    # -------------------------
    # RELAYS
    # -------------------------
    def relay_on(self, slot: int) -> None:
        """
        Set ID pins for this slot BEFORE powering it ON,
        so the RUP boots/latches the correct ID config.
        """
        if slot not in (1, 2, 3, 4):
            raise ValueError(f"Invalid slot: {slot}")

        self._apply_id_only(slot)

        if slot == 1:
            relay_on_rup1()
        elif slot == 2:
            relay_on_rup2()
        elif slot == 3:
            relay_on_rup3()
        else:
            relay_on_rup4()

    def relay_off(self, slot: int) -> None:
        if slot == 1:
            relay_off_rup1()
        elif slot == 2:
            relay_off_rup2()
        elif slot == 3:
            relay_off_rup3()
        elif slot == 4:
            relay_off_rup4()
        else:
            raise ValueError(f"Invalid slot: {slot}")

    def relay_off_all(self) -> None:
        for s in (1, 2, 3, 4):
            try:
                self.relay_off(s)
            except Exception:
                pass

    # -------------------------
    # POWER DETECT
    # -------------------------
    def power_present(self, slot: int) -> bool:
        if slot == 1:
            return bool(read_power_state_rup1())
        if slot == 2:
            return bool(read_power_state_rup2())
        if slot == 3:
            return bool(read_power_state_rup3())
        if slot == 4:
            return bool(read_power_state_rup4())
        raise ValueError(f"Invalid slot: {slot}")

    # -------------------------
    # CLEANUP
    # -------------------------
    def cleanup(self) -> None:
        try:
            cleanup_gpio()
        except Exception:
            pass
