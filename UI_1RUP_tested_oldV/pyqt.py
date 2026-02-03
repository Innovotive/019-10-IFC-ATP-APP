import sys
import os
import csv
import subprocess
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QPushButton, QLabel, QTextEdit,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QFrame, QProgressBar, QMessageBox
)


# ======================================================================
#   SLOT UI WIDGET
# ======================================================================
class SlotWidget(QWidget):
    def __init__(self, slot_index: int, color_name: str):
        super().__init__()
        self.slot_index = slot_index

        # UI labels
        self.title_label = QLabel(f"Slot {slot_index} ({color_name})")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        self.sn_label = QLabel("SN: ---")
        self.status_label = QLabel("Status: Idle")
        self.gate_label = QLabel("Gate: ---")

        # LED indicator
        self.led = QFrame()
        self.led.setFixedSize(20, 20)
        self.led.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.set_led_color("gray")

        # Gate progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 8)
        self.progress.setValue(0)
        self.progress.setFormat("Gate %v / 8")

        # Layout structure
        header = QHBoxLayout()
        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.led)

        layout = QVBoxLayout()
        layout.addLayout(header)
        layout.addWidget(self.sn_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.gate_label)
        layout.addWidget(self.progress)

        self.setLayout(layout)
        self.setStyleSheet("""
            SlotWidget {
                border: 1px solid #444;
                border-radius: 6px;
            }
        """)

    def set_led_color(self, color):
        self.led.setStyleSheet(f"background-color: {color}; border: 1px solid black;")

    def set_status(self, text):
        self.status_label.setText(f"Status: {text}")

    def set_gate(self, gate):
        if gate == 0:
            self.gate_label.setText("Gate: ---")
        else:
            self.gate_label.setText(f"Gate: {gate}")
        self.progress.setValue(gate)



# ======================================================================
#   MAIN ATP UI
# ======================================================================
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RUP ATP Test Platform")
        self.resize(1024, 600)

        # ================================================================
        # SIMULATED PER-RUP GATE RESULTS (Replace later with real hardware)
        # ================================================================
        self.gate_results = {
            1: {1: True,  2: True,  3: True,  4: True},
            2: {1:  True,  2: True,  3: True,  4: True},

            3: {1: True,  2: False, 3: False, 4: True},
            4: {1: False, 2: False, 3: True,  4: True},
            5: {1: True,  2: True,  3: False, 4: True},
            6: {1: False, 2: True,  3: False, 4: True},
            7: {1: True,  2: True,  3: True,  4: False},
            8: {1: False, 2: False, 3: True,  4: True},
        }

        # ================================================================
        # PASS REASONS FROM ATP DOCUMENT
        # ================================================================
        self.pass_text = {
            1: "Power Pass-Through Voltage PASS",
            2: "CAN-Bus Pass-Through PASS",
            3: "CAN Communication PASS",
            4: "Termination Resistor Control PASS",
            5: "Guide Light PASS",
            6: "ID Pins Functional PASS",
            7: "Power Accuracy PASS",
            8: "Load Regulation PASS",
        }

        # ================================================================
        # FAIL REASONS FROM ATP DOCUMENT (detailed, using format placeholders)
        # ================================================================
        self.fail_text = {
            # Gate1
            1: "RUP {rup} failed power pass through test, please replace the RUP",
            # Gate2
            2: "RUP {rup} failed CAN bus pass through test, please replace the RUP",
            # Gate3
            3: "RUP {rup} CAN bus failure (no response to CAN messages)",
            # Gate4
            4: "RUP {rup} failed termination resistor CONTROL",
            # Gate5
            5: "RUP {rup} Guide light failure",
            # Gate6
            6: "RUP {rup}, ID pin {pin} fail",
            # Gate7
            7: "RUP {rup} fails the power accuracy requirement.",
            # Gate8
            8: "RUP {rup}, {watts}W fail",
        }

        # State machine
        self.test_mode = "idle"
        self.current_gate = 0
        self.quick_test_done = False

        self.timer = QTimer()
        self.timer.timeout.connect(self.run_gate_step)

        # ================================================================
        # UI BUILD
        # ================================================================
        central = QWidget()
        self.setCentralWidget(central)
        main = QVBoxLayout()
        central.setLayout(main)

        title = QLabel("RUP Acceptance Test Platform")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        main.addWidget(title)

        body = QHBoxLayout()
        main.addLayout(body, stretch=1)

        # Slot widgets
        slots = QGridLayout()
        body.addLayout(slots, stretch=3)

        self.slot_widgets = []
        colors = ["Blue", "Orange", "Green", "Yellow"]
        for i in range(4):
            w = SlotWidget(i + 1, colors[i])
            self.slot_widgets.append(w)
            slots.addWidget(w, i // 2, i % 2)

        # Controls
        controls = QVBoxLayout()
        body.addLayout(controls, stretch=1)

        self.btn_quick = QPushButton("Quick Pass-Through Test")
        self.btn_full  = QPushButton("Full ATP")
        self.btn_stop  = QPushButton("Stop")
        self.btn_exit  = QPushButton("Exit")

        for b in (self.btn_quick, self.btn_full, self.btn_stop, self.btn_exit):
            b.setMinimumHeight(40)

        controls.addWidget(self.btn_quick)
        controls.addWidget(self.btn_full)
        controls.addWidget(self.btn_stop)
        controls.addStretch()
        controls.addWidget(self.btn_exit)

        self.btn_quick.clicked.connect(self.start_quick_test)
        self.btn_full.clicked.connect(self.start_full_atp)
        self.btn_stop.clicked.connect(self.stop_test)
        self.btn_exit.clicked.connect(self.close)

        # Log view
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("font-family: monospace;")
        main.addWidget(self.log_box, stretch=1)

        self.statusBar().showMessage("Ready")
        self.update_buttons()

    # ==================================================================
    # UTILITIES
    # ==================================================================
    def log(self, msg):
        self.log_box.append(msg)
        sb = self.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    def update_buttons(self):
        if self.test_mode == "idle":
            self.btn_quick.setEnabled(True)
            self.btn_full.setEnabled(self.quick_test_done)
            self.btn_stop.setEnabled(False)
        else:
            self.btn_quick.setEnabled(False)
            self.btn_full.setEnabled(False)
            self.btn_stop.setEnabled(True)

    def _format_fail_msg(self, gate, rup):
        """Helper to format fail messages with rup/pin/watts."""
        # Default placeholders
        pin = "x"
        watts = "x"
        template = self.fail_text[gate]
        return template.format(rup=rup, pin=pin, watts=watts)

    # ==================================================================
    # QUICK TEST — GATES 1 & 2
    # ==================================================================
    def start_quick_test(self):
        if self.test_mode != "idle":
            return

        self.log("[SIM] Quick Test started.")
        self.test_mode = "quick"
        self.current_gate = 0
        self.quick_test_done = False

        for s in self.slot_widgets:
            s.set_status("Running Quick Test…")
            s.set_led_color("yellow")
            s.set_gate(0)

        self.timer.start(800)
        self.update_buttons()

    def _quick_step(self):

        # ---------------- GATE 1 ----------------
        if self.current_gate == 0:
            self.current_gate = 1

            for rup, slot in enumerate(self.slot_widgets, start=1):
                ok = self.gate_results[1][rup]
                slot.set_gate(1)
                slot.set_status("GATE 1 PASS" if ok else "GATE 1 FAIL")

                if not ok:
                    slot.set_led_color("red")

                if ok:
                    msg = self.pass_text[1]
                else:
                    msg = self._format_fail_msg(1, rup)
                self.log(f"[GATE 1] Slot {rup} — {msg}")

        # ---------------- GATE 2 ----------------
        elif self.current_gate == 1:
            self.current_gate = 2

            for rup, slot in enumerate(self.slot_widgets, start=1):
                ok = self.gate_results[2][rup]
                slot.set_gate(2)
                slot.set_status("GATE 2 PASS" if ok else "GATE 2 FAIL")

                if not ok:
                    slot.set_led_color("red")

                if ok:
                    msg = self.pass_text[2]
                else:
                    msg = self._format_fail_msg(2, rup)
                self.log(f"[GATE 2] Slot {rup} — {msg}")

            # Quick pass?
            passed = all(self.gate_results[1][r] and self.gate_results[2][r] for r in range(1, 5))
            self.quick_test_done = passed

            if passed:
                for s in self.slot_widgets:
                    s.set_led_color("green")
                    s.set_status("Quick PASS")
                self.log("[SIM] Quick Test complete. PASS")
            else:
                for s in self.slot_widgets:
                    s.set_led_color("red")
                    s.set_status("Quick FAIL")

                # List which RUPs failed Gate1 or Gate2
                failed_rups = []
                for rup in range(1, 5):
                    if not (self.gate_results[1][rup] and self.gate_results[2][rup]):
                        failed_rups.append(rup)

                self.log("[SIM] Quick Test complete. FAIL")
                if failed_rups:
                    lines = ["One or more RUPs failed Gates 1 & 2.",
                             "Replace the failed RUP(s) and repeat Gates 1 and 2.",
                             ""]
                    for rup in failed_rups:
                        lines.append(f"RUP {rup} failed. Replace the RUP and press OK to repeat Gates 1 & 2.")

                    QMessageBox.information(
                        self,
                        "Quick Test Failed",
                        "\n".join(lines)
                    )

            self.test_mode = "idle"
            self.timer.stop()
            self.update_buttons()

    # ==================================================================
    # FULL ATP — GATES 3–8
    # ==================================================================
    def start_full_atp(self):
        if not self.quick_test_done:
            QMessageBox.warning(self, "Quick Test Required", "Quick Test must PASS first.")
            return

        if self.test_mode != "idle":
            return

        self.log("[SIM] Full ATP started.")
        self.test_mode = "full"
        self.current_gate = 2  # next is gate 3

        for s in self.slot_widgets:
            s.set_status("Running Full ATP…")
            s.set_led_color("yellow")

        self.timer.start(800)
        self.update_buttons()

    def _full_step(self):

        # Run gates 3 → 8
        if self.current_gate < 8:
            self.current_gate += 1
            g = self.current_gate

            for rup, slot in enumerate(self.slot_widgets, start=1):
                ok = self.gate_results[g][rup]
                slot.set_gate(g)
                slot.set_status(f"GATE {g} PASS" if ok else f"GATE {g} FAIL")

                if ok:
                    msg = self.pass_text[g]
                else:
                    msg = self._format_fail_msg(g, rup)

                # Leave LED yellow during running tests
                self.log(f"[GATE {g}] Slot {rup} — {msg}")

        # Final evaluation
        else:
            for rup, slot in enumerate(self.slot_widgets, start=1):
                passed = all(self.gate_results[g][rup] for g in range(1, 9))
                slot.set_led_color("green" if passed else "red")
                slot.set_status("FULL ATP PASS" if passed else "FULL ATP FAIL")

            self.log("[SIM] Full ATP complete.")
            self.statusBar().showMessage("Full ATP complete")

            self.timer.stop()
            self.test_mode = "idle"
            self.update_buttons()

            # Save detailed CSV with reasons
            self.save_csv_summary()

    # ==================================================================
    # CSV EXPORT WITH DETAILED REASONS
    # ==================================================================
    def save_csv_summary(self):
        """Create a single CSV with PASS/FAIL + detailed reasons."""
        if not os.path.exists("logs"):
            os.makedirs("logs")

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fname = f"logs/ATP_{timestamp}.csv"

        with open(fname, "w", newline="") as f:
            writer = csv.writer(f)

            header = ["RUP"] + [f"Gate {g}" for g in range(1, 9)] + ["Final Result"]
            writer.writerow(header)

            for rup in range(1, 5):
                row = [f"RUP {rup}"]

                for g in range(1, 9):
                    ok = self.gate_results[g][rup]
                    if ok:
                        row.append(f"PASS ({self.pass_text[g]})")
                    else:
                        fail_msg = self._format_fail_msg(g, rup)
                        row.append(f"FAIL ({fail_msg})")

                final_pass = all(self.gate_results[g][rup] for g in range(1, 9))
                row.append("PASS" if final_pass else "FAIL")

                writer.writerow(row)

        self.log(f"[CSV] Saved results to {fname}")

        # Auto-open LibreOffice Calc
        try:
            subprocess.Popen(["libreoffice", "--calc", fname])
            self.log("[UI] Opening LibreOffice Calc…")
        except Exception as e:
            self.log(f"[ERROR] Cannot open LibreOffice: {e}")

    # ==================================================================
    # STOP + EXIT
    # ==================================================================
    def run_gate_step(self):
        if self.test_mode == "quick":
            self._quick_step()
        elif self.test_mode == "full":
            self._full_step()

    def stop_test(self):
        if self.test_mode == "idle":
            return

        self.timer.stop()
        for s in self.slot_widgets:
            s.set_status("Stopped")
            s.set_led_color("red")

        self.test_mode = "idle"
        self.update_buttons()
        self.log("[UI] Test stopped by user.")

    def closeEvent(self, e):
        if self.test_mode != "idle":
            btn = QMessageBox.question(
                self, "Exit", "A test is running. Stop it?",
                QMessageBox.Yes | QMessageBox.No
            )
            if btn != QMessageBox.Yes:
                e.ignore()
                return
        e.accept()



# ======================================================================
#   RUN PROGRAM
# ======================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
