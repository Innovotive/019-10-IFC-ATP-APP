#!/usr/bin/env python3
import time
import json
from pm125 import PM125
from power_negociation import run_gate7
from acroname_switch import select_rup, sw

WAIT_FOR_PD = 5  # seconds


def test_single_rup(port: int, pm: PM125) -> bool:
    print("\n=======================================")
    print(f"        TESTING RUP ON PORT {port}       ")
    print("=======================================\n")

    # 1️⃣ Switch Acroname
    select_rup(port)

    try:
        mux_state = sw.mux.getChannel().value
        print(f"✓ Acroname mux channel = {mux_state}")
    except Exception:
        print("⚠ Cannot read mux channel")

    # 2️⃣ Wait PD
    print("→ Waiting for PD negotiation...")
    time.sleep(WAIT_FOR_PD)

    # 3️⃣ PM125 status
    print("\n→ PM125 status BEFORE tests:")
    print("Status:", pm.get_connection_status())
    print("Stats:", pm.get_statistics())

    # 4️⃣ Gate 7 — REAL RESULT
    print("\n=======================================")
    print("        STARTING GATE 7 (PDO TEST)       ")
    print("=======================================\n")

    gate7_ok = run_gate7(pm)
    print(f"[GATE 7] RESULT: {'PASS' if gate7_ok else 'FAIL'}")

    print(f"✔ Completed tests for RUP {port}\n")
    return gate7_ok


def test_all_rups() -> dict:
    pm = PM125()
    results = {}

    for port in [0, 1, 2, 3]:
        print(f"\n########## START RUP {port} ##########")
        ok = test_single_rup(port, pm)
        results[port + 1] = ok
        print(f"########## END   RUP {port} ##########\n")
        time.sleep(2)

    print("\n===== ALL RUP NEGOTIATION TESTS COMPLETE =====")
    print("FINAL RESULTS:", results)

    return results


if __name__ == "__main__":
    results = test_all_rups()

    # 🔑 CRITICAL: machine-readable output for UI
    print("\n=== JSON_RESULT ===")
    print(json.dumps(results))
