# ui/worker_1rup.py
from PyQt5.QtCore import QThread, pyqtSignal
import time

from tests.power_PT.relay import idcfg_on, idcfg_off, power_on, power_off, relay_close

from tests.gate1_can_check import run_gate1_can_check
from tests.gate2_tr_check import run_gate2_termination_check
from tests.gate3_id_flip_check import run_gate3_id_flip_check
from tests.gate4_pd_load import run_gate4_pd_load


class ATPWorker1RUP(QThread):
    """
    1-RUP ATP worker thread
    Flow:
      - IDCFG ON (GPIO8)
      - POWER ON (GPIO25)
      - Gate1: CAN check (START_ATP + ID read) expects expected_on
      - Gate2: Termination resistor check
      - Gate3: Flip IDCFG (GPIO8 OFF) + ID read expects expected_off
      - Gate4: PDO/PM125 check
      - Always POWER OFF in finally
    """

    log_sig = pyqtSignal(str)
    gate_sig = pyqtSignal(int, str)   # (gate_number, status): IDLE/RUNNING/PASS/FAIL
    done_sig = pyqtSignal(bool)       # overall pass/fail

    def __init__(self, serial_number: str, expected_on: set, expected_off: set, parent=None):
        super().__init__(parent)
        self.sn = (serial_number or "").strip()
        self.expected_on = set(expected_on or [])
        self.expected_off = set(expected_off or [])
        self._cancel = False

    # Optional: allow UI to cancel mid-run
    def cancel(self):
        self._cancel = True

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log_sig.emit(f"[{ts}] {msg}")

    def set_gate(self, gate_n: int, status: str):
        self.gate_sig.emit(gate_n, status)

    def _check_cancel(self):
        if self._cancel:
            raise RuntimeError("Cancelled by operator")

    def run(self):
        overall_pass = False

        # Initialize gate labels as IDLE (nice if UI listens)
        for g in (1, 2, 3, 4):
            self.set_gate(g, "IDLE")

        try:
            if not self.sn:
                self.log("[ERROR] Serial number is empty")
                self.done_sig.emit(False)
                return

            self.log(f"SN={self.sn}")

            # ----------------------------
            # STEP: set ID config + power
            # ----------------------------
            self._check_cancel()
            self.log("[HW] IDCFG ON (GPIO8) -> initial config")
            idcfg_on()
            time.sleep(0.3)

            self._check_cancel()
            self.log("[HW] POWER ON (GPIO25) -> RUP ON")
            power_on()
            time.sleep(1.0)

            # ----------------------------
            # GATE 1: CAN check
            # ----------------------------
            self._check_cancel()
            self.set_gate(1, "RUNNING")
            ok = run_gate1_can_check(expected_values=self.expected_on, log_cb=self.log)
            self.set_gate(1, "PASS" if ok else "FAIL")
            if not ok:
                self.done_sig.emit(False)
                return

            # ----------------------------
            # GATE 2: Termination resistor
            # ----------------------------
            self._check_cancel()
            self.set_gate(2, "RUNNING")
            ok = run_gate2_termination_check(log_cb=self.log)
            self.set_gate(2, "PASS" if ok else "FAIL")
            if not ok:
                self.done_sig.emit(False)
                return

            # ----------------------------
            # GATE 3: ID flip check
            # (Gate function will flip GPIO8 OFF itself)
            # ----------------------------
            self._check_cancel()
            self.set_gate(3, "RUNNING")
            ok = run_gate3_id_flip_check(expected_values_after_flip=self.expected_off, log_cb=self.log)
            self.set_gate(3, "PASS" if ok else "FAIL")
            if not ok:
                self.done_sig.emit(False)
                return

            # ----------------------------
            # GATE 4: PDO check (PM125)
            # ----------------------------
            self._check_cancel()
            self.set_gate(4, "RUNNING")
            ok = run_gate4_pd_load(log_cb=self.log)
            self.set_gate(4, "PASS" if ok else "FAIL")
            if not ok:
                self.done_sig.emit(False)
                return

            overall_pass = True
            self.done_sig.emit(True)

        except Exception as e:
            self.log(f"[ERROR] Worker exception: {e}")
            self.done_sig.emit(False)

        finally:
            # Always power off + cleanup no matter what
            try:
                self.log("[HW] POWER OFF (GPIO25)")
                power_off()
            except Exception:
                pass

            # Optional baseline restore
            try:
                self.log("[HW] IDCFG ON (GPIO8) baseline")
                idcfg_on()
            except Exception:
                pass

            try:
                relay_close()
            except Exception:
                pass

            self.log(f"[END] overall={'PASS' if overall_pass else 'FAIL'}")
