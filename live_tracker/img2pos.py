#!/usr/bin/env python3
# coding: utf-8

# # DotTrack
# 
# (C) 2018 - 2019 Dennis Schüsselbauer (original code)  
# (C) 2020 Raphael Wimmer (porting, cleanup)
# (C) 2021 Andreas Schmid (extending, cleanup)

from PIL import Image, ImageDraw, ImageFilter, ImageFont
#from IPython.display import display
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
from http.server import BaseHTTPRequestHandler, HTTPServer
from dottrack import get_coords

m5stacks = []
m5count = 0

imgsize = [36, 36] # resolution of the sensor/camera
img_byte_len = imgsize[0] * imgsize[1]

IP = '0.0.0.0' # replace this the IP of the machine where this program runs
CONNECTION_HANDLER_PORT = 8089
TCP_PORT = 8090
UDP_PORT = 9090
BUFFER_SIZE = 1

# size of the printed DBT in millimeters
CROP_W_MM = 1390
CROP_H_MM = 707

#SCREEN_W_PX = 580 * 2
#SCREEN_H_PX = 400 * 2

SCREEN_W_PX = 1920
SCREEN_H_PX = 1080

receivingCoords = True

CAT_MODE = False

LINE_MODE = False

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
    if(CAT_MODE == False):
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
    liftOff = True
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
        global m5count
        self.sock_image = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_image.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock_image.bind((IP, self.TCP_PORT))
        self.sock_image.listen(1)
        self.conn, self.addr = self.sock_image.accept()

        self.sock_coords = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP-Socket to receive Coordinates
        self.sock_coords.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock_coords.bind((IP, self.UDP_PORT))

        self.connected = True
        m5count += 1
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
                time.sleep(0.1)
                continue
            if(self.sock_coords.recv != None):
                coord_buffer, addr = self.sock_coords.recvfrom(1024)
                tmp = str(coord_buffer).split('|')
                x = (int(tmp[0][4:]) / 10000) * SCREEN_W_PX
                y = (int(tmp[1][2:]) / 10000) * SCREEN_H_PX
                self.liftOff = bool(int(tmp[2][2:-2]))
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
            if not CAT_MODE:
                angle = (angle + 270) % 360
            else:
                angle = (angle) % 360
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

class MFakeStack(M5Stack):

    def __init__(self, number):
        self.liftOff = False
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
        print(self.number, "dying...")
        self.alive = False

def get_distance(x1, x2, y1, y2):
    return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)

def get_center(x1, x2, y1, y2):
    xdist = abs(x1 - x2) / 2
    ydist = abs(y1 - y2) / 2
    return (min(x1, x2) + xdist, min(y1, y2) + ydist)

def get_angle(x1, x2, y1, y2):
    dx = x2 - x1
    dy = y2 - y1
    angle = math.atan2(dy, dx)
    deg = np.rad2deg(angle)
    #if deg < 0:
    #    deg += 360
    return deg

def get_angle_between(a1, a2):
    a1 = np.deg2rad(a1)
    a2 = np.deg2rad(a2)
    angle = math.atan2(math.sin(a1 - a2), math.cos(a1 - a2))
    deg = np.rad2deg(angle)
    return deg


# Debug view application
# uses PIL to compose the preview and OpenCV to display it
if __name__ == "__main__":
    SHOW_LIVE_PREVIEW = 0
    SHOW_SENSOR_IMAGE = 1
    SHOW_CUPBOARD_DEMO = 2
    SHOW_ONLY_ABSOLUTE = 3

    SENSOR_IMAGE_WIDTH = 1000
    SENSOR_IMAGE_HEIGHT = 1000

    mode = SHOW_LIVE_PREVIEW

    # register two tangibles
    #m5stacks.append(MFakeStack(0))
    #m5stacks.append(MFakeStack(1))
    #m5stacs.append(MFakeStack(2))
    #m5stacks.append(M5Stack(0))
    #m5stacks.append(M5Stack(1))
    #m5stacks.append(M5Stack(2))

    #m5stacks.append(MFakeStack(0))
    #m5stacks.append(MFakeStack(1))

    #m5stacks.append(MFakeStack(0))

    # size of displayed M5Stacks in pixels
    m5_w = 60
    m5_h = 60

    # import things
    #font = ImageFont.truetype('Pillow/Tests/fonts/FreeMonoBold.ttf', 40)
    #font = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf', 40)
    #font = ImageFont.load_default()
    font = ImageFont.truetype('FreeMonoBold.ttf', 40)

    img_m5 = Image.open("m5stack.png").convert('RGBA')
    img_m5_ghost = Image.open("m5stack_ghost.png").convert('RGBA')

    img_m5 = img_m5.resize((m5_w, m5_h))
    img_m5_ghost = img_m5_ghost.resize((m5_w, m5_h))

    connectionHandler = HTTPServer(('0.0.0.0', CONNECTION_HANDLER_PORT), ConnectionHandler)
    connectionHandlerThread = threading.Thread(target=ConnectionHandlerThread, args=(connectionHandler,))
    connectionHandlerThread.start()

    # main loop
    while True:
        # set relative positions for googly eye demo
        #m5stacks[2].setRelativePosition((0,0))
        #m5stacks[1].setRelativePosition((0,0))
        #m5stacks[0].setRelativePosition(m5stacks[1].getPosition())
        #m5stacks[1].setRelativePosition(m5stacks[0].getPosition())
        for m5 in m5stacks:
            m5.setRelativePosition((0,0))

        # background
        preview = Image.new('RGB', (SCREEN_W_PX, SCREEN_H_PX), (200, 200, 200, 255))
        # text for coordinates
        text = Image.new('RGBA', (SCREEN_W_PX, SCREEN_H_PX), (255, 255, 255, 0))

        draw = ImageDraw.Draw(preview)
        drawText = ImageDraw.Draw(text)

        if(mode == SHOW_LIVE_PREVIEW):
            # draw grid

            if not CAT_MODE:
                num_lines_x = 8
                for i in range(num_lines_x):
                    line_x = int(SCREEN_W_PX / num_lines_x) * i
                    draw.line([line_x, 0, line_x, SCREEN_H_PX], fill=128)
                draw.line([0, int(SCREEN_H_PX * 0.33), SCREEN_W_PX, int(SCREEN_H_PX * 0.33)], fill=128)
                draw.line([0, int(SCREEN_H_PX * 0.66), SCREEN_W_PX, int(SCREEN_H_PX * 0.66)], fill=128)

            if LINE_MODE:
                try:
                    (x1, y1) = m5stacks[0].getPosition()
                    if(m5count == 2):
                        (x2, y2) = m5stacks[1].getPosition()
                        distance = int(get_distance(x1, x2, y1, y2)) / 10.0
                        text_position = get_center(x1, x2, y1, y2)
                        # measure distance
                        if x2 != 0:
                            draw.line([x1, y1, x2, y2], fill=128, width=5)
                            drawText.text((text_position[0] + 10, text_position[1] + 10), "{} cm".format(distance), font=font, fill=text_color)
                    elif(m5count == 3):
                        # show pythagoras
                        (x2, y2) = m5stacks[1].getPosition()
                        (x3, y3) = m5stacks[2].getPosition()
                        if x3 != 0 and x2 != 0:
                            arc_size = 50
                            a1 = int(get_angle(x1, x2, y1, y2))
                            a2 = int(get_angle(x1, x3, y1, y3))

                            b2 = int(get_angle(x2, x1, y2, y1))
                            b1 = int(get_angle(x2, x3, y2, y3))

                            c2 = int(get_angle(x3, x1, y3, y1))
                            c1 = int(get_angle(x3, x2, y3, y2))

                            theta1 = abs(a2 - a1)
                            theta2 = abs(b2 - b1)
                            theta3 = abs(c2 - c1)
                            #theta1 = int(abs(get_angle_between(a1, a2)))

                            #theta1 = a2 - a1
                            #theta1 = abs((theta1 + 180) % 360 - 180)

                            #print(a1, a2, theta1)



                            #theta2 = abs(b2 - b1)
                            #theta3 = 180 - (theta1 + theta2)

                            draw.polygon([(x1, y1), (x2, y2), (x3, y3)], fill=(255, 255, 255))

                            text_position = get_center(x1, x2, y1, y2)
                            distance = int(get_distance(x1, x2, y1, y2)) / 10.0
                            drawText.text((text_position[0] + 10, text_position[1] + 10), "{}cm".format(distance), font=font, fill=text_color)

                            text_position = get_center(x2, x3, y2, y3)
                            distance = int(get_distance(x2, x3, y2, y3)) / 10.0
                            drawText.text((text_position[0] + 10, text_position[1] + 10), "{}cm".format(distance), font=font, fill=text_color)

                            text_position = get_center(x1, x3, y1, y3)
                            distance = int(get_distance(x1, x3, y1, y3)) / 10.0
                            drawText.text((text_position[0] + 10, text_position[1] + 10), "{}cm".format(distance), font=font, fill=text_color)

                            #draw.arc([x1 - arc_size, y1 - arc_size, x1 + arc_size, y1 + arc_size], min(a1, a2), max(a1, a2), fill=128, width=5)

                            if(abs(min(a1, a2) - min(a1, a2) + theta1) < 180):
                                draw.arc([x1 - arc_size, y1 - arc_size, x1 + arc_size, y1 + arc_size], min(a1, a2), min(a1, a2) + theta1, fill=128, width=5)
                            else:
                                draw.arc([x1 - arc_size, y1 - arc_size, x1 + arc_size, y1 + arc_size], max(a1, a2), min(a1, a2), fill=128, width=5)
                                theta1 = 360 - abs(max(a1, a2) - min(a1, a2))

                            if(abs(min(b1, b2) - min(b1, b2) + theta2) < 180):
                                draw.arc([x2 - arc_size, y2 - arc_size, x2 + arc_size, y2 + arc_size], min(b1, b2), min(b1, b2) + theta2, fill=128, width=5)
                            else:
                                draw.arc([x2 - arc_size, y2 - arc_size, x2 + arc_size, y2 + arc_size], max(b1, b2), min(b1, b2), fill=128, width=5)
                                theta2 = 360 - abs(max(b1, b2) - min(b1, b2))

                            if(abs(min(c1, c2) - min(c1, c2) + theta3) < 180):
                                draw.arc([x3 - arc_size, y3 - arc_size, x3 + arc_size, y3 + arc_size], min(c1, c2), min(c1, c2) + theta3, fill=128, width=5)
                            else:
                                draw.arc([x3 - arc_size, y3 - arc_size, x3 + arc_size, y3 + arc_size], max(c1, c2), min(c1, c2), fill=128, width=5)
                                theta3 = 360 - abs(max(c1, c2) - min(c1, c2))

                            drawText.text((x1 + 10, y1 + 30), "{}°".format(theta1), font=font, fill=text_color)
                            drawText.text((x2 + 10, y2 + 30), "{}°".format(theta2), font=font, fill=text_color)
                            drawText.text((x3 + 10, y3 + 30), "{}°".format(theta3), font=font, fill=text_color)

                            #if(a1 - a2 < 0):
                            #    draw.arc([x1 - arc_size, y1 - arc_size, x1 + arc_size, y1 + arc_size], a2, a2 + theta1, fill=128, width=5)
                            #else:
                            #    draw.arc([x1 - arc_size, y1 - arc_size, x1 + arc_size, y1 + arc_size], a1, a1 + theta1, fill=128, width=5)


                            #draw.arc([x2 - arc_size, y2 - arc_size, x2 + arc_size, y2 + arc_size], min(b1, b2), min(b1, b2) + theta2, fill=128, width=5)

                            #draw.arc([x3 - arc_size, y3 - arc_size, x3 + arc_size, y3 + arc_size], min(a2 + 180, a3 + 180), max(a2 + 180, a3 + 180), fill=128, width=5)

                            draw.line([x1, y1, x2, y2], fill=128, width=5)
                            draw.line([x2, y2, x3, y3], fill=128, width=5)
                            draw.line([x1, y1, x3, y3], fill=128, width=5)
                except Exception as e:
                    print(e)
                    print("LINE_MODE: could not draw lines - too few M5Stacks?")



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
                    print("could not load image")
                    pass

                # adjust rotation
                img_m5_temp = img_m5_temp.rotate(360 - m5.last_angle)

                # draw text with coordinates
                text_color = (50, 0, 200, 255)
                if(m5.hasMoved() and not CAT_MODE):
                    text_color = (200, 0, 50, 255)
                    preview.paste(img_m5_ghost, (int(abs_x - (m5_w / 2)), int(abs_y - (m5_h / 2))), img_m5)
                drawText.text((10, (m5.number+1) * 50), "{}, {}".format(x, y), font=font, fill=text_color)
                preview.paste(img_m5_temp, (int(x - (m5_w / 2)), int(y - (m5_h / 2))), img_m5)


            preview.paste(text, (0, 0), text)
        elif(mode == SHOW_ONLY_ABSOLUTE):

            if not CAT_MODE:
                # draw grid
                num_lines_x = 8
                for i in range(num_lines_x):
                    line_x = int(SCREEN_W_PX / num_lines_x) * i
                    draw.line([line_x, 0, line_x, SCREEN_H_PX], fill=128)
                draw.line([0, int(SCREEN_H_PX * 0.33), SCREEN_W_PX, int(SCREEN_H_PX * 0.33)], fill=128)
                draw.line([0, int(SCREEN_H_PX * 0.66), SCREEN_W_PX, int(SCREEN_H_PX * 0.66)], fill=128)


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
                preview.paste(img_m5_temp, (int(abs_x - (m5_w / 2)), int(abs_y - (m5_h / 2))), img_m5)
                drawText.text((10, (m5.number+1) * 50), "{}, {}".format(x, y), font=font, fill=text_color)
                #preview.paste(img_m5_temp, (int(x - (m5_w / 2)), int(y - (m5_h / 2))), img_m5)


            preview.paste(text, (0, 0), text)
        elif(mode == SHOW_SENSOR_IMAGE):
            m5 = m5stacks[0]
            pattern = Image.fromarray(m5.raw_img).convert('RGBA')
            pattern = pattern.resize((SENSOR_IMAGE_WIDTH, SENSOR_IMAGE_HEIGHT), Image.NEAREST)
            preview.paste(pattern, (int(SCREEN_W_PX / 2 - SENSOR_IMAGE_WIDTH / 2), int(SCREEN_H_PX / 2 - SENSOR_IMAGE_HEIGHT / 2)), pattern)
        elif(mode == SHOW_CUPBOARD_DEMO):
            m5 = m5stacks[0]

            for i in range(3):
                if( m5.getPosition()[0] > i * (SCREEN_W_PX / 3) and
                    m5.getPosition()[0] < (i + 1) * (SCREEN_W_PX / 3)):
                    color = (255, 0, 0)
                else:
                    color = (50, 50, 50)

                left = int(SCREEN_W_PX * 0.1)
                right = int(SCREEN_W_PX * 0.9)
                top = int(SCREEN_H_PX * 0.1) + i * (SCREEN_H_PX / 4)
                bottom = top + (SCREEN_H_PX / 4)

                draw.rectangle([left, 
                                top,
                                right,
                                bottom],
                                fill=color,
                                outline=(0, 0, 0),
                                width=5)



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
            mode = SHOW_ONLY_ABSOLUTE
        elif(key == ord('s')):
            mode = SHOW_SENSOR_IMAGE
        elif(key == ord('d')):
            mode = SHOW_CUPBOARD_DEMO
        elif(key == ord('c')):
            CAT_MODE = not CAT_MODE
        elif(key == ord('l')):
            LINE_MODE = not LINE_MODE
        elif(key == ord('x')):
            m5stacks.append(MFakeStack(2))
            m5count += 1

    connectionHandler.server_close()
    connectionHandlerThread.join()

    for m5 in m5stacks:
        m5.die()
    time.sleep(1)
    sys.exit()
