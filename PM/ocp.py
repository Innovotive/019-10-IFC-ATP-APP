from pm125_driver import PM125
import time

with PM125("/dev/ttyUSB0") as pm:

    # allow >3A loads
    pm.set_max_current(5000)

    # set 5V
    pm.set_voltage(0, 5000)
    time.sleep(1)

    # request 3A
    pm.set_current(0)
    time.sleep(2)

    # request overcurrent
    pm.set_current(3500)
    time.sleep(2)

    print(pm.get_statistics())
