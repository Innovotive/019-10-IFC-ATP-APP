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

# ✅ ID pins: set ONCE at startup (no verification, no re-apply)
from tests.ID.id_pins_init import init_id_pins_full_config

# ✅ CAN target selection (per-slot TX arbitration ID)
from tests.CAN.can_commands import set_target_slot


class HardwareController:
    """
    Hardware abstraction for:
      - Relays (power control)
      - Power detect
      - Per-slot CAN target selection

    IMPORTANT DESIGN (as requested):
      ✅ ID pins are configured ONCE at startup (all 4 slots)
      ✅ We DO NOT read/verify/print ID bits in the app
      ✅ We DO NOT re-apply ID configs per slot (that test happens later)
      ✅ Before any relay ON, we ensure startup ID init succeeded
    """

    def __init__(self, log_cb: Callable[[str], None]):
        self.log = log_cb

        # Track whether ID pins were configured successfully at startup
        self._id_config_ok = False

        # -------------------------------------------------
        # 1) Configure MCP23S17 outputs + apply all 4 ID configs ONCE
        # -------------------------------------------------
        try:
            self._id_config_ok = bool(init_id_pins_full_config())
            if self._id_config_ok:
                self.log("[HW] MCP23S17 ID pins configured (startup, all 4 slots)")
            else:
                self.log("[HW][WARN] MCP23S17 ID pins config returned False (startup)")
        except Exception as e:
            self._id_config_ok = False
            self.log(f"[HW][WARN] MCP23S17 ID pins config failed (startup): {e}")

        # -------------------------------------------------
        # 2) Default CAN target to slot 1
        # -------------------------------------------------
        try:
            set_target_slot(1)
            self.log("[HW] Default CAN target set to slot 1 (TX_ID=0x001)")
        except Exception as e:
            self.log(f"[HW][WARN] Default CAN target set failed: {e}")

    # -------------------------
    # CAN TARGET ONLY
    # -------------------------
    def select_slot(self, slot: int) -> None:
        """
        Only sets the CAN target arbitration ID for the slot.
        (ID pins are NOT touched here, by design.)
        """
        if slot not in (1, 2, 3, 4):
            raise ValueError(f"Invalid slot: {slot}")

        set_target_slot(slot)
        self.log(f"[HW] Selected slot {slot}: CAN target set")

    # -------------------------
    # RELAYS
    # -------------------------
    def relay_on(self, slot: int) -> None:
        """
        Power ON one RUP relay.

        Safety rule:
          - If startup ID pin config failed, we refuse to power anything ON.
        """
        if slot not in (1, 2, 3, 4):
            raise ValueError(f"Invalid slot: {slot}")

        if not self._id_config_ok:
            raise RuntimeError("Refusing relay ON because MCP23S17 ID init/config failed at startup")

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
