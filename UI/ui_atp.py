# ui_atp.py
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QLabel, QTextEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QGridLayout, QFrame, QProgressBar
)

# ======================================================================
# SLOT WIDGET (UI ONLY)
# ======================================================================
class SlotWidget(QWidget):
    def __init__(self, slot_index, color):
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

    def _make_title(self):
        if self.rup_id:
            return f"Slot {self.slot_index} ({self.color_name}) — ID: {self.rup_id}"
        return f"Slot {self.slot_index} ({self.color_name})"

    # ---- UI update helpers (still UI-side) ----
    def set_rup_id(self, rup_id):
        self.rup_id = rup_id
        self.title.setText(self._make_title())

    def set_led(self, color):
        self.led.setStyleSheet(f"background:{color}; border:1px solid black")

    def set_status(self, txt):
        self.status.setText(f"Status: {txt}")

    def set_gate(self, g):
        self.gate.setText("Gate: ---" if g == 0 else f"Gate: {g}")
        self.progress.setValue(g)


# ======================================================================
# UI BUILDER (ALL LAYOUT / UX HERE)
# ======================================================================
class Ui_MainWindow:
    """
    Qt Designer-style UI class:
    - setupUi(main_window) builds all widgets/layouts
    - exposes widget refs as self.btn_start, self.log_box, self.slots, etc.
    """
    def setupUi(self, main_window):
        main_window.setWindowTitle("RUP ATP Test Platform")
        main_window.resize(1050, 720)

        self.central = QWidget()
        main_window.setCentralWidget(self.central)
        layout = QVBoxLayout(self.central)

        self.title = QLabel("RUP Acceptance Test Platform")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("font-size:18px; font-weight:bold")
        layout.addWidget(self.title)

        self.instructions = QLabel(
            "Instructions:\n"
            "1) Click Start ATP\n"
            "2) Enter each RUP ID before inserting (IDs are not visible after insertion)\n"
            "3) Run Quick Test (must PASS) then Full ATP"
        )
        self.instructions.setWordWrap(True)
        self.instructions.setStyleSheet(
            "background:#222; color:#fff; padding:10px; border-radius:6px; font-size:14px;"
        )
        layout.addWidget(self.instructions)

        grid = QGridLayout()
        self.slots = []
        colors = ["Blue", "Orange", "Green", "Yellow"]
        for i in range(4):
            slot = SlotWidget(i + 1, colors[i])
            self.slots.append(slot)
            grid.addWidget(slot, i // 2, i % 2)
        layout.addLayout(grid)

        btns = QHBoxLayout()
        self.btn_start = QPushButton("Start ATP")
        self.btn_quick = QPushButton("Quick Test")
        self.btn_full = QPushButton("Full ATP")
        self.btn_replace = QPushButton("Replace Failed RUP(s)")
        self.btn_stop = QPushButton("Stop")

        btns.addWidget(self.btn_start)
        btns.addWidget(self.btn_quick)
        btns.addWidget(self.btn_full)
        btns.addWidget(self.btn_replace)
        btns.addWidget(self.btn_stop)
        layout.addLayout(btns)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("font-family: monospace")
        layout.addWidget(self.log_box)
