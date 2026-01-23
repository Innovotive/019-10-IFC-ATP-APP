#!/usr/bin/env python3
import sys
import os
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
from UI.tests.gate3_TR import run_gate4_termination_check
from UI.tests.gate4_iul_check import run_gate5_iul_check
from UI.tests.gate5_ID_check import gate6_id_check
from UI.tests.gate6_pdo import run_gate7

from tests.power_PT.relay import relay_on, relay_off
from tests.CAN.can_commands import end_atp


# ======================================================================
# SLOT WIDGET
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
# MAIN WINDOW
# ======================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("RUP ATP Test Platform")
        self.resize(1050, 720)

        self.logs_dir = "ATP_logs"
        os.makedirs(self.logs_dir, exist_ok=True)

        # ================================================================
        # HARDWARE INIT
        # ================================================================
        try:
            ok = init_id_pins_active_high()
            print(
                "[INIT] ID pins initialized (ID3 OFF)"
                if ok else "[INIT][WARN] ID pin initialization failed"
            )
        except Exception as e:
            print(f"[INIT][ERROR] MCP23S17 init failed: {e}")

        # ================================================================
        # IDs + FILES
        # ================================================================
        self.rup_ids = {1: None, 2: None, 3: None, 4: None}
        self.setup_complete = False
        self.setup_in_progress = False
        self.setup_locked = False  # Start ATP locked after setup

        self.log_file = None
        self.session_ts = None

        # Track failed slots (replacement flow)
        self.failed_slots = []

        # lock Quick Test when a failure exists until replacement is done
        self.quick_locked = False

        # ================================================================
        # RESULTS STORAGE
        # ================================================================
        # Gates are 1..7 (NO GATE8)
        self.gate_results = {g: {1: True, 2: True, 3: True, 4: True} for g in range(1, 8)}

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

        self.btn_start.clicked.connect(self.start_atp_setup)
        self.btn_quick.clicked.connect(self.start_quick)
        self.btn_full.clicked.connect(self.start_full)
        self.btn_replace.clicked.connect(self.replace_failed_rups)
        self.btn_stop.clicked.connect(self.stop_test)

        self.set_buttons_state()

    # ================================================================
    def set_instruction(self, msg: str):
        self.instructions.setText(msg)

    def log(self, txt: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {txt}"
        print(line)
        self.log_box.append(line)
        if self.log_file:
            self.log_file.write(line + "\n")
            self.log_file.flush()
        sb = self.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    def open_new_session_files(self):
        if self.log_file:
            try:
                self.log_file.close()
            except Exception:
                pass
            self.log_file = None

        self.session_ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        ids_str = "_".join([(self.rup_ids[i] or "NA") for i in range(1, 5)])
        log_path = os.path.join(self.logs_dir, f"ATP_{ids_str}_{self.session_ts}.log")
        self.log_file = open(log_path, "w")

        self.log("[INIT] ID pins configured (ACTIVE-HIGH, ID3 OFF)")
        self.log(f"=== ATP START — IDs: {self.rup_ids} ===")
        self.log(f"[FILE] Log created: {log_path}")

    def update_title_with_ids(self):
        ids_str = ", ".join([f"S{i}:{self.rup_ids[i] or '---'}" for i in range(1, 5)])
        self.title.setText(f"RUP ATP — {ids_str}")

    # ================================================================
    # BUTTON STATES
    # ================================================================
    def set_buttons_state(self):
        idle = (self.test_mode == "idle")

        self.btn_stop.setEnabled(True)

        # Start ATP disabled once setup is locked
        self.btn_start.setEnabled(idle and not self.setup_in_progress and not self.setup_locked)

        # Quick Test disabled if quick_locked is True
        self.btn_quick.setEnabled(
            idle and self.setup_complete and not self.setup_in_progress and not self.quick_locked
        )

        self.btn_full.setEnabled(
            idle and self.setup_complete and self.quick_test_done and not self.setup_in_progress
        )

        # Replace enabled when failure exists (and quick is locked / not passed)
        self.btn_replace.setEnabled(
            idle and self.setup_complete and (len(self.failed_slots) > 0) and (not self.quick_test_done)
        )

    # ================================================================
    # START ATP (GUIDED SETUP)
    # ================================================================
    def start_atp_setup(self):
        if self.test_mode != "idle":
            return

        self.setup_in_progress = True
        self.setup_complete = False
        self.quick_test_done = False
        self.failed_slots = []

        # unlock Start ATP during setup
        self.setup_locked = False

        # unlock Quick Test at setup start
        self.quick_locked = False

        # Reset ALL gate results to True baseline each new setup (1..7)
        self.gate_results = {g: {1: True, 2: True, 3: True, 4: True} for g in range(1, 8)}

        self.set_buttons_state()

        for i, slot in enumerate(self.slots, start=1):
            self.rup_ids[i] = None
            slot.set_rup_id(None)
            slot.set_led("gray")
            slot.set_gate(0)
            slot.set_status("Setup")

        self.update_title_with_ids()
        self.log("[UI] Start ATP — Guided Setup BEGIN")

        for i in range(1, 5):
            if not self._setup_step_for_slot(i):
                self.log("[UI] Setup CANCELLED by user")
                self.setup_in_progress = False
                self.setup_complete = False
                self.setup_locked = False
                self.quick_locked = False
                self.set_buttons_state()
                self.set_instruction("Setup cancelled. Click Start ATP to begin again.")
                return

        self.setup_in_progress = False
        self.setup_complete = True

        # lock Start ATP after successful setup
        self.setup_locked = True

        self.open_new_session_files()
        self.update_title_with_ids()

        for s in self.slots:
            s.set_led("gray")
            s.set_status("Ready")

        self.log("[UI] Setup COMPLETE — Quick Test enabled")
        self.set_instruction(
            "Setup complete ✅\n\n"
            "Next: Click Quick Test.\n"
            "Note: Start ATP is locked. If Quick Test fails, use Replace Failed RUP(s)."
        )
        QMessageBox.information(self, "Setup Complete", "All RUP IDs captured.\nYou may now run Quick Test.")
        self.set_buttons_state()

    def _setup_step_for_slot(self, slot_idx: int) -> bool:
        slot_widget = self.slots[slot_idx - 1]

        rup_id, ok = QInputDialog.getText(
            self,
            f"Step {slot_idx} of 4 — RUP ID",
            f"Enter the ID (serial) of RUP for Slot {slot_idx}.\n"
            f"IMPORTANT: Read the sticker BEFORE inserting the RUP."
        )
        if not ok:
            return False

        rup_id = (rup_id or "").strip()
        if not rup_id:
            QMessageBox.warning(self, "Blocked", "ID is required. Setup cannot continue.")
            return self._setup_step_for_slot(slot_idx)

        for s in range(1, 5):
            if s != slot_idx and self.rup_ids[s] == rup_id:
                QMessageBox.warning(self, "Duplicate ID", f"This ID is already used for Slot {s}. Please re-enter.")
                return self._setup_step_for_slot(slot_idx)

        self.rup_ids[slot_idx] = rup_id
        slot_widget.set_rup_id(rup_id)
        slot_widget.set_led("yellow")
        slot_widget.set_status("Awaiting insertion")
        self.update_title_with_ids()
        self.log(f"[SETUP] Slot {slot_idx} ID captured: {rup_id}")

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle(f"Insert RUP — Slot {slot_idx}")
        msg.setText(
            f"Insert RUP with ID:\n\n  {rup_id}\n\ninto Slot {slot_idx} now.\n\n"
            "When done, click OK."
        )
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        res = msg.exec_()
        if res != QMessageBox.Ok:
            return False

        slot_widget.set_led("gray")
        slot_widget.set_status("Inserted confirmed")
        self.log(f"[SETUP] Slot {slot_idx} insertion confirmed")
        return True

    # ================================================================
    # QUICK TEST
    # ================================================================
    def start_quick(self):
        if self.test_mode != "idle" or self.setup_in_progress:
            return
        if not self.setup_complete:
            QMessageBox.warning(self, "Blocked", "Please run Start ATP (setup) first.")
            return
        if self.quick_locked:
            QMessageBox.warning(self, "Blocked", "Quick Test is locked. Replace failed RUP(s) first.")
            return

        self.failed_slots = []
        self.set_buttons_state()

        self.set_instruction("Quick Test running...\nDo not touch hardware.")
        self.log("[UI] Quick Test START")
        self.test_mode = "quick"
        self.current_gate = 0
        self.quick_test_done = False
        self.set_buttons_state()

        for s in self.slots:
            s.set_led("yellow")
            s.set_gate(0)
            s.set_status("Quick Test")

        relay_on()
        self.log("[HW] relay_on()")
        self.timer.start(700)

    def run_quick(self):
        if self.current_gate == 0:
            self.current_gate = 1
            self.log("[GATE 1] REAL (RUP1)")
            self.gate_results[1][1] = bool(run_gate1_power_test())

        elif self.current_gate == 1:
            self.current_gate = 2
            self.log("[GATE 2] REAL (RUP1)")
            self.gate_results[2][1] = bool(gate2_can_check())

        else:
            self.quick_test_done = (bool(self.gate_results[1][1]) and bool(self.gate_results[2][1]))

            # since quick is only for RUP1, simulate others as PASS
            for r in (2, 3, 4):
                self.gate_results[1][r] = True
                self.gate_results[2][r] = True

            self.failed_slots = [] if self.quick_test_done else [1]

            # if quick fails, lock Quick Test until replacement happens
            self.quick_locked = (not self.quick_test_done)

            if self.failed_slots:
                self.log(f"[UI] Quick Test failed — failed_slots={self.failed_slots}")
                self.log("[UI] Quick Test LOCKED until replacement is done")

            for idx, s in enumerate(self.slots, start=1):
                if idx == 1:
                    s.set_led("green" if self.quick_test_done else "red")
                    s.set_status("Quick PASS (real)" if self.quick_test_done else "Quick FAIL (real)")
                else:
                    s.set_led("green")
                    s.set_status("Quick PASS (simulated)")

            self.timer.stop()
            self.test_mode = "idle"
            self.log("[UI] Quick Test COMPLETE")
            self.set_buttons_state()

            if self.quick_test_done:
                self.set_instruction("Quick Test PASS ✅\n\nNext: Click Full ATP.")
            else:
                self.set_instruction(
                    "Quick Test FAIL ❌\n\n"
                    "Quick Test is now locked.\n"
                    "Next: Click Replace Failed RUP(s).\n"
                    "After replacement, Quick Test will unlock."
                )
            return

        g = self.current_gate
        for rup, slot in enumerate(self.slots, start=1):
            ok = bool(self.gate_results[g][rup])
            slot.set_gate(g)
            slot.set_status("PASS" if ok else "FAIL")

    # ================================================================
    # REPLACEMENT FLOW
    # ================================================================
    def replace_failed_rups(self):
        if self.test_mode != "idle" or self.setup_in_progress:
            return
        if not self.setup_complete:
            QMessageBox.warning(self, "Blocked", "Please run Start ATP (setup) first.")
            return
        if len(self.failed_slots) == 0:
            QMessageBox.information(self, "No failures", "No failed slots to replace.")
            return

        failed_sorted = sorted(set(self.failed_slots))
        self.log(f"[REWORK] Replace failed slots: {failed_sorted}")

        for slot_idx in failed_sorted:
            old_id = self.rup_ids.get(slot_idx) or "UNKNOWN"

            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle(f"Remove failed RUP — Slot {slot_idx}")
            msg.setText(
                f"Remove the failed RUP from Slot {slot_idx}.\n\n"
                f"Old ID recorded: {old_id}\n\n"
                "Click OK when removed."
            )
            msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            res = msg.exec_()
            if res != QMessageBox.Ok:
                self.log("[REWORK] Replacement cancelled by user")
                self.set_buttons_state()
                return

            new_id, ok = QInputDialog.getText(
                self,
                f"New ID — Slot {slot_idx}",
                f"Enter NEW ID for Slot {slot_idx}:"
            )
            if not ok:
                self.log("[REWORK] Replacement cancelled by user during ID entry")
                self.set_buttons_state()
                return

            new_id = (new_id or "").strip()
            if not new_id:
                QMessageBox.warning(self, "Blocked", "New ID is required.")
                return self.replace_failed_rups()

            for s in range(1, 5):
                if s != slot_idx and self.rup_ids.get(s) == new_id:
                    QMessageBox.warning(self, "Duplicate ID", f"This ID is already used for Slot {s}. Re-enter.")
                    return self.replace_failed_rups()

            ins = QMessageBox(self)
            ins.setIcon(QMessageBox.Information)
            ins.setWindowTitle(f"Insert new RUP — Slot {slot_idx}")
            ins.setText(
                f"Insert NEW RUP with ID:\n\n  {new_id}\n\ninto Slot {slot_idx}.\n\n"
                "Click OK when inserted."
            )
            ins.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            res2 = ins.exec_()
            if res2 != QMessageBox.Ok:
                self.log("[REWORK] Replacement cancelled by user during insertion confirm")
                self.set_buttons_state()
                return

            self.rup_ids[slot_idx] = new_id
            self.slots[slot_idx - 1].set_rup_id(new_id)
            self.slots[slot_idx - 1].set_led("gray")
            self.slots[slot_idx - 1].set_status("Replaced (Ready)")
            self.update_title_with_ids()

            self.log(f"[REWORK] Slot {slot_idx} replaced: {old_id} -> {new_id}")

        # Clear failures and UNLOCK quick test
        self.failed_slots = []
        self.quick_test_done = False
        self.quick_locked = False
        self.log("[UI] Quick Test UNLOCKED after replacement")

        self.set_buttons_state()
        QMessageBox.information(
            self,
            "Replacement done",
            "Failed RUP(s) replaced.\nQuick Test is now unlocked.\nPlease re-run Quick Test."
        )

    # ================================================================
    # FULL ATP
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

    def start_full(self):
        if self.setup_in_progress:
            return
        if not self.setup_complete:
            QMessageBox.warning(self, "Blocked", "Please run Start ATP (setup) first.")
            return
        if not self.quick_test_done:
            QMessageBox.warning(self, "Blocked", "Quick Test must PASS first.")
            return
        if self.test_mode != "idle":
            return

        self.set_instruction("Full ATP running...\nDo not touch hardware.")
        self.log("[UI] Full ATP START")
        self.test_mode = "full"

        # start from after Gate2 (because Quick already did 1-2)
        self.current_gate = 2

        self.set_buttons_state()

        for s in self.slots:
            s.set_led("yellow")
            s.set_status("Full ATP")

        self.timer.start(900)

    def finalize_full_results(self):
        for rup, slot in enumerate(self.slots, start=1):
            overall_pass = all(bool(self.gate_results[g][rup]) for g in range(1, 8))  # 1..7
            slot.set_led("green" if overall_pass else "red")
            slot.set_status("FINAL PASS" if overall_pass else "FINAL FAIL")

    def run_full(self):
        # Run gates 3..7 (no Gate8)
        if self.current_gate < 7:
            self.current_gate += 1
            g = self.current_gate

            if g == 3:
                g2_ok = bool(self.gate_results[2][1])
                for r in range(1, 5):
                    self.gate_results[3][r] = g2_ok
                self.log("[GATE 3] SIMULATED (depends on Gate 2)")

            if g == 4:
                self.gate_results[4][1] = bool(run_gate4_termination_check(self.log))
                for r in (2, 3, 4):
                    self.gate_results[4][r] = True

            if g == 5:
                self.gate_results[5][1] = bool(run_gate5_iul_check(self.log))
                for r in (2, 3, 4):
                    self.gate_results[5][r] = True

            if g == 6:
                self.gate_results[6][1] = bool(gate6_id_check())
                for r in (2, 3, 4):
                    self.gate_results[6][r] = True

            if g == 7:
                # IMPORTANT: run_gate7() returns {"pass": True/False, ...}
                results, logs = run_gate7(log_cb=self.log)
                gate7_ok = bool(results.get("pass", False))

                # only RUP1 is real tested -> apply same to all slots
                for r in range(1, 5):
                    self.gate_results[7][r] = gate7_ok

                self.log(f"[GATE7] Gate7 pass={gate7_ok} (RUP1 real, RUP2-4 simulated)")
                # If you still want the full gate7 internal logs list:
                try:
                    for line in logs:
                        self.log(line)
                except Exception:
                    pass

            for rup, slot in enumerate(self.slots, start=1):
                ok = bool(self.gate_results[g][rup])
                slot.set_gate(g)
                slot.set_status("PASS" if ok else "FAIL")
            return

        self.log("[UI] Full ATP COMPLETE")
        self.finalize_full_results()

        self.shutdown_hw("Full ATP complete")
        self.timer.stop()
        self.test_mode = "idle"
        self.write_excel_results()
        self.set_buttons_state()

        if self.log_file:
            self.log("=== ATP END ===")
            try:
                self.log_file.close()
            except Exception:
                pass
            self.log_file = None

    def write_excel_results(self):
        ts = self.session_ts or datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        ids_str = "_".join([(self.rup_ids[i] or "NA") for i in range(1, 5)])
        path = os.path.join(self.logs_dir, f"ATP_{ids_str}_{ts}.xlsx")

        wb = Workbook()
        ws = wb.active
        ws.title = "Gate Results"

        ws.append(["Gate", "RUP1", "RUP2", "RUP3", "RUP4"])
        for cell in ws[1]:
            cell.font = Font(bold=True)

        for g in range(1, 8):  # 1..7
            ws.append(
                [f"Gate {g}"] +
                ["PASS" if bool(self.gate_results[g][r]) else "FAIL" for r in range(1, 5)]
            )

        wb.save(path)
        self.log(f"[FILE] Excel written: {path}")

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

        # On stop, unlock quick (so operator can retry after fixing things)
        self.quick_locked = False

        self.set_buttons_state()

        for s in self.slots:
            s.set_led("red")
            s.set_status("Stopped")

        if self.log_file:
            self.log("=== ATP ABORTED ===")
            try:
                self.log_file.close()
            except Exception:
                pass
            self.log_file = None

    def closeEvent(self, e):
        self.shutdown_hw("Window closed")
        e.accept()


# ======================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
