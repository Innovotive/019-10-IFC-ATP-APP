# runners/full_runner.py
#!/usr/bin/env python3
"""
FullRunner — Gate-by-gate across slots

Key behavior:
- Gate3 is ONE-SHOT for all slots (your TR order) => returns {1:bool,2:bool,3:bool,4:bool}
- Gate4/5/6 run per-slot (slot1..slot4)
- If a slot fails a gate => it fails for itself only; keep going for next slots
- FullRunner does NOT power relays (main_atp decides power policy)
"""

from dataclasses import dataclass
from typing import Callable, Dict, Optional, Any, List


@dataclass
class FullUpdate:
    gate: int
    slot: int
    status: str
    led: Optional[str] = None  # e.g. "green", "red", "yellow", "gray"


class FullRunner:
    def __init__(
        self,
        log_cb: Callable[[str], None],
        on_update: Callable[[FullUpdate], None],

        # Gate runners:
        run_gate3_all_fn: Callable[[Optional[Callable[[str], None]]], Dict[int, bool]],
        run_gate4_bool_fn: Callable[[int, Optional[Callable[[str], None]]], bool],
        run_gate5_bool_fn: Callable[[int, Optional[Callable[[str], None]]], bool],
        run_gate6_bool_fn: Callable[[int, Optional[Callable[[str], None]]], bool],

        # Slots:
        slots: List[int] = None,
    ):
        self.log = log_cb
        self.on_update = on_update

        self.run_gate3_all_fn = run_gate3_all_fn
        self.run_gate4_bool_fn = run_gate4_bool_fn
        self.run_gate5_bool_fn = run_gate5_bool_fn
        self.run_gate6_bool_fn = run_gate6_bool_fn

        self.slots = slots or [1, 2, 3, 4]

        # results[gate][slot] = bool
        self.results: Dict[int, Dict[int, bool]] = {3: {}, 4: {}, 5: {}, 6: {}}

    def _set_ui(self, gate: int, slot: int, status: str, led: Optional[str] = None):
        self.on_update(FullUpdate(gate=gate, slot=slot, status=status, led=led))

    def run(self) -> Dict[int, Dict[int, bool]]:
        """
        Runs Gate3..Gate6 gate-by-gate.
        Returns dict results.
        """
        self.log("[FULL] Start: GATE-BY-GATE (Gate3..Gate6) across RUP1..RUP4 (RUPs already powered ON)")

        # --------------------------
        # GATE 3 (ONE-SHOT, ALL SLOTS)
        # --------------------------
        self.log("[FULL] Gate3 START (one-shot sequence for all slots)")
        for s in self.slots:
            self._set_ui(3, s, "Running...", led="yellow")

        try:
            g3 = self.run_gate3_all_fn(self.log)  # expects {1:bool,2:bool,3:bool,4:bool}
        except Exception as e:
            self.log(f"[GATE3][ERROR] {e}")
            g3 = {s: False for s in self.slots}

        for s in self.slots:
            ok = bool(g3.get(s, False))
            self.results[3][s] = ok
            self._set_ui(3, s, "PASS" if ok else "FAIL", led=("green" if ok else "red"))

        self.log("[FULL] Gate3 COMPLETE for all slots ✅")

        # --------------------------
        # GATE 4 (PER SLOT)
        # --------------------------
        self.log("[FULL] Gate4 START (per slot)")
        for s in self.slots:
            self._set_ui(4, s, "Running...", led="yellow")
            try:
                ok = self.run_gate4_bool_fn(s, self.log)
            except Exception as e:
                self.log(f"[GATE4][ERROR] slot={s}: {e}")
                ok = False

            self.results[4][s] = ok
            self._set_ui(4, s, "PASS" if ok else "FAIL", led=("green" if ok else "red"))
        self.log("[FULL] Gate4 COMPLETE for all slots ✅")

        # --------------------------
        # GATE 5 (PER SLOT)
        # --------------------------
        self.log("[FULL] Gate5 START (per slot)")
        for s in self.slots:
            self._set_ui(5, s, "Running...", led="yellow")
            try:
                ok = self.run_gate5_bool_fn(s, self.log)
            except Exception as e:
                self.log(f"[GATE5][ERROR] slot={s}: {e}")
                ok = False

            self.results[5][s] = ok
            self._set_ui(5, s, "PASS" if ok else "FAIL", led=("green" if ok else "red"))
        self.log("[FULL] Gate5 COMPLETE for all slots ✅")

        # --------------------------
        # GATE 6 (PER SLOT)
        # --------------------------
        self.log("[FULL] Gate6 START (per slot)")
        for s in self.slots:
            self._set_ui(6, s, "Running...", led="yellow")
            try:
                ok = self.run_gate6_bool_fn(s, self.log)
            except Exception as e:
                self.log(f"[GATE6][ERROR] slot={s}: {e}")
                ok = False

            self.results[6][s] = ok
            self._set_ui(6, s, "PASS" if ok else "FAIL", led=("green" if ok else "red"))
        self.log("[FULL] Gate6 COMPLETE for all slots ✅")

        self.log("[FULL] Finished Gate3..Gate6 across all RUPs")
        return self.results
