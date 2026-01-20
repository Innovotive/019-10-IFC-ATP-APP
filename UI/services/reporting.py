# services/reporting.py
import os
import datetime
from typing import Callable, Dict

from openpyxl import Workbook
from openpyxl.styles import Font


class Reporter:
    def __init__(self, logs_dir: str, log_cb: Callable[[str], None]):
        self.logs_dir = logs_dir
        self.log_cb = log_cb
        os.makedirs(self.logs_dir, exist_ok=True)

        self.log_file = None
        self.session_ts = None
        self.log_path = None

    def open_session(self, rup_ids: Dict[int, str]) -> None:
        self.close_session()

        self.session_ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        ids_str = "_".join([(rup_ids[i] or "NA") for i in range(1, 5)])
        self.log_path = os.path.join(self.logs_dir, f"ATP_{ids_str}_{self.session_ts}.log")
        self.log_file = open(self.log_path, "w")

        self.write_line("[INIT] Session opened")
        self.write_line(f"=== ATP START — IDs: {rup_ids} ===")
        self.write_line(f"[FILE] Log created: {self.log_path}")

    def write_line(self, line: str) -> None:
        # This function expects the caller to add timestamps if desired.
        if self.log_file:
            self.log_file.write(line + "\n")
            self.log_file.flush()

    def close_session(self) -> None:
        if self.log_file:
            try:
                self.log_file.close()
            except Exception:
                pass
        self.log_file = None
        self.log_path = None

    def write_excel_results(self, gate_results: Dict[int, Dict[int, bool]], rup_ids: Dict[int, str]) -> str:
        ts = self.session_ts or datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        ids_str = "_".join([(rup_ids[i] or "NA") for i in range(1, 5)])
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
                ["PASS" if bool(gate_results[g][r]) else "FAIL" for r in range(1, 5)]
            )

        wb.save(path)
        return path
