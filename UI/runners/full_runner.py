# runners/full_runner.py
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple, Any

from services.hardware import HardwareController
from tests.CAN.can_commands import set_target_slot


@dataclass
class FullUpdate:
    gate: int
    slot: int
    status: str
    led: Optional[str]  # "yellow"/"green"/"red"/None


class FullRunner:
    """
    Full ATP (sequential per RUP):
      For slot 1..4:
        relay ON
        gate3..gate7
        relay OFF
    """

    def __init__(
        self,
        hw: HardwareController,
        log_cb: Callable[[str], None],
        on_update: Callable[[FullUpdate], None],
        run_gate4_fn: Callable[[int, Callable[[str], None]], bool],  # slot-aware
        run_gate5_fn: Callable[[int, Callable[[str], None]], bool],  # slot-aware
        run_gate6_fn: Callable[[int, Callable[[str], None]], bool],  # slot-aware
        run_gate7_fn: Callable[..., Tuple[Dict[str, Any], list]],     # now called with (slot, log_cb=...)
        check_power_before_full: bool = True,
    ):
        self.hw = hw
        self.log = log_cb
        self.on_update = on_update

        self.run_gate4_fn = run_gate4_fn
        self.run_gate5_fn = run_gate5_fn
        self.run_gate6_fn = run_gate6_fn
        self.run_gate7_fn = run_gate7_fn

        self.check_power_before_full = check_power_before_full
        self.reset()

    def reset(self) -> None:
        self.active = False
        self.done = False
        self.current_slot = 1
        self.phase = "power_on"  # power_on, gate3, gate4, gate5, gate6, gate7, power_off

    def start(self) -> None:
        self.reset()
        self.active = True
        self.done = False
        self.log("[FULL] Start: sequential RUP1..RUP4 (gates 3..7)")
        self.on_update(FullUpdate(gate=0, slot=1, status="Starting...", led="yellow"))

    def step(self, gate_results: Dict[int, Dict[int, bool]]) -> bool:
        if not self.active or self.done:
            return True

        s = self.current_slot
        if s > 4:
            self._finish()
            return True

        # -------------------------
        # POWER ON
        # -------------------------
        if self.phase == "power_on":
            self.log(f"[FULL] RUP{s}: relay ON")
            self.on_update(FullUpdate(gate=0, slot=s, status="Powering ON...", led="yellow"))
            try:
                self.hw.relay_on(s)
            except Exception as e:
                self.log(f"[HW][FAIL] RUP{s} relay ON error: {e}")
                for g in range(3, 8):
                    gate_results[g][s] = False
                self.phase = "power_off"
                return False

            if self.check_power_before_full:
                try:
                    pwr = self.hw.power_present(s)
                except Exception as e:
                    self.log(f"[HW][FAIL] RUP{s} power detect error: {e}")
                    pwr = False

                if not pwr:
                    self.log(f"[HW][FAIL] RUP{s}: power_detect=False")
                    for g in range(3, 8):
                        gate_results[g][s] = False
                    self.on_update(FullUpdate(gate=0, slot=s, status="NO POWER (FAIL)", led="red"))
                    self.phase = "power_off"
                    return False

            # Ensure subsequent CAN commands are addressed to this slot
            try:
                set_target_slot(s)
            except Exception as e:
                self.log(f"[CAN][WARN] set_target_slot({s}) failed: {e}")

            self.on_update(FullUpdate(gate=0, slot=s, status="Powered (Ready)", led="yellow"))
            self.phase = "gate3"
            return False

        # -------------------------
        # GATE 3 (depends on gate2 for this slot)
        # -------------------------
        if self.phase == "gate3":
            g = 3
            self.log(f"[GATE3] RUP{s}: simulated depends on Gate2")
            gate_results[g][s] = bool(gate_results[2][s])
            self.on_update(FullUpdate(gate=g, slot=s, status="PASS" if gate_results[g][s] else "FAIL", led=None))
            self.phase = "gate4"
            return False

        # -------------------------
        # GATE 4 (REAL, slot-aware)
        # -------------------------
        if self.phase == "gate4":
            g = 4
            self.log(f"[GATE4] RUP{s}: REAL")
            try:
                set_target_slot(s)
                gate_results[g][s] = bool(self.run_gate4_fn(s, self.log))
            except Exception as e:
                self.log(f"[GATE4][ERROR] RUP{s}: {e}")
                gate_results[g][s] = False
            self.on_update(FullUpdate(gate=g, slot=s, status="PASS" if gate_results[g][s] else "FAIL", led=None))
            self.phase = "gate5"
            return False

        # -------------------------
        # GATE 5 (REAL, slot-aware)
        # -------------------------
        if self.phase == "gate5":
            g = 5
            self.log(f"[GATE5] RUP{s}: REAL")
            try:
                set_target_slot(s)
                gate_results[g][s] = bool(self.run_gate5_fn(s, self.log))
            except Exception as e:
                self.log(f"[GATE5][ERROR] RUP{s}: {e}")
                gate_results[g][s] = False
            self.on_update(FullUpdate(gate=g, slot=s, status="PASS" if gate_results[g][s] else "FAIL", led=None))
            self.phase = "gate6"
            return False

        # -------------------------
        # GATE 6 (REAL, slot-aware)
        # -------------------------
        if self.phase == "gate6":
            g = 6
            self.log(f"[GATE6] RUP{s}: REAL")
            try:
                set_target_slot(s)
                gate_results[g][s] = bool(self.run_gate6_fn(s, self.log))
            except Exception as e:
                self.log(f"[GATE6][ERROR] RUP{s}: {e}")
                gate_results[g][s] = False
            self.on_update(FullUpdate(gate=g, slot=s, status="PASS" if gate_results[g][s] else "FAIL", led=None))
            self.phase = "gate7"
            return False

        # -------------------------
        # GATE 7 (REAL, slot-aware: pass slot to gate7)
        # -------------------------
        if self.phase == "gate7":
            g = 7
            self.log(f"[GATE7] RUP{s}: REAL")
            try:
                set_target_slot(s)
                results, logs = self.run_gate7_fn(s, log_cb=self.log)  # ✅ pass slot
                ok = bool(results.get("pass", False))
                gate_results[g][s] = ok
                self.log(f"[GATE7] RUP{s} pass={ok}")
                try:
                    for line in logs:
                        self.log(line)
                except Exception:
                    pass
            except Exception as e:
                self.log(f"[GATE7][ERROR] RUP{s}: {e}")
                gate_results[g][s] = False

            self.on_update(FullUpdate(gate=g, slot=s, status="PASS" if gate_results[g][s] else "FAIL", led=None))
            self.phase = "power_off"
            return False

        # -------------------------
        # POWER OFF + NEXT SLOT
        # -------------------------
        if self.phase == "power_off":
            self.log(f"[FULL] RUP{s}: relay OFF")
            try:
                self.hw.relay_off(s)
            except Exception as e:
                self.log(f"[HW][WARN] RUP{s} relay OFF error: {e}")

            full_ok = all(bool(gate_results[g][s]) for g in range(3, 8))
            self.on_update(FullUpdate(
                gate=7,
                slot=s,
                status="Done (PASS)" if full_ok else "Done (FAIL)",
                led="green" if full_ok else "red"
            ))

            self.current_slot += 1
            if self.current_slot <= 4:
                self.on_update(FullUpdate(gate=0, slot=self.current_slot, status="Starting...", led="yellow"))
                self.phase = "power_on"
            else:
                self._finish()

            return False

        # fallback
        self.log(f"[FULL][WARN] Unknown phase: {self.phase}")
        self._finish()
        return True

    def _finish(self) -> None:
        self.log("[FULL] Finished stepping all RUPs")
        try:
            self.hw.relay_off_all()
        except Exception:
            pass
        self.active = False
        self.done = True
