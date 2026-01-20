import lgpio
import time

GPIO_18 = 18 #21 breadboard version
GPIO_23 = 23 
GPIO_24 = 24 
GPIO_25 = 25 
# Open gpio chip
h = lgpio.gpiochip_open(0)

# Claim GPIO21 as input
lgpio.gpio_claim_input(h, GPIO_18)
lgpio.gpio_claim_input(h, GPIO_23)
lgpio.gpio_claim_input(h, GPIO_24)
lgpio.gpio_claim_input(h, GPIO_25)



while True:
    state_18 = lgpio.gpio_read(h, GPIO_18)
    state_23 = lgpio.gpio_read(h, GPIO_23)
    state_24 = lgpio.gpio_read(h, GPIO_24)
    state_25 = lgpio.gpio_read(h, GPIO_25)

    if state_18 == 0:
       
        print("LED is ON (GPIO_18 = LOW)")

    if state_23 == 0:
        
        print("LED is ON (GPIO_23 = LOW)")

    if state_24 == 0:
       
        print("LED is ON (GPIO_24 = LOW)")

    if state_25 == 0:
        
        print("LED is ON (GPIO_25 = LOW)")

    time.sleep(0.5)
