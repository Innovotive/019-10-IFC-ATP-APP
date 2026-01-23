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

# ✅ NEW: ID-pins API (sets all 4 without resetting per-call)
from tests.ID.id_pins_init import (
    init_id_pins_full_config,
    set_all_slots_id_configs,
)

# ✅ CAN target selection (per-slot TX arbitration ID)
from tests.CAN.can_commands import set_target_slot


class HardwareController:
    """
    Hardware abstraction for:
      - Relays (power control)
      - Power detect
      - Slot selection:
          * sets CAN target arbitration ID (slot->CAN_TX_ID)
          * ensures MCP23S17 ID-pin config is correct

    IMPORTANT:
      - ID pins must already be correct BEFORE powering ON a RUP.
    """

    # Put your FINAL desired table here (bits are "ID3ID2ID1")
    # Example:
    # Slot1 → 110 (ID3 shorted)
    # Slot2 → 101 (ID2 shorted)
    # Slot3 → 011 (ID1 shorted)
    # Slot4 → 100 (ID2 + ID3 shorted)
    DEFAULT_SLOT_BITS = {
        1: "110",
        2: "101",
        3: "011",
        4: "100",
    }

    def __init__(self, log_cb: Callable[[str], None]):
        self.log = log_cb

        # Init + apply ALL 4 slot configs once at startup
        try:
            ok = bool(init_id_pins_full_config())
            self.log("[HW] MCP23S17 init + FULL ID config OK" if ok else "[HW][WARN] MCP23S17 full init returned False")
        except Exception as e:
            self.log(f"[HW][WARN] MCP23S17 full init failed: {e}")

        # Default CAN target to slot 1
        try:
            set_target_slot(1)
            self.log("[HW] Default CAN target set to slot 1 (TX_ID=0x001)")
        except Exception as e:
            self.log(f"[HW][WARN] Default CAN target set failed: {e}")

    # -------------------------
    # ID PINS (apply full config safely)
    # -------------------------
    def _apply_all_id_configs(self) -> None:
        ok = bool(set_all_slots_id_configs(self.DEFAULT_SLOT_BITS, verify=True))
        if not ok:
            raise RuntimeError("set_all_slots_id_configs returned False")

    # -------------------------
    # SLOT SELECT (CAN)
    # -------------------------
    def select_slot(self, slot: int) -> None:
        if slot not in (1, 2, 3, 4):
            raise ValueError(f"Invalid slot: {slot}")

        # CAN target changes per slot
        set_target_slot(slot)

        # Optional but safe: re-apply full ID config (does not break other slots)
        # If you don't need to re-apply every time, you can remove this line.
        self._apply_all_id_configs()

        self.log(f"[HW] Selected slot {slot}: CAN target set (ID pins kept consistent)")

    # -------------------------
    # RELAYS
    # -------------------------
    def relay_on(self, slot: int) -> None:
        """
        Ensure ID pins are correct BEFORE powering ON any RUP.
        We apply the full table (safe), then power the requested slot.
        """
        if slot not in (1, 2, 3, 4):
            raise ValueError(f"Invalid slot: {slot}")

        self._apply_all_id_configs()

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
