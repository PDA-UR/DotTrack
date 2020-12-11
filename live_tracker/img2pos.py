#!/usr/bin/env python3
# coding: utf-8

# # DotTrack
# 
# (C) 2018 - 2019 Dennis Schüsselbauer (original code)  
# (C) 2020 Raphael Wimmer (porting, cleanup)
# (C) 2020 Andreas Schmid (extending, cleanup)

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from IPython.display import display
import skimage
from skimage import io
from skimage.filters import threshold_sauvola
import numpy as np
import time
from torus import Torus
from generate_dbt import TorusGenerator
from collections import Counter
import sys
import math
import re
import os
import cv2
import socket
import struct
import imutils
import threading
from dottrack import get_coords

imgsize = [36, 36]
img_byte_len = imgsize[0] * imgsize[1]

IP = '1.2.3.4' # replace this the IP of the machine where this program runs
TCP_PORT = 8090
UDP_PORT = 9090
BUFFER_SIZE = 1

# size of the printed DBT in millimeters
CROP_W_MM = 1390
CROP_H_MM = 707

SCREEN_W_PX = 580 * 2
SCREEN_H_PX = 400 * 2

receivingCoords = True

# coordinates (in mm) are transformed to a relative postion
# and multiplied by 10000 so it can be sent to the microcontroller as int
# example for tangible in the center:
# x == CROP_W_MM / 2 => 50% == 0.5 => 0.5 * 10000 = 5000
def convert_coords(x, y):
    new_x = ((x / CROP_W_MM) * 10000)
    new_y = ((y / CROP_H_MM) * 10000)

    # A4 landscape
    #new_y = ((x / 210) * 10000)
    #new_x = 10000 - ((y / 297) * 10000)

    return (new_x, new_y)

# object representation of a tangible
# handles all netcode and image processing
class M5Stack:
    coords = (0, 0) # current coordinates in pixels
    absolute_coords = (0, 0) # coordinates of last successful decoded pattern in pixels
    angle = 0 # rotation of the tangible in degrees (currently only 0, 90, 180, 270)

    # duplicate of coords
    # used as a backup if determining the position of the tangible is not successful
    # there is a better solution for this for sure
    lastX = 0
    lastY = 0
    last_angle = 0

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
        self.sock_image = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_image.bind((IP, self.TCP_PORT))
        self.sock_image.listen(1)
        self.conn, self.addr = self.sock_image.accept()

        self.sock_coords = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP-Socket to receive Coordinates
        self.sock_coords.bind((IP, self.UDP_PORT))

        self.connected = True
        print(self.number, "connected")

    # receive coordinates from the tangible
    # they are converted to pixel coordinates and saved to self.coords
    # messages look like this:
    # x:1234|y:1234;
    def receiveCoords(self):
        print(self.number, "receiveCoords started")
        while(self.alive == True):
            if(self.connected == False):
                time.sleep(0.1)
                continue
            if(self.sock_coords.recv != None):
                coord_buffer, addr = self.sock_coords.recvfrom(1024)
                tmp = str(coord_buffer).split('|')
                x = (int(tmp[0][4:]) / 10000) * SCREEN_W_PX
                y = (int(tmp[1][2:-2]) / 10000) * SCREEN_H_PX
                #if(int(x) != int(self.coords[0]) or int(y) != int(self.coords[1])):
                #print(get_distance(x, self.coords[0], y, self.coords[1]))
                if(get_distance(x, self.coords[0], y, self.coords[1]) > 5):
                    self.has_moved = True
                self.coords = (x, y)

    # receive raw image from tangible and save it as np.array
    def get_image(self):
        global imgsize
        global img_byte_len
        buf = b''

        while True:
            received = self.conn.recv(BUFFER_SIZE)
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
                print(self.number, "receive image failed")
                break
            message = "failed\n"

            # decode position of the sensor image
            (x_in_mm, y_in_mm), confidence, angle, self.binarized_img, anchor = get_coords(img)
            # adjust rotation (sensor looks sideways)
            angle = (angle + 270) % 360
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
        print(self.number, "dying...")
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


def get_distance(x, x2, y, y2):
    return math.sqrt((x-x2)**2 + (y-y2)**2)

# Debug view application
# uses PIL to compose the preview and OpenCV to display it
if __name__ == "__main__":
    # register two tangibles
    m5stacks = []
    m5stacks.append(M5Stack(0))
    m5stacks.append(M5Stack(1))

    # size of displayed M5Stacks in pixels
    m5_w = 60
    m5_h = 60

    # import things
    font = ImageFont.truetype('Pillow/Tests/fonts/FreeMono.ttf', 40)

    img_m5 = Image.open("m5stack.png").convert('RGBA')
    img_m5_ghost = Image.open("m5stack_ghost.png").convert('RGBA')

    img_m5 = img_m5.resize((m5_w, m5_h))
    img_m5_ghost = img_m5_ghost.resize((m5_w, m5_h))

    # main loop
    while True:
        # set relative positions for googly eye demo
        #m5stacks[0].setRelativePosition((0,0))
        #m5stacks[1].setRelativePosition((0,0))
        m5stacks[0].setRelativePosition(m5stacks[1].getPosition())
        m5stacks[1].setRelativePosition(m5stacks[0].getPosition())

        # background
        preview = Image.new('RGB', (SCREEN_W_PX, SCREEN_H_PX), (200, 200, 200, 255))
        # text for coordinates
        text = Image.new('RGBA', (SCREEN_W_PX, SCREEN_H_PX), (255, 255, 255, 0))

        draw = ImageDraw.Draw(preview)
        drawText = ImageDraw.Draw(text)

        # draw M5Stacks
        for m5 in m5stacks:
            if(m5.alive == False):
                m5.die()
                continue

            (x, y) = m5.getPosition() # in pixels
            x = round(x, 2)
            y = round(y, 2)

            (abs_x, abs_y) = m5.absolute_coords # in pixels

            img_m5_temp = img_m5.copy()

            # draw raw image on the virtual M5Stack's Display
            try:
                pattern = Image.fromarray(m5.raw_img).convert('RGBA')
                img_m5_temp.paste(pattern, (12, 8), pattern)
            except:
                pass

            # adjust rotation
            img_m5_temp = img_m5_temp.rotate(360 - m5.last_angle)

            # draw text with coordinates
            text_color = (50, 0, 200, 255)
            if(m5.hasMoved()):
                text_color = (200, 0, 50, 255)
                preview.paste(img_m5_ghost, (int(abs_x - (m5_w / 2)), int(abs_y - (m5_h / 2))), img_m5)
            drawText.text((10, (m5.number+1) * 50), "{}, {}".format(x, y), font=font, fill=text_color)
            preview.paste(img_m5_temp, (int(x - (m5_w / 2)), int(y - (m5_h / 2))), img_m5)


        preview.paste(text, (0, 0), text)

        # display the image with OpenCV as PIL can't do real time things
        out = cv2.cvtColor(np.array(preview), cv2.COLOR_BGR2RGB)
        cv2.imshow("preview", np.array(out))

        key = cv2.waitKey(1)
        if(key == ord('q')):
            break

    for m5 in m5stacks:
        m5.die()
    time.sleep(1)
    sys.exit()
