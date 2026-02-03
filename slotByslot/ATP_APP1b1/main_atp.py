#!/usr/bin/env python3
# main_atp.py — RUP ATP (4-Slot Dashboard) — 1-by-1 POWERED slots
#
# Updates:
# - Adds GATE0 (Step0): operator confirms Guide Light blinking (PASS/FAIL popup)
# - Serial numbers must be unique across the 4 slots (case-insensitive)
# - Excel + UI include Gate0 results
# - If Gate0 FAIL => skip gates 1..6 for that slot (slot FAIL)

import sys
import os
import re
import datetime
import traceback

from PyQt5.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool, QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QInputDialog

from openpyxl import Workbook
from openpyxl.styles import Font

from ui_layout import build_ui
from slot_config import get_slot_config, SlotConfig

# ID pins
from tests.ID.id_pins_init import init_id_pins_for_slot, force_id_pins_off_for_slot

# Relays
from tests.power_PT.relay import relay_on, relay_off

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
    0: "Guide Light Blink Check",
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
# Worker infra (for Gate1..Gate6 only)
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
        self.powered_slot = None  # track which slot is currently ON

        self.slot_queue = [1, 2, 3, 4]
        self.current_slot_idx = 0

        self.slot_serials = {}         # {slot: sn_raw}
        self.used_serials_norm = set() # set of normalized SNs (upper) for uniqueness
        self.slot_gate_results = {}    # {slot: {gate: bool}}

        # Per-slot run state
        self.slot_cfg: SlotConfig = get_slot_config(1)

        self.running_gate = None
        self.sequence = []
        self.phase = "idle"  # idle|running

        # gate results includes gate0..6
        self.gate_results = {g: True for g in range(0, 7)}

        # Startup init
        self._startup_hw_init()

        # Initialize UI state
        self.reset_ui_state()

    # ----------------------------
    # Startup HW init
    # ----------------------------
    def _startup_hw_init(self):
        # Best-effort: power OFF all slots + force ID=000 for all
        for s in (1, 2, 3, 4):
            try:
                sc = get_slot_config(s)
                relay_off(sc, log_cb=self.log)
            except Exception as e:
                self.log(f"[INIT][WARN] relay_off slot={s} failed: {e}")
            try:
                force_id_pins_off_for_slot(s)
            except Exception as e:
                self.log(f"[INIT][WARN] force_id_off slot={s} failed: {e}")

        self.powered_slot = None
        self.log("[INIT] Startup: relays OFF + ID pins forced 000 (best-effort)")

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
        self.used_serials_norm = set()
        self.slot_gate_results = {}

        for s in (1, 2, 3, 4):
            sw = self.slot_widgets[s]
            sw.set_led("gray")
            sw.set_status("Idle")
            sw.set_gate(0, "")

        self.set_instruction(
            "Slot-by-slot ATP:\n"
            "• For each slot: set ID -> relay ON -> Gate0 (Guide Light) -> gates -> relay OFF -> ID=000\n"
            "• Only one slot is powered at a time\n"
        )

        self.ui["btn_start"].setEnabled(True)
        self.ui["btn_stop"].setEnabled(True)

    def set_slot_widget_running(self, slot: int, gate: int, status_text="Running..."):
        sw = self.slot_widgets[slot]
        sw.set_led("yellow")
        sw.set_status(status_text)
        sw.set_gate(gate, GATE_NAMES.get(gate, ""))

    def set_slot_widget_result(self, slot: int, ok: bool):
        sw = self.slot_widgets[slot]
        sw.set_led("green" if ok else "red")
        sw.set_status("PASS" if ok else "FAIL")

    def sanitize_for_filename(self, s: str) -> str:
        s = (s or "").strip()
        s = re.sub(r"[^A-Za-z0-9\-_]+", "_", s)
        return s[:64] if s else "NO_SN"

    # ----------------------------
    # Serial prompt (unique SN)
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

            sn_norm = sn.upper()
            # Uniqueness check across all slots (case-insensitive)
            if sn_norm in self.used_serials_norm:
                QMessageBox.warning(
                    self,
                    "Duplicate Serial",
                    f"This serial number was already used in this session.\n\nSN: {sn}\n\nEnter a different SN."
                )
                continue

            # store
            self.slot_serials[slot] = sn
            self.used_serials_norm.add(sn_norm)
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
        self.used_serials_norm = set()
        self.slot_gate_results = {}
        self.current_slot_idx = 0

        for s in (1, 2, 3, 4):
            sw = self.slot_widgets[s]
            sw.set_led("gray")
            sw.set_status("Idle")
            sw.set_gate(0, "")

        # Ask serials for all 4 upfront (with uniqueness enforcement)
        for s in (1, 2, 3, 4):
            if not self.prompt_serial_for_slot(s):
                self.stop_test()
                return

        self.phase = "running"
        QTimer.singleShot(200, self.start_next_slot)

    # ----------------------------
    # Slot prepare: ID then power ON
    # ----------------------------
    def prepare_slot(self, slot: int) -> bool:
        # Safety: if some other slot was ON, turn it OFF and force its IDs low
        if self.powered_slot is not None and self.powered_slot != slot:
            try:
                prev_cfg = get_slot_config(self.powered_slot)
                relay_off(prev_cfg, log_cb=self.log)
            except Exception as e:
                self.log(f"[PWR][WARN] relay_off prev slot {self.powered_slot} failed: {e}")
            try:
                force_id_pins_off_for_slot(self.powered_slot)
            except Exception as e:
                self.log(f"[ID][WARN] force_id_off prev slot {self.powered_slot} failed: {e}")
            self.powered_slot = None

        # 1) Set ID pins for this slot (pattern)
        if not init_id_pins_for_slot(slot):
            self.log(f"[ID][FAIL] init_id_pins_for_slot({slot})")
            return False
        self.log(f"[ID] Slot {slot} ID pattern applied")

        # 2) Relay ON this slot
        self.slot_cfg = get_slot_config(slot)
        try:
            relay_on(self.slot_cfg, log_cb=self.log)
            self.powered_slot = slot
            self.log(f"[PWR] Slot {slot} relay ON (GPIO {self.slot_cfg.relay_gpio})")
            return True
        except Exception as e:
            self.log(f"[PWR][FAIL] relay_on slot {slot}: {e}")
            return False

    # ----------------------------
    # Gate0 popup: Guide light blinking
    # ----------------------------
    def run_gate0_guidelight(self, slot: int) -> bool:
        # UI + operator confirmation popup (PASS / FAIL)
        self.set_slot_widget_running(slot, gate=0, status_text="Waiting operator...")

        self.log(f"[GATE 0] START — {GATE_NAMES[0]} | slot={slot}")
        self.set_instruction(
            "👀 Step 0 (Gate0): Check the RUP Guide Light.\n"
            "Confirm it is BLINKING, then choose PASS or FAIL."
        )

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Gate0 — Guide Light Check")
        box.setText(
            f"Slot {slot}:\n\n"
            "Please CHECK the Guide Light on the RUP board.\n"
            "Is it BLINKING?"
        )
        btn_pass = box.addButton("PASS", QMessageBox.AcceptRole)
        btn_fail = box.addButton("FAIL", QMessageBox.RejectRole)
        box.setDefaultButton(btn_pass)

        box.exec_()
        clicked = box.clickedButton()
        ok = (clicked == btn_pass)

        self.log(f"[GATE 0] DONE — {'PASS' if ok else 'FAIL'} | slot={slot}")
        return ok

    # ----------------------------
    # Slot finish: END_ATP -> relay OFF -> ID=000
    # ----------------------------
    def finish_slot_power(self, why=""):
        slot = self.active_slot
        if why:
            self.log(f"[HW] Slot {slot} finish: {why}")

        # END_ATP best-effort
        try:
            end_atp(self.slot_cfg)
            self.log("[HW] END_ATP sent")
        except Exception as e:
            self.log(f"[HW][WARN] END_ATP failed: {e}")

        # Relay OFF this slot
        try:
            relay_off(self.slot_cfg, log_cb=self.log)
            self.log(f"[PWR] Slot {slot} relay OFF")
        except Exception as e:
            self.log(f"[PWR][WARN] relay_off(slot={slot}) failed: {e}")

        # Force ID pins to 000 for true power-down
        try:
            force_id_pins_off_for_slot(slot)
            self.log(f"[ID] Slot {slot} ID pins forced LOW (000)")
        except Exception as e:
            self.log(f"[ID][WARN] force_id_pins_off_for_slot(slot={slot}) failed: {e}")

        self.powered_slot = None

    # ----------------------------
    # Run slots sequentially
    # ----------------------------
    def start_next_slot(self):
        if self.abort_requested:
            return

        if self.current_slot_idx >= len(self.slot_queue):
            self.finish_all_slots()
            return

        slot = self.slot_queue[self.current_slot_idx]
        self.active_slot = slot
        self.slot_cfg = get_slot_config(slot)

        self.open_slot_log(slot)

        # reset gate results for this slot (Gate0..Gate6)
        self.gate_results = {g: True for g in range(0, 7)}

        self.log(f"[SLOT] START slot={slot}")

        # Prepare slot (ID -> ON)
        if not self.prepare_slot(slot):
            self.log(f"[SLOT][FAIL] Prepare failed slot={slot}")
            self.set_slot_widget_result(slot, ok=False)
            self.slot_gate_results[slot] = {g: False for g in range(0, 7)}
            self.write_excel_for_slot(slot)
            self.close_slot_log("=== ATP END (Prepare FAIL) ===")
            self.finish_slot_power("Prepare failed")
            self.current_slot_idx += 1
            QTimer.singleShot(250, self.start_next_slot)
            return

        # Boot settle, then Gate0 popup
        QTimer.singleShot(600, self.run_gate0_then_continue)

    def run_gate0_then_continue(self):
        if self.abort_requested:
            return

        slot = self.active_slot

        ok0 = self.run_gate0_guidelight(slot)
        self.gate_results[0] = bool(ok0)

        if not ok0:
            # Gate0 fail => skip remaining gates
            self.log(f"[SLOT] Gate0 FAIL => skipping Gate1..Gate6 | slot={slot}")

            # mark remaining as False (so Excel shows FAIL)
            for g in range(1, 7):
                self.gate_results[g] = False

            self.finish_sequence()  # uses current gate_results (includes Gate0)
            return

        # Gate0 pass => continue with Gate1..Gate6
        QTimer.singleShot(150, lambda: self.start_sequence([1, 2, 3, 4, 5, 6]))

    # ----------------------------
    # Gate function map (Gate1..Gate6)
    # ----------------------------
    def gate_fn(self, g: int):
        sc = self.slot_cfg
        if g == 1:
            return lambda: run_gate1_power_test(sc, log_cb=self.log)
        if g == 2:
            return lambda: gate2_can_check(sc, log_cb=self.log)
        if g == 3:
            return lambda: run_gate3_termination_check(sc, log_cb=self.log)
        # if g == 4:
        #     return lambda: run_gate4_iul_check(sc, log_cb=self.log)
        if g == 4:
            # BYPASS: In-Use Light check not required in this version
            def _g4_bypass():
                self.log(f"[GATE 4] BYPASS — auto PASS (IUL not required)")
                return True
            return _g4_bypass

        if g == 5:
            return lambda: run_gate5_id_check(sc, log_cb=self.log)
        if g == 6:
            def _g6():
                # run inside PM venv via subprocess, for the active slot
                results, _logs = run_gate6_pd_load(sc.slot, log_cb=self.log)
                return bool((results or {}).get("pass", False))
            return _g6

        raise ValueError(f"Unknown gate {g}")

    # ----------------------------
    # Sequence runner (Gate1..Gate6)
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

        self.log(f"[GATE {g}] DONE — {'PASS' if ok else 'FAIL'} | slot={slot}")

        self.running_gate = None
        QTimer.singleShot(150, self.run_next_gate)

    def finish_sequence(self):
        slot = self.active_slot
        overall = all(bool(self.gate_results[g]) for g in range(0, 7))

        self.log(f"[SLOT] COMPLETE slot={slot} — {'PASS' if overall else 'FAIL'}")
        self.slot_gate_results[slot] = dict(self.gate_results)

        self.set_slot_widget_result(slot, ok=overall)
        self.write_excel_for_slot(slot)
        self.close_slot_log("=== ATP END ===")

        # Power down (relay OFF + ID=000)
        self.finish_slot_power("slot done")

        self.current_slot_idx += 1
        QTimer.singleShot(250, self.start_next_slot)

    # ----------------------------
    # Excel per slot (Gate0..Gate6)
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

        results = self.slot_gate_results.get(slot, {}) or {}
        for g in range(0, 7):
            val = results.get(g, None)
            res_txt = "PASS" if bool(val) else "FAIL"
            ws.append([g, GATE_NAMES.get(g, ""), res_txt])

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

        # Ensure any powered slot is fully off
        if self.powered_slot is not None:
            try:
                sc = get_slot_config(self.powered_slot)
                relay_off(sc, log_cb=self.log)
            except Exception:
                pass
            try:
                force_id_pins_off_for_slot(self.powered_slot)
            except Exception:
                pass
            self.powered_slot = None

    # ----------------------------
    # Stop / shutdown
    # ----------------------------
    def stop_test(self):
        self.abort_requested = True
        self.log("[UI] STOPPED")

        # fully power down current slot
        try:
            self.finish_slot_power("User pressed Stop")
        except Exception:
            pass

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
            self.finish_slot_power("App closed")
        except Exception:
            pass
        e.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
