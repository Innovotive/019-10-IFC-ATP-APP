"""
pm125.py - PassMark PM125 Driver for Linux (Raspberry Pi)
Implements the PM125 serial protocol exactly as in PDTesterAPI.cpp

Usage example:

    from pm125 import PM125

    with PM125("/dev/ttyUSB0") as pm:
        print("Device Info:", pm.get_dev_info())
        print("PDOs:", pm.get_port_capabilities())
        pm.set_voltage(0, 5000)
        pm.set_current(3000)
        print(pm.get_statistics())
        pm.set_current(0)

"""

import serial
import time


# ===============================
# Exceptions
# ===============================

class PM125Error(Exception):
    pass

class PM125Timeout(PM125Error):
    pass


# ===============================
# PM125 Main Class
# ===============================

class PM125:

    # ---- Command Codes ----
    GET_DEV_INFO = 0x01
    GET_CONSTAT = 0x0A
    GET_PORT_CAPABILITIES = 0x0B
    GET_STAT = 0x0C
    SET_PORT_VOLTAGE = 0x0D
    SET_DEF_VOLTAGE = 0x0E
    SET_DEF_CURRENT = 0x0F
    SET_CURRENT = 0x10
    SET_CURRENT_FAST = 0x11
    SET_DEF_PROFILE = 0x12
    GET_STEP_RESPONSE = 0x13
    SET_USB_CONNECTION = 0x14
    INJECT_PD_MSG = 0x15
    INJECT_PD_MSG_RAW = 0x16
    GET_SUB_HW_REV = 0xD1
    SET_CALIB_DATA = 0xE3
    GET_CALIB_DATA = 0xE4
    RESET_CALIB_DATA = 0xE5
    SET_CONFIG = 0xE0
    GET_CONFIG = 0xE1
    SET_PD_ANALYZER = 0xE7

    # ===============================
    # Constructor
    # ===============================

    def __init__(self, port="/dev/ttyUSB0", baudrate=115200, timeout=1.0):

        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
            bytesize=8,
            parity=serial.PARITY_NONE,
            stopbits=1
        )

        # Prevent FTDI auto-reset
        self.ser.dtr = False
        self.ser.rts = False

        self.timeout = timeout

    # For "with PM125() as pm:"
    def __enter__(self):
        return self   # FIXED

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def close(self):
        if self.ser.is_open:
            self.ser.close()

    # ===============================
    # Internal Helpers
    # ===============================

    @staticmethod
    def _checksum(data):
        """
        XOR of all bytes in [0x02, LEN, CMD, PAYLOAD...] then XOR 0x03
        """
        chk = 0
        for b in data:
            chk ^= b
        chk ^= 0x03
        return chk & 0xFF

    def _build_frame(self, cmd, payload):
        """
        Frame structure:
        0x02 | LEN | CMD | PAYLOAD | CHK | 0x03
        LEN = CMD + PAYLOAD count
        """
        payload = payload or []
        length = 1 + len(payload)

        content = [0x02, length, cmd] + payload
        chk = self._checksum(content)

        frame = content + [chk, 0x03]
        return bytes(frame)

    def _read_frame(self):
        """
        Read a full PM125 frame, verify checksum.
        Returns (cmd, data_bytes) where data_bytes excludes CMD.
        """
        s = self.ser

        # Wait for 0x02
        while True:
            b = s.read(1)
            if not b:
                raise PM125Timeout("Timeout waiting for start byte (0x02).")
            if b[0] == 0x02:
                break

        # Read LEN
        b = s.read(1)
        if not b:
            raise PM125Timeout("Timeout waiting for LEN byte.")
        data_len = b[0]

        # Read (CMD + PAYLOAD + CHK + END)
        rest = s.read(data_len + 2)
        if len(rest) != data_len + 2:
            raise PM125Timeout("Timed out reading rest of frame.")

        cmd = rest[0]
        payload = list(rest[1:data_len])
        chk = rest[data_len]
        end = rest[data_len + 1]

        if end != 0x03:
            raise PM125Error("Bad frame end byte (expected 0x03).")

        # checksum verification
        content = [0x02, data_len, cmd] + payload
        exp_chk = self._checksum(content)
        if chk != exp_chk:
            raise PM125Error(f"Checksum mismatch (got {chk}, expected {exp_chk})")

        return cmd, payload

    def _send(self, cmd, payload=None, expect=None):
        """
        Send a command and receive a reply.
        """
        frame = self._build_frame(cmd, payload)
        self.ser.reset_input_buffer()
        self.ser.write(frame)

        resp_cmd, resp_payload = self._read_frame()

        if expect is not None and resp_cmd != expect:
            raise PM125Error(
                f"Unexpected response cmd 0x{resp_cmd:02X}, expected 0x{expect:02X}"
            )

        return resp_cmd, resp_payload

    # ===============================
    # High-Level API
    # ===============================

    def get_dev_info(self):
        """Return (HW_ver, FW_ver)."""
        _, data = self._send(self.GET_DEV_INFO, expect=self.GET_DEV_INFO)
        return data[0], data[1]

    def get_statistics(self):
        """Return dict of temperature, voltage, current, set_current, loopback."""
        _, data = self._send(self.GET_STAT, expect=self.GET_STAT)

        return {
            "status": data[0],
            "temperature_c": data[1],
            "voltage_mv": data[2] | (data[3] << 8),
            "set_current_ma": data[4] | (data[5] << 8),
            "current_ma": data[6] | (data[7] << 8),
            "loopback_current_ma": data[8] | (data[9] << 8),
        }

    def get_connection_status(self):
        """Return dict containing contract and profile data."""
        _, d = self._send(self.GET_CONSTAT, expect=self.GET_CONSTAT)

        return {
            "port_status": d[0],
            "profile_index": d[1],
            "profile": d[2],
            "profile_subtype": d[3],
            "voltage_mv": d[4] | (d[5] << 8),
            "max_current_ma": d[6] | (d[7] << 8),
            "max_power_mw": (
                d[8]
                | (d[9] << 8)
                | (d[10] << 16)
                | (d[11] << 24)
            ),
        }

    def get_port_capabilities(self):
        """
        Return list of all PDOs supported by the RUP.
        Each PDO = {pdo_index, voltage_mv, max_current_ma, max_power_mw}
        """
        _, data = self._send(
            self.GET_PORT_CAPABILITIES,
            expect=self.GET_PORT_CAPABILITIES
        )

        count = data[0]
        pdos = []
        idx = 1

        for i in range(count):
            v = data[idx] | (data[idx+1] << 8)
            i_ma = data[idx+2] | (data[idx+3] << 8)
            p_mw = (
                data[idx+4]
                | (data[idx+5] << 8)
                | (data[idx+6] << 16)
                | (data[idx+7] << 24)
            )

            pdos.append({
                "pdo_index": i,
                "voltage_mv": v,
                "max_current_ma": i_ma,
                "max_power_mw": p_mw
            })

            idx += 8

        return pdos

    # ===============================
    # Write Commands
    # ===============================

    def set_current(self, ma):
        if ma < 0 or ma > 10000:
            raise ValueError("Current must be 0–10000 mA")

        lsb = ma & 0xFF
        msb = (ma >> 8) & 0xFF

        self._send(
            self.SET_CURRENT,
            [lsb, msb],
            expect=self.SET_CURRENT
        )

    def set_voltage(self, profile_index, voltage_mv):
        v_lsb = voltage_mv & 0xFF
        v_msb = (voltage_mv >> 8) & 0xFF

        self._send(
            self.SET_PORT_VOLTAGE,
            [profile_index, v_lsb, v_msb],
            expect=self.SET_PORT_VOLTAGE,
        )

    def stop_load(self):
        self.set_current(0)

    def request_5v_3a(self):
        self.set_voltage(0, 5000)
        time.sleep(0.2)
        self.set_current(3000)


# ===============================
# Self-test when running directly
# ===============================

if __name__ == "__main__":
    pm = PM125("/dev/ttyUSB0")

    try:
        print("Device Info:", pm.get_dev_info())
        print("Connection:", pm.get_connection_status())
        print("PDOs:", pm.get_port_capabilities())

        print("Requesting 5V...")
        pm.set_voltage(0, 5000)
        time.sleep(0.5)

        print("Setting 3A...")
        pm.set_current(3000)
        time.sleep(1)

        print("Stats @3A:", pm.get_statistics())

        print("Resetting load...")
        pm.set_current(0)
        time.sleep(0.5)

        print("Stats @0A:", pm.get_statistics())

    finally:
        pm.close()
