#!/usr/bin/env python3
# coding: utf-8

# # DotTrack
# 
# (C) 2018 - 2019 Dennis Schüsselbauer (original code)  
# (C) 2020 Raphael Wimmer (porting, cleanup)
# (C) 2020 Andreas Schmid (extending, cleanup)

from PIL import Image, ImageDraw, ImageFilter
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

imgsize = [36, 36]
img_byte_len = imgsize[0] * imgsize[1]

#IP = '10.61.15.136' # local IP
IP = '192.168.178.77'
TCP_PORT = 8090
UDP_PORT = 9090
BUFFER_SIZE = 1

DBT_DPI = 150
DBT_W_PX = 8192
DBT_H_PX = 4096
DBT_W_MM = DBT_W_PX / DBT_DPI * 25.4
DBT_H_MM = DBT_H_PX / DBT_DPI * 25.4
#CROP_W_MM = 290
#CROP_H_MM = 200
CROP_W_MM = 1390
CROP_H_MM = 707
CROP_SHIFT_RIGHT = 0 #DBT_W_MM - CROP_W_MM
CROP_SHIFT_DOWN = 0 #DBT_H_MM - CROP_H_MM

SCREEN_W_PX = 580 * 2
SCREEN_H_PX = 400 * 2

receivingCoords = True

def get_dbt_log(dbt_w, dbt_h, win_w, win_h):
    # 1. DBT/Log Generation:
    dbt_gen = TorusGenerator(dbt_w, dbt_h, win_w, win_h)
    dbt_log = dbt_gen.constr_log
    return dbt_log

def extract_bitarray(img, cam_size, dbt_img_dpi, pipeline_id="baseline"):
    # Here we turn the image into a binary array of 0/255 pixels that represent the DBT pattern under the sensor.
    # Convert size from millimeters to inch
    cam_size_inch = (cam_size[0] / 25.4, cam_size[1] / 25.4)
    # Number of pattern pixels the sensor should be able to see
    # In our case:
    # 1.135 mm = 0.0447 inch
    # 0.0477 inch * 150 dpi = 6.7 (int() truncates to 6)
    num_ppx = (dbt_img_dpi[0]*cam_size_inch[0],
               dbt_img_dpi[1]*cam_size_inch[1])

    # Ratio of camera/image pixel per pattern pixel
    # In our case:
    # 36 px / 6 px = 6 
    px_ppx_ratio = (img.size[0]/num_ppx[0], img.size[1]/num_ppx[1])

    bit_array = np.zeros((int(num_ppx[1]), int(num_ppx[0])), dtype="uint8")
    #img = skimage.transform.rotate(np.array(img), 45)
    #cv2.imshow('rotate', np.array(img))

    # Calculate threshold value (with Otsus method) (omitted here as it is not used --RW)
    threshold = 127

    # Grid based extraction
    # 0. Find grid anchor (for later)
    min_error = None
    offset_range_x = px_ppx_ratio[0]
    offset_range_y = px_ppx_ratio[1]
    # We don't have a perfect alignment of DBT pattern and image borders.
    # Brute-force find the offset that results in the "best" binarization, i.e. 
    # where DBT pixels are completely white or black. Minimize the variance in each cell.
    # shift between 0 and 5 pixels in X and Y -> 25 calculationsi
    img_array = skimage.img_as_ubyte(img)
    #cv2.imshow('angle: {}'.format(angle*90), np.array(img_array))
    for angle in range(0, 90, 10):
        # looks like its not THAT easy
        #img_array = skimage.transform.rotate(np.array(img), angle)
        #cv2.imshow("angle: {}".format(angle), img_array)
        for a_x in np.arange(0.0, offset_range_x, offset_range_x / num_ppx[0]):
            for a_y in np.arange(0.0, offset_range_y, offset_range_y / num_ppx[1]):
                anchor = (a_x, a_y) # the camera coordinates where the DBT pattern starts
                array = np.zeros((math.ceil(num_ppx[1]), math.ceil(num_ppx[0])), dtype="uint8")
                error_count = 0
                # 1. Implement grid as for-loop that walks every cell
                # In our case:
                # X/Y anchor + 36 
                # RW: TODO is this necessary?
                # RW better: generate 25 image copies, each shifted by anchor, scale it to 6x6 px, 
                # count completely black/white pixels 
                stop = (anchor[0]+px_ppx_ratio[0]*num_ppx[0],
                        anchor[1]+px_ppx_ratio[1]*num_ppx[1])
                x_range = list(np.arange(anchor[0], stop[0], px_ppx_ratio[0]))
                y_range = list(np.arange(anchor[1], stop[1], px_ppx_ratio[1]))
                for i, x in enumerate(x_range):
                    for j, y in enumerate(y_range):
                        cell = img_array[int(y):int(y+px_ppx_ratio[1]), int(x):int(x+px_ppx_ratio[0])]
                        # 2. Calculate cell binary value (count black/white pixels;
                        # optional margin)
                        bit_color, err = calc_cell_bit(cell,
                                                       ret_err_count=True,
                                                       threshold=threshold,
                                                       pipeline_id=pipeline_id)
                        error_count += err
                        # 3. Write value to bit_array
                        array[j, i] = bit_color
                if min_error is None or min_error > error_count:
                    min_error = error_count
                    array = np.delete(array, -1, 1)
                    bit_array = array[:-1] # test
                    final_anchor = anchor
                    final_angle = angle
        break

    return bit_array, final_anchor, final_angle 

def preprocess_image(img, pipeline_id="baseline"):
    if pipeline_id == "direct_bit_extract":
        # No preprocessing wanted
        return img

    # Edge enhance
    img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)

    img_ero_3 = img.filter(ImageFilter.MinFilter(3))
    img_ero_3_dil_3 = img_ero_3.filter(ImageFilter.MaxFilter(3))
    img = img_ero_3_dil_3

    img = cv2.adaptiveThreshold(np.array(img),255,cv2.ADAPTIVE_THRESH_MEAN_C,\
                cv2.THRESH_BINARY,19,2)

    img = Image.fromarray(img)
    return img

# return: 0/black or 255/white and win_lose_delta (for error variable)
def calc_cell_bit(cell_array, ret_err_count=False, margin=(0, 0),
                  x_shaped_crop=False, threshold=127, pipeline_id="baseline"):
    # TODO: Crop to margin
    # TODO: Maybe count in a cross shape when there are very few pixels (3x3)

    BLACK = 0  # Black in greyscale.
    WHITE = 255  # White in greyscale.

    if pipeline_id == "baseline":
        col_counts = {}
        # https://stackoverflow.com/a/35549699
        col_counts[WHITE] = np.count_nonzero(cell_array == WHITE)
        col_counts[BLACK] = np.count_nonzero(cell_array == BLACK)
        # Currently biased towards white:
        # (if white_count == black_count: return WHITE)
        if col_counts[BLACK] > col_counts[WHITE]:
            if ret_err_count:
                return BLACK, col_counts[WHITE]
            else:
                return BLACK
        else:
            if ret_err_count:
                return WHITE, col_counts[BLACK]
            else:
                return WHITE
    elif pipeline_id == "direct_bit_extract":
        # 1. Get threshold value of entire image (Otsu)
        # Given by extract_bitarray function.

        # 2. Calculate greyscale errors
        # 2.1. Determine if bigger or smaller than threshold
        # 2.2. Calculate difference from threshold
        # 2.3. Normalize threshold-difference (because we use Otsu and don't
        # split right in the middle)

        err_sum = 0.0
        for x in range(cell_array.shape[1]):
            for y in range(cell_array.shape[0]):
                px = cell_array[y, x]
                if px > threshold:
                    # normalized delta error of white pixels (positive values)
                    # 255 = maximal possible value of (whole) image
                    # TODO: use maximal value of whole image?
                    # TODO: use maximal value of cell image?
                    err = (px - threshold) / (255 - threshold)
                else:
                    # normalized delta error of black pixels (negative values)
                    err = (px - threshold) / threshold
                err_sum += err

        # 3. Extract bit (and error count)
        # 3.1 Summarise all pixel error values -> cell error value
        # 3.2 Determine bit color

        if err_sum > 0.0:
            # white / 255 value
            if ret_err_count:
                return WHITE, err_sum
            else:
                return WHITE
        else:
            # black / zero value
            if ret_err_count:
                return BLACK, err_sum
            else:
                return BLACK

def decode_dbt_positions(wins_array, win_w, win_h, dbt_log):
    positions = []
    x_range = wins_array.shape[1] - win_w + 1
    y_range = wins_array.shape[0] - win_h + 1
    # Check if number of possible window positions is sound
    if x_range < 1 or y_range < 1:
        raise ValueError("Windows array too small for requested window.")

    for x in range(x_range):
        for y in range(y_range):
            win = wins_array[y:y+win_h, x:x+win_w]
            x_pos, y_pos = decode_dbt_pos(win, dbt_log)
            if x_pos != -1: 
                # offset found position by window offset, so we get the true anchor
                x_pos -= x
                y_pos -= y
                positions.append((x_pos, y_pos))
            #else:
            #    return None
    return positions



# Decoding algorithm according to Shiu ("Decoding de Bruijn arrays as
# constructed by Fan et al.")
def decode_dbt_pos(win, log):  # , src_dbt=None):
    BLACK = 0  # Black in greyscale.
    WHITE = 255  # White in greyscale.
    # Variables needed:
    # * Window matrix (win).
    # * Generation protocol/data object. Holds all pertinent information needed
    # for decoding the dbt position and should allow for recursion along the
    # recorded protocol.
    # * array_type (or a value from which you can reverse the array type; e.g.
    # construction type, col_sums, ODD/EVEN, etc.)
    # * Source dbt which was used to generate the final dbt (src_dbt). This
    # should indicate that there is no more recursion wanted and that D(M)
    # should be searched by brute force. Maybe can be part of the generation
    # data/protocol object.

    x, y = -1, -1

    # => 4x4 (and 5x5) DBTs are **type 1** arrays. -> focus on type 1 decoding
    # first

    # Decoding algorithm seems to be recursive (find in step 2) and needs the
    # matrices that were used for construction.

    # We need the source DBT (values), which eventually gets searched. The make
    # and transpose steps need to record the pertinent information.

    # Be aware/cautious of the different initial values for positional values.
    # In the math world you start counting at 1 (origin is at (1, 1)) but in
    # informatics you start at 0 (origin is at (0, 0)).
    # Therefore when there are +1 or -1 calculations that don't show up in
    # Shius algorithm it is most likely to compensate for differing positional
    # values.

    # Decoding algorithm for arrays of type 1:
    # r, s = src_dbt.shape  # TODO: Get from TorusGenerator object
    # m, n = win.shape[0] - 1, win.shape[1]
    # m, n = win.shape
    # m -= 1
    log_entry = log[-2]
    # #placeholder_print(win)
    # #placeholder_print(log_entry)
    src_dbt = None
    r, s, m, n = log_entry.dimensions
    # if log[-1].transposed:
    #     r, s = s, r
    #     m, n = n, m
    dbs_seed = Torus.debruijn(n)
    dbs_seed = dbs_seed[1:]
    dbs_seed = dbs_seed + dbs_seed[:n-1]
    dbs_seed = np.array(dbs_seed) * WHITE
    ##placeholder_print(f"DBS seed: {dbs_seed}")

    # Step 1: Compute: {dm}")
    dm = compute_dm(win)
    # #placeholder_print(f"dm:\n{dm}")

    # Step 2: Find the location of D(M) in A. Get i, j.
    # if src_dbt is not None:
    if len(log) == 2:
        # #placeholder_print("BRUTE FORCE LOOKUP:")
        # Brute force lookup if it is the last two log entry.
        src_dbt = io.imread(log_entry.fname)
        j, i = find_in_array(dm, src_dbt)
        # #placeholder_print(f"BRUTE FORCE LOOKUP ENDED: {j}, {i}")
    else:
        # TODO: do recursion
        # #placeholder_print(f"RECURSION {len(log)}:")
        if log_entry.transposed:
            # #placeholder_print("Transposed!")
            i, j = decode_dbt_pos(dm.transpose(), log[:-1])
        else:
            # #placeholder_print("NOT transposed!")
            j, i = decode_dbt_pos(dm, log[:-1])
        # #placeholder_print(f"RECURSION {len(log)} ENDED:")
    # #placeholder_print(f"win:\n{win}")
    # #placeholder_print(f"r: {r}, s: {s}, m: {m}, n: {n}")
    # #placeholder_print(f"i: {i}, j: {j}")

    # Step 3: Calculate -a>.
    if src_dbt is None:
        src_dbt = io.imread(log_entry.fname)
    a_vec = np.zeros(win[0, ].shape, dtype=np.uint8)
    a_vec |= win[0, ]
    for i_tmp in range(i):
        a_vec ^= src_dbt[i_tmp, j:j+n]
    zero_vec = np.zeros(a_vec.shape, dtype=np.uint8)
    # #placeholder_print(f"a_vec:\n{a_vec}")
    # #placeholder_print(f"dbs_seed:\n{dbs_seed}")

    # Step 4:
    #       if -a> == -0>:
    #           k = j
    #       else:
    #           Find g in alpha (de Bruijn sequence)
    if (a_vec == zero_vec).all():
        k = j
    else:
        g = find_in_seq(a_vec, dbs_seed) + 1
        if not 1 <= g <= 2**n - 1:
            raise ValueError(f"The g variable ({g}) is not in the right " +
                             f"value range.")
        # #placeholder_print(f"g: {g}")

        # Step 5: Solve congruence equation: g+(2**n-1)*x === j (mod s),
        # 0<=x<=s–1.

        # Found in this thread:
        # https://stackoverflow.com/a/16044630
        # Not sure about license:
        # https://www.algorithmist.com/index.php/Modular_inverse
        # Implemented according to Wikipedias pseudocode:
        # https://en.wikipedia.org/wiki/Extended_Euclidean_algorithm#Modular_integers
        def inverse(a, n):
            t, newt = 0, 1
            r, newr = n, a
            while newr != 0:
                quotient = r // newr
                t, newt = newt, t - quotient * newt
                r, newr = newr, r - quotient * newr
            if r > 1:
                raise ValueError(f"a ({a}) is not invertible")
            if t < 0:
                t = t + n
            return t

        x_tmp = inverse((2**n - 1), s)
        if x_tmp is None:
            raise ValueError(f"inverse({2**n-1}, {s}) is not solvable")
        b = ((j+1) - g)
        x_tmp *= b
        x_tmp %= s
        # if ((b * (2**n - 1)) % s) != (j+1):
        #     raise ValueError(f"Check not working!")
        # x_tmp = (((j+1) - g) * (2**n - 1)) % s
        if not 0 <= x_tmp <= s-1:
            raise ValueError(f"The x_tmp variable ({x_tmp}) is not in the " +
                             f"right value range.")
        # #placeholder_print(f"x_tmp: {x_tmp}")

        # Step 6: Calculate k: k = s + g + (2**n - 1) * x
        k = (s + g + (2**n - 1) * x_tmp) - 1
    # #placeholder_print(f"k: {k}")

    # Step 7: The top left hand corner of M is the (i,k)-th entry of A1.
    x, y = k, i
    # #placeholder_print(f"x: {x}, y: {y}")

    # if log[-1].transposed:
    #     x, y = y, x

    return x, y

def compute_dm(array):
    dm = []
    for y in range(array.shape[0] - 1):
        dm.append(array[y, ] ^ array[y+1, ])
    return np.vstack(dm)


def find_in_array(win, array):
    # #placeholder_print(f"find_in_array:\nwin:\n{win},\narray.shape(extended): " +
    #       f"{array.shape}")
    x_range = array.shape[1] - win.shape[1] + 1
    y_range = array.shape[0] - win.shape[0] + 1

    # TODO/FIXME/URGENT: Extend edges. Should be done to PNGs. (NOT AT RUNTIME)
    # top_rows = array[0:win.shape[0]-1, ]
    # left_cols = array[:, 0:win.shape[1]-1]
    # top_left_corner = array[0:win.shape[0]-1, 0:win.shape[1]-1]
    # bottom = np.hstack((top_rows, top_left_corner))
    # left_added = np.hstack((array, left_cols))
    # bottom_added = np.vstack((left_added, bottom))
    # new_array = bottom_added
    # #placeholder_print(new_array)
    # #placeholder_print(f"find_in_array:\nwin: {win},\narray.shape: {array.shape}")

    for x in range(x_range):
        for y in range(y_range):
            # np.array_equal() is slower (rather big difference)
            subarray = array[y:y+win.shape[0], x:x+win.shape[1]]
            if (win == subarray).all():
                return x, y
    return -1, -1



# 4. Calculate actual positions on the page (in millimeters)
def calculate_real_positions(px_positions, dpi, margin):
    # TODO: Use the center of the dbt window instead of the top left position.
    # TODO: Improve real position based on window anchor.
    # TODO: Check if real position is possible with help of pagesize and/or
    # cropped_area.
    # , win_w, win_h, win_anchor, cam_reso, cam_size, pagesize=None,
    # cropped_area=None):
    positions = []
    for px_pos in px_positions:
        x = ((px_pos[0] / dpi[0]) * 25.4) + margin[0]
        y = ((px_pos[1] / dpi[1]) * 25.4) + margin[1]
        positions.append((x, y))
    return positions


def calculate_confidence(dbt_positions):
    most_common = Counter(dbt_positions).most_common()

    #placeholder_print(most_common)
    position = most_common[0][0]
    if len(most_common) == 1: # one position
        confidence = 100
    elif len(most_common) == len(dbt_positions):
        confidence = 0
    else:
        confidence = int(100 * (1.0 - (most_common[-1][1] / most_common[0][1])/2)) # 2,2 → 0.5 / 2,1,1 → 0.75 / 3,1 → 0.85 
    return confidence, position

def find_in_seq(win, sequence):
    pos = -1
    seq_range = len(sequence) - len(win) + 1
    for i in range(seq_range):
        if (win == sequence[i:i+len(win)]).all():
            pos = i
            break
    return pos

def remove_small_connected_regions(image, min_size, get_only_regions_to_remove=False):
        # https://stackoverflow.com/questions/42798659/how-to-remove-small-connected-objects-using-opencv
        nb_components, output, stats, centroids = cv2.connectedComponentsWithStats(image, connectivity=8)
        sizes = stats[1:, -1]
        nb_components = nb_components - 1

        output_image = np.zeros(shape=image.shape, dtype=np.uint8)
        # for every component in the image, you keep it only if it's above min_size
        for i in range(0, nb_components):
            if get_only_regions_to_remove:
                if sizes[i] < min_size:
                    output_image[output == i + 1] = 255
            else:
                if sizes[i] >= min_size:
                    output_image[output == i + 1] = 255

        return output_image

def get_coords(subframe: Image, dbt_dpi=DBT_DPI): # Pillow Image with 36x36 px
    CAM_RESO = (36, 36)  # Camera resolution in pixel.
    CAM_SIZE = (1.135, 1.135)  # Camera capture area in millimeters. See https://github.com/PDA-UR/DotTrack/commit/fb9fb1e
    DBT_W, DBT_H = 8192, 4096  # De Bruijn torus width & height (pixels).
    WIN_W, WIN_H = 5, 5  # De Bruijn torus window width & height.
    
    # change me
    pipeline_id = "baseline"
    #pipeline_id = "direct_bit_extract"
    # 1. Image Generation:
    dbt_w, dbt_h, win_w, win_h = DBT_W, DBT_H, WIN_W, WIN_H
    dpi = (dbt_dpi, dbt_dpi)
    dbt_gen = TorusGenerator(dbt_w, dbt_h, win_w, win_h)
    dbt_log = dbt_gen.constr_log
    dbt_fname = dbt_log[-1].fname

    original = subframe

    # 2. Image Analysis (extract array out of picture):
    start_time = time.perf_counter()
    # subframe = unrotate_image(subframe)  # TODO

    angle = 0
    subframe = preprocess_image(subframe, pipeline_id)

    subarray = [None]*4
    dbt_positions = [None]*4
    confidence = [None]*4
    position = [None]*4

    subarray[0], anchor, angle2 = extract_bitarray(subframe, CAM_SIZE, dpi, pipeline_id)
    subarray[1] = np.rot90(subarray[0], 3)
    subarray[2] = np.rot90(subarray[0], 2)
    subarray[3] = np.rot90(subarray[0])

    best_confidence = 0
    best_confidence_i = 0
    # 3. Decoding algorithm according to Shiu
    for i in range(0, 4):
        dbt_positions[i] = decode_dbt_positions(subarray[i], win_w, win_h, dbt_log)
        confidence[i], position[i] = calculate_confidence(dbt_positions[i])
        if(confidence[i] > best_confidence):
            best_confidence = confidence[i]
            best_confidence_i = i

    #placeholder_print("Candidates (DBT): ", dbt_positions)
    
    # 4. Calculate actual positions on the page (in millimeters)
    # Variables:
    # * dbt/pixel positions
    # * dpi
    # * margin (hardcoded for now; assumes (5, 5) mm) # RW: determined numbers for test run capture
    #placeholder_print("DBT position:", position)
    margin = (-27.5, -26)
    real_position = calculate_real_positions([position[best_confidence_i]], dpi, margin)[0]
    #placeholder_print("real position:", real_position)

    total_time = time.perf_counter() - start_time
    print(f"Frame analysing took {total_time:.3f}s")
    
    # overlay
    #original = np.array(original)
    #original = cv2.cvtColor(original, cv2.COLOR_GRAY2RGB)
    #height, width = original.shape[:2]
    #overlay = cv2.resize(subarray[0],(width, height), interpolation = cv2.INTER_NEAREST)
    #overlay = cv2.cvtColor(overlay, cv2.COLOR_GRAY2RGB)

    #overlay[np.where((overlay==[0,0,0]).all(axis=2))] = [0,0,255]
    #overlay[np.where((overlay==[255,255,255]).all(axis=2))] = [0,255,0]

    #cv2.addWeighted(original, 0.9, overlay, 0.1, 0, overlay)

    return(real_position, confidence[best_confidence_i], best_confidence_i * 90 + angle, subarray[0], anchor)


def convert_coords(x, y):
    new_x = 10000 - (x / CROP_W_MM) * 10000
    new_y = 10000 - ((y / CROP_H_MM) * 10000)
    return (new_x, new_y)


class M5Stack:
    coords = (0, 0)
    angle = 0

    lastX = 0
    lastY = 0
    lastAngle = 0

    eyeAngle = 0

    flag_kill_connect_thread = True
    connected = False

    temp_img = None
    binarized_img = None

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

        print(number, " initialized with ports ", self.TCP_PORT, self.UDP_PORT)

    def connect(self):
        self.sock_image = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_image.bind((IP, self.TCP_PORT))
        self.sock_image.listen(1)
        self.conn, self.addr = self.sock_image.accept()

        self.sock_coords = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP-Socket to receive Coordinates
        self.sock_coords.bind((IP, self.UDP_PORT))

        self.connected = True
        print(self.number, "connected")

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
                self.coords = (x, y)

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
        img = Image.frombytes("L", imgsize, data)
        self.temp_img = img

        return img

    def update(self):
        print(self.number, "update started")
        while(self.alive == True):
            if(self.connected == False):
                time.sleep(0.1)
                continue
            else:
                if(self.flag_kill_connect_thread == True):
                    self.connectThread.join()
                    self.flag_kill_connect_thread = False
                    print(self.number, "connect thread killed")

            img = self.get_image()
            if(img == None):
                print(self.number, "receive image failed")
                break
            message = "failed\n"
            (x_in_mm, y_in_mm), confidence, angle, self.binarized_img, anchor = get_coords(img)
            angle = (angle + 90) % 90
            if(confidence >= 83):
                (coord1, coord2) = convert_coords(x_in_mm, y_in_mm)
                message = '{}|{}|{}|{}|{};\n'.format(coord1, coord2, angle, self.eyeAngle, self.distance)
                self.lastX = coord1
                self.lastY = coord2
                self.lastAngle = angle

            else:
                message = '{}|{}|{}|{}|{};\n'.format(self.lastX, self.lastY, self.lastAngle, self.eyeAngle, self.distance)
            self.conn.send(message.encode())
        self.alive = False

    def die(self):
        print(self.number, "dying...")
        self.sock_image.close()
        self.alive = False
        self.receiveCoordThread.join()
        self.updateThread.join()

    def getPosition(self):
        return self.coords
    
    def setRelativePosition(self, otherCoords):
        x, y = self.coords
        x2, y2, = otherCoords
        self.distance = math.sqrt((x-x2)**2 + (y-y2)**2)
        self.eyeAngle = math.degrees(math.atan2(x-x2, y-y2))


# AS:
# What if we don't binarize but accept "unsure" dots?
# We could brute force them?
def preprocess_test(raw, binarized):
    size = (256, 256)
    img = raw

    ground_truth = np.array(preprocess_image(Image.fromarray(raw)))

    ######################
    # Visualize pipeline #
    ######################

    pipeline = img

    #img = Image.fromarray(img)
    #img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)


    # Normalize (0 - 255)
    img = img.astype(np.float32)
    minimum = img.min()
    maximum = img.max()

    img -= minimum
    img /= maximum - minimum
    img *= 255

    img = img.astype(np.uint8)
    #pipeline = np.concatenate((pipeline, img), axis=1)

    #kernel = np.array([ [-1,0,1],
    #                    [-1,0,1],
    #                    [-1,0,1]])

    kernel = np.array([ [-1,-1,-1],
                        [-1,9,-1],
                        [-1,-1,-1]])
    img = cv2.filter2D(img, -1, kernel)

    pipeline = np.concatenate((pipeline, img), axis=1)

    #img = cv2.fastNlMeansDenoising(img,None,10,3,5)

    ## tried some blurring!
    #tmp = img
    #buf = None

    #for i in [3, 5, 7, 9]:
    #    if(i == 3):
    #        buf = cv2.medianBlur(img, i)
    #    else:
    #        buf = np.concatenate((buf, cv2.medianBlur(img, i)), axis = 1)
    #buf = np.concatenate((buf, img), axis = 1)
    #buf = cv2.resize(buf, (256 * 5, 256), interpolation=cv2.INTER_NEAREST)
    #cv2.imshow("blur", buf)

    # best bilateral filter!
    #img = cv2.bilateralFilter(img,15,50,50)

    img = cv2.medianBlur(img, 3)

    pipeline = np.concatenate((pipeline, img), axis=1)

    # Boolean Mask

    kernel = np.ones((3,3), np.uint8) 
    img = cv2.erode(img, kernel, iterations=1) 

    #pipeline = np.concatenate((pipeline, img), axis=1)

    kernel = np.ones((3,3), np.uint8) 
    img = cv2.dilate(img, kernel, iterations=1) 

    pipeline = np.concatenate((pipeline, img), axis=1)

    # setze alles dunkle auf schwarz
    mask = img < 70
    img[mask] = 0
    pipeline = np.concatenate((pipeline, img), axis=1)

    img = cv2.adaptiveThreshold(np.array(img),255,cv2.ADAPTIVE_THRESH_MEAN_C,\
                cv2.THRESH_BINARY,19,2)

    pipeline = np.concatenate((pipeline, img), axis=1)

    (x_in_mm, y_in_mm), confidence, angle, binarized, anchor = get_coords(Image.fromarray(img))
    anchor = list(anchor)
    anchor[0] *= (256 / 36)
    anchor[1] *= (256 / 36)

    binarized = cv2.resize(np.array(binarized), (36, 36), interpolation=cv2.INTER_NEAREST)
    pipeline = np.concatenate((pipeline, np.array(binarized)), axis=1)

    white = np.ones((36, 36), np.uint8)
    pipeline = np.concatenate((pipeline, white), axis=1)

    pipeline = cv2.resize(pipeline, (256 * 8, 256), interpolation=cv2.INTER_NEAREST)
    pipeline = cv2.cvtColor(pipeline, cv2.COLOR_GRAY2RGB)
    cv2.rectangle(pipeline, (256 * 7, 0), (256 * 8, 256), (150, 150, 150), -1)

    # draw binarization grid
    for x in range(0, 256, int(256/6)):
        cv2.line(pipeline,  (int(256 * 5 + anchor[0]), int(0 + anchor[1] + x)),
                            (int(256 * 6 + anchor[0]), int(0 + anchor[1] + x)),
                            (255, 0, 0), 1)

        cv2.line(pipeline,  (int(256 * 5 + anchor[0] + x), int(anchor[1])),
                            (int(256 * 5 + anchor[0] + x), int(anchor[1] + 256)),
                            (255, 0, 0), 1)

    pipeline = cv2.putText(pipeline, "{}%".format(confidence), (255 * 7 + 50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0))

    cv2.imshow("pipeline", pipeline)

    #############
    # Old Stuff #
    #############

    #img = img.filter(ImageFilter.MinFilter(3))
    #pipeline = np.concatenate((pipeline, np.array(img)), axis=1)
    #img = img.filter(ImageFilter.MaxFilter(3))
    #pipeline = np.concatenate((pipeline, np.array(img)), axis=1)

    #img = cv2.adaptiveThreshold(np.array(img),255,cv2.ADAPTIVE_THRESH_MEAN_C,\
    #            cv2.THRESH_BINARY,19,2)
    #pipeline = np.concatenate((pipeline, np.array(img)), axis=1)

    #(x_in_mm, y_in_mm), confidence, angle, binarized, anchor = get_coords(np.array(img))
    #binarized = cv2.resize(np.array(binarized), (36, 36), interpolation=cv2.INTER_NEAREST)
    #pipeline = np.concatenate((pipeline, np.array(binarized)), axis=1)

    #pipeline = cv2.resize(pipeline, (256 * 6, 256), interpolation=cv2.INTER_NEAREST)
    #pipeline = cv2.putText(preview, "{}".format(confidence), (10, 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 0, 50))
    #cv2.imshow("pipeline", pipeline)
    
    ############################
    # Test bilateral filtering #
    ############################

    #bilat = None

    #for d in [3, 7, 11]:
    #    row = None
    #    for s in [25, 50, 75]:
    #        tmp = cv2.bilateralFilter(img, d, s, s)

    #        if row is None: 
    #            row = tmp
    #        else:
    #            row = np.concatenate((row, tmp))
    #    if bilat is None:
    #        bilat = row
    #    else:
    #        bilat = np.concatenate((bilat, row), axis=1)
    #            
    #bilat = cv2.resize(bilat, (768, 768), interpolation=cv2.INTER_NEAREST)
    #cv2.imshow("bilat", bilat)

    #############
    # Old stuff #
    #############

    #raw = cv2.resize(raw, size, interpolation = cv2.INTER_NEAREST)
    #binarized = cv2.resize(binarized, size, interpolation = cv2.INTER_NEAREST)
    ##img = cv2.resize(img, size, interpolation = cv2.INTER_NEAREST)
    #ground_truth = cv2.resize(ground_truth, size, interpolation = cv2.INTER_NEAREST)

    #out = np.concatenate((binarized, raw, ground_truth), axis=1)
    ##bilat = np.concatenate((bilat1, bilat2, bilat3), axis=1)
    ##out = np.concatenate((out, bilat))
    #cv2.imshow("output", out)

if __name__ == "__main__":
    m5stacks = []
    m5stacks.append(M5Stack(0))
    m5stacks.append(M5Stack(1))

    while True:
        preview = np.zeros((SCREEN_H_PX, SCREEN_W_PX), dtype="uint8")
        preview = cv2.cvtColor(preview, cv2.COLOR_GRAY2RGB)
        cv2.rectangle(preview, (0, 0), (SCREEN_W_PX, SCREEN_H_PX), (200, 200, 200), -1)

        m5stacks[0].setRelativePosition(m5stacks[1].getPosition())
        m5stacks[1].setRelativePosition(m5stacks[0].getPosition())

        for m5 in m5stacks:
            if(m5.alive == False):
                m5.die()
                continue

            (x, y) = m5.getPosition()
            x = round(x, 2)
            y = round(y, 2)
            try:
                cv2.rectangle(preview, (int(x-10), int(y-10)), (int(x+10), int(y+10)), (50, 0, 200), -1)
            except:
                pass
            preview = cv2.putText(preview, "{}, {}".format(x, y), (10, (m5.number+1) * 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 0, 50))
            #cv2.rectangle(preview, (x-5, y-5), (x+5, y+5), (255, 0, 0))

            try:
                preprocess_test(np.array(m5.temp_img), np.array(m5.binarized_img))

                #resized = np.array(m5.temp_img)
                #resized = cv2.resize(np.array(m5.temp_img),None,fx=16, fy=16, interpolation = cv2.INTER_NEAREST)
                #resized_bin = cv2.resize(np.array(m5.binarized_img),None,fx=64, fy=64, interpolation = cv2.INTER_NEAREST)
                #cv2.imshow("test", np.array(m5.temp_img) # TEST
                #cv2.imshow("binarized", resized_bin) # TEST
            except Exception as e:
                #print(e)
                pass

        cv2.imshow("preview", preview)
        
        key = cv2.waitKey(1)
        if(key == ord('q')):
            break
        elif(key == ord('p')):
            cv2.imwrite("image_{}.png".format(time.localtime()), np.array(img))

    for m5 in m5stacks:
        m5.die()
    time.sleep(1)
    sys.exit()
