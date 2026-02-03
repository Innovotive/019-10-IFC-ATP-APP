#!/usr/bin/env python3
import sys, os, datetime, traceback
from PyQt5.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool, QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox

from openpyxl import Workbook
from openpyxl.styles import Font

from ui_layout import build_ui
from tests.ID.id_pins_init import init_id_pins_active_high

# NEW numbered gate modules (your renamed files)
from tests.gate1_power_passthrough import run_gate1_power_test
from tests.gate2_CAN_check import gate2_can_check
from tests.gate3_termination_check import run_gate3_termination_check
from tests.gate4_iul_check import run_gate4_iul_check
from tests.gate5_ID_check import run_gate5_id_check
from tests.gate6_pd_load import run_gate6_pd_load

from tests.power_PT.relay import relay_off
from tests.CAN.can_commands import end_atp


GATE_NAMES = {
    1: "Power Pass-Through Voltage",
    2: "CAN-Bus Pass-Through",
    3: "CAN Termination Resistance Check",
    4: "In-Use Light Check",
    5: "ID-Pins Functional Test",
    6: "USB-C Power Delivery / Load Regulation",
}


# ----------------------------
# Worker infra (runs gate off the UI thread)
# ----------------------------
class WorkerSignals(QObject):
    started = pyqtSignal(int)                       # gate number
    finished = pyqtSignal(int, bool, str)           # gate, ok, err_str


class GateWorker(QRunnable):
    def __init__(self, gate_num: int, fn):
        super().__init__()
        self.gate_num = gate_num
        self.fn = fn
        self.signals = WorkerSignals()

    def run(self):
        self.signals.started.emit(self.gate_num)
        ok = False
        err = ""
        try:
            ok = bool(self.fn())
        except Exception:
            ok = False
            err = traceback.format_exc()
        self.signals.finished.emit(self.gate_num, ok, err)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RUP ATP — 1 RUP")
        self.resize(900, 650)

        self.ui = build_ui(self)
        self.slot = self.ui["slot"]

        # buttons
        self.ui["btn_start"].clicked.connect(self.start_new_session)
        self.ui["btn_quick"].clicked.connect(self.start_quick)
        self.ui["btn_full"].clicked.connect(self.start_full)
        self.ui["btn_replace"].clicked.connect(self.replace_rup)
        self.ui["btn_stop"].clicked.connect(self.stop_test)

        # logs
        self.logs_dir = "ATP_logs"
        os.makedirs(self.logs_dir, exist_ok=True)
        self.log_file = None
        self.session_ts = None

        # state
        self.threadpool = QThreadPool.globalInstance()
        self.running_gate = None
        self.sequence = []  # list of gate numbers to run
        self.test_mode = "idle"  # idle|quick|full
        self.quick_test_done = False
        self.quick_locked = False
        self.failed = False

        self.gate_results = {g: True for g in range(1, 7)}

        # init hw
        try:
            ok = init_id_pins_active_high()
            print("[INIT] ID pins initialized" if ok else "[INIT][WARN] ID pin init failed")
        except Exception as e:
            print(f"[INIT][ERROR] MCP23S17 init failed: {e}")

        self.auto_setup()

    # ----------------------------
    # UI + logging
    # ----------------------------
    def log(self, txt: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {txt}"
        print(line)
        self.ui["log_box"].append(line)
        if self.log_file:
            self.log_file.write(line + "\n")
            self.log_file.flush()

    def set_instruction(self, msg: str):
        self.ui["instructions"].setText(msg)

    def open_new_session_files(self):
        if self.log_file:
            try: self.log_file.close()
            except Exception: pass
            self.log_file = None

        self.session_ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_path = os.path.join(self.logs_dir, f"ATP_1RUP_{self.session_ts}.log")
        self.log_file = open(log_path, "w")
        self.log("=== ATP START — 1 RUP (Slot 1) ===")
        self.log(f"[FILE] Log created: {log_path}")

    # ----------------------------
    # Buttons state
    # ----------------------------
    def set_buttons_state(self):
        idle = (self.test_mode == "idle" and self.running_gate is None)

        self.ui["btn_start"].setEnabled(idle)
        self.ui["btn_stop"].setEnabled(True)

        self.ui["btn_quick"].setEnabled(idle and not self.quick_locked)
        self.ui["btn_full"].setEnabled(idle and self.quick_test_done)
        self.ui["btn_replace"].setEnabled(idle and self.failed and (not self.quick_test_done))

    # ----------------------------
    # Setup / session
    # ----------------------------
    def auto_setup(self):
        self.running_gate = None
        self.sequence = []
        self.test_mode = "idle"
        self.quick_test_done = False
        self.quick_locked = False
        self.failed = False
        self.gate_results = {g: True for g in range(1, 7)}

        self.slot.set_led("gray")
        self.slot.set_gate(0)
        self.slot.set_status("Ready")

        self.open_new_session_files()
        self.set_instruction("Setup auto-completed ✅\n\nNext: Click Quick Test.")
        self.log("[UI] Auto setup complete")
        self.set_buttons_state()

    def start_new_session(self):
        res = QMessageBox.question(
            self, "Start new session?",
            "This resets results and creates a new log file.\nContinue?",
            QMessageBox.Yes | QMessageBox.No
        )
        if res == QMessageBox.Yes:
            self.auto_setup()

    # ----------------------------
    # Gate function map
    # ----------------------------
    def gate_fn(self, g: int):
        if g == 1:
            return run_gate1_power_test
        if g == 2:
            return gate2_can_check
        if g == 3:
            return lambda: run_gate3_termination_check(self.log)
        if g == 4:
            return lambda: run_gate4_iul_check(self.log)
        if g == 5:
            return run_gate5_id_check
        if g == 6:
            # allow either bool return or (results, logs) return
            def _g6():
                out = run_gate6_pd_load(log_cb=self.log)
                if isinstance(out, tuple) and len(out) >= 1 and isinstance(out[0], dict):
                    results = out[0]
                    logs = out[1] if len(out) > 1 else []
                    for line in (logs or []):
                        self.log(line)
                    return bool(results.get("pass", False))
                return bool(out)
            return _g6
        raise ValueError(f"Unknown gate {g}")

    # ----------------------------
    # Sequence runner (perfect sync)
    # ----------------------------
    def start_sequence(self, mode: str, gates: list):
        if self.running_gate is not None:
            return

        self.test_mode = mode
        self.sequence = list(gates)
        self.slot.set_led("yellow")
        self.slot.set_status("Running...")

        self.set_buttons_state()
        self.run_next_gate()

    def run_next_gate(self):
        if self.running_gate is not None:
            return

        if not self.sequence:
            self.finish_sequence()
            return

        g = self.sequence.pop(0)
        self.running_gate = g

        # UI: show EXACT gate + name, and "Running..."
        self.slot.set_gate(g, GATE_NAMES[g])
        self.slot.set_status("Running...")

        self.log(f"[GATE {g}] START — {GATE_NAMES[g]}")

        worker = GateWorker(g, self.gate_fn(g))
        worker.signals.finished.connect(self.on_gate_finished)
        self.threadpool.start(worker)

    def on_gate_finished(self, g: int, ok: bool, err: str):
        # update results + UI only when the gate REALLY finished
        self.gate_results[g] = bool(ok)

        if err:
            self.log(f"[GATE {g}][ERROR]\n{err}")

        self.slot.set_status("PASS" if ok else "FAIL")
        self.log(f"[GATE {g}] DONE — {'PASS' if ok else 'FAIL'}")

        self.running_gate = None

        # small delay so the user can see PASS/FAIL before next gate flips back to Running
        QTimer.singleShot(250, self.run_next_gate)

    def finish_sequence(self):
        # called when sequence is empty
        if self.test_mode == "quick":
            self.quick_test_done = bool(self.gate_results[1] and self.gate_results[2])
            self.failed = not self.quick_test_done
            self.quick_locked = self.failed

            self.slot.set_led("green" if self.quick_test_done else "red")
            self.slot.set_status("Quick PASS" if self.quick_test_done else "Quick FAIL")

            self.log("[UI] Quick Test COMPLETE")

            if self.quick_test_done:
                self.set_instruction("Quick Test PASS ✅\n\nNext: Click Full ATP.")
            else:
                self.set_instruction(
                    "Quick Test FAIL ❌\n\nQuick Test is locked.\n"
                    "Click Replace RUP, then re-run Quick Test."
                )

        elif self.test_mode == "full":
            overall_pass = all(bool(self.gate_results[g]) for g in range(1, 7))
            self.slot.set_led("green" if overall_pass else "red")
            self.slot.set_status("FINAL PASS" if overall_pass else "FINAL FAIL")

            self.log("[UI] Full ATP COMPLETE")
            self.shutdown_hw("Full ATP complete")
            self.write_excel_results()

            if self.log_file:
                self.log("=== ATP END ===")
                try: self.log_file.close()
                except Exception: pass
                self.log_file = None

        self.test_mode = "idle"
        self.set_buttons_state()

    # ----------------------------
    # Quick / Full
    # ----------------------------
    def start_quick(self):
        if self.test_mode != "idle":
            return
        if self.quick_locked:
            QMessageBox.warning(self, "Blocked", "Quick Test is locked. Replace the RUP first.")
            return

        self.failed = False
        self.quick_test_done = False

        self.set_instruction("Quick Test running...\nDo not touch hardware.")
        self.log("[UI] Quick Test START")
        self.start_sequence("quick", [1, 2])

    def start_full(self):
        if self.test_mode != "idle":
            return
        if not self.quick_test_done:
            QMessageBox.warning(self, "Blocked", "Quick Test must PASS first.")
            return

        self.set_instruction("Full ATP running...\nDo not touch hardware.")
        self.log("[UI] Full ATP START")
        self.start_sequence("full", [3, 4, 5, 6])

    # ----------------------------
    # Replace
    # ----------------------------
    def replace_rup(self):
        if self.test_mode != "idle" or self.running_gate is not None:
            return
        if not self.failed:
            QMessageBox.information(self, "No failure", "No failed RUP to replace.")
            return

        self.log("[REWORK] Replace RUP (Slot 1)")

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Remove failed RUP")
        msg.setText("Remove the failed RUP from Slot 1.\n\nClick OK when removed.")
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        if msg.exec_() != QMessageBox.Ok:
            self.log("[REWORK] Cancelled")
            self.set_buttons_state()
            return

        ins = QMessageBox(self)
        ins.setIcon(QMessageBox.Information)
        ins.setWindowTitle("Insert new RUP")
        ins.setText("Insert NEW RUP into Slot 1.\n\nClick OK when inserted.")
        ins.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        if ins.exec_() != QMessageBox.Ok:
            self.log("[REWORK] Cancelled")
            self.set_buttons_state()
            return

        self.failed = False
        self.quick_test_done = False
        self.quick_locked = False

        self.slot.set_led("gray")
        self.slot.set_gate(0)
        self.slot.set_status("Replaced (Ready)")

        self.log("[REWORK] Replacement done — Quick Test unlocked")
        self.set_buttons_state()
        QMessageBox.information(self, "Done", "Replacement done.\nRe-run Quick Test.")

    # ----------------------------
    # Excel
    # ----------------------------
    def write_excel_results(self):
        ts = self.session_ts or datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = os.path.join(self.logs_dir, f"ATP_1RUP_{ts}.xlsx")

        wb = Workbook()
        ws = wb.active
        ws.title = "Gate Results"

        ws.append(["Gate", "Gate Name", "Result"])
        for cell in ws[1]:
            cell.font = Font(bold=True)

        for g in range(1, 7):
            ws.append([g, GATE_NAMES[g], "PASS" if bool(self.gate_results[g]) else "FAIL"])

        wb.save(path)
        self.log(f"[FILE] Excel written: {path}")

    # ----------------------------
    # Stop / shutdown
    # ----------------------------
    def shutdown_hw(self, why=""):
        if why:
            self.log(f"[HW] Shutdown: {why}")
        try:
            end_atp()
            self.log("[HW] END_ATP sent")
        except Exception as e:
            self.log(f"[HW][WARN] END_ATP failed: {e}")
        try:
            relay_off()
            self.log("[HW] relay_off()")
        except Exception as e:
            self.log(f"[HW][WARN] relay_off failed: {e}")

    def stop_test(self):
        self.log("[UI] STOPPED")
        self.shutdown_hw("User pressed Stop")

        # We cannot forcibly kill a running python function safely,
        # but we *can* stop scheduling next gates.
        self.sequence = []
        self.test_mode = "idle"
        self.quick_locked = False

        self.slot.set_led("red")
        self.slot.set_status("Stopped")
        self.set_buttons_state()

        if self.log_file:
            self.log("=== ATP ABORTED ===")
            try: self.log_file.close()
            except Exception: pass
            self.log_file = None

    def closeEvent(self, e):
        self.shutdown_hw("Window closed")
        e.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
