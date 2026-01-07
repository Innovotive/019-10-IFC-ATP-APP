# ============================================================
# pm125_driver.py  — PM125 Linux driver with SET_CONFIG support
# Adds: set_max_current()
# ============================================================

import serial
import time

class PM125Error(Exception):
    pass

class PM125Timeout(PM125Error):
    pass


class PM125:

    # -------------------------------
    # Command IDs (same as firmware)
    # -------------------------------
    GET_DEV_INFO            = 0x01
    GET_CONSTAT             = 0x0A
    GET_PORT_CAPABILITIES   = 0x0B
    GET_STAT                = 0x0C
    SET_PORT_VOLTAGE        = 0x0D
    SET_DEF_VOLTAGE         = 0x0E
    SET_DEF_CURRENT         = 0x0F
    SET_CURRENT             = 0x10
    SET_CURRENT_FAST        = 0x11
    SET_DEF_PROFILE         = 0x12
    GET_STEP_RESPONSE       = 0x13
    SET_USB_CONNECTION      = 0x14
    INJECT_PD_MSG           = 0x15
    INJECT_PD_MSG_RAW       = 0x16

    # NEW CONFIG COMMANDS
    SET_CONFIG              = 0xE0
    GET_CONFIG              = 0xE1
    CFG_SET_MAX_CURRENT     = 0x01   # <--- IMPORTANT
    FORCE_LIMIT             = 0x01

    def __init__(self, port="/dev/ttyUSB0", baudrate=115200, timeout=1.0):

        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
            bytesize=8,
            parity=serial.PARITY_NONE,
            stopbits=1,
        )

        self.ser.dtr = False
        self.ser.rts = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, tb):
        self.close()

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    # -------------------------------
    # Internal helpers
    # -------------------------------

    @staticmethod
    def _checksum(data):
        chk = 0
        for b in data:
            chk ^= b
        chk ^= 0x03
        return chk & 0xFF

    def _build_frame(self, cmd, payload):
        payload = payload or []
        length = 1 + len(payload)     # CMD + payload

        core = [0x02, length, cmd] + payload
        chk = self._checksum(core)
        frame = core + [chk, 0x03]
        return bytes(frame)

    def _read_frame(self):
        s = self.ser

        # Wait for 0x02
        while True:
            b = s.read(1)
            if not b:
                raise PM125Timeout("Timeout waiting for frame start.")
            if b[0] == 0x02:
                break

        # Length byte
        b = s.read(1)
        if not b:
            raise PM125Timeout("Timeout reading LEN.")
        data_len = b[0]

        # CMD + PAYLOAD + CHK + END
        rest = s.read(data_len + 2)
        if len(rest) != data_len + 2:
            raise PM125Timeout("Timeout reading frame body.")

        cmd = rest[0]
        payload = list(rest[1:data_len])
        chk = rest[data_len]
        end = rest[data_len + 1]

        if end != 0x03:
            raise PM125Error("Bad frame terminator.")

        # Verify checksum
        core = [0x02, data_len, cmd] + payload
        if chk != self._checksum(core):
            raise PM125Error("Checksum mismatch.")

        return cmd, payload

    def _send(self, cmd, payload=None, expect=None):
        frame = self._build_frame(cmd, payload)
        self.ser.reset_input_buffer()
        self.ser.write(frame)
        resp_cmd, data = self._read_frame()

        if expect is not None and resp_cmd != expect:
            raise PM125Error(
                f"Unexpected response 0x{resp_cmd:02X} (expected 0x{expect:02X})"
            )
        return resp_cmd, data

    # -------------------------------
    # High level API
    # -------------------------------

    def get_dev_info(self):
        _, d = self._send(self.GET_DEV_INFO, expect=self.GET_DEV_INFO)
        return d[0], d[1]

    def get_statistics(self):
        _, d = self._send(self.GET_STAT, expect=self.GET_STAT)
        return {
            "status": d[0],
            "temperature_c": d[1],
            "voltage_mv": d[2] | (d[3] << 8),
            "set_current_ma": d[4] | (d[5] << 8),
            "current_ma": d[6] | (d[7] << 8),
            "loopback_current_ma": d[8] | (d[9] << 8),
        }

    def get_connection_status(self):
        _, d = self._send(self.GET_CONSTAT, expect=self.GET_CONSTAT)
        return {
            "port_status": d[0],
            "profile_index": d[1],
            "profile": d[2],
            "profile_subtype": d[3],
            "voltage_mv": d[4] | (d[5] << 8),
            "max_current_ma": d[6] | (d[7] << 8),
            "max_power_mw": (
                d[8] | (d[9] << 8) | (d[10] << 16) | (d[11] << 24)
            )
        }

    # -------------------------------
    # BASIC COMMANDS
    # -------------------------------

    def set_voltage(self, profile_index, voltage_mv):
        lsb = voltage_mv & 0xFF
        msb = (voltage_mv >> 8) & 0xFF
        self._send(
            self.SET_PORT_VOLTAGE,
            [profile_index, lsb, msb],
            expect=self.SET_PORT_VOLTAGE
        )

    def set_current(self, ma):
        if ma < 0 or ma > 10000:
            raise ValueError("Current must be in range 0–10000 mA")
        lsb = ma & 0xFF
        msb = (ma >> 8) & 0xFF
        self._send(
            self.SET_CURRENT,
            [lsb, msb],
            expect=self.SET_CURRENT
        )

    # -------------------------------
    # ⭐ NEW — SET MAX CURRENT LIMIT
    # -------------------------------

    def set_max_current(self, ma):
        """
        Equivalent to Windows CFG_SET_MAX_CURRENT.
        Allows >3A overcurrent test.
        """
        if ma < 0 or ma > 10000:
            raise ValueError("set_max_current must be 0–10000 mA")

        payload = [
            self.CFG_SET_MAX_CURRENT,   # config ID
            self.FORCE_LIMIT,           # force limit = 1
            ma & 0xFF,                  # LSB
            (ma >> 8) & 0xFF            # MSB
        ]

        # LEN = CMD + 4 bytes payload = 5
        self._send(
            self.SET_CONFIG,
            payload,
            expect=self.SET_CONFIG
        )

        print(f"[OK] Max current limit updated to {ma} mA")


# End of pm125_driver.py
