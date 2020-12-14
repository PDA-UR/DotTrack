#!/usr/bin/env python3

import ebb_motion
import ebb_serial
import math
import time
import socket
import os
import numpy as np
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

IP = '1.2.3.4' # local IP, change this
TCP_PORT = 8090
BUFFER_SIZE = 1

M5_SIZE = 54

# AxiDraw settings
STEPS_PER_MM = 81.05    # AxiDraw documentation states 80 steps, however 
COLUMNS = 100
ROWS = 100

# page settings
PAGE_WIDTH = A4[0] / mm
PAGE_HEIGHT = A4[1] / mm
PAGE_MARGIN = 5
# the movement boundaries for the M5Stack
MOVE_AREA_WIDTH = PAGE_WIDTH - 2*PAGE_MARGIN - M5_SIZE
MOVE_AREA_HEIGHT = PAGE_HEIGHT - 2*PAGE_MARGIN - M5_SIZE

# the amount of steps to move between columns/rows
STEPS_X = round(MOVE_AREA_WIDTH / (COLUMNS-1) * STEPS_PER_MM * -1)
STEPS_Y = round(MOVE_AREA_HEIGHT / (ROWS-1) * STEPS_PER_MM)

imgsize = [36, 36]
img_byte_len = imgsize[0] * imgsize[1]
conn = None
sock_image = None

path = "test"


# TODO: replace local M5Stack functions with imports from ./livetracker/raw_grabber.py
def connect():
    global conn, sock_image
    sock_image = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock_image.bind((IP, TCP_PORT))
    sock_image.listen(1)
    conn, addr = sock_image.accept()
    print("connected")

def get_image():
    global conn, sock_image
    buf = b''

    while True:
        try:
            received = conn.recv(BUFFER_SIZE)
        except ConnectionResetError:
            print("connection reset by peer. trying to reconnect...")
            sock_image.close()
            connect()
            return None
        except:
            print("unkown error trying to receive image")

        if received == b'':
            print("connection broken")
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
    img = Image.frombytes("L", imgsize, data)

    return np.array(img)


def pos_in_grid(row, col):
    pos = (
        round(PAGE_MARGIN + M5_SIZE/2 + (col) * STEPS_X / STEPS_PER_MM * (-1), 2),
        round(PAGE_MARGIN + M5_SIZE/2 + (row) * STEPS_Y / STEPS_PER_MM, 2)
    )
    return pos

def save_img(r, c):
    pos = pos_in_grid(r, c)
    global conn

    # save dataset in /DotTrack/img_dataset/
    filename = "{}_{}-{}_{}.png".format(pos[0], pos[1], r, c)
    #str(pos[0]) + "_" + str(pos[1] + "-" + str(r) + "_" + str(c)) + ".png"
    target_dir = os.path.dirname(os.path.dirname(__file__)) + path + "/"
    if not os.path.exists(target_dir):
        os.mkdir(target_dir)

    while True:
        message = "failed\n"
        conn.send(message.encode()) # looks strange again. just believe dev #2 as well
        img = None
        img = get_image()
        conn.send(message.encode()) # looks strange but just believe me

        if img.any():   # continue on image received
            break

    # save image to file
    image = Image.fromarray(get_image())
    image.save(target_dir + filename)

def move_over_page(port, cols, rows, duration):
    # abrupt stops can cause the AxiDraw to missallign.
    # 2s recommended to move from one short end of the paper to the other
    # multiply duration with the golden ratio (1.4142) to achieve the same AxiDraw speed

    return_duration_x = 2000
    return_duration_y = round(2000 * 1.4142)
    duration_x = duration
    duration_y = round(duration * 1.4142)

    # move over the defined grid size of the page
    # code has to sleep for the same duration the AxiDraw was instructed to move at least.
    # added short sleeps to prevent AxiDraw missalligning due to abrupt movements
    # added short sleep before image capture to prevent shaky images
    for r in range(rows):
        #if(r < 13):
        #    continue
        time.sleep(0.1) # pause before starting a row
        for c in range(cols):
            #if(r == 7 and c <= 72):
            #    continue
            time.sleep(0.1) # pause before image capture
            save_img(r, c)
            # c0->c99 requires only 98 movements
            if c != cols-1:
                ebb_motion.doABMove(port, 0, STEPS_X, duration_x)
                time.sleep(duration_x/1000)

        # move back to the first column
        ebb_motion.doABMove(port, 0, -1*STEPS_X*(cols-1), return_duration_x)
        time.sleep(return_duration_x/1000)
        if r != rows-1:
            ebb_motion.doABMove(port, STEPS_Y, 0, duration_y)
            time.sleep(duration_y/1000)

    # move back to home position (0, 0)
    ebb_motion.doABMove(port, -1*STEPS_Y*(rows-1), 0, return_duration_y)
    time.sleep(return_duration_y/1000)

if __name__ == "__main__":
    duration = 200

    connect()
    port = ebb_serial.openPort()
    ebb_motion.sendDisableMotors(port)

    move_over_page(port, COLUMNS, ROWS, duration)

    ebb_motion.sendDisableMotors(port)
    sock_image.close()
