#!/usr/bin/env python3
import sys
import os
import datetime

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QInputDialog

# UI
from ui_atp import Ui_MainWindow

# services
from services.hardware import HardwareController
from services.reporting import Reporter

# runners
from runners.quick_runner import QuickRunner, SlotUpdate
from runners.full_runner import FullRunner, FullUpdate

# =========================
# GATE IMPORTS
# =========================
from tests.gate1_power_passthrough import run_gate1_power_test
from tests.gate2_CAN_check import gate2_can_check
from tests.gate4_test import run_gate4_termination_check
from tests.gate5_iul_check import run_gate5_iul_check
from tests.gate6_ID_check import gate6_id_check
from tests.gate7 import run_gate7

from tests.CAN.can_commands import end_atp


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # UI
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.slots = self.ui.slots

        # dirs
        self.logs_dir = "ATP_logs"
        os.makedirs(self.logs_dir, exist_ok=True)

        # state
        self.rup_ids = {1: None, 2: None, 3: None, 4: None}
        self.setup_complete = False
        self.setup_in_progress = False
        self.setup_locked = False

        self.failed_slots = []
        self.quick_locked = False
        self.quick_test_done = False

        self.test_mode = "idle"  # idle | quick | full

        # results (gates 1..7)
        self.gate_results = {g: {1: True, 2: True, 3: True, 4: True} for g in range(1, 8)}

        # logging/reporting
        self.reporter = Reporter(self.logs_dir, log_cb=self.log)

        # hardware
        self.hw = HardwareController(log_cb=self.log)

        # runners
        # NOTE: These assume you've updated Gate1/Gate2 to accept slot argument:
        #   run_gate1_power_test(slot)
        #   gate2_can_check(slot)
        self.quick = QuickRunner(
            hw=self.hw,
            log_cb=self.log,
            gate1_fn=run_gate1_power_test,
            gate2_fn=gate2_can_check,
            on_update=self.on_quick_update,
        )

        # FullRunner is the new sequential-per-RUP version (gates 3..7)
        self.full = FullRunner(
            hw=self.hw,
            log_cb=self.log,
            on_update=self.on_full_update,
            run_gate4_fn=run_gate4_termination_check,
            run_gate5_fn=run_gate5_iul_check,
            run_gate6_fn=gate6_id_check,
            run_gate7_fn=run_gate7,
            check_power_before_full=True,
        )

        # timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.run_step)

        # signals
        self.ui.btn_start.clicked.connect(self.start_atp_setup)
        self.ui.btn_quick.clicked.connect(self.start_quick)
        self.ui.btn_full.clicked.connect(self.start_full)
        self.ui.btn_replace.clicked.connect(self.replace_failed_rups)
        self.ui.btn_stop.clicked.connect(self.stop_test)

        self.set_buttons_state()

    # ================================================================
    # basic ui/log helpers
    # ================================================================
    def set_instruction(self, msg: str):
        self.ui.instructions.setText(msg)

    def update_title_with_ids(self):
        ids_str = ", ".join([f"S{i}:{self.rup_ids[i] or '---'}" for i in range(1, 5)])
        self.ui.title.setText(f"RUP ATP — {ids_str}")

    def log(self, txt: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {txt}"
        print(line)
        self.ui.log_box.append(line)

        if self.reporter.log_file:
            self.reporter.write_line(line)

        sb = self.ui.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ================================================================
    # button states
    # ================================================================
    def set_buttons_state(self):
        idle = (self.test_mode == "idle")
        self.ui.btn_stop.setEnabled(True)

        self.ui.btn_start.setEnabled(idle and not self.setup_in_progress and not self.setup_locked)
        self.ui.btn_quick.setEnabled(
            idle and self.setup_complete and not self.quick_locked and not self.setup_in_progress
        )
        self.ui.btn_full.setEnabled(
            idle and self.setup_complete and self.quick_test_done and not self.setup_in_progress
        )

        self.ui.btn_replace.setEnabled(
            idle and self.setup_complete and (len(self.failed_slots) > 0) and (not self.quick_test_done)
        )

    # ================================================================
    # setup flow
    # ================================================================
    def start_atp_setup(self):
        if self.test_mode != "idle":
            return

        self.setup_in_progress = True
        self.setup_complete = False
        self.quick_test_done = False
        self.failed_slots = []
        self.quick_locked = False
        self.setup_locked = False

        # reset results
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
                self.set_instruction("Setup cancelled. Click Start ATP to begin again.")
                self.set_buttons_state()
                return

        self.setup_in_progress = False
        self.setup_complete = True
        self.setup_locked = True

        self.reporter.open_session(self.rup_ids)
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
    # Quick Test
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

        self.test_mode = "quick"
        self.quick_test_done = False
        self.failed_slots = []
        self.set_buttons_state()

        self.set_instruction("Quick Test running (RUP1→RUP4)...\nDo not touch hardware.")
        self.log("[UI] Quick Test START")

        for idx, s in enumerate(self.slots, start=1):
            s.set_led("yellow")
            s.set_gate(0)
            s.set_status("Queued" if idx != 1 else "Starting...")

        self.quick.start()
        self.timer.start(250)

    def on_quick_update(self, upd: SlotUpdate):
        slot = self.slots[upd.slot - 1]
        if upd.led:
            slot.set_led(upd.led)
        slot.set_gate(upd.gate)
        slot.set_status(upd.status)

    def finish_quick(self):
        for r in (1, 2, 3, 4):
            self.gate_results[1][r] = bool(self.quick.results[1][r])
            self.gate_results[2][r] = bool(self.quick.results[2][r])

        self.failed_slots = list(self.quick.failed_slots)
        self.quick_test_done = self.quick.overall_pass()
        self.quick_locked = (not self.quick_test_done)

        self.timer.stop()
        self.test_mode = "idle"
        self.set_buttons_state()

        if self.quick_test_done:
            self.log("[UI] Quick Test COMPLETE: PASS (all RUPs)")
            self.set_instruction("Quick Test PASS ✅ (RUP1..RUP4)\n\nNext: Click Full ATP.")
        else:
            self.log(f"[UI] Quick Test COMPLETE: FAIL — failed_slots={self.failed_slots}")
            self.log("[UI] Quick Test LOCKED until replacement is done")
            self.set_instruction(
                "Quick Test FAIL ❌\n\n"
                f"Failed slot(s): {self.failed_slots}\n"
                "Quick Test is now locked.\n"
                "Next: Click Replace Failed RUP(s).\n"
                "After replacement, Quick Test will unlock."
            )

    # ================================================================
    # Full ATP (sequential per RUP for gates 3..7)
    # ================================================================
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

        self.test_mode = "full"
        self.set_buttons_state()

        self.set_instruction("Full ATP running (RUP1→RUP4)...\nDo not touch hardware.")
        self.log("[UI] Full ATP START")

        for idx, s in enumerate(self.slots, start=1):
            s.set_led("yellow")
            s.set_status("Queued" if idx != 1 else "Starting...")
            # keep gate progress as-is (gates 1-2 already done)
            s.set_gate(2)

        self.full.start()
        self.timer.start(600)

    def on_full_update(self, upd: FullUpdate):
        slot = self.slots[upd.slot - 1]
        slot.set_gate(upd.gate if upd.gate >= 0 else 0)
        slot.set_status(upd.status)
        if upd.led:
            slot.set_led(upd.led)

    def finalize_full_results(self):
        for rup, slot in enumerate(self.slots, start=1):
            overall_pass = all(bool(self.gate_results[g][rup]) for g in range(1, 8))
            slot.set_led("green" if overall_pass else "red")
            slot.set_status("FINAL PASS" if overall_pass else "FINAL FAIL")

    def shutdown_hw(self, why=""):
        if why:
            self.log(f"[HW] Shutdown: {why}")

        try:
            self.hw.relay_off_all()
            self.log("[HW] All relays OFF")
        except Exception as e:
            self.log(f"[HW][WARN] relays off failed: {e}")

        try:
            end_atp()
            self.log("[HW] END_ATP sent")
        except Exception as e:
            self.log(f"[HW][WARN] END_ATP failed: {e}")

    def finish_full(self):
        self.log("[UI] Full ATP COMPLETE")
        self.finalize_full_results()

        self.shutdown_hw("Full ATP complete")

        self.timer.stop()
        self.test_mode = "idle"

        xlsx_path = self.reporter.write_excel_results(self.gate_results, self.rup_ids)
        self.log(f"[FILE] Excel written: {xlsx_path}")

        self.set_buttons_state()

        if self.reporter.log_file:
            self.log("=== ATP END ===")
            self.reporter.close_session()

    # ================================================================
    # Replace failed RUP(s)
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
    # timer dispatch
    # ================================================================
    def run_step(self):
        if self.test_mode == "quick":
            done = self.quick.step(self.gate_results) if "gate_results" in self.quick.step.__code__.co_varnames else self.quick.step()
            if done:
                self.finish_quick()

        elif self.test_mode == "full":
            done = self.full.step(self.gate_results)
            if done:
                self.finish_full()

    # ================================================================
    # stop + close
    # ================================================================
    def stop_test(self):
        self.log("[UI] STOPPED")
        self.timer.stop()
        self.shutdown_hw("User pressed Stop")

        self.test_mode = "idle"
        self.quick_locked = False
        self.set_buttons_state()

        for s in self.slots:
            s.set_led("red")
            s.set_status("Stopped")

        if self.reporter.log_file:
            self.log("=== ATP ABORTED ===")
            self.reporter.close_session()

    def closeEvent(self, e):
        self.shutdown_hw("Window closed")
        self.hw.cleanup()
        try:
            self.reporter.close_session()
        except Exception:
            pass
        e.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
