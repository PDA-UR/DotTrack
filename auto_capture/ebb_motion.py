# ebb_motion.py
# Motion control utilities for EiBotBoard
# https://github.com/evil-mad/plotink
# 
# Intended to provide some common interfaces that can be used by 
# EggBot, WaterColorBot, AxiDraw, and similar machines.
#
# Version 0.10, Dated October 12, 2017.
#
# The MIT License (MIT)
# 
# Copyright (c) 2017 Evil Mad Scientist Laboratories
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import ebb_serial
import math

def version():
	return "0.10"	# Version number for this document

def doABMove( portName, deltaA, deltaB, duration ):
	# Issue command to move A/B axes as: "XM,<move_duration>,<axisA>,<axisB><CR>"
	# Then, <Axis1> moves by <AxisA> + <AxisB>, and <Axis2> as <AxisA> - <AxisB>
	if (portName is not None):
		strOutput = ','.join( ['XM', str( duration ), str( deltaA ), str( deltaB )] ) + '\r'
		ebb_serial.command( portName, strOutput)

def doTimedPause( portName, nPause ):
	if (portName is not None):
		while ( nPause > 0 ):
			if ( nPause > 750 ):
				td = int( 750 )
			else:
				td = nPause
				if ( td < 1 ):
					td = int( 1 ) # don't allow zero-time moves
			ebb_serial.command( portName, 'SM,' + str( td ) + ',0,0\r')		
			nPause -= td

def doXYAccelMove( portName, deltaX, deltaY, vInitial, vFinal ):
	# Move X/Y axes as: "AM,<initial_velocity>,<final_velocity>,<axis1>,<axis2><CR>"
	# Typically, this is wired up such that axis 1 is the Y axis and axis 2 is the X axis of motion.
	# On EggBot, Axis 1 is the "pen" motor, and Axis 2 is the "egg" motor.
	# Note that minimum move duration is 5 ms.
	# Important: Requires firmware version 2.4 or higher.
	if (portName is not None):
		strOutput = ','.join( ['AM', str( vInitial ), str( vFinal ), str( deltaX ), str( deltaY )] ) + '\r'
		ebb_serial.command( portName, strOutput)

def doLowLevelMove( portName, Ri1, Steps1, DeltaR1, Ri2, Steps2, DeltaR2 ):
	# A "pre-computed" XY movement of the form 
	#  "LM,RateTerm1,AxisSteps1,DeltaR1,RateTerm2,AxisSteps2,DeltaR2<CR>"
	# See http://evil-mad.github.io/EggBot/ebb.html#LM for documentation.
	# Important: Requires firmware version 2.5.1 or higher.
	if (portName is not None):
		if ( ( ((Ri1 == 0) and (DeltaR1 == 0)) or (Steps1 == 0) ) and ( ((Ri2 == 0) and (DeltaR2 == 0)) or (Steps2 == 0) ) ):
			return
		strOutput = ','.join( ['LM',str( Ri1 ),str( Steps1 ),str( DeltaR1 ),str( Ri2 ),str( Steps2 ),str( DeltaR2 )] ) + '\r'
		ebb_serial.command( portName, strOutput)

		
def doXYMove( portName, deltaX, deltaY, duration ):
	# Move X/Y axes as: "SM,<move_duration>,<axis1>,<axis2><CR>"
	# Typically, this is wired up such that axis 1 is the Y axis and axis 2 is the X axis of motion.
	# On EggBot, Axis 1 is the "pen" motor, and Axis 2 is the "egg" motor.
	if (portName is not None):
		strOutput = ','.join( ['SM', str( duration ), str( deltaY ), str( deltaX )] ) + '\r'
		ebb_serial.command( portName, strOutput)

def moveDistLM(Rin, DeltaRin, timeTicks):
	# Calculate the number of motor steps taken using the LM command,
	# with rate factor R, delta factor DeltaR, and in a given number
	# of 40 us timeTicks. Calculation is for one axis only.
	
	# Distance moved after n time ticks is given by (n * R + (n^2 - n)*DeltaR/2) / 2^31
	
	n = int(timeTicks)	#Ensure that the inputs are integral.
	R = int(Rin)
	DeltaR = int(DeltaRin)
	
	if (n == 0):
		return 0
	else:
		np = (n*n - n) >> 1		#(n^2 - n)/2 is always an integer.
		S = (n * R) + DeltaR * np
		S = S >> 31
		return S	

def moveTimeLM( Ri, Steps, DeltaR):
	# Calculate how long, in 40 us ISR intervals, the LM command will take to move one axis.
	
	# First: Distance in steps moved after n time ticks is given by 
	#  the formula: distance(time n) = (10 * R + (n^2 - n)*DeltaR/2) / 2^31.
	# Use the quadratic formula to solve for possible values of n,
	# the number of time ticks needed to travel the through distance of Steps.
	# As this is a floating point result, we will round down the output, and 
	# then move one time step forward until we find the result.

	R = float (Ri)
	D = float (DeltaR)
	if (Steps < 0):
		Steps = -1 * Steps	#Distance to move is absolute value of Steps.
	root1 = 0
	root2 = 0
	
	if (Steps == 0):
		return 0	# No steps to take, so takes zero time.
	
	if (DeltaR == 0):
		if (Ri == 0):
			return 0	# No move will be made if Ri and DeltaR are both zero.
		
		# Else, case of no acceleration. 
		# Simple to get actual movement time:
		# T (seconds) = (AxisSteps << 31)/(25 kHz * RateTerm)
		
		F = int(Steps) << 31
		t = F / R
		t2 = int(math.ceil(t))
		return t2	
	else:	
		factor1 = (D/2.0) - R
		factor2 = R*R - D*R + (D*D/4.0) + (2 * D * 2147483648.0 * Steps)
		
		if (factor2 < 0):
			factor2 = 0
		factor2 = math.sqrt(factor2)
		root1 = int(math.floor((factor1 + factor2) / D))
		root2 = int(math.floor((factor1 - factor2) / D))
		
	if ((root1 < 0) and (root1 < 0)):
		return -1			# No plausible roots -- movmement time must be greater than zero.
	
	if (root1 < 0):
		timeTicks = root2	# Pick the positive root
	elif (root2 < 0):
		timeTicks = root1	# Pick the positive root
	elif (root2 < root1):	# If both are valid, pick the smaller value.
		timeTicks = root2
	else:
		timeTicks = root1
	
	# Now that we have an floor estimate for the time:
	# calculate how many steps occur in the estimated time.
	# Then, using that head start, calculate the
	# exact number of time ticks needed.
	
	dist = 0
	continueLoop = True
	while (continueLoop):
		timeTicks = timeTicks + 1		

		dist = moveDistLM(Ri, DeltaR, timeTicks)
		
		if (dist > 0) and (dist < Steps):
			pass
		else:
			continueLoop = False

	if (dist == 0):
		timeTicks = 0

	return timeTicks

def QueryPenUp( portName ):
	if (portName is not None):
		PenStatus = ebb_serial.query( portName, 'QP\r' )
		if PenStatus[0] == '0':
			return False
		else:
			return True

def QueryPRGButton( portName ):
	if (portName is not None):
		return ebb_serial.query( portName, 'QB\r' )

def sendDisableMotors( portName ):
	if (portName is not None):
		ebb_serial.command( portName, 'EM,0,0\r')

def sendEnableMotors( portName, Res ):
	if (Res < 0):
		Res = 0
	if (Res > 5):
		Res = 5	
	if (portName is not None):
		ebb_serial.command( portName, 'EM,' + str(Res) + ',' + str(Res) + '\r' )
		# If Res == 0, -> Motor disabled
		# If Res == 1, -> 16X microstepping
		# If Res == 2, -> 8X microstepping
		# If Res == 3, -> 4X microstepping
		# If Res == 4, -> 2X microstepping
		# If Res == 5, -> No microstepping

def sendPenDown( portName, PenDelay ):
	if (portName is not None):
		strOutput = ','.join( ['SP,0', str( PenDelay )] ) + '\r'
		ebb_serial.command( portName, strOutput)

def sendPenUp( portName, PenDelay ):
	if (portName is not None):
		strOutput = ','.join( ['SP,1', str( PenDelay )] ) + '\r'
		ebb_serial.command( portName, strOutput)

def TogglePen( portName ):
	if (portName is not None):
		ebb_serial.command( portName, 'TP\r')

def setPenDownPos( portName, ServoMax ):
	if (portName is not None):
		ebb_serial.command(portName,  'SC,5,' + str( ServoMax ) + '\r' )	
		# servo_max may be in the range 1 to 65535, in units of 83 ns intervals. This sets the "Pen Down" position.
		# http://evil-mad.github.io/EggBot/ebb.html#SC

def setPenDownRate( portName, PenDownRate ):
	if (portName is not None):
		ebb_serial.command(portName,  'SC,12,' + str( PenDownRate ) + '\r' )	
		# Set the rate of change of the servo when going down.
		# http://evil-mad.github.io/EggBot/ebb.html#SC

def setPenUpPos( portName, ServoMin ):
	if (portName is not None):
		ebb_serial.command(portName,  'SC,4,' + str( ServoMin ) + '\r' )	
		# servo_min may be in the range 1 to 65535, in units of 83 ns intervals. This sets the "Pen Up" position.
		# http://evil-mad.github.io/EggBot/ebb.html#SC

def setPenUpRate( portName, PenUpRate ):
	if (portName is not None):
		ebb_serial.command(portName,  'SC,11,' + str( PenUpRate ) + '\r' )	
		# Set the rate of change of the servo when going up.
		# http://evil-mad.github.io/EggBot/ebb.html#SC