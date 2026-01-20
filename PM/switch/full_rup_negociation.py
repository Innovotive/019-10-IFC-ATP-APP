#!/usr/bin/env python3
import time
import json
from pm125 import PM125
from PM.switch.power_negociation import run_gate7
from acroname_switch import select_rup, sw

WAIT_FOR_PD = 5


def test_single_rup(port: int, pm: PM125) -> bool:
    print("\n=======================================")
    print(f"        TESTING RUP ON PORT {port}       ")
    print("=======================================\n")

    select_rup(port)

    try:
        mux_state = sw.mux.getChannel().value
        print(f"✓ Acroname mux channel = {mux_state}")
    except Exception:
        print("⚠ Cannot read mux channel")

    print("→ Waiting for PD negotiation...")
    time.sleep(WAIT_FOR_PD)

    print("\n→ PM125 status BEFORE tests:")
    print("Status:", pm.get_connection_status())
    print("Stats:", pm.get_statistics())

    gate7_ok = run_gate7(pm)
    print(f"[GATE 7] RESULT: {'PASS' if gate7_ok else 'FAIL'}")

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
    print("\n=== JSON_RESULT ===")
    print(json.dumps(results))
