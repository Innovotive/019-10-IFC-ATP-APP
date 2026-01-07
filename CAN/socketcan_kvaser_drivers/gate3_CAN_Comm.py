import can
import time

# ==================================================
# CONFIG
# ==================================================
CAN_IFACE = "can0"

TX_CAN_ID = 0x002      # Messages sent TO RUP
RX_CAN_ID = 0x002      # RUP responds on same ID (adjust if needed)

RESPONSE_TIMEOUT = 1.0  # seconds

# ==================================================
# COMMAND BYTES (FIRST DATA BYTE)
# ==================================================
CMD_START_ATP = 0x02   # ATP mode command
CMD_REQUEST_ID = 0x42  # ID request command

# Fixed payload (bytes 1..7)
BASE_PAYLOAD = [0x53, 0xD9, 0x12, 0x02, 0x7F, 0x70, 0x55]

# ==================================================
# INIT CAN BUS
# ==================================================
bus = can.interface.Bus(
    channel=CAN_IFACE,
    bustype="socketcan"
)

# ==================================================
# SEND CAN MESSAGE
# ==================================================
def send_can(cmd, description):
    data = [cmd] + BASE_PAYLOAD
    msg = can.Message(
        arbitration_id=TX_CAN_ID,
        data=data,
        is_extended_id=False
    )
    bus.send(msg)
    print(f"TX → {description}")
    print(f"     ID=0x{TX_CAN_ID:03X} DATA={[hex(b) for b in data]}")

# ==================================================
# WAIT FOR RESPONSE FROM RUP
# ==================================================
def wait_for_response(timeout):
    start = time.time()
    while time.time() - start < timeout:
        msg = bus.recv(timeout=0.1)
        if msg is None:
            continue

        if msg.arbitration_id == RX_CAN_ID:
            return msg

    return None

# ==================================================
# GATE 3 TEST (SINGLE RUP)
# ==================================================
def gate3_single_rup():
    print("\n========== GATE 3 – SINGLE RUP ==========")

    # 1️ Start ATP mode
    send_can(CMD_START_ATP, "START ATP MODE")
    time.sleep(0.2)

    # 2️ Request RUP ID
    send_can(CMD_REQUEST_ID, "REQUEST RUP ID")

    # 3️ Wait for response
    response = wait_for_response(RESPONSE_TIMEOUT)

    if response is None:
        print("❌ FAIL: No CAN response from RUP (ID 0x02)")
        return False

    # 4️ Decode response
    rup_id = response.data[0]

    print(f"RX ← CAN response received")
    print(f"     ID=0x{response.arbitration_id:03X} DATA={[hex(b) for b in response.data]}")

    if rup_id == 0x02:
        print("✅ PASS: RUP ID = 0x02 confirmed")
        return True
    else:
        print(f"❌ FAIL: Unexpected RUP ID {hex(rup_id)}")
        return False


# ==================================================
# MAIN
# ==================================================
if __name__ == "__main__":
    gate3_single_rup()
