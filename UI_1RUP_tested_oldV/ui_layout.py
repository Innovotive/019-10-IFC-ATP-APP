# ui_layout.py
"""
UI layout builder (UX only).

This file contains:
- SlotWidget (same as before)
- build_ui(main_window) -> returns a dict of created widgets

Main idea:
Your main logic code (ui_main.py) calls build_ui(self),
and then you just use the returned objects:
    self.ui["btn_start"], self.ui["slots"], self.ui["log_box"], etc.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QPushButton, QLabel, QTextEdit,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QFrame, QProgressBar
)


# ======================================================================
# SLOT WIDGET
# ======================================================================
class SlotWidget(QWidget):
    def __init__(self, slot_index: int, color: str):
        super().__init__()
        self.slot_index = slot_index
        self.color_name = color
        self.rup_id = None

        self.title = QLabel(self._make_title())
        self.title.setStyleSheet("font-weight:bold")

        self.status = QLabel("Status: Idle")
        self.gate = QLabel("Gate: ---")

        self.led = QFrame()
        self.led.setFixedSize(16, 16)
        self.set_led("gray")

        self.progress = QProgressBar()
        self.progress.setRange(0, 7)  # last gate is 7
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

    def _make_title(self) -> str:
        if self.rup_id:
            return f"Slot {self.slot_index} ({self.color_name}) — ID: {self.rup_id}"
        return f"Slot {self.slot_index} ({self.color_name})"

    def set_rup_id(self, rup_id):
        self.rup_id = rup_id
        self.title.setText(self._make_title())

    def set_led(self, color: str):
        self.led.setStyleSheet(f"background:{color}; border:1px solid black")

    def set_status(self, txt: str):
        self.status.setText(f"Status: {txt}")

    def set_gate(self, g: int):
        self.gate.setText("Gate: ---" if g == 0 else f"Gate: {g}")
        self.progress.setValue(g)


# ======================================================================
# BUILD WHOLE UX
# ======================================================================
def build_ui(main_window):
    """
    Build the whole UI into the given QMainWindow (main_window).

    Returns a dict containing references to the widgets you need.
    """
    central = QWidget()
    main_window.setCentralWidget(central)
    layout = QVBoxLayout(central)

    title = QLabel("RUP Acceptance Test Platform")
    title.setAlignment(Qt.AlignCenter)
    title.setStyleSheet("font-size:18px; font-weight:bold")
    layout.addWidget(title)

    instructions = QLabel(
        "Instructions:\n"
        "1) Click Start ATP\n"
        "2) Enter each RUP ID before inserting (IDs are not visible after insertion)\n"
        "3) Run Quick Test (must PASS) then Full ATP"
    )
    instructions.setWordWrap(True)
    instructions.setStyleSheet(
        "background:#222; color:#fff; padding:10px; border-radius:6px; font-size:14px;"
    )
    layout.addWidget(instructions)

    grid = QGridLayout()
    slots = []
    colors = ["Blue", "Orange", "Green", "Yellow"]
    for i in range(4):
        slot = SlotWidget(i + 1, colors[i])
        slots.append(slot)
        grid.addWidget(slot, i // 2, i % 2)
    layout.addLayout(grid)

    btns = QHBoxLayout()
    btn_start = QPushButton("Start ATP")
    btn_quick = QPushButton("Quick Test")
    btn_full = QPushButton("Full ATP")
    btn_replace = QPushButton("Replace Failed RUP(s)")
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
        "slots": slots,
        "btn_start": btn_start,
        "btn_quick": btn_quick,
        "btn_full": btn_full,
        "btn_replace": btn_replace,
        "btn_stop": btn_stop,
        "log_box": log_box,
    }
