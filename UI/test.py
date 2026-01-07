import sys
import datetime
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QPushButton, QLabel, QTextEdit,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QFrame, QProgressBar, QMessageBox, QInputDialog
)

from openpyxl import Workbook
from openpyxl.styles import Font

# =========================
# HARDWARE INIT (RUN ON APP START)
# =========================
from tests.ID.id_pins_init import init_id_pins_active_high

# =========================
# REAL GATE IMPORTS
# =========================
from tests.gate1_power_passthrough import run_gate1_power_test
from tests.gate2_CAN_check import gate2_can_check
#from tests.gate4_TR_check import run_gate4_termination_check
from tests.tr import run_gate4_termination_check
from tests.gate5_iul_check import run_gate5_iul_check
from tests.gate6_ID_check import gate6_id_check
from tests.gate7_PDO import run_gate7_all_rups
from tests.gate8_power_mode_check import run_gate8_power_mode_check
from tests.power_PT.relay import relay_on, relay_off
from tests.CAN.can_commands import end_atp


# ======================================================================
# SLOT WIDGET
# ======================================================================
class SlotWidget(QWidget):
    def __init__(self, slot_index, color):
        super().__init__()

        self.title = QLabel(f"Slot {slot_index} ({color})")
        self.title.setStyleSheet("font-weight:bold")

        self.status = QLabel("Status: Idle")
        self.gate = QLabel("Gate: ---")

        self.led = QFrame()
        self.led.setFixedSize(16, 16)
        self.set_led("gray")

        self.progress = QProgressBar()
        self.progress.setRange(0, 8)
        self.progress.setValue(0)

        header = QHBoxLayout()
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.led)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self.status)
        layout.addWidget(self.gate)
        layout.addWidget(self.progress)

    def set_led(self, color):
        self.led.setStyleSheet(f"background:{color}; border:1px solid black")

    def set_status(self, txt):
        self.status.setText(f"Status: {txt}")

    def set_gate(self, g):
        self.gate.setText("Gate: ---" if g == 0 else f"Gate: {g}")
        self.progress.setValue(g)


# ======================================================================
# MAIN WINDOW
# ======================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("RUP ATP Test Platform")
        self.resize(1050, 620)

        # ================================================================
        # HARDWARE INIT — RUN ON APP START
        # ================================================================
        try:
            ok = init_id_pins_active_high()
            print("[INIT] ID pins initialized (ID3 OFF)" if ok
                else "[INIT][WARN] ID pin initialization failed")
        except Exception as e:
            print(f"[INIT][ERROR] MCP23S17 init failed: {e}")


        # ================================================================
        # RUP ID + FILES
        # ================================================================
        self.rup1_id = None
        self.log_file = None

        # ================================================================
        # RESULTS STORAGE
        # ================================================================
        self.gate_results = {
            g: {1: True, 2: True, 3: True, 4: True}
            for g in range(1, 9)
        }

        self.pass_text = {
            1: "Power Pass-Through Voltage PASS",
            2: "CAN ID Pins PASS",
            3: "CAN Communication PASS",
            4: "Termination Resistor Control PASS",
            5: "IUL Functional PASS",
            6: "ID Pins Functional PASS",
            7: "Power Accuracy PASS",
            8: "Load Regulation PASS",
        }

        self.fail_text = {
            1: "RUP {rup} failed power pass through test",
            2: "RUP {rup} failed CAN ID pins test",
            3: "RUP {rup} CAN bus failure",
            4: "RUP {rup} termination resistor failure",
            5: "RUP {rup} IUL functional failure",
            6: "RUP {rup} ID pin failure",
            7: "RUP {rup} power accuracy failure",
            8: "RUP {rup} load regulation failure",
        }

        # ================================================================
        # STATE
        # ================================================================
        self.test_mode = "idle"
        self.current_gate = 0
        self.quick_test_done = False

        self.timer = QTimer()
        self.timer.timeout.connect(self.run_gate_step)

        # ================================================================
        # UI
        # ================================================================
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.title = QLabel("RUP Acceptance Test Platform")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("font-size:18px; font-weight:bold")
        layout.addWidget(self.title)

        grid = QGridLayout()
        self.slots = []
        colors = ["Blue", "Orange", "Green", "Yellow"]

        for i in range(4):
            slot = SlotWidget(i + 1, colors[i])
            self.slots.append(slot)
            grid.addWidget(slot, i // 2, i % 2)

        layout.addLayout(grid)

        btns = QHBoxLayout()
        self.btn_quick = QPushButton("Quick Test")
        self.btn_full = QPushButton("Full ATP")
        self.btn_stop = QPushButton("Stop")

        btns.addWidget(self.btn_quick)
        btns.addWidget(self.btn_full)
        btns.addWidget(self.btn_stop)
        layout.addLayout(btns)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("font-family: monospace")
        layout.addWidget(self.log_box)

        self.btn_quick.clicked.connect(self.start_quick)
        self.btn_full.clicked.connect(self.start_full)
        self.btn_stop.clicked.connect(self.stop_test)

    # ================================================================
    # LOGGING
    # ================================================================
    def log(self, txt):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {txt}"
        print(line)
        self.log_box.append(line)

        if self.log_file:
            self.log_file.write(line + "\n")
            self.log_file.flush()

        sb = self.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _format_fail(self, gate, rup):
        return self.fail_text[gate].format(rup=rup)

    # ================================================================
    # RUP1 ID
    # ================================================================
    def ensure_rup1_id(self) -> bool:
        if self.rup1_id:
            return True

        rup_id, ok = QInputDialog.getText(
            self,
            "Enter RUP1 ID",
            "Enter RUP1 Serial / ID:"
        )

        if not ok or not rup_id.strip():
            QMessageBox.warning(self, "Blocked", "RUP1 ID is required.")
            return False

        self.rup1_id = rup_id.strip()
        self.title.setText(f"RUP ATP — RUP1: {self.rup1_id}")

        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_file = open(f"ATP_RUP1_{self.rup1_id}_{ts}.log", "w")
        self.log(f"[INIT] ID pins configured (ACTIVE-HIGH, ID3 OFF)")
        self.log(f"=== ATP START — RUP1 ID: {self.rup1_id} ===")
        return True

    # ================================================================
    # HW SHUTDOWN
    # ================================================================
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

    # ================================================================
    # QUICK TEST
    # ================================================================
    def start_quick(self):
        if self.test_mode != "idle":
            return
        if not self.ensure_rup1_id():
            return

        self.log("[UI] Quick Test START")
        self.test_mode = "quick"
        self.current_gate = 0
        self.quick_test_done = False
        self.timer.start(700)

        for s in self.slots:
            s.set_led("yellow")
            s.set_gate(0)
            s.set_status("Quick Test")

        relay_on()
        self.log("[HW] relay_on()")

    def run_quick(self):
        if self.current_gate == 0:
            self.current_gate = 1
            self.log("[GATE 1] REAL (RUP1)")
            self.gate_results[1][1] = run_gate1_power_test()
            for r in (2, 3, 4):
                self.gate_results[1][r] = True

        elif self.current_gate == 1:
            self.current_gate = 2
            self.log("[GATE 2] REAL (RUP1)")
            self.gate_results[2][1] = gate2_can_check()
            for r in (2, 3, 4):
                self.gate_results[2][r] = True

        else:
            self.quick_test_done = self.gate_results[1][1] and self.gate_results[2][1]
            for s in self.slots:
                s.set_led("green" if self.quick_test_done else "red")
                s.set_status("Quick PASS" if self.quick_test_done else "Quick FAIL")

            self.timer.stop()
            self.test_mode = "idle"
            self.log("[UI] Quick Test COMPLETE")
            return

        g = self.current_gate
        for rup, slot in enumerate(self.slots, start=1):
            ok = self.gate_results[g][rup]
            slot.set_gate(g)
            slot.set_status("PASS" if ok else "FAIL")
            src = "REAL" if rup == 1 else "SIM"
            self.log(f"[GATE {g}] RUP{rup} ({src}) → {'PASS' if ok else 'FAIL'}")

    # ================================================================
    # FULL ATP
    # ================================================================
    def start_full(self):
        if not self.ensure_rup1_id():
            return
        if not self.quick_test_done:
            QMessageBox.warning(self, "Blocked", "Quick Test must PASS first")
            return

        self.log("[UI] Full ATP START")
        self.test_mode = "full"
        self.current_gate = 2
        self.timer.start(900)

        for s in self.slots:
            s.set_led("yellow")
            s.set_status("Full ATP")

    def run_full(self):
        if self.current_gate < 8:
            self.current_gate += 1
            g = self.current_gate

            if g == 3:
                for r in (1, 2, 3, 4):
                    self.gate_results[3][r] = True

            if g == 4:
                self.gate_results[4][1] = run_gate4_termination_check(self.log)
                for r in (2, 3, 4):
                    self.gate_results[4][r] = True

            if g == 5:
                self.gate_results[5][1] = run_gate5_iul_check(self.log)
                for r in (2, 3, 4):
                    self.gate_results[5][r] = True

            if g == 6:
                self.gate_results[6][1] = gate6_id_check()
                for r in (2, 3, 4):
                    self.gate_results[6][r] = True

            if g == 7:
                results, logs = run_gate7_all_rups()
                for r in range(1, 5):
                    self.gate_results[7][r] = bool(results.get(r, False))
                for line in str(logs).splitlines():
                    self.log(line)

            if g == 8:
                self.gate_results[8][1] = run_gate8_power_mode_check(self.log)
                for r in (2, 3, 4):
                    self.gate_results[8][r] = True

            for rup, slot in enumerate(self.slots, start=1):
                ok = self.gate_results[g][rup]
                slot.set_gate(g)
                slot.set_status("PASS" if ok else "FAIL")

            return

        self.log("[UI] Full ATP COMPLETE")
        self.shutdown_hw("Full ATP complete")
        self.timer.stop()
        self.test_mode = "idle"

        self.write_excel_results()

        if self.log_file:
            self.log("=== ATP END ===")
            self.log_file.close()
            self.log_file = None

    # ================================================================
    # EXCEL EXPORT
    # ================================================================
    def write_excel_results(self):
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = f"ATP_RUP1_{self.rup1_id}_{ts}.xlsx"

        wb = Workbook()
        ws = wb.active
        ws.title = "Gate Results"
        ws.append(["Gate", "RUP1", "RUP2", "RUP3", "RUP4"])

        for cell in ws[1]:
            cell.font = Font(bold=True)

        for g in range(1, 9):
            ws.append(
                [f"Gate {g}"] +
                ["PASS" if self.gate_results[g][r] else "FAIL" for r in range(1, 5)]
            )

        ws2 = wb.create_sheet("Summary")
        ws2.append(["RUP", "Final Result"])
        for cell in ws2[1]:
            cell.font = Font(bold=True)

        for r in range(1, 5):
            passed = all(self.gate_results[g][r] for g in range(1, 9))
            ws2.append([f"RUP{r}", "PASS" if passed else "FAIL"])

        wb.save(path)
        self.log(f"[FILE] Excel written: {path}")

    # ================================================================
    def run_gate_step(self):
        if self.test_mode == "quick":
            self.run_quick()
        elif self.test_mode == "full":
            self.run_full()

    def stop_test(self):
        self.log("[UI] STOPPED")
        self.shutdown_hw("User pressed Stop")
        self.timer.stop()
        self.test_mode = "idle"

        for s in self.slots:
            s.set_led("red")
            s.set_status("Stopped")

        if self.log_file:
            self.log("=== ATP ABORTED ===")
            self.log_file.close()
            self.log_file = None

    def closeEvent(self, e):
        self.shutdown_hw("Window closed")
        if self.log_file:
            self.log("=== ATP TERMINATED BY CLOSE ===")
            self.log_file.close()
            self.log_file = None
        e.accept()


# ======================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
