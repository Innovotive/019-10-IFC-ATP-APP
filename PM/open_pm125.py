from pm125 import PM125
pm = PM125("/dev/ttyUSB0")
print(pm.get_connection_status())
