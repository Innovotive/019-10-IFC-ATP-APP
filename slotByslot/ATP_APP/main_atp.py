#!/usr/bin/env python3
# main_atp.py — RUP ATP (4-Slot Dashboard + Session + STEP0 Guide-Light Confirm)
#
# What this version does:
# - UI shows 4 slots like your screenshot (no "(Blue/Green/..)" text).
# - Gate label shows: "Gate X — Gate Name"
# - Status shows: Idle / Running / PASS / FAIL
# - Button: "Start New Session" to run batches of 4 repeatedly
#
# Session flow:
# 1) Start New Session
# 2) Ask Serial Number for Slot 1..4 (one dialog each)
# 3) STEP0 (Guide Light):
#    - Turn ON relay for Slot1 -> wait 5s -> operator clicks PASS/FAIL
#    - Then Slot2, Slot3, Slot4 (same)
#    - If FAIL -> slot is marked FAIL and will be skipped for gates
# 4) For each slot that passed STEP0:
#    - Quick = Gate1, Gate2
#    - If quick PASS -> Full = Gate3..Gate6
# 5) End: you can Start New Session again
#
# Stop:
# - Aborts run
# - Sends END_ATP to current slot (best-effort)
# - Turns OFF all relays (needs relay_off_all helper)

import sys
import os
import re
import time
import datetime
import traceback

from PyQt5.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool, QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QInputDialog

from openpyxl import Workbook
from openpyxl.styles import Font

from ui_layout import build_ui
from slot_config import get_slot_config, SlotConfig

# HW init
from tests.ID.id_pins_init import init_id_pins_all_slots

# Relays
from tests.power_PT.relay import relay_on, relay_off
from tests.power_PT.relay_all import relay_off_all  # make sure this uses your proven relay_off()

# Gates
from tests.gate1_power_passthrough import run_gate1_power_test
from tests.gate2_CAN_check import gate2_can_check
from tests.gate3_termination_check import run_gate3_termination_check
from tests.gate4_iul_check import run_gate4_iul_check
from tests.gate5_ID_check import run_gate5_id_check
from tests.gate6_pd_load import run_gate6_pd_load

# CAN end
from tests.CAN.can_commands import end_atp


GATE_NAMES = {
    1: "Power Pass-Through Voltage",
    2: "CAN-Bus Pass-Through",
    3: "CAN Termination Resistance Check",
    4: "In-Use Light Check",
    5: "ID-Pins Functional Test",
    6: "USB-C Power Delivery / Load Regulation",
}

SERIAL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_]{2,63}$")  # 3..64 chars


# ------------------------------------------------------------
# Thread-safe log emitter (avoid QTextCursor warnings)
# ------------------------------------------------------------
class LogEmitter(QObject):
    line = pyqtSignal(str)


# ------------------------------------------------------------
# Worker infra
# ------------------------------------------------------------
class WorkerSignals(QObject):
    finished = pyqtSignal(int, bool, str)


class GateWorker(QRunnable):
    def __init__(self, gate_num: int, fn):
        super().__init__()
        self.gate_num = gate_num
        self.fn = fn
        self.signals = WorkerSignals()

    def run(self):
        ok = False
        err = ""
        try:
            ok = bool(self.fn())
        except Exception:
            ok = False
            err = traceback.format_exc()
        self.signals.finished.emit(self.gate_num, ok, err)


# ------------------------------------------------------------
# Main Window
# ------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("RUP Acceptance Test Platform")
        self.resize(1100, 760)

        # UI
        self.ui = build_ui(self)
        self.slot_widgets = self.ui["slots"]

        # Buttons
        self.ui["btn_start"].clicked.connect(self.start_new_session)
        self.ui["btn_stop"].clicked.connect(self.stop_test)

        # Thread pool + thread-safe logging
        self.threadpool = QThreadPool.globalInstance()
        self.log_emitter = LogEmitter()
        self.log_emitter.line.connect(self._append_log_line)

        # Files
        self.logs_dir = "ATP_logs"
        os.makedirs(self.logs_dir, exist_ok=True)
        self.log_file = None
        self.session_ts = None

        # Session data
        self.abort_requested = False
        self.active_slot = 1

        self.slot_queue = [1, 2, 3, 4]
        self.current_slot_idx = 0

        self.slot_serials = {}         # {slot: sn}
        self.slot_step0_pass = {}      # {slot: bool}
        self.slot_gate_results = {}    # {slot: {gate: bool}}

        # Per-slot run state
        self.slot_cfg: SlotConfig = get_slot_config(1)
        self.rup_serial = None

        self.running_gate = None
        self.sequence = []
        self.phase = "idle"  # idle|step0|quick|full

        self.gate_results = {g: True for g in range(1, 7)}

        # Startup init
        self._startup_hw_init()

        # Initialize UI state
        self.reset_ui_state()

    # ----------------------------
    # Startup HW init
    # ----------------------------
    def _startup_hw_init(self):
        ok = False
        try:
            ok = init_id_pins_all_slots()
        except Exception as e:
            self.log(f"[INIT][ERROR] init_id_pins_all_slots failed: {e}")
        self.log("[INIT] ID pins ALL slots baseline set" if ok else "[INIT][WARN] ID init failed")

        # Do not force relays ON here; we will do it in Step0 sequentially.

    # ----------------------------
    # Logging
    # ----------------------------
    def _append_log_line(self, line: str):
        self.ui["log_box"].append(line)
        if self.log_file:
            self.log_file.write(line + "\n")
            self.log_file.flush()

    def log(self, txt: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {txt}"
        print(line)
        self.log_emitter.line.emit(line)

    # ----------------------------
    # UI helpers
    # ----------------------------
    def set_instruction(self, msg: str):
        self.ui["instructions"].setText(msg)

    def reset_ui_state(self):
        self.abort_requested = False
        self.phase = "idle"
        self.running_gate = None
        self.sequence = []
        self.current_slot_idx = 0

        self.slot_serials = {}
        self.slot_step0_pass = {}
        self.slot_gate_results = {}

        for s in (1, 2, 3, 4):
            sw = self.slot_widgets[s]
            sw.set_led("gray")
            sw.set_status("Idle")
            sw.set_gate(0, "")

        self.set_instruction(
            "Instructions:\n"
            "1) Click Start New Session\n"
            "2) Enter serial numbers for Slot 1–4\n"
            "3) Insert RUPs\n"
            "4) Step 0: confirm Guide Light blinking for each slot\n"
            "5) Quick then Full ATP runs automatically (slot-by-slot)\n"
        )

        self.ui["btn_start"].setEnabled(True)
        self.ui["btn_stop"].setEnabled(True)

    def set_slot_widget_running(self, slot: int, gate: int, status_text="Running..."):
        sw = self.slot_widgets[slot]
        sw.set_led("yellow")
        sw.set_status(status_text)
        if gate == 0:
            sw.set_gate(0, "")
        else:
            sw.set_gate(gate, GATE_NAMES.get(gate, ""))

    def set_slot_widget_result(self, slot: int, ok: bool, final=False):
        sw = self.slot_widgets[slot]
        sw.set_led("green" if ok else "red")
        sw.set_status("PASS" if ok else "FAIL")
        # keep last gate text as-is

    def sanitize_for_filename(self, s: str) -> str:
        s = (s or "").strip()
        s = re.sub(r"[^A-Za-z0-9\-_]+", "_", s)
        return s[:64] if s else "NO_SN"

    # ----------------------------
    # Serial prompt
    # ----------------------------
    def prompt_serial_for_slot(self, slot: int) -> bool:
        while True:
            text, ok = QInputDialog.getText(
                self,
                "Enter RUP Serial Number",
                f"Slot {slot}: Enter RUP Serial Number (SN):"
            )
            if not ok:
                self.log(f"[SERIAL] Cancelled for slot {slot}")
                return False

            sn = (text or "").strip()
            if not sn:
                QMessageBox.warning(self, "Invalid", "Serial number cannot be empty.")
                continue
            if not SERIAL_RE.match(sn):
                QMessageBox.warning(self, "Invalid", "Allowed: letters/numbers, '-' '_' (3..64 chars).")
                continue

            self.slot_serials[slot] = sn
            self.log(f"[SERIAL] Slot {slot} SN set: {sn}")
            return True

    # ----------------------------
    # Session file handling (per slot)
    # ----------------------------
    def open_slot_log(self, slot: int):
        # close previous
        if self.log_file:
            try:
                self.log_file.close()
            except Exception:
                pass
            self.log_file = None

        self.session_ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        sn = self.slot_serials.get(slot, "NO_SN")
        sn_safe = self.sanitize_for_filename(sn)
        path = os.path.join(self.logs_dir, f"ATP_S{slot}_{sn_safe}_{self.session_ts}.log")

        self.log_file = open(path, "w", buffering=1)
        self.log(f"=== ATP START | Slot {slot} ===")
        self.log(f"[SERIAL] {sn}")
        self.log(f"[FILE] {path}")

    def close_slot_log(self, why=""):
        if self.log_file:
            if why:
                self.log(why)
            try:
                self.log_file.close()
            except Exception:
                pass
            self.log_file = None

    # ----------------------------
    # Start New Session
    # ----------------------------
    def start_new_session(self):
        if self.phase != "idle":
            return

        self.abort_requested = False
        self.ui["btn_start"].setEnabled(False)

        # reset per-session state
        self.slot_serials = {}
        self.slot_step0_pass = {}
        self.slot_gate_results = {}
        self.current_slot_idx = 0

        for s in (1, 2, 3, 4):
            sw = self.slot_widgets[s]
            sw.set_led("gray")
            sw.set_status("Idle")
            sw.set_gate(0, "")

        # Ask serials for all 4 upfront
        for s in (1, 2, 3, 4):
            if not self.prompt_serial_for_slot(s):
                self.stop_test()
                return

        self.set_instruction(
            "STEP 0: Guide Light Confirmation\n"
            "- The app will power ON each slot one-by-one.\n"
            "- Watch the guide light blinking.\n"
            "- Click PASS/FAIL when asked.\n"
        )

        self.phase = "step0"
        self.current_slot_idx = 0
        QTimer.singleShot(200, self.step0_next_slot)

    # ----------------------------
    # STEP 0 — Guide Light Confirm (manual)
    # ----------------------------
    def step0_next_slot(self):
        if self.abort_requested:
            return

        if self.current_slot_idx >= len(self.slot_queue):
            self.log("[STEP0] Completed for all slots")
            self.phase = "quick"
            self.current_slot_idx = 0
            QTimer.singleShot(200, self.start_next_slot_quick)
            return

        slot = self.slot_queue[self.current_slot_idx]
        self.active_slot = slot
        self.slot_cfg = get_slot_config(slot)

        # Show slot running in UI
        self.set_slot_widget_running(slot, gate=0, status_text="Guide Light Check")

        # Power ON this slot now
        try:
            relay_on(self.slot_cfg)
            self.log(f"[STEP0] Slot {slot}: relay ON (GPIO {self.slot_cfg.relay_gpio})")
        except Exception as e:
            self.log(f"[STEP0][ERROR] Slot {slot} relay_on failed: {e}")
            self.slot_step0_pass[slot] = False
            self.set_slot_widget_result(slot, ok=False)
            self.current_slot_idx += 1
            QTimer.singleShot(200, self.step0_next_slot)
            return

        # Wait 5 seconds to let operator see blinking
        self.log(f"[STEP0] Slot {slot}: wait 5s for blinking...")
        QTimer.singleShot(5000, self.step0_prompt_pass_fail)

    def step0_prompt_pass_fail(self):
        if self.abort_requested:
            return

        slot = self.active_slot

        # PASS/FAIL dialog (operator clicks)
        msg = QMessageBox(self)
        msg.setWindowTitle("Guide Light Check")
        msg.setText(f"Slot {slot}:\nIs the Guide Light blinking correctly?")
        btn_pass = msg.addButton("PASS", QMessageBox.AcceptRole)
        btn_fail = msg.addButton("FAIL", QMessageBox.RejectRole)
        msg.setIcon(QMessageBox.Question)
        msg.exec_()

        clicked = msg.clickedButton()
        ok = (clicked == btn_pass)

        self.slot_step0_pass[slot] = ok
        self.log(f"[STEP0] Slot {slot}: {'PASS' if ok else 'FAIL'}")

        if ok:
            self.set_slot_widget_result(slot, ok=True)
        else:
            self.set_slot_widget_result(slot, ok=False)
            # Optional: turn OFF failed slot so operator can replace it later
            try:
                relay_off(self.slot_cfg)
                self.log(f"[STEP0] Slot {slot}: relay OFF (failed guide light)")
            except Exception as e:
                self.log(f"[STEP0][WARN] Slot {slot} relay_off failed: {e}")

        self.current_slot_idx += 1
        QTimer.singleShot(200, self.step0_next_slot)

    # ----------------------------
    # Quick + Full run per slot (skips STEP0 fails)
    # ----------------------------
    def start_next_slot_quick(self):
        if self.abort_requested:
            return

        # find next slot that passed step0
        while self.current_slot_idx < len(self.slot_queue):
            slot = self.slot_queue[self.current_slot_idx]
            if self.slot_step0_pass.get(slot, False):
                break
            self.log(f"[AUTO] Slot {slot} skipped (STEP0 FAIL)")
            self.current_slot_idx += 1

        if self.current_slot_idx >= len(self.slot_queue):
            self.finish_all_slots()
            return

        slot = self.slot_queue[self.current_slot_idx]
        self.active_slot = slot
        self.slot_cfg = get_slot_config(slot)

        # open log for this slot
        self.open_slot_log(slot)

        # reset gate results
        self.gate_results = {g: True for g in range(1, 7)}

        self.log(f"[AUTO] Slot {slot} QUICK START")
        self.phase = "quick"
        self.start_sequence([1, 2])

    def start_full_for_active_slot(self):
        slot = self.active_slot
        self.log(f"[AUTO] Slot {slot} FULL START")
        self.phase = "full"
        self.start_sequence([3, 4, 5, 6])

    # ----------------------------
    # Gate function map
    # ----------------------------
    def gate_fn(self, g: int):
        sc = self.slot_cfg
        if g == 1:
            return lambda: run_gate1_power_test(sc, log_cb=self.log)
        if g == 2:
            return lambda: gate2_can_check(sc, log_cb=self.log)
        if g == 3:
            return lambda: run_gate3_termination_check(sc, log_cb=self.log)
        if g == 4:
            return lambda: run_gate4_iul_check(sc, log_cb=self.log)
        if g == 5:
            return lambda: run_gate5_id_check(sc, log_cb=self.log)
        if g == 6:
            def _g6():
                results, logs = run_gate6_pd_load(sc, log_cb=self.log)
                for line in (logs or []):
                    self.log(line)
                return bool((results or {}).get("pass", False))
            return _g6
        raise ValueError(f"Unknown gate {g}")

    # ----------------------------
    # Sequence runner
    # ----------------------------
    def start_sequence(self, gates: list):
        if self.running_gate is not None:
            return
        self.sequence = list(gates)
        self.run_next_gate()

    def run_next_gate(self):
        if self.running_gate is not None or self.abort_requested:
            return

        if not self.sequence:
            self.finish_sequence()
            return

        g = self.sequence.pop(0)
        self.running_gate = g

        slot = self.active_slot
        self.set_slot_widget_running(slot, gate=g, status_text="Running...")

        self.log(f"[GATE {g}] START — {GATE_NAMES[g]} | slot={slot}")

        worker = GateWorker(g, self.gate_fn(g))
        worker.signals.finished.connect(self.on_gate_finished)
        self.threadpool.start(worker)

    def on_gate_finished(self, g: int, ok: bool, err: str):
        slot = self.active_slot

        self.gate_results[g] = bool(ok)
        if err:
            self.log(f"[GATE {g}][ERROR]\n{err}")

        # Update status
        if ok:
            self.slot_widgets[slot].set_status("Running...")  # still running overall
        else:
            self.slot_widgets[slot].set_status("FAIL")

        self.log(f"[GATE {g}] DONE — {'PASS' if ok else 'FAIL'} | slot={slot}")

        self.running_gate = None
        QTimer.singleShot(200, self.run_next_gate)

    def finish_sequence(self):
        slot = self.active_slot

        if self.phase == "quick":
            quick_ok = bool(self.gate_results[1] and self.gate_results[2])
            self.log(f"[AUTO] Slot {slot} QUICK COMPLETE — {'PASS' if quick_ok else 'FAIL'}")

            # store partial results
            self.slot_gate_results.setdefault(slot, {}).update({1: self.gate_results[1], 2: self.gate_results[2]})

            if quick_ok:
                self.start_full_for_active_slot()
                return

            # quick fail -> finalize slot as FAIL
            self.set_slot_widget_result(slot, ok=False)
            self.shutdown_slot_hw("Quick failed")
            self.write_excel_for_slot(slot)
            self.close_slot_log("=== ATP END (Quick FAIL) ===")

            self.current_slot_idx += 1
            QTimer.singleShot(300, self.start_next_slot_quick)
            return

        if self.phase == "full":
            overall = all(bool(self.gate_results[g]) for g in range(1, 7))
            self.log(f"[AUTO] Slot {slot} FULL COMPLETE — {'PASS' if overall else 'FAIL'}")

            # store full results
            self.slot_gate_results[slot] = dict(self.gate_results)

            self.set_slot_widget_result(slot, ok=overall)
            self.shutdown_slot_hw("Full done")
            self.write_excel_for_slot(slot)
            self.close_slot_log("=== ATP END ===")

            self.current_slot_idx += 1
            QTimer.singleShot(300, self.start_next_slot_quick)
            return

        # fallback
        self.phase = "idle"

    # ----------------------------
    # Slot HW end (END_ATP only; relays stay as-is unless STOP)
    # ----------------------------
    def shutdown_slot_hw(self, why=""):
        if why:
            self.log(f"[HW] Slot {self.active_slot} shutdown: {why}")
        try:
            end_atp(self.slot_cfg)
            self.log("[HW] END_ATP sent")
        except Exception as e:
            self.log(f"[HW][WARN] END_ATP failed: {e}")

    # ----------------------------
    # Excel per slot
    # ----------------------------
    def write_excel_for_slot(self, slot: int):
        ts = self.session_ts or datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        sn = self.slot_serials.get(slot, "NO_SN")
        sn_safe = self.sanitize_for_filename(sn)
        path = os.path.join(self.logs_dir, f"ATP_S{slot}_{sn_safe}_{ts}.xlsx")

        wb = Workbook()
        ws = wb.active
        ws.title = "Gate Results"

        ws.append(["Slot", slot])
        ws.append(["Serial", sn])
        ws.append([])
        ws.append(["Gate", "Gate Name", "Result"])
        for cell in ws[4]:
            cell.font = Font(bold=True)

        # Build per-slot results from stored dict, fallback to current gate_results if active slot
        results = self.slot_gate_results.get(slot)
        if results is None and slot == self.active_slot:
            results = dict(self.gate_results)
        results = results or {}

        for g in range(1, 7):
            val = results.get(g, None)
            if val is None:
                res_txt = "SKIP"
            else:
                res_txt = "PASS" if bool(val) else "FAIL"
            ws.append([g, GATE_NAMES[g], res_txt])

        wb.save(path)
        self.log(f"[FILE] Excel written: {path}")

    # ----------------------------
    # Finish all slots
    # ----------------------------
    def finish_all_slots(self):
        self.phase = "idle"
        self.ui["btn_start"].setEnabled(True)
        self.set_instruction("✅ Session complete.\nClick Start New Session for next batch of 4.")

        self.log("[AUTO] ✅ Session COMPLETE (all slots processed)")

    # ----------------------------
    # Stop / shutdown
    # ----------------------------
    def stop_test(self):
        self.abort_requested = True
        self.log("[UI] STOPPED")

        # Best-effort: END_ATP current slot
        try:
            self.shutdown_slot_hw("User pressed Stop")
        except Exception:
            pass

        # Power OFF all relays
        try:
            relay_off_all(log_cb=self.log)
            self.log("[HW] ✅ All relays OFF")
        except Exception as e:
            self.log(f"[HW][WARN] relay_off_all failed: {e}")

        self.sequence = []
        self.running_gate = None
        self.phase = "idle"

        self.close_slot_log("=== ATP ABORTED ===")

        # Update UI
        self.ui["btn_start"].setEnabled(True)
        self.set_instruction("❌ Aborted.\nFix hardware and click Start New Session again.")

    def closeEvent(self, e):
        self.abort_requested = True
        try:
            relay_off_all(log_cb=self.log)
        except Exception:
            pass
        e.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
