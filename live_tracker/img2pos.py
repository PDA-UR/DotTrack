#!/usr/bin/env python3
# coding: utf-8

# # DotTrack
# 
# (C) 2018 - 2019 Dennis Schüsselbauer (original code)  
# (C) 2020 Raphael Wimmer (porting, cleanup)
# (C) 2021 Andreas Schmid (extending, cleanup)

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np
import time
import sys
import math
import re
import os
import cv2
import socket
import struct
import imutils
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from dottrack import get_coords
from demos import *
from angle_detector import calculate_angle, angular_distance

imgsize = [36, 36] # resolution of the sensor/camera
img_byte_len = imgsize[0] * imgsize[1]

# size of the printed DBT in millimeters
CROP_W_MM = 1390
CROP_H_MM = 707

SCREEN_W_PX = 1920
SCREEN_H_PX = 1080

IMAGE_MODE = False    # display image in the background
GEOMETRY_MODE = False # show geometry demo with distance and pythagoras

m5stacks = [] # list of all tangibles
m5count = 0   # total number of tangibles

# replace this the IP of the machine where this program runs
# or leave at 0.0.0.0 to accept all connections
IP = '0.0.0.0' 
CONNECTION_HANDLER_PORT = 8089
TCP_PORT = 8090
UDP_PORT = 9090
BUFFER_SIZE = 1

# little HTTP server to dynamically manage connecting tangibles
# they send an HTTP GET request and are provided a TCP and UDP port
# which they can use to connect with the actual application
class ConnectionHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global m5count
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(bytes(f'{TCP_PORT + m5count},{UDP_PORT + m5count}', 'utf-8'))
        m5stacks.append(M5Stack(m5count))
        m5count = m5count + 1

def ConnectionHandlerThread(server):
    server.serve_forever()

# coordinates (in mm) are transformed to a relative postion
# and multiplied by 10000 so it can be sent to the microcontroller as int
# example for tangible in the center:
# x == CROP_W_MM / 2 => 50% == 0.5 => 0.5 * 10000 = 5000
def convert_coords(x, y):
    if(IMAGE_MODE == False):
        new_x = ((x / CROP_W_MM) * 10000)
        new_y = ((y / CROP_H_MM) * 10000)
    else:
        # A4 landscape
        new_y = ((x / 210) * 10000)
        new_x = 10000 - ((y / 297) * 10000)

    return (new_x, new_y)

# object representation of a tangible
# handles networking and image processing
class M5Stack:
    liftOff = True # False if on a surface, True if lift off
    coords = (0, 0) # current coordinates in pixels
    absolute_coords = (0, 0) # coordinates of last successful decoded pattern in pixels
    angle = 0 # rotation of the tangible in degrees (currently only 0, 90, 180, 270)
    distance = 0
    power = 0
    orientation = 0

    # duplicate of coords
    # used as a backup if determining the position of the tangible is not successful
    # there is a better solution for this for sure
    lastX = 0
    lastY = 0
    last_angle = 0
    orientation_list = []

    eyeAngle = 0 # view rotation of the eye for googly eyes demo

    # kill connection thread after connection is successful
    flag_kill_connect_thread = True
    connected = False

    raw_img = None # last raw sensor image (36x36 8 bit np.array)
    binarized_img = None # binarized version of last raw sensor image (6x6 1 bit np.array)

    has_moved = False # was there an update of relative position since the last absolute position?

    # register a new tangible
    # passed number is used to identify the device and generate unique ports
    # recommendation: start with 0
    def __init__(self, number):
        self.alive = True
        self.number = number

        self.TCP_PORT = TCP_PORT + number
        self.UDP_PORT = UDP_PORT + number
       
        self.connectThread = threading.Thread(target=self.connect)
        self.connectThread.start()

        self.receiveCoordThread = threading.Thread(target=self.receiveCoords)
        self.receiveCoordThread.start()

        self.updateThread = threading.Thread(target=self.update)
        self.updateThread.start()

        print(number, " initialized with ports", self.TCP_PORT, self.UDP_PORT)

    # do network things
    # TCP connection to receive images
    # UDP connection to send and receive coordinates
    # nothing special to see here
    def connect(self):
        global m5count
        # TCP socket to receive sensor images
        self.sock_image = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_image.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock_image.bind((IP, self.TCP_PORT))
        self.sock_image.listen(1)
        self.conn, self.addr = self.sock_image.accept()

        # UDP socket to receive coordinates
        self.sock_coords = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 
        self.sock_coords.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock_coords.bind((IP, self.UDP_PORT))

        self.connected = True
        #m5count += 1 # already happens in ConnectionHandler
        print(self.number, "connected")

    # receive coordinates from the tangible
    # they are converted to pixel coordinates and saved to self.coords
    # last value is liftOff, a boolean indicating whether the device is on a surface
    # messages look like this:
    # x:1234|y:1234|l:0;
    def receiveCoords(self):
        print(self.number, "receiveCoords started")
        while(self.alive == True):
            if(self.connected == False):
                # wait for connection
                time.sleep(0.1)
                continue
            if(self.sock_coords.recv != None):
                coord_buffer, addr = self.sock_coords.recvfrom(1024)
                # coordinates and liftoff are sent as a string
                # fields are separated with pipe | symbols
                tmp = str(coord_buffer).split('|')

                x = (int(tmp[0][4:]) / 10000) * SCREEN_W_PX
                y = (int(tmp[1][2:]) / 10000) * SCREEN_H_PX
                self.liftOff = bool(int(tmp[2][2:]))
                #print(self.liftOff)
                self.power = int(tmp[3][2:])
                gyro = int(tmp[4][2:-2]) / 10000.0

                if self.liftOff:
                    self.orientation_list = []
                    self.was_lift_off = True

                if(get_distance(x, self.coords[0], y, self.coords[1]) > 5):
                    self.has_moved = True
                self.coords = (x, y)

    # receive raw image from tangible and save it as np.array
    def get_image(self):
        global imgsize
        global img_byte_len
        buf = b''

        while True:
            try:
                received = self.conn.recv(BUFFER_SIZE)
            except ConnectionResetError:
                print("ConnectionResetError")
                self.die()

            if received == b'':
                print(self.number, "connection broken")
                return None

            buf += received
            if received != b"\xFE":
                continue

            data = buf
            buf = b''

            # Remove terminator byte
            data = data[:-1]
            # Remove header byte (indicates frame analyse request)
            if len(data) == img_byte_len + 1 and data[0] == 0xFD:
                data = data[1:]
            # If the length is still not correct try again
            if len(data) != img_byte_len:
                #placeholder_print("Received bad data from image capture. Trying again...")
                continue
            break

        # Expand bytes to full range (0-255)
        data = bytes([min(b * 2, 255) for b in data])
        # Create image
        img = np.array(Image.frombytes("L", imgsize, data))
        self.raw_img = img

        return img

    # main loop of the tangible
    def update(self):
        print(self.number, "update started")
        while(self.alive == True):
            if(self.connected == False):
                time.sleep(0.1) # wait for connection
                continue
            else:
                if(self.flag_kill_connect_thread == True):
                    self.connectThread.join() # we are connected, so kill the connection thread
                    self.flag_kill_connect_thread = False
                    print(self.number, "connect thread killed")

            # try to receive a new sensor image
            img = self.get_image()
            if(img is None):
                print(self.number, 'receive image failed')
                break
            message = 'failed\n'

            self.last_orientation = self.orientation

            self.orientation = int(calculate_angle(img))

            #self.orientation_list.append(self.orientation)
            #if len(self.orientation_list) > 3:
            #    self.orientation_list = self.orientation_list[1:]
            #self.orientation = np.median(self.orientation_list)

            self.last_angle = (self.last_angle - self.last_orientation + self.orientation) % 360
            # decode position of the sensor image
            (x_in_mm, y_in_mm), confidence, angle, self.binarized_img, anchor = get_coords(img, self.orientation)
            # adjust rotation (sensor looks sideways)
            if not IMAGE_MODE:
                angle = (angle + 270) % 360
            else:
                angle = (angle) % 360

            #if not self.was_lift_off:
            #    if angular_distance(angle, self.last_angle, 360) > 90:
            #        if angle > self.last_angle:
            #            angle -= 90
            #        else:
            #            angle += 90
            #angle = angle % 360


            if(confidence >= 83): # position successfully decoded
                (coord1, coord2) = convert_coords(x_in_mm, y_in_mm)

                # generate answer message
                # this can be extended for more demo applications
                message = '{}|{}|{}|{}|{};\n'.format(coord1, coord2, angle, self.eyeAngle, self.distance)
                self.lastX = coord1
                self.lastY = coord2
                self.absolute_coords = (int((x_in_mm / CROP_W_MM) * SCREEN_W_PX), int((y_in_mm / CROP_H_MM) * SCREEN_H_PX))
                self.last_angle = angle
                self.has_moved = False
                #self.coords = self.absolute_coords # AS maybe needed?

            else:
                # if we were not successful, send back the last coordinates
                message = '{}|{}|{}|{}|{};\n'.format(self.lastX, self.lastY, self.last_angle, self.eyeAngle, self.distance)

            # send answer to tangible
            self.conn.send(message.encode())
        self.alive = False

    # close all connections
    def die(self):
        print(self.number, 'dying...')
        self.sock_image.close()
        self.alive = False
        self.receiveCoordThread.join()
        self.updateThread.join()

    def getPosition(self):
        return self.coords
   
    # used for googly eye demo
    # calculate tangible's position in relation to another position
    def setRelativePosition(self, otherCoords):
        x, y = self.coords
        x2, y2, = otherCoords
        self.distance = math.sqrt((x-x2)**2 + (y-y2)**2)
        self.eyeAngle = math.degrees(math.atan2(x-x2, y-y2))

    def hasMoved(self):
        #print(self.number, self.lastX, self.coords[0], self.lastY, self.coords[1])
        #return (self.coords[0] != self.lastX or self.coords[1] != self.lastY)
        return self.has_moved

# used to test demo applications without connecting tangibles
class MFakeStack(M5Stack):

    def __init__(self, number):
        self.liftOff = False
        self.power = 0
        self.alive = True
        self.number = number
        self.x_speed = 0
        self.y_speed = 0
        #self.x_speed = 5 + number
        #self.y_speed = 10 + number

        self.coords = (0, 0)
        if(number == 0):
            self.coords = (1000, 400)
        if(number == 1):
            self.coords = (1400, 420)
        if(number == 2):
            self.coords = (1300, 800)
        self.raw_img = np.zeros((36, 36))
        self.updateThread = threading.Thread(target=self.update)
        self.updateThread.start()

    def update(self):
        while(True):
            if(self.coords[0] > SCREEN_W_PX - 200 and self.x_speed > 0):
                self.x_speed = -self.x_speed
            if(self.coords[0] < 200 and self.x_speed < 0):
                self.x_speed = -self.x_speed

            if(self.coords[1] > SCREEN_H_PX - 200 and self.y_speed > 0):
                self.y_speed = -self.y_speed
            if(self.coords[1] < 200 and self.y_speed < 0):
                self.y_speed = -self.y_speed

            self.coords = (self.coords[0] + self.x_speed, self.coords[1] + self.y_speed)
            self.absolute_coords = self.coords

            if(self.alive == False):
                break

            time.sleep(0.1)

    def die(self):
        print(self.number, 'dying...')
        self.alive = False

# Debug view application
# uses PIL to compose the preview and OpenCV to display it
if __name__ == '__main__':
    SHOW_LIVE_PREVIEW = 0
    SHOW_SENSOR_IMAGE = 1
    SHOW_CUPBOARD_DEMO = 2
    SHOW_RELATIVE_POSITION = True

    mode = SHOW_LIVE_PREVIEW

    connectionHandler = HTTPServer(('0.0.0.0', CONNECTION_HANDLER_PORT), ConnectionHandler)
    connectionHandlerThread = threading.Thread(target=ConnectionHandlerThread, args=(connectionHandler,))
    connectionHandlerThread.start()

    # main loop
    while True:
        num_m5 = 0
        m5_active = []

        # create a list of tangibles on the pattern
        for m5 in m5stacks:
            if not m5.alive:
                m5.die()
                continue
            if not m5.liftOff:
                num_m5 += 1
                m5_active.append(m5)
        
        # set relative positions for googly eyes demo
        # two m5stacks look at each other
        # for more than two, it is cyclic:
        # 1 -> 2; 2 -> 3; 3 -> 1
        if(num_m5 > 1):
            for i in range(num_m5):
                m5 = m5_active[i]
                m5_relative = m5_active[i - 1]
                m5.setRelativePosition(m5_relative.getPosition())

        # background
        preview = Image.new('RGB', (SCREEN_W_PX, SCREEN_H_PX), (200, 200, 200, 255))
        # text for coordinates
        text = Image.new('RGBA', (SCREEN_W_PX, SCREEN_H_PX), (255, 255, 255, 0))

        draw = ImageDraw.Draw(preview)
        drawText = ImageDraw.Draw(text)

        if(mode == SHOW_LIVE_PREVIEW):
            # draw grid
            if not IMAGE_MODE:
                draw_grid(draw)

            if GEOMETRY_MODE:
                try:
                    if(num_m5 == 2):
                        draw_geometry_distance(draw, drawText, m5_active)
                    elif(num_m5 == 3):
                        # show pythagoras
                        draw_geometry_pythagoras(draw, drawText, m5_active)

                except Exception as e:
                    print(e)
                    print("GEOMETRY_MODE: could not draw lines - too few M5Stacks?")

            # draw M5Stacks
            draw_m5stacks(preview, text, draw, drawText, m5_active, show_relative=SHOW_RELATIVE_POSITION)
        elif(mode == SHOW_SENSOR_IMAGE):
            if(num_m5 > 0):
                show_sensor_image(preview, draw, m5_active[0])
        elif(mode == SHOW_CUPBOARD_DEMO):
            if(num_m5 > 0):
                show_cupboard_demo(draw, m5_active[0])

        # display the image with OpenCV as PIL can't do real time things
        out = cv2.cvtColor(np.array(preview), cv2.COLOR_BGR2RGB)

        cv2.namedWindow('preview', cv2.WINDOW_FREERATIO)
        cv2.setWindowProperty('preview', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        cv2.imshow("preview", np.array(out))

        key = cv2.waitKey(1)
        if(key == ord('q')):
            break
        elif(key == ord('a')):
            mode = SHOW_LIVE_PREVIEW
        elif(key == ord('w')):
            SHOW_RELATIVE_POSITION = not SHOW_RELATIVE_POSITION
        elif(key == ord('s')):
            mode = SHOW_SENSOR_IMAGE
        elif(key == ord('d')):
            mode = SHOW_CUPBOARD_DEMO
        elif(key == ord('c')):
            IMAGE_MODE = not IMAGE_MODE
        elif(key == ord('l')):
            GEOMETRY_MODE = not GEOMETRY_MODE
        elif(key == ord('x')):
            m5stacks.append(MFakeStack(m5count))
            m5count += 1

    connectionHandler.server_close()
    connectionHandler.shutdown()
    connectionHandlerThread.join()

    for m5 in m5stacks:
        m5.die()

    time.sleep(1)
    sys.exit()
