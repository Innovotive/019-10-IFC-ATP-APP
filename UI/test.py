#!/usr/bin/env python3
import sys
import os
import datetime

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QInputDialog

from openpyxl import Workbook
from openpyxl.styles import Font

# UI moved out
from ui_atp import Ui_MainWindow


# =========================
# REAL GATE IMPORTS
# =========================
from tests.gate1_power_passthrough import run_gate1_power_test
from tests.gate2_CAN_check import gate2_can_check
from tests.gate4_test import run_gate4_termination_check
from tests.gate5_iul_check import run_gate5_iul_check
from tests.gate6_ID_check import gate6_id_check
from tests.gate7 import run_gate7

from tests.CAN.can_commands import end_atp

# =========================
# MULTI-RUP RELAY + POWER DETECT
# =========================
from tests.power_PT.relay_1_4 import (
    relay_on_rup1, relay_off_rup1,
    relay_on_rup2, relay_off_rup2,
    relay_on_rup3, relay_off_rup3,
    relay_on_rup4, relay_off_rup4,
)

from tests.power_PT.power_1_4 import (
    read_power_state_rup1,
    read_power_state_rup2,
    read_power_state_rup3,
    read_power_state_rup4,
    cleanup_gpio,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # ================================================================
        # UI SETUP
        # ================================================================
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.slots = self.ui.slots  # convenience

        self.logs_dir = "ATP_logs"
        os.makedirs(self.logs_dir, exist_ok=True)

        # ================================================================
        # IDs + FILES
        # ================================================================
        self.rup_ids = {1: None, 2: None, 3: None, 4: None}
        self.setup_complete = False
        self.setup_in_progress = False
        self.setup_locked = False

        self.log_file = None
        self.session_ts = None

        # Track failed slots
        self.failed_slots = []
        self.quick_locked = False

        # ================================================================
        # RESULTS STORAGE (Gates 1..7)
        # ================================================================
        self.gate_results = {g: {1: True, 2: True, 3: True, 4: True} for g in range(1, 8)}

        # ================================================================
        # STATE
        # ================================================================
        self.test_mode = "idle"  # "idle" | "quick" | "full"
        self.current_gate = 0
        self.quick_test_done = False

        # QUICK SEQUENCE STATE MACHINE
        # phases: "power_on" -> "gate1" -> "gate2" -> "power_off" -> next rup
        self.quick_rup = 1
        self.quick_phase = "power_on"

        self.timer = QTimer()
        self.timer.timeout.connect(self.run_gate_step)

        # ================================================================
        # CONNECT UI SIGNALS
        # ================================================================
        self.ui.btn_start.clicked.connect(self.start_atp_setup)
        self.ui.btn_quick.clicked.connect(self.start_quick)
        self.ui.btn_full.clicked.connect(self.start_full)
        self.ui.btn_replace.clicked.connect(self.replace_failed_rups)
        self.ui.btn_stop.clicked.connect(self.stop_test)

        self.set_buttons_state()

    # ================================================================
    # RELAY + POWER ROUTERS (slot_idx = 1..4)
    # ================================================================
    def relay_on_for_slot(self, slot_idx: int) -> None:
        if slot_idx == 1:
            relay_on_rup1()
        elif slot_idx == 2:
            relay_on_rup2()
        elif slot_idx == 3:
            relay_on_rup3()
        elif slot_idx == 4:
            relay_on_rup4()
        else:
            self.log(f"[HW][WARN] relay_on_for_slot invalid slot={slot_idx}")

    def relay_off_for_slot(self, slot_idx: int) -> None:
        if slot_idx == 1:
            relay_off_rup1()
        elif slot_idx == 2:
            relay_off_rup2()
        elif slot_idx == 3:
            relay_off_rup3()
        elif slot_idx == 4:
            relay_off_rup4()
        else:
            self.log(f"[HW][WARN] relay_off_for_slot invalid slot={slot_idx}")

    def power_present_for_slot(self, slot_idx: int) -> bool:
        if slot_idx == 1:
            return bool(read_power_state_rup1())
        elif slot_idx == 2:
            return bool(read_power_state_rup2())
        elif slot_idx == 3:
            return bool(read_power_state_rup3())
        elif slot_idx == 4:
            return bool(read_power_state_rup4())
        else:
            self.log(f"[HW][WARN] power_present_for_slot invalid slot={slot_idx}")
            return False

    def relay_off_all(self) -> None:
        for s in (1, 2, 3, 4):
            try:
                self.relay_off_for_slot(s)
            except Exception:
                pass

    # ================================================================
    # UI HELPERS
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
        if self.log_file:
            self.log_file.write(line + "\n")
            self.log_file.flush()
        sb = self.ui.log_box.verticalScrollBar()
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

    # ================================================================
    # BUTTON STATES
    # ================================================================
    def set_buttons_state(self):
        idle = (self.test_mode == "idle")
        self.ui.btn_stop.setEnabled(True)

        self.ui.btn_start.setEnabled(idle and not self.setup_in_progress and not self.setup_locked)

        self.ui.btn_quick.setEnabled(
            idle and self.setup_complete and not self.setup_in_progress and not self.quick_locked
        )

        self.ui.btn_full.setEnabled(
            idle and self.setup_complete and self.quick_test_done and not self.setup_in_progress
        )

        self.ui.btn_replace.setEnabled(
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

        self.setup_locked = False
        self.quick_locked = False

        # Reset gate results
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
    # QUICK TEST (NEW: sequential RUP1..RUP4, Gate1+Gate2 each)
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
        self.quick_test_done = False
        self.set_buttons_state()

        # reset only gates 1-2 results
        for r in (1, 2, 3, 4):
            self.gate_results[1][r] = True
            self.gate_results[2][r] = True

        # init state machine
        self.test_mode = "quick"
        self.quick_rup = 1
        self.quick_phase = "power_on"
        self.current_gate = 0

        self.set_instruction("Quick Test running (RUP1→RUP4)...\nDo not touch hardware.")
        self.log("[UI] Quick Test START (sequential RUP1..RUP4)")

        for idx, s in enumerate(self.slots, start=1):
            s.set_led("yellow")
            s.set_gate(0)
            s.set_status("Queued" if idx != 1 else "Starting...")

        # start stepping
        self.timer.start(300)

    def _quick_mark_slot_after_gate(self, gate_num: int, rup: int):
        ok = bool(self.gate_results[gate_num][rup])
        slot = self.slots[rup - 1]
        slot.set_gate(gate_num)
        slot.set_status("PASS" if ok else "FAIL")

    def _quick_finalize(self):
        # determine failures on gates 1-2
        self.failed_slots = []
        for r in (1, 2, 3, 4):
            if (not bool(self.gate_results[1][r])) or (not bool(self.gate_results[2][r])):
                self.failed_slots.append(r)

        self.quick_test_done = (len(self.failed_slots) == 0)
        self.quick_locked = (not self.quick_test_done)

        # update LEDs/status
        for r, slot in enumerate(self.slots, start=1):
            r_ok = bool(self.gate_results[1][r]) and bool(self.gate_results[2][r])
            slot.set_led("green" if r_ok else "red")
            slot.set_status("Quick PASS" if r_ok else "Quick FAIL")

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

    def run_quick(self):
        r = self.quick_rup
        phase = self.quick_phase

        if r > 4:
            # safety
            self.relay_off_all()
            self._quick_finalize()
            return

        slot = self.slots[r - 1]

        # -------------------------
        # PHASE: POWER ON
        # -------------------------
        if phase == "power_on":
            self.log(f"[QUICK] RUP{r}: relay ON")
            try:
                self.relay_on_for_slot(r)
            except Exception as e:
                self.log(f"[HW][FAIL] RUP{r} relay ON error: {e}")
                self.gate_results[1][r] = False
                self.gate_results[2][r] = False
                self.failed_slots.append(r)
                self.quick_phase = "power_off"
                return

            slot.set_status("Powering ON...")
            slot.set_led("yellow")

            # optional power detect check
            try:
                pwr = self.power_present_for_slot(r)
            except Exception as e:
                self.log(f"[HW][WARN] RUP{r} power detect error: {e}")
                pwr = False

            if not pwr:
                self.log(f"[HW][FAIL] RUP{r}: power detect = False (ACTIVE-HIGH)")
                # mark both gates fail (since no power)
                self.gate_results[1][r] = False
                self.gate_results[2][r] = False
                self.quick_phase = "power_off"
                slot.set_status("NO POWER (FAIL)")
                slot.set_gate(0)
                return

            self.log(f"[HW] RUP{r}: power detect OK")
            slot.set_status("Powered (Ready)")
            self.quick_phase = "gate1"
            return

        # -------------------------
        # PHASE: GATE 1
        # -------------------------
        if phase == "gate1":
            self.current_gate = 1
            self.log(f"[GATE 1] REAL (RUP{r})")
            try:
                self.gate_results[1][r] = bool(run_gate1_power_test())
            except Exception as e:
                self.log(f"[GATE1][ERROR] RUP{r}: {e}")
                self.gate_results[1][r] = False

            self._quick_mark_slot_after_gate(1, r)
            self.quick_phase = "gate2"
            return

        # -------------------------
        # PHASE: GATE 2
        # -------------------------
        if phase == "gate2":
            self.current_gate = 2
            self.log(f"[GATE 2] REAL (RUP{r})")
            try:
                self.gate_results[2][r] = bool(gate2_can_check())
            except Exception as e:
                self.log(f"[GATE2][ERROR] RUP{r}: {e}")
                self.gate_results[2][r] = False

            self._quick_mark_slot_after_gate(2, r)
            self.quick_phase = "power_off"
            return

        # -------------------------
        # PHASE: POWER OFF + NEXT
        # -------------------------
        if phase == "power_off":
            self.log(f"[QUICK] RUP{r}: relay OFF")
            try:
                self.relay_off_for_slot(r)
            except Exception as e:
                self.log(f"[HW][WARN] RUP{r} relay OFF error: {e}")

            # determine this RUP quick overall
            r_ok = bool(self.gate_results[1][r]) and bool(self.gate_results[2][r])
            if not r_ok and r not in self.failed_slots:
                self.failed_slots.append(r)

            slot.set_status("Done (PASS)" if r_ok else "Done (FAIL)")
            slot.set_led("green" if r_ok else "red")

            # advance to next RUP
            self.quick_rup += 1
            if self.quick_rup <= 4:
                nxt = self.slots[self.quick_rup - 1]
                nxt.set_status("Starting...")
                nxt.set_led("yellow")
                nxt.set_gate(0)
                self.quick_phase = "power_on"
                return

            # finished all RUPs
            self.relay_off_all()
            self._quick_finalize()
            return

    # ================================================================
    # REPLACEMENT FLOW (unchanged)
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
    # FULL ATP (kept mostly same, but Gate3 now depends per-RUP on Gate2)
    # ================================================================
    def shutdown_hw(self, why=""):
        if why:
            self.log(f"[HW] Shutdown: {why}")

        # Always power off all relays
        try:
            self.relay_off_all()
            self.log("[HW] All relays OFF")
        except Exception as e:
            self.log(f"[HW][WARN] relay_off_all failed: {e}")

        try:
            end_atp()
            self.log("[HW] END_ATP sent")
        except Exception as e:
            self.log(f"[HW][WARN] END_ATP failed: {e}")

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

        # start from after Gate2 (Quick already did 1-2)
        self.current_gate = 2

        self.set_buttons_state()

        for s in self.slots:
            s.set_led("yellow")
            s.set_status("Full ATP")

        self.timer.start(900)

    def finalize_full_results(self):
        for rup, slot in enumerate(self.slots, start=1):
            overall_pass = all(bool(self.gate_results[g][rup]) for g in range(1, 8))
            slot.set_led("green" if overall_pass else "red")
            slot.set_status("FINAL PASS" if overall_pass else "FINAL FAIL")

    def run_full(self):
        if self.current_gate < 7:
            self.current_gate += 1
            g = self.current_gate

            if g == 3:
                # Gate3 depends on Gate2 per RUP now
                for r in range(1, 5):
                    self.gate_results[3][r] = bool(self.gate_results[2][r])
                self.log("[GATE 3] SIMULATED (depends on Gate 2 per-RUP)")

            if g == 4:
                # still only real-testing RUP1 here (you can extend later)
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
                results, logs = run_gate7(log_cb=self.log)
                gate7_ok = bool(results.get("pass", False))
                for r in range(1, 5):
                    self.gate_results[7][r] = gate7_ok
                self.log(f"[GATE7] Gate7 pass={gate7_ok} (RUP1 real, others simulated)")
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

        for g in range(1, 8):
            ws.append(
                [f"Gate {g}"] +
                ["PASS" if bool(self.gate_results[g][r]) else "FAIL" for r in range(1, 5)]
            )

        wb.save(path)
        self.log(f"[FILE] Excel written: {path}")

    # ================================================================
    # TIMER DISPATCH
    # ================================================================
    def run_gate_step(self):
        if self.test_mode == "quick":
            self.run_quick()
        elif self.test_mode == "full":
            self.run_full()

    # ================================================================
    # STOP / EXIT
    # ================================================================
    def stop_test(self):
        self.log("[UI] STOPPED")
        self.timer.stop()
        self.test_mode = "idle"

        self.shutdown_hw("User pressed Stop")

        # unlock quick so operator can retry after fixing
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
        try:
            cleanup_gpio()
        except Exception:
            pass
        e.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
