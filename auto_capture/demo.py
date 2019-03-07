#!/usr/bin/env python3

import ebb_motion
import ebb_serial
import time

port = ebb_serial.openPort()
ebb_motion.sendDisableMotors(port)
input("Please move Axidraw to home position, then press <enter>")

# ebb_motion.doABMove(port, 24000, 0, 1500)
# time.sleep(1.5)
# ebb_motion.doABMove(port, 0, 16000, 1000)
# time.sleep(1)
# ebb_motion.doABMove(port, -24000, 0, 1500)
# time.sleep(1.5)
# ebb_motion.doABMove(port, 0, -16000, 1000)
# time.sleep(1)
ebb_motion.doABMove(port, 12000, 0, 1500)
time.sleep(1.5)
ebb_motion.doABMove(port, 0, 8000, 1000)
time.sleep(1)
ebb_motion.doABMove(port, -12000, 0, 1500)
time.sleep(1.5)
ebb_motion.doABMove(port, 0, -8000, 1000)
time.sleep(1)

ebb_motion.setPenUpPos(port, 25000)
ebb_motion.setPenDownPos(port, 15000)
ebb_motion.sendPenUp(port, 2000)
time.sleep(2)
ebb_motion.sendPenDown(port, 2000)
time.sleep(2)

ebb_motion.sendDisableMotors(port)
