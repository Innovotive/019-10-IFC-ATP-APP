#!/usr/bin/env python3
# test.py — 1-RUP ATP UI Launcher (uses ATPWorker1RUP, runs all gates)

import sys
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QMessageBox
)
from PyQt5.QtCore import Qt

from worker_1rup import ATPWorker1RUP


# ============================
# EDIT THESE EXPECTED VALUES
# ============================
EXPECTED_IDCFG_ON  = {0x00}   # when GPIO8 relay is ON (initial config)
EXPECTED_IDCFG_OFF = {0x01}   # when GPIO8 relay is OFF (flipped config)


class MainWindow1RUP(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ATP 1-RUP")
        self.worker = None

        # --- Top controls ---
        self.sn_edit = QLineEdit()
        self.sn_edit.setPlaceholderText("Enter RUP Serial Number...")
        self.start_btn = QPushButton("Start ATP (1-RUP)")
        self.start_btn.clicked.connect(self.on_start)

        top = QHBoxLayout()
        top.addWidget(QLabel("SN:"))
        top.addWidget(self.sn_edit)
        top.addWidget(self.start_btn)

        # --- Gate status labels ---
        self.gate_labels = {
            1: QLabel("Gate 1 (CAN): IDLE"),
            2: QLabel("Gate 2 (TR):  IDLE"),
            3: QLabel("Gate 3 (ID Flip): IDLE"),
            4: QLabel("Gate 4 (PDO): IDLE"),
        }
        for lbl in self.gate_labels.values():
            lbl.setAlignment(Qt.AlignLeft)

        # --- Log box ---
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

        # --- Layout ---
        root = QVBoxLayout()
        root.addLayout(top)
        root.addSpacing(6)
        for i in (1, 2, 3, 4):
            root.addWidget(self.gate_labels[i])
        root.addSpacing(8)
        root.addWidget(QLabel("Logs:"))
        root.addWidget(self.log_box)

        self.setLayout(root)
        self.resize(900, 550)

    # -------------------------
    # UI helpers
    # -------------------------
    def append_log(self, msg: str):
        self.log_box.append(msg)

    def set_gate_status(self, gate_n: int, status: str):
        # status is RUNNING / PASS / FAIL
        name_map = {
            1: "Gate 1 (CAN)",
            2: "Gate 2 (TR)",
            3: "Gate 3 (ID Flip)",
            4: "Gate 4 (PDO)",
        }
        name = name_map.get(gate_n, f"Gate {gate_n}")

        self.gate_labels[gate_n].setText(f"{name}: {status}")

        # Optional: add simple visual emphasis
        if status == "RUNNING":
            self.gate_labels[gate_n].setStyleSheet("font-weight: 600;")
        elif status == "PASS":
            self.gate_labels[gate_n].setStyleSheet("font-weight: 600;")
        elif status == "FAIL":
            self.gate_labels[gate_n].setStyleSheet("font-weight: 600;")

    def set_ui_running(self, running: bool):
        self.start_btn.setEnabled(not running)
        self.sn_edit.setEnabled(not running)

    # -------------------------
    # Worker callbacks
    # -------------------------
    def on_done(self, ok: bool):
        self.set_ui_running(False)

        if ok:
            QMessageBox.information(self, "ATP Result", "✅ PASS")
        else:
            QMessageBox.warning(self, "ATP Result", "❌ FAIL")

        # Keep worker object (or drop it)
        self.worker = None

    # -------------------------
    # Start test
    # -------------------------
    def on_start(self):
        sn = self.sn_edit.text().strip()
        if not sn:
            QMessageBox.warning(self, "Missing Serial Number", "Please enter a serial number.")
            return

        # Reset UI
        self.log_box.clear()
        self.gate_labels[1].setText("Gate 1 (CAN): IDLE")
        self.gate_labels[2].setText("Gate 2 (TR):  IDLE")
        self.gate_labels[3].setText("Gate 3 (ID Flip): IDLE")
        self.gate_labels[4].setText("Gate 4 (PDO): IDLE")
        for i in (1, 2, 3, 4):
            self.gate_labels[i].setStyleSheet("")

        self.set_ui_running(True)

        # Create + start worker
        self.worker = ATPWorker1RUP(
            serial_number=sn,
            expected_on=EXPECTED_IDCFG_ON,
            expected_off=EXPECTED_IDCFG_OFF,
        )
        self.worker.log_sig.connect(self.append_log)
        self.worker.gate_sig.connect(self.set_gate_status)
        self.worker.done_sig.connect(self.on_done)

        # A little header log
        ts = time.strftime("%H:%M:%S")
        self.append_log(f"[{ts}] UI START | SN={sn}")

        self.worker.start()


def main():
    app = QApplication(sys.argv)
    win = MainWindow1RUP()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
