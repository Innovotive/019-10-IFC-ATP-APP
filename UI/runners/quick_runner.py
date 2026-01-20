# runners/quick_runner.py
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from services.hardware import HardwareController


@dataclass
class SlotUpdate:
    slot: int
    gate: int
    status: str
    led: Optional[str]


class QuickRunner:
    """
    Quick Test (NEW FLOW):
      1) Power ON ALL RUPs (1..4) once and keep them ON
      2) Gate1: test slot 1..4 sequentially
      3) Gate2: test slot 1..4 sequentially

    Switching between RUPs happens HERE via hw.select_slot(slot),
    which sets the MCP23S17 ID configuration per slot.
    """

    def __init__(
        self,
        hw: HardwareController,
        log_cb: Callable[[str], None],
        gate1_fn: Callable[[int], bool],     # Gate1 needs slot
        gate2_fn: Callable[[int], bool],     # ✅ Gate2 needs slot now
        on_update: Callable[[SlotUpdate], None],
    ):
        self.hw = hw
        self.log = log_cb
        self.gate1_fn = gate1_fn
        self.gate2_fn = gate2_fn
        self.on_update = on_update
        self.reset()

    def reset(self) -> None:
        self.active = False
        self.done = False
        self.phase = "power_on_all"  # power_on_all -> gate1 -> gate2 -> finish
        self.current_slot = 1

        self.results: Dict[int, Dict[int, bool]] = {
            1: {1: True, 2: True, 3: True, 4: True},
            2: {1: True, 2: True, 3: True, 4: True},
        }
        self.failed_slots: List[int] = []

    def start(self) -> None:
        self.reset()
        self.active = True
        self.done = False
        self.log("[QUICK] Start: power ON all RUPs, Gate1(1..4), then Gate2(1..4)")

        for s in (1, 2, 3, 4):
            self.on_update(SlotUpdate(slot=s, gate=0, status="Queued", led="yellow"))
        self.on_update(SlotUpdate(slot=1, gate=0, status="Starting...", led="yellow"))

    def step(self) -> bool:
        if not self.active or self.done:
            return True

        # -------------------------
        # PHASE: POWER ON ALL
        # -------------------------
        if self.phase == "power_on_all":
            self.log("[QUICK] Powering ON all RUPs (1..4)")

            for s in (1, 2, 3, 4):
                self.on_update(SlotUpdate(slot=s, gate=0, status="Powering ON...", led="yellow"))

                try:
                    self.hw.relay_on(s)
                    self.log(f"[HW] RUP{s}: relay ON")
                except Exception as e:
                    self.log(f"[HW][FAIL] RUP{s} relay ON error: {e}")
                    self._mark_fail_both(s)
                    self.on_update(SlotUpdate(slot=s, gate=0, status="RELAY ON FAIL", led="red"))
                    continue

                # optional startup power detect
                try:
                    pwr = bool(self.hw.power_present(s))
                except Exception as e:
                    self.log(f"[HW][FAIL] RUP{s} power detect read error: {e}")
                    pwr = False

                if not pwr:
                    self.log(f"[HW][FAIL] RUP{s}: power_detect=False")
                    self._mark_fail_both(s)
                    self.on_update(SlotUpdate(slot=s, gate=0, status="NO POWER (FAIL)", led="red"))
                else:
                    self.on_update(SlotUpdate(slot=s, gate=0, status="Powered (Ready)", led="yellow"))

            self.phase = "gate1"
            self.current_slot = 1
            return False

        # -------------------------
        # PHASE: GATE 1 (1..4)
        # -------------------------
        if self.phase == "gate1":
            s = self.current_slot
            if s > 4:
                self.phase = "gate2"
                self.current_slot = 1
                self.log("[QUICK] Gate1 complete. Moving to Gate2...")
                return False

            # Configure ID pins for this slot
            try:
                self.hw.select_slot(s)
            except Exception as e:
                self.log(f"[HW][FAIL] select_slot({s}) failed: {e}")
                self._mark_fail_both(s)
                self.on_update(SlotUpdate(slot=s, gate=1, status="SELECT FAIL", led="red"))
                self.current_slot += 1
                return False

            self.log(f"[GATE1] RUP{s} running...")
            ok = False
            try:
                ok = bool(self.gate1_fn(s))
            except Exception as e:
                self.log(f"[GATE1][ERROR] RUP{s}: {e}")
                ok = False

            self.results[1][s] = ok
            self.on_update(SlotUpdate(slot=s, gate=1, status="PASS" if ok else "FAIL", led=None))
            if not ok and s not in self.failed_slots:
                self.failed_slots.append(s)

            self.current_slot += 1
            return False

        # -------------------------
        # PHASE: GATE 2 (1..4)
        # -------------------------
        if self.phase == "gate2":
            s = self.current_slot
            if s > 4:
                self._finish()
                return True

            # Configure ID pins for this slot
            try:
                self.hw.select_slot(s)
            except Exception as e:
                self.log(f"[HW][FAIL] select_slot({s}) failed: {e}")
                self._mark_fail_both(s)
                self.on_update(SlotUpdate(slot=s, gate=2, status="SELECT FAIL", led="red"))
                self.current_slot += 1
                return False

            self.log(f"[GATE2] RUP{s} running...")
            ok = False
            try:
                ok = bool(self.gate2_fn(s))   # ✅ pass slot
            except Exception as e:
                self.log(f"[GATE2][ERROR] RUP{s}: {e}")
                ok = False

            self.results[2][s] = ok
            self.on_update(SlotUpdate(slot=s, gate=2, status="PASS" if ok else "FAIL", led=None))
            if not ok and s not in self.failed_slots:
                self.failed_slots.append(s)

            self.current_slot += 1
            return False

        self.log(f"[QUICK][WARN] Unknown phase: {self.phase}")
        self._finish()
        return True

    def _mark_fail_both(self, slot: int) -> None:
        self.results[1][slot] = False
        self.results[2][slot] = False
        if slot not in self.failed_slots:
            self.failed_slots.append(slot)

    def _finish(self) -> None:
        self.log("[QUICK] Finished Quick Test (RUPs remain powered ON)")
        self.active = False
        self.done = True

    def overall_pass(self) -> bool:
        return len(self.failed_slots) == 0
