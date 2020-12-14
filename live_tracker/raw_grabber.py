#!/usr/bin/env python3
# coding: utf-8

# # DotTrack
# 
# (C) 2018 - 2019 Dennis Schüsselbauer (original code)  
# (C) 2020 Raphael Wimmer (porting, cleanup)
# (C) 2020 Andreas Schmid (extending, cleanup)

from PIL import Image, ImageDraw, ImageFilter
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

imgsize = [36, 36]
img_byte_len = imgsize[0] * imgsize[1]

IP = '1.2.3.4' # local IP, change this
TCP_PORT = 8090
BUFFER_SIZE = 1

connected = False

def connect():
    sock_image = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock_image.bind((IP, TCP_PORT))
    sock_image.listen(1)
    conn, addr = sock_image.accept()

    connected = True
    print("connected")
    return sock_image, conn

def get_image(conn):
    buf = b''

    while True:
        received = conn.recv(BUFFER_SIZE)
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

def main():
    sock_image, conn = connect()
    counter = 0

    while(True):
        if not connected:
            time.sleep(1)

        img = None
        img = get_image(conn)
        if img is None:
            print("receiving image failed")
            img = np.zeros((36, 36), dtype="uint8")

        message = "failed\n"
        conn.send(message.encode()) # looks strange but just believe me

        cv2.imshow("preview", img)

        key = cv2.waitKey(1)
        if(key == ord('q')):
            break
        if(key == ord('p')):
            cv2.imwrite('output/{}_0-0_0.png'.format(counter), img)
            counter += 1
            print("{} written!".format(counter))

        #time.sleep(0.1)
    sock_image.close()
    sys.exit()

if __name__ == "__main__":
    main()
