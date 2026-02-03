from gpiozero import LED
from time import sleep

# =========================================================
# RELAY GPIO PINS (BCM numbering)
# =========================================================
RELAY_PINS = [22, 27, 6, 13]  # add more if needed: 19, 26

# True  = active-low relay (LOW = ON)
# False = active-high relay (HIGH = ON)
ACTIVE_LOW = True

# =========================================================
# MODE
#   True  -> walk one-by-one (only one relay ON at a time)
#   False -> all relays ON together, then all OFF together
# =========================================================
toggle_one_by_one = True

# =========================================================
# SETUP
# =========================================================
relays = [LED(pin) for pin in RELAY_PINS]

def relay_on(r):
    r.off() if ACTIVE_LOW else r.on()

def relay_off(r):
    r.on() if ACTIVE_LOW else r.off()

def all_off():
    for r in relays:
        relay_off(r)

def all_on():
    for r in relays:
        relay_on(r)

print("Starting relay test... (CTRL+C to stop)")

try:
    # Safety: start with everything OFF
    all_off()
    for i, pin in enumerate(RELAY_PINS, start=1):
        print(f"Relay {i} OFF (GPIO {pin})")

    while True:
        if toggle_one_by_one:
            print("\n--- One-by-one (walk) ---")
            for i, r in enumerate(relays, start=1):
                # ensure ONLY one relay is ON
                all_off()
                relay_on(r)
                print(f"Relay {i} ON  (GPIO {RELAY_PINS[i-1]})")
                sleep(10)

            # end of cycle: turn everything OFF
            all_off()
            sleep(2)

        else:
            print("\n--- All relays ON together ---")
            all_on()
            print("All relays ON")
            sleep(10)

            print("--- All relays OFF together ---")
            all_off()
            print("All relays OFF")
            sleep(2)

except KeyboardInterrupt:
    print("\nStopping... turning everything OFF")
    all_off()
