# ui_layout.py
"""
UI layout builder (UX only) — SINGLE RUP ONLY.

- One SlotWidget only
- Progress range is 0..6 (because Gate3 removed and gates re-numbered)
- SlotWidget.set_gate(g, name) shows: "Gate: 3 — <name>"
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QPushButton, QLabel, QTextEdit,
    QVBoxLayout, QHBoxLayout,
    QFrame, QProgressBar
)


class SlotWidget(QWidget):
    def __init__(self, slot_index: int, color: str):
        super().__init__()
        self.slot_index = slot_index
        self.color_name = color

        self.title = QLabel(f"RUP (Slot {self.slot_index}) — {self.color_name}")
        self.title.setStyleSheet("font-weight:bold")

        self.status = QLabel("Status: Idle")
        self.gate = QLabel("Gate: ---")

        self.led = QFrame()
        self.led.setFixedSize(16, 16)
        self.set_led("gray")

        self.progress = QProgressBar()
        self.progress.setRange(0, 6)   # ✅ now only 6 gates
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

    def set_led(self, color: str):
        self.led.setStyleSheet(f"background:{color}; border:1px solid black")

    def set_status(self, txt: str):
        self.status.setText(f"Status: {txt}")

    def set_gate(self, g: int, name: str = ""):
        if g == 0:
            self.gate.setText("Gate: ---")
            self.progress.setValue(0)
            return

        if name:
            self.gate.setText(f"Gate: {g} — {name}")
        else:
            self.gate.setText(f"Gate: {g}")

        self.progress.setValue(g)


def build_ui(main_window):
    central = QWidget()
    main_window.setCentralWidget(central)
    layout = QVBoxLayout(central)

    title = QLabel("RUP Acceptance Test Platform — 1 RUP")
    title.setAlignment(Qt.AlignCenter)
    title.setStyleSheet("font-size:18px; font-weight:bold")
    layout.addWidget(title)

    instructions = QLabel(
        "Instructions:\n"
        "1) Insert RUP in Slot 1\n"
        "2) Click Quick Test (Gate 1-2)\n"
        "3) If PASS, click Full ATP (Gate 3-6)"
    )
    instructions.setWordWrap(True)
    instructions.setStyleSheet(
        "background:#222; color:#fff; padding:10px; border-radius:6px; font-size:14px;"
    )
    layout.addWidget(instructions)

    slot = SlotWidget(1, "Blue")
    layout.addWidget(slot)

    btns = QHBoxLayout()
    btn_start = QPushButton("Start New Session")
    btn_quick = QPushButton("Quick Test")
    btn_full = QPushButton("Full ATP")
    btn_replace = QPushButton("Replace RUP")
    btn_stop = QPushButton("Stop")

    btns.addWidget(btn_start)
    btns.addWidget(btn_quick)
    btns.addWidget(btn_full)
    btns.addWidget(btn_replace)
    btns.addWidget(btn_stop)
    layout.addLayout(btns)

    log_box = QTextEdit()
    log_box.setReadOnly(True)
    log_box.setStyleSheet("font-family: monospace")
    layout.addWidget(log_box)

    return {
        "title": title,
        "instructions": instructions,
        "slot": slot,
        "btn_start": btn_start,
        "btn_quick": btn_quick,
        "btn_full": btn_full,
        "btn_replace": btn_replace,
        "btn_stop": btn_stop,
        "log_box": log_box,
    }
