# ui/worker_1rup.py
from PyQt5.QtCore import QThread, pyqtSignal
import time

from tests.power_PT.relay import idcfg_on, idcfg_off, power_on, power_off, relay_close
from tests.gates.gate1_can_check import run_gate1_can_check
from tests.gates.gate2_tr_check import run_gate2_termination_check
from tests.gates.gate3_id_flip_check import run_gate3_id_flip_check
from tests.gates.gate4_pdo_check import run_gate4_pdo_check


class ATPWorker1RUP(QThread):
    log_sig = pyqtSignal(str)
    gate_sig = pyqtSignal(int, str)   # (gate_number, status) status: RUNNING/PASS/FAIL
    done_sig = pyqtSignal(bool)       # overall pass/fail

    def __init__(self, serial_number: str, expected_on: set, expected_off: set, parent=None):
        super().__init__(parent)
        self.sn = serial_number
        self.expected_on = expected_on
        self.expected_off = expected_off

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log_sig.emit(f"[{ts}] {msg}")

    def set_gate(self, gate_n: int, status: str):
        self.gate_sig.emit(gate_n, status)

    def run(self):
        overall_pass = False

        try:
            # ---------- STEP: set config + power ----------
            self.log(f"SN={self.sn}")
            self.log("[HW] IDCFG ON (GPIO8)")
            idcfg_on()
            time.sleep(0.3)

            self.log("[HW] POWER ON (GPIO25)")
            power_on()
            time.sleep(1.0)

            # ---------- GATE 1: CAN ----------
            self.set_gate(1, "RUNNING")
            ok = run_gate1_can_check(expected_values=self.expected_on, log_cb=self.log)
            self.set_gate(1, "PASS" if ok else "FAIL")
            if not ok:
                self.done_sig.emit(False)
                return

            # ---------- GATE 2: TR ----------
            self.set_gate(2, "RUNNING")
            ok = run_gate2_termination_check(log_cb=self.log)
            self.set_gate(2, "PASS" if ok else "FAIL")
            if not ok:
                self.done_sig.emit(False)
                return

            # ---------- GATE 3: ID flip ----------
            self.set_gate(3, "RUNNING")
            ok = run_gate3_id_flip_check(expected_values_after_flip=self.expected_off, log_cb=self.log)
            self.set_gate(3, "PASS" if ok else "FAIL")
            if not ok:
                self.done_sig.emit(False)
                return

            # ---------- GATE 4: PDO ----------
            self.set_gate(4, "RUNNING")
            ok = run_gate4_pdo_check(log_cb=self.log)
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
            # Always power off
            try:
                self.log("[HW] POWER OFF (GPIO25)")
                power_off()
            except Exception:
                pass

            # Optional: restore idcfg baseline
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
