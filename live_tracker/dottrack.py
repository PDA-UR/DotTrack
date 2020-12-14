#!/usr/bin/env python3
# coding: utf-8

# # DotTrack
# 
# (C) 2018 - 2019 Dennis Schüsselbauer (original code)  
# (C) 2020 Raphael Wimmer (porting, cleanup)
# (C) 2020 Andreas Schmid (extending, cleanup)

import numpy as np
import time
import math
from generate_dbt import TorusGenerator
from collections import Counter
import cv2
from decode_dbt import decode_dbt_positions

imgsize = [36, 36]

DBT_DPI = 150 # number of printed De-Bruijn dots per inch of the paper

CAM_SIZE = (1.05, 1.05)  # eyebally the best result
DBT_W, DBT_H = 8192, 4096  # De Bruijn torus width & height (pixels).
WIN_W, WIN_H = 5, 5  # De Bruijn torus window width & height.
cam_size_inch = (CAM_SIZE[0] / 25.4, CAM_SIZE[1] / 25.4)
num_ppx = (DBT_DPI*cam_size_inch[0],
           DBT_DPI*cam_size_inch[1])
px_ppx_ratio = (imgsize[0]/num_ppx[0], imgsize[1]/num_ppx[1])

margin = (-27.5, -26)

top_shift = -1
left_shift = -1

pipeline = ["denoise_foil", "adaptive", "rescale"]

def extract_bitarray(img_array, pipeline_id):
    bit_array = np.zeros((int(num_ppx[1]), int(num_ppx[0])), dtype="uint8")

    # Grid based extraction
    # 0. Find grid anchor (for later)
    min_error = None
    offset_range_x = px_ppx_ratio[0]
    offset_range_y = px_ppx_ratio[1]
    # We don't have a perfect alignment of DBT pattern and image borders.
    # Brute-force find the offset that results in the "best" binarization, i.e. 
    # where DBT pixels are completely white or black. Minimize the variance in each cell.
    # shift between 0 and 5 pixels in X and Y -> 25 calculationsi

    step_x = offset_range_x / num_ppx[0]
    step_y = offset_range_y / num_ppx[1]

    border_width = 5 # likely way too much
    img_array_border = cv2.copyMakeBorder(img_array, border_width, border_width, border_width, border_width, cv2.BORDER_REPLICATE, None, None)

    angle = 0

    for a_x in np.arange(left_shift * step_x, offset_range_x, offset_range_x / num_ppx[0]):
        for a_y in np.arange(top_shift * step_y, offset_range_y, offset_range_y / num_ppx[1]):

            anchor = (a_x, a_y) # the camera coordinates where the DBT pattern starts
            array = np.zeros((math.ceil(num_ppx[1]), math.ceil(num_ppx[0])), dtype="uint8")
            error_count = 0

            # generate 25 image copies, each shifted by anchor, scale it to 6x6 px, 
            # count completely black/white pixels 
            crop = img_array_border[max(int(a_x), 0)+border_width:int((px_ppx_ratio[0] * 6 + a_x))+border_width, max(int(a_y), 0)+border_width:int((px_ppx_ratio[1] * 6 + a_y))+border_width]
            small = cv2.resize(crop, (6, 6), interpolation = cv2.INTER_LINEAR)
            num_white = np.sum(small == 255)
            num_black = np.sum(small == 0)
            error_count = 6 * 6 - (num_white + num_black)

            if min_error is None or min_error > error_count:
                min_error = error_count

                bit_array = small
                final_anchor = anchor
                final_angle = angle

    # binarize very light or dark pixels
    # threshold determined by trial and error
    adaptive_threshold = 80
    bit_array[bit_array > 255 - adaptive_threshold] = 255
    bit_array[bit_array < adaptive_threshold] = 0

    return bit_array, final_anchor, angle

def preprocess_image(img, pipeline_id):
    if "none" in pipeline_id:
        # No preprocessing wanted
        pass

    elif "denoise" in pipeline_id:
        ## sharpen
        sharpness = 1

        kernel = np.array([ [-sharpness,-sharpness,-sharpness],
                            [-sharpness,9*sharpness,-sharpness],
                            [-sharpness,-sharpness,-sharpness]])

        img = cv2.filter2D(img, -1, kernel)

        # denoise
        img = cv2.bilateralFilter(img,13,50,50)

        kernel = np.ones((3,3), np.uint8) 
        img = cv2.erode(img, kernel, iterations=1) 

        kernel = np.ones((5,5), np.uint8) 
        img = cv2.dilate(img, kernel, iterations=1) 

        # Todo: try fixed threshold
        img = cv2.adaptiveThreshold(np.array(img),255,cv2.ADAPTIVE_THRESH_MEAN_C,\
                    cv2.THRESH_BINARY,19,2)

    elif "denoise_foil" in pipeline_id:
        # this is all it needs in terms of preprocessing if the paper and print are nice
        # Todo: try fixed threshold
        img = cv2.adaptiveThreshold(np.array(img),255,cv2.ADAPTIVE_THRESH_MEAN_C,\
                    cv2.THRESH_BINARY,19,2)
    return img

# 4. Calculate actual positions on the page (in millimeters)
def calculate_real_positions(px_positions):
    # TODO: Use the center of the dbt window instead of the top left position.
    # TODO: Improve real position based on window anchor.
    # TODO: Check if real position is possible with help of pagesize and/or
    # cropped_area.
    # , win_w, win_h, win_anchor, cam_reso, cam_size, pagesize=None,
    # cropped_area=None):
    positions = []
    for px_pos in px_positions:
        x = ((px_pos[0] / DBT_DPI) * 25.4) + margin[0]
        y = ((px_pos[1] / DBT_DPI) * 25.4) + margin[1]
        positions.append((x, y))
    return positions

def calculate_confidence(dbt_positions):
    most_common = Counter(dbt_positions).most_common()

    position = most_common[0][0]
    if len(most_common) == 1: # one position
        confidence = 100
    elif len(most_common) == len(dbt_positions):
        confidence = 0
    else:
        confidence = int(100 * (1.0 - (most_common[-1][1] / most_common[0][1])/2)) # 2,2 → 0.5 / 2,1,1 → 0.75 / 3,1 → 0.85 
    return confidence, position

# other method to calculate confidence
# not used
def calculate_confidence_diagonals(dbt_positions):
    #print(dbt_positions)
    try:
        assert(len(dbt_positions) == 4) # only for 5x5 at the moment AS
    except AssertionError as e:
        print(len(dbt_positions))

    confidence = 0
    if(dbt_positions[0] == dbt_positions[2]):
        confidence += 30
    if(dbt_positions[1] == dbt_positions[3]):
        confidence += 30
    if(dbt_positions[0] == dbt_positions[1]):
        confidence += 9
    if(dbt_positions[0] == dbt_positions[3]):
        confidence += 9
    if(dbt_positions[1] == dbt_positions[2]):
        confidence += 9
    if(dbt_positions[2] == dbt_positions[3]):
        confidence += 9

    most_common = Counter(dbt_positions).most_common()

    if len(most_common) == 1: # one position
        confidence = 100
    elif len(most_common) == len(dbt_positions):
        confidence = 0

    position = most_common[0][0]
    return confidence, position

def get_coords(subframe, pipeline_id=pipeline): # Pillow Image with 36x36 px
    dbt_gen = TorusGenerator(DBT_W, DBT_H, WIN_W, WIN_H)
    dbt_log = dbt_gen.constr_log
    dbt_fname = dbt_log[-1].fname

    original = subframe

    # 2. Image Analysis (extract array out of picture):
    start_time = time.perf_counter()

    # stretch brightness over whole dynamic range
    # this avoids disturbances caused by varying exposure times of the sensor
    normalized = original.astype(np.float32)
    minimum = normalized.min()
    maximum = normalized.max()

    normalized -= minimum
    normalized /= maximum - minimum
    normalized *= 255
    normalized = original.astype(np.uint8)

    # preprocess the normalized image and binarize it
    subframe = preprocess_image(normalized, pipeline_id)

    # convert it down to a 6 by 6 pixel array
    bit_array, anchor, angle2 = extract_bitarray(subframe, pipeline_id)

    # there might be some grey pixels left
    # the value of those is determined by comparing their average value in the raw image
    # to their surrounding area ("smart threshold")
    unknown_pixels = bit_array.shape[0] * bit_array.shape[1] - (np.sum(bit_array == 255)+np.sum(bit_array == 0))

    # smart threshold
    bit_array_w = bit_array.shape[0]
    bit_array_h = bit_array.shape[1]
    step_x = px_ppx_ratio[0]
    step_y = px_ppx_ratio[1]

    area_size_x = step_x
    area_size_y = step_y

    for x in range(0, bit_array_w):
        for y in range(0, bit_array_h):
            if(bit_array[y, x] != 0 and bit_array[y, x] != 255):
                # area of the pixel in the raw image
                left = anchor[1] + (step_x * x)
                right = anchor[1] + (step_x * (x + 1))
                top = anchor[0] + (step_y * y)
                bottom = anchor[0] + (step_y * (y + 1))

                # surrounding area
                area_left   = int(max(left - area_size_x, 0))
                area_right  = int(min(right + area_size_x, imgsize[0]))
                area_top    = int(max(top - area_size_y, 0))
                area_bottom = int(min(bottom + area_size_y, imgsize[1]))

                center = normalized[int(top) : int(bottom), int(left) : int(right)]

                # get mean brightness of pixel
                brightness_center = np.mean(center)

                # ... and area
                area = normalized[area_top : area_bottom, area_left : area_right]

                brightness_area = np.mean(area)

                # TODO: introduce threshold
                # still unknown dots should be brute forced
                if(brightness_center > brightness_area):
                    bit_array[y, x] = 255
                else:
                    bit_array[y, x] = 0

    # as orientation has to be determined by trial and error,
    # we need four versions of the pixel array
    subarray = [None]*4
    dbt_positions = [None]*4
    confidence = [None]*4
    position = [None]*4

    # rotate each one so we have 0, 90. 180 and 270 degrees
    subarray[0] = bit_array
    subarray[1] = np.rot90(subarray[0], 3)
    subarray[2] = np.rot90(subarray[0], 2)
    subarray[3] = np.rot90(subarray[0], 1)

    best_confidence = 0
    best_confidence_i = 0
    # 3. Decoding algorithm according to Shiu
    for i in range(0, 4):
        dbt_positions[i] = decode_dbt_positions(subarray[i], dbt_log)
        #confidence[i], position[i] = calculate_confidence_diagonals(dbt_positions[i])
        confidence[i], position[i] = calculate_confidence(dbt_positions[i])
        if(confidence[i] > best_confidence):
            best_confidence = confidence[i]
            best_confidence_i = i

    # the one with the highest confidence is our result
    confidence = confidence[best_confidence_i]
    position = position[best_confidence_i]
    rotation = best_confidence_i * 90

    real_position = calculate_real_positions([position])[0]

    total_time = time.perf_counter() - start_time

    return(real_position, confidence, rotation, total_time, subarray[0])

def convert_coords(x, y):
    pixels_x = 140.0 / 150.0 * DBT_DPI
    pixels_y = 240.0 / 150.0 * DBT_DPI  #4096 / 150 * 25.4
    new_y = int((x / (pixels_x)) * 10000)
    new_x = 10000 - int((y / (pixels_y)) * 10000)
    return (new_x, new_y)

# Usage:
# img: np.array
# (x_dbt, y_dbt), confidence, angle, exec_time, bit_array = get_coords(img)
