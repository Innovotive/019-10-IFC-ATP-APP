#!/usr/bin/env python3
# main_atp_1rup.py — 1-RUP ATP (GPIO8 IDCFG relay + GPIO25 POWER relay)

import time

from tests.power_PT.relay import (
    idcfg_on, idcfg_off,
    power_on, power_off,
    relay_close
)

from tests.gate1_can_check import run_gate1_can_check
from tests.gate2_tr_check import run_gate2_termination_check
from tests.gate3_id_flip_check import run_gate3_id_flip_check
from tests.gate4_pd_load import run_gate4_pd_load


# -----------------------------
# CONFIG (EDIT THESE)
# -----------------------------
EXPECTED_IDCFG_ON  = {0x00}   # when GPIO8 relay is ON (initial config)
EXPECTED_IDCFG_OFF = {0x01}   # when GPIO8 relay is OFF (flipped config)  <-- adjust


def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def main():
    log("========== 1-RUP ATP START ==========")

    sn = input("Enter RUP Serial Number: ").strip()
    if not sn:
        log("[ERROR] Serial number is empty. Abort.")
        return

    results = {}

    try:
        # --------------------------------
        # STEP A: set ID config + power ON
        # --------------------------------
        log("[HW] IDCFG relay ON (GPIO8) -> set initial ID configuration")
        idcfg_on()
        time.sleep(0.3)

        log("[HW] POWER relay ON (GPIO25) -> RUP ON")
        power_on()
        time.sleep(1.0)

        # -----------------------------
        # GATE 1: CAN communication
        # -----------------------------
        log("---- GATE 1: CAN check (START_ATP + ID read) ----")
        ok = run_gate1_can_check(expected_values=EXPECTED_IDCFG_ON, log_cb=log)
        results["gate1_can"] = ok
        if not ok:
            log("[FAIL] Gate1 failed -> stopping.")
            return

        # -----------------------------
        # GATE 2: Termination resistor
        # -----------------------------
        log("---- GATE 2: TR check ----")
        ok = run_gate2_termination_check(log_cb=log)
        results["gate2_tr"] = ok
        if not ok:
            log("[FAIL] Gate2 failed -> stopping.")
            return

        # -----------------------------
        # GATE 3: ID flip check (GPIO8 OFF)
        # -----------------------------
        log("---- GATE 3: ID flip check (GPIO8 OFF) ----")
        ok = run_gate3_id_flip_check(
            expected_values_after_flip=EXPECTED_IDCFG_OFF,
            log_cb=log
        )
        results["gate3_idflip"] = ok
        if not ok:
            log("[FAIL] Gate3 failed -> stopping.")
            return

        # -----------------------------
        # GATE 4: PDO / PM125 power check
        # -----------------------------
        log("---- GATE 4: PDO check (PM125) ----")
        ok = run_gate4_pd_load(log_cb=log)
        results["gate4_pdo"] = ok
        if not ok:
            log("[FAIL] Gate4 failed.")
            return

        log("✅ ALL GATES PASS")

    finally:
        # Always power off
        log("[HW] POWER OFF (GPIO25)")
        try:
            power_off()
        except Exception:
            pass

        # Put ID config back to known state (optional)
        log("[HW] IDCFG back ON (GPIO8) (optional baseline)")
        try:
            idcfg_on()
        except Exception:
            pass

        try:
            relay_close()
        except Exception:
            pass

        log(f"Session end | SN={sn} | results={results}")
        log("========== 1-RUP ATP END ==========")


if __name__ == "__main__":
    main()
