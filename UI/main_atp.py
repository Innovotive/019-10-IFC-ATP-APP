#!/usr/bin/env python3
# main_atp.py

import sys
import os
import datetime
import traceback

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QInputDialog

from ui_atp import Ui_MainWindow

from services.hardware import HardwareController
from services.reporting import Reporter

from runners.quick_runner import QuickRunner
from runners.full_runner import FullRunner

from tests.gate1_power_passthrough import run_gate1_power_test as run_gate1_power_detect_check
from tests.gate2_CAN_check import gate2_can_check as run_gate2_id_pins_can_check
from tests.gate3_TR import run_gate3_all_ordered as run_gate3_all_slots
from tests.gate4_iul_check import run_gate4_iul_check
from tests.gate5_ID_check import gate5_id_check as run_gate5_id_config_check
from tests.gate6_pdo import run_gate6

SLOTS = (1, 2, 3, 4)
LOG_DIR = "ATP_logs"


class MainATP(QMainWindow):
    def __init__(self):
        super().__init__()

        # ---------- UI ----------
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        os.makedirs(LOG_DIR, exist_ok=True)

        # ---------- STATE ----------
        self.slot_ids = {s: None for s in SLOTS}
        self.slot_inserted = {s: False for s in SLOTS}
        self.relays_are_on = False

        # gate_results[gate][slot] = True / False / None
        self.gate_results = {g: {s: None for s in SLOTS} for g in (1, 2, 3, 4, 5, 6)}

        # ---------- HARDWARE ----------
        self.hw = HardwareController(log_cb=self.log)

        # ---------- REPORTER ----------
        self.reporter = self._make_reporter()

        # ---------- RUNNERS (exact signatures) ----------
        self.quick = QuickRunner(
            hw=self.hw,
            log_cb=self.log,
            gate1_fn=run_gate1_power_detect_check,
            gate2_fn=run_gate2_id_pins_can_check,
            on_update=self.on_quick_update,
        )

        self.full = FullRunner(
            log_cb=self.log,
            on_update=self.on_full_update,
            run_gate3_all_fn=run_gate3_all_slots,
            run_gate4_bool_fn=run_gate4_iul_check,
            run_gate5_bool_fn=run_gate5_id_config_check,
            run_gate6_bool_fn=run_gate6,
            slots=list(SLOTS),
        )

        # ---------- UI CONNECTIONS (MATCH ui_atp.py NAMES) ----------
        self.ui.btn_start.clicked.connect(self.on_start_setup_clicked)
        self.ui.btn_quick.clicked.connect(self.on_quick_clicked)
        self.ui.btn_full.clicked.connect(self.on_full_clicked)
        self.ui.btn_stop.clicked.connect(self.on_stop_clicked)

        # Optional: disable until setup
        self.ui.btn_quick.setEnabled(False)
        self.ui.btn_full.setEnabled(False)

        # ---------- TIMER for QuickRunner stepping ----------
        self.timer = QTimer(self)
        self.timer.setInterval(60)  # ms
        self.timer.timeout.connect(self.tick)
        self.timer.start()

        # ---------- STARTUP ----------
        self.log("=== ATP START ===")

        try:
            if hasattr(self.hw, "init_id_pins_startup_all_slots"):
                self.hw.init_id_pins_startup_all_slots()
            elif hasattr(self.hw, "init_id_pins_all_slots"):
                self.hw.init_id_pins_all_slots()
        except Exception as e:
            self.log(f"[HW][WARN] ID pin init failed: {e}")

        try:
            self.hw.select_slot(1)
        except Exception:
            pass

    # =========================================================
    # REPORTER
    # =========================================================
    def _make_reporter(self):
        try:
            return Reporter(LOG_DIR, log_cb=self.log)
        except TypeError:
            pass
        try:
            return Reporter(LOG_DIR)
        except TypeError:
            pass
        try:
            return Reporter(log_cb=self.log)
        except TypeError:
            pass
        return Reporter()

    # =========================================================
    # LOG
    # =========================================================
    def log(self, msg: str):
        ts = datetime.datetime.now().strftime("[%H:%M:%S]")
        line = f"{ts} {msg}"
        print(line)
        try:
            self.ui.log_box.append(line)  # ✅ matches ui_atp.py
        except Exception:
            pass

    # =========================================================
    # SETUP
    # =========================================================
    def on_start_setup_clicked(self):
        self.log("[UI] Guided Setup START")

        for s in SLOTS:
            rid, ok = QInputDialog.getText(self, "RUP ID", f"Enter RUP ID for Slot {s}:")
            if not ok or not rid.strip():
                QMessageBox.warning(self, "Setup", f"Missing ID for Slot {s}")
                return

            self.slot_ids[s] = rid.strip()
            self.slot_inserted[s] = True  # your UI asks insertion confirm before; you can re-add if you want

            # Update slot widget title
            try:
                self.ui.slots[s - 1].set_rup_id(rid.strip())
                self.ui.slots[s - 1].set_status("Ready")
                self.ui.slots[s - 1].set_led("yellow")
            except Exception:
                pass

            self.log(f"[SETUP] Slot{s} ID = {rid.strip()}")

        self.ui.btn_quick.setEnabled(True)
        self.ui.btn_full.setEnabled(True)

        self.log("[UI] Setup COMPLETE")

    # =========================================================
    # QUICK TEST
    # =========================================================
    def on_quick_clicked(self):
        if not all(self.slot_inserted.values()):
            QMessageBox.warning(self, "Quick Test", "Run Start ATP first.")
            return

        self.log("[UI] Quick Test START")
        try:
            self.quick.start()
        except Exception as e:
            self.log(f"[QUICK][ERROR] {e}")
            self.log(traceback.format_exc())

    # =========================================================
    # FULL TEST
    # =========================================================
    def on_full_clicked(self):
        if not all(self.slot_inserted.values()):
            QMessageBox.warning(self, "Full ATP", "Run Start ATP first.")
            return

        self.log("[UI] Full ATP START")

        # Power ON only if needed
        try:
            if not self.relays_are_on:
                self.log("[FULL] Powering ON relays once")
                if hasattr(self.hw, "power_on_all_relays_and_check"):
                    self.relays_are_on = bool(self.hw.power_on_all_relays_and_check())
                elif hasattr(self.hw, "power_on_all_rups"):
                    self.relays_are_on = bool(self.hw.power_on_all_rups())
        except Exception as e:
            self.log(f"[FULL][WARN] Relay ON failed: {e}")

        # FullRunner is synchronous
        try:
            results = self.full.run()
            for gate in (3, 4, 5, 6):
                for s in SLOTS:
                    self.gate_results[gate][s] = bool(results.get(gate, {}).get(s, False))

            self.log("[UI] Full ATP COMPLETE")
            self.on_atp_complete()
        except Exception as e:
            self.log(f"[FULL][ERROR] {e}")
            self.log(traceback.format_exc())

    # =========================================================
    # STOP
    # =========================================================
    def on_stop_clicked(self):
        self.log("[UI] STOP clicked")
        self.shutdown("User stopped")
        QMessageBox.information(self, "ATP", "Stopped.")

    # =========================================================
    # TICK: advance QuickRunner
    # =========================================================
    def tick(self):
        try:
            if getattr(self.quick, "active", False) and not getattr(self.quick, "done", False):
                done = bool(self.quick.step())
                if done:
                    for s in SLOTS:
                        self.gate_results[1][s] = bool(self.quick.results[1].get(s, False))
                        self.gate_results[2][s] = bool(self.quick.results[2].get(s, False))
                    self.relays_are_on = True
                    self.log("[UI] Quick Test COMPLETE")
        except Exception as e:
            self.log(f"[QUICK][ERROR] {e}")
            self.log(traceback.format_exc())

    # =========================================================
    # RUNNER CALLBACKS -> update UI SlotWidgets
    # =========================================================
    def on_quick_update(self, upd):
        # upd: slot, gate, status, led
        s = getattr(upd, "slot", None)
        g = getattr(upd, "gate", None)
        st = getattr(upd, "status", "")
        led = getattr(upd, "led", None)

        if s in SLOTS:
            try:
                w = self.ui.slots[s - 1]
                w.set_gate(g if g else 0)
                w.set_status(st)
                if led:
                    w.set_led(led)
            except Exception:
                pass

        if g in (1, 2) and s in SLOTS and st in ("PASS", "FAIL"):
            self.gate_results[g][s] = (st == "PASS")

    def on_full_update(self, upd):
        # upd: gate, slot, status, led
        s = getattr(upd, "slot", None)
        g = getattr(upd, "gate", None)
        st = getattr(upd, "status", "")
        led = getattr(upd, "led", None)

        if s in SLOTS:
            try:
                w = self.ui.slots[s - 1]
                w.set_gate(g if g else 0)
                w.set_status(st)
                if led:
                    w.set_led(led)
            except Exception:
                pass

        if g in (3, 4, 5, 6) and s in SLOTS and st in ("PASS", "FAIL"):
            self.gate_results[g][s] = (st == "PASS")

    # =========================================================
    # END ATP
    # =========================================================
    def on_atp_complete(self):
        try:
            if hasattr(self.reporter, "write_excel"):
                path = self.reporter.write_excel(slot_ids=self.slot_ids, gate_results=self.gate_results)
                self.log(f"[FILE] Excel written: {path}")
        except Exception as e:
            self.log(f"[FILE][ERROR] {e}")

        self.shutdown("ATP complete")

    def shutdown(self, reason=""):
        self.log(f"[HW] Shutdown ({reason})")

        try:
            if hasattr(self.hw, "power_off_all_relays"):
                self.hw.power_off_all_relays()
        except Exception:
            pass

        try:
            if hasattr(self.hw, "send_end_atp"):
                self.hw.send_end_atp()
        except Exception:
            pass

        try:
            if hasattr(self.hw, "close_can_bus_cleanly"):
                self.hw.close_can_bus_cleanly()
        except Exception:
            pass

    def closeEvent(self, event):
        self.shutdown("Window closed")
        event.accept()


def main():
    app = QApplication(sys.argv)
    w = MainATP()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
