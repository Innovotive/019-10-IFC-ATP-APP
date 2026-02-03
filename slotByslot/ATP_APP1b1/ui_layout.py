from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QPushButton, QLabel, QTextEdit,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QFrame, QProgressBar
)

class SlotWidget(QWidget):
    def __init__(self, slot_num: int):
        super().__init__()
        self.slot = slot_num

        self.title = QLabel(f"Slot {slot_num}")
        self.title.setStyleSheet("font-weight:bold; font-size:14px;")

        self.status = QLabel("Status: Idle")
        self.gate = QLabel("Gate: ---")

        self.led = QFrame()
        self.led.setFixedSize(14, 14)
        self.set_led("gray")

        # 7 steps: Gate0..Gate6
        self.progress = QProgressBar()
        self.progress.setRange(0, 7)
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

    def set_gate(self, gate_num: int, name: str = ""):
        if gate_num == 0:
            # Gate0 is a real step: show it and set progress to 1
            self.gate.setText("Gate 0 — " + (name or "Guide Light Blink Check"))
            self.progress.setValue(1)
        elif gate_num is None:
            self.gate.setText("Gate: ---")
            self.progress.setValue(0)
        else:
            self.gate.setText(f"Gate {gate_num} — {name}")
            # Gate1..Gate6 => progress 2..7
            self.progress.setValue(gate_num + 1)


def build_ui(main_window):
    central = QWidget()
    main_window.setCentralWidget(central)
    root = QVBoxLayout(central)

    title = QLabel("RUP Acceptance Test Platform")
    title.setAlignment(Qt.AlignCenter)
    title.setStyleSheet("font-size:18px; font-weight:bold;")
    root.addWidget(title)

    instructions = QLabel(
        "Instructions:\n"
        "1) Click Start New Session\n"
        "2) Enter serial numbers for Slot 1–4 (no duplicates)\n"
        "3) Insert RUPs\n"
        "4) For each slot: confirm Guide Light blinking (Gate0)\n"
        "5) ATP runs automatically"
    )
    instructions.setWordWrap(True)
    instructions.setStyleSheet(
        "background:#222; color:white; padding:10px; border-radius:6px;"
    )
    root.addWidget(instructions)

    grid = QGridLayout()
    slot_widgets = {}

    for i in range(4):
        sw = SlotWidget(i + 1)
        slot_widgets[i + 1] = sw
        grid.addWidget(sw, i // 2, i % 2)

    root.addLayout(grid)

    btns = QHBoxLayout()
    btn_start = QPushButton("Start New Session")
    btn_stop = QPushButton("Stop")

    btns.addWidget(btn_start)
    btns.addStretch()
    btns.addWidget(btn_stop)

    root.addLayout(btns)

    log_box = QTextEdit()
    log_box.setReadOnly(True)
    log_box.setStyleSheet("font-family: monospace;")
    root.addWidget(log_box)

    return {
        "instructions": instructions,
        "slots": slot_widgets,
        "btn_start": btn_start,
        "btn_stop": btn_stop,
        "log_box": log_box,
    }
