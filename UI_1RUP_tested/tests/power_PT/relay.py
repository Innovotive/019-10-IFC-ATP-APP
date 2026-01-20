from gpiozero import LED

# Active-low relay:
# GPIO HIGH  -> relay OFF
# GPIO LOW   -> relay ON 
relay = LED(
    22,
    active_high=False,     # IMPORTANT#26 pin breadboard version
    initial_value=False     # GPIO HIGH at creation -> relay OFF
)

def relay_on():
    relay.on()   # active_low -> GPIO LOW
    print("[HW] OK – relay is ON")

def relay_off():
    relay.off()  # active_low -> GPIO HIGH
    print("[HW] OK – relay is OFF")
 