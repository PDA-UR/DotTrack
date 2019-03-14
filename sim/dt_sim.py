# import os
import skimage
from skimage import io
from skimage.filters import threshold_sauvola
import numpy as np
import time
from torus import Torus
from PIL import Image, ImageFilter
from generate_dbt import TorusGenerator
# from extract_frame import extract_frame


# Cameras resolution in pixel.
CAM_RESO = (36, 36)
# Cameras capture area in millimeter.
# Calculated/Estimated as explained in
# https://github.com/PDA-UR/DotTrack/commit/fb9fb1e
CAM_SIZE = (1.135, 1.135)
# De Bruijn torus width & height.
DBT_W, DBT_H = 256, 256
# DBT_W, DBT_H = 8192, 4096
# De Bruijn torus window width & height.
WIN_W, WIN_H = 4, 4
# WIN_W, WIN_H = 5, 5
# Image dpi of the de Bruijn torus.
DPI = (150, 150)
# Black in greyscale.
BLACK = 0
# White in greyscale.
WHITE = 255


def main():
    # Testing:
    # generate multiple test images
    # run pipeline
    # compare to truth

    # Testing 2:
    # test with real images

    pipeline_id = "baseline"
    # pipeline_id = "direct_bit_extract"

    # 1. Image Generation:
    # dbt_w, dbt_h, win_w, win_h = 256, 256, 4, 4
    dbt_w, dbt_h, win_w, win_h = DBT_W, DBT_H, WIN_W, WIN_H
    dpi = DPI

    dbt_gen = TorusGenerator(dbt_w, dbt_h, win_w, win_h)
    dbt_log = dbt_gen.constr_log
    dbt_fname = dbt_log[-1].fname

    # 1.1. Test frame simulation:
    # TODO/FIXME/URGENT: (248, 248) does not work with decoding algo
    # [(249, 249), (249, 250), (249, 251), (250, 249), (250, 250), (250, 251),
    # (251, 249), (251, 250), (251, 251)]
    cam_anchor = (0, 0)
    # TODO/FIXME: (0, 248) returns bad values for the first row (fix image
    # analysis / bit extraction)
    # cam_anchor = (0, 248)
    rot = 0
    subframe = get_test_frame(dbt_fname,
                              dpi,
                              cam_anchor,
                              CAM_RESO,
                              CAM_SIZE,
                              rot=rot)
    # subframe.show()  # DEBUG OUTPUT

    # 2. Image Analysis (extract array out of picture):
    start_time = time.perf_counter()

    # subframe = unrotate_image(subframe)  # TODO
    subframe = preprocess_image(subframe, pipeline_id)
    # subframe.show()  # DEBUG OUTPUT
    subarray = extract_bitarray(subframe, CAM_SIZE, dpi, pipeline_id)
    # print(subarray)  # DEBUG OUTPUT

    # 3. Decode array (and get position):
    # Brute force
    # positions = find_sequences_in_dbt(subarray, dbt_fname, win_w, win_h)

    # Decoding alogrithm according to Shiu
    positions = decode_dbt_positions(subarray, win_w, win_h, dbt_log)

    print(positions)

    total_time = time.perf_counter() - start_time
    print(f"Frame analysing took {total_time:.3f}s")

    # Test to compare correctness of brute force vs. Shius decoding algorithm
    # positions_bf = []
    # positions_shiu = []
    # dbt_array = io.imread(dbt_log[-1].fname)
    # dbt_img = Image.fromarray(dbt_array)
    # # print(f"dbt_array.shape: {dbt_array.shape}")
    # x_range = dbt_array.shape[1] - win_w + 1
    # y_range = dbt_array.shape[0] - win_h + 1
    # for x in range(x_range):
    #     for y in range(y_range):
    #         subarray = dbt_array[y:y+win_h, x:x+win_w]
    #         # Brute force
    #         # positions_bf.extend(find_sequences_in_dbt(subarray,
    #         #                                           dbt_img,
    #         #                                           win_w,
    #         #                                           win_h))
    #         positions_bf.extend([(x, y)])
    #         # Decoding alogrithm according to Shiu
    #         positions_shiu.extend(decode_dbt_positions(subarray,
    #                                                    win_w,
    #                                                    win_h,
    #                                                    dbt_log))
    #         # print(positions_bf)
    #         # print(positions_shiu)
    # if len(positions_shiu) != len(positions_bf):
    #     raise ValueError(f"Different length of positions arrays. Should " +
    #                      f"not happen!")
    # for i in range(len(positions_shiu)):
    #     if positions_shiu[i] != positions_bf[i]:
    #         print(f"MISMATCH:\nBrute force: {positions_bf[i]}\n" +
    #               f"Shiu: {positions_shiu[i]}")


def get_dbt_log(dbt_w, dbt_h, win_w, win_h):
    # 1. DBT/Log Generation:
    dbt_gen = TorusGenerator(dbt_w, dbt_h, win_w, win_h)
    dbt_log = dbt_gen.constr_log
    return dbt_log


def analyse_frame(frame, cam_size, dbt_log, dbt_dpi, win_w, win_h,
                  pipeline_id):
    start_time = time.perf_counter()

    # frame.show()  # DEBUG OUTPUT
    # frame = set_frame_dpi(frame, cam_size)
    # 2. Image Analysis (extract array out of picture):
    # frame = unrotate_image(frame)  # TODO
    frame = preprocess_image(frame, pipeline_id)
    # frame.show()  # DEBUG OUTPUT
    subarray = extract_bitarray(frame, cam_size, dbt_dpi,
                                pipeline_id)
    # print(subarray)  # DEBUG OUTPUT
    # Image.fromarray(subarray).show()  # DEBUG OUTPUT

    # 3. Decode array (and get position):
    # Brute force
    # dbt_fname = dbt_log[-1].fname
    # positions = find_sequences_in_dbt(subarray, dbt_fname, win_w, win_h)

    # Decoding alogrithm according to Shiu
    positions = decode_dbt_positions(subarray, win_w, win_h, dbt_log)

    print(positions)

    total_time = time.perf_counter() - start_time
    print(f"Frame analysing took {total_time:.3f}s")


# def set_frame_dpi(frame, cam_size):
#     # Convert size from millimeters to inch
#     cam_size_inch = (cam_size[0]*0.039370079, cam_size[1]*0.039370079)
#     cam_dpi = (int(frame.size[0]//cam_size_inch[0]),
#                int(frame.size[1]//cam_size_inch[1]))
#     frame.info["dpi"] = cam_dpi
#     return frame


# 1.1. Test frame simulation:
# get_test_frame.py
# from PIL import Image


# for testing the recognition pipeline
def get_test_frame(fname, dpi, cam_anchor, cam_reso, cam_size=(1, 1), rot=0):
    # TODO Make cam_anchor an absolut position in mm or inch. Or allow an
    # offset to test patterns being cut off

    # Convert size from millimeters to inch
    cam_size_inch = (cam_size[0]*0.039370079, cam_size[1]*0.039370079)
    cam_dpi = (int(cam_reso[0]//cam_size_inch[0]),
               int(cam_reso[1]//cam_size_inch[1]))

    # Set up DPI value
    # dpi = None
    # cam_dpi = (int(cam_reso[0]//cam_size_inch[0]),
    #            int(cam_reso[1]//cam_size_inch[1]))
    # # Read out DPI value from PNG metadata.
    # for key in img.info:
    #     if(key == "dpi"):
    #         dpi = img.info[key]
    # if dbt_dpi_overwrite is not None:
    #     # Set DPI to overwrite value
    #     dpi = dbt_dpi_overwrite
    # if dpi is None:
    #     # Set DPI to default value (dpi of camera/sensor).
    #     # TODO: Nyquist as default?? 36 --> (36/2)-1 = 17 --> 17//size
    #     dpi = cam_dpi

    # Calculate scaling factors & scale accordingly.
    # The ratio_scale variable is required to scale the DBT image to the wanted
    # size and in correct relation to the camera size.
    ratio_scale = (cam_dpi[0]/dpi[0], cam_dpi[1]/dpi[1])
    # To prevent not intended anti aliasing (3 because of Nyquist).
    safety_scale = (3, 3)
    # Complete scale.
    scale = (ratio_scale[0]*safety_scale[0], ratio_scale[1]*safety_scale[0])
    # Resize to set the image size in relation to the camera size and also
    # scale up to retain quality.
    img = Image.open(fname)
    # TODO/FIXME: Resize takes too much memory (OOM killer bad).
    # At 150dpi it would resize 5x5 DBT to 131955*66009 => ~8.7 GB
    # Solution: Maybe directly crop to relevant area and scale that area.
    img = img.resize((int(img.size[0]*scale[0]),
                      int(img.size[1]*scale[0])))

    # TODO Value-/Boundschecks?
    if rot != 0:
        img = img.rotate(-rot,
                         expand=False,
                         # center=(cam_anchor[0],
                         #         cam_anchor[1]),
                         center=(cam_anchor[0]*scale[0],
                                 cam_anchor[1]*scale[1]),
                         translate=(0, 0))
    left = int(cam_anchor[0]*scale[0])
    top = int(cam_anchor[1]*scale[1])
    right = int(cam_anchor[0]*scale[0]+cam_reso[0]*safety_scale[0])
    bottom = int(cam_anchor[1]*scale[1]+cam_reso[1]*safety_scale[1])
    # left = int(cam_anchor[0]/scale[0])
    # top = int(cam_anchor[1]/scale[1])
    # right = int(cam_anchor[0]/scale[0]+cam_reso[0]/safety_scale[0])
    # bottom = int(cam_anchor[1]/scale[1]+cam_reso[1]/safety_scale[1])
    img = img.crop(box=(int(left),
                        int(top),
                        int(right),
                        int(bottom)))
    # img.show()
    # img = img.resize((int(img.size[0]*scale[0]),
    #                   int(img.size[1]*scale[0])))
    # img.show()
    # "L": 8-bit greyscale. 0 means black, 255 means white.
    # "1": 1-bit bilevel, stored with the leftmost pixel in the most
    # significant bit. 0 means black, 1 means white.
    mode = "L"
    # Convert to greyscale (which is needed for the blur filter)
    img = img.convert(mode)
    # The blur is supposed to emulate greyscale noise.
    img = img.filter(ImageFilter.GaussianBlur(radius=min(safety_scale)+1))
    img = img.resize(cam_reso)  # , resample=Image.NEAREST) TODO:filter needed?
    # Since img is now the camera frame it should set the dpi value to the
    # cameras dpi value (cam_dpi).
    # img.info["dpi"] = cam_dpi
    return img


# 2. Image Analysis (extract array out of picture):
def preprocess_image(img, pipeline_id="baseline"):
    if pipeline_id == "direct_bit_extract":
        # No preprocessing wanted
        return img

    # dpi = img.info["dpi"]
    # Edge enhance
    img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)

    # Thresholding
    img = skimage.img_as_ubyte(img)

    # Tests
    # from skimage.filters import (try_all_threshold, threshold_sauvola,
    #                              threshold_local, threshold_niblack)
    # import matplotlib.pyplot as plt

    # tmp = skimage.img_as_ubyte(img > threshold_local(img, 15))
    # Image.fromarray(tmp).show()

    # tmp = skimage.img_as_ubyte(img > threshold_niblack(img))
    # Image.fromarray(tmp).show()

    # tmp = skimage.img_as_ubyte(img > threshold_sauvola(img))
    # Image.fromarray(tmp).show()

    # fig, ax = try_all_threshold(img, verbose=False)
    # plt.show()

    img = skimage.img_as_ubyte(img > threshold_sauvola(img))
    img = Image.fromarray(img)
    # img.info["dpi"] = dpi
    return img


def unrotate_image(img):
    # preprocess image for easier stabilization
    # img = img.filter(ImageFilter.CONTOUR)
    # img = img.filter(ImageFilter.EMBOSS)
    img = img.filter(ImageFilter.FIND_EDGES)
    # TODO: do stuff to get assumed rotation
    # APPROACH 1: rotate with 15° increments
    rot = 0
    img = img.rotate(rot,
                     expand=False,
                     center=(img.size[0]//2, img.size[1]//2),
                     translate=(0, 0))
    return img


def remove_helper_lines(img):
    pass


def extract_bitarray(img, cam_size, dbt_img_dpi, pipeline_id="baseline"):
    # Convert size from millimeters to inch
    cam_size_inch = (cam_size[0]*0.039370079, cam_size[1]*0.039370079)
    # Number of pattern pixel the sensor should be able to see
    num_ppx = (int(dbt_img_dpi[0]*cam_size_inch[0]),
               int(dbt_img_dpi[1]*cam_size_inch[1]))
    # Ratio of camera/image pixel per pattern pixel
    px_ppx_ratio = (int(img.size[0]/num_ppx[0]), int(img.size[1]/num_ppx[1]))
    # print(dbt_img_dpi[0]*cam_size_inch[0],
    #       img.size[0]/(dbt_img_dpi[0]*cam_size_inch[0]))
    # print(dbt_img_dpi, num_ppx, px_ppx_ratio)

    bit_array = np.zeros((num_ppx[1], num_ppx[0]), dtype="uint8")
    img_array = skimage.img_as_ubyte(img)

    # Calculate threshold value (with Otsus method)
    if pipeline_id == "direct_bit_extract":
        # threshold = skimage.filters.threshold_isodata(img_array)
        # print("isodata:{}".format(threshold))
        # threshold = skimage.filters.threshold_li(img_array)
        # print("li:{}".format(threshold))
        # threshold = skimage.filters.threshold_mean(img_array)
        # print("mean:{}".format(threshold))
        # threshold = skimage.filters.threshold_minimum(img_array)
        # print("minimum:{}".format(threshold))
        # threshold = skimage.filters.threshold_otsu(img_array)
        # print("otsu:{}".format(threshold))
        # threshold = skimage.filters.threshold_triangle(img_array)
        # print("triangle:{}".format(threshold))
        # threshold = skimage.filters.threshold_yen(img_array)
        # print("yen:{}".format(threshold))
        # print("255 // 2 = 127")
        threshold = 127
    else:
        # default value (255 // 2)
        threshold = 127

    # Grid based extraction
    # 0. Find grid anchor (for later)
    min_error = None
    # offset_range_x = img.size[0] - num_ppx[0] * px_ppx_ratio[0]
    # offset_range_y = img.size[1] - num_ppx[1] * px_ppx_ratio[1]
    offset_range_x = px_ppx_ratio[0]
    offset_range_y = px_ppx_ratio[1]
    for a_x in range(offset_range_x):
        for a_y in range(offset_range_y):
            anchor = (a_x, a_y)
            # print(anchor)
            array = np.zeros((num_ppx[1], num_ppx[0]), dtype="uint8")
            error_count = 0
            # 1. Implement grid as for-loop that walks every cell
            stop = (anchor[0]+px_ppx_ratio[0]*num_ppx[0],
                    anchor[1]+px_ppx_ratio[1]*num_ppx[1])
            x_range = list(range(anchor[0], stop[0], px_ppx_ratio[0]))
            y_range = list(range(anchor[1], stop[1], px_ppx_ratio[1]))
            for i, x in enumerate(x_range):
                for j, y in enumerate(y_range):
                    cell = img_array[y:y+px_ppx_ratio[1], x:x+px_ppx_ratio[0]]
                    # print(x, y)
                    # print(cell)
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
                bit_array = array
                # print(f"New min error ({min_error}) at {anchor} anchor.")
                # print(bit_array)
    return bit_array


# return: 0/black or 255/white and win_lose_delta (for error variable)
def calc_cell_bit(cell_array, ret_err_count=False, margin=(0, 0),
                  x_shaped_crop=False, threshold=127, pipeline_id="baseline"):
    # TODO: Crop to margin
    # TODO: Maybe count in a cross shape when there are very few pixels (3x3)

    if pipeline_id == "baseline":
        col_counts = {}
        # https://stackoverflow.com/a/35549699
        col_counts[WHITE] = np.count_nonzero(cell_array == WHITE)
        col_counts[BLACK] = np.count_nonzero(cell_array == BLACK)
        # colors, counts = np.lib.arraysetops.unique(cell_array,
        #                                            return_counts=True)
        # col_counts = dict(zip(colors, counts))

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


# 3. Decode array (and get position):
def find_sequences_in_dbt(frame_array, dbt_fname, win_w, win_h):
    start_time = time.perf_counter()

    positions = []

    dbt_array = io.imread(dbt_fname)

    # List comprehension for x, y and dbt_x, dbt_y produces more loops
    # Less looping ==> bit faster
    # Caching the range variables is also a tiny bit faster
    frame_x_range = frame_array.shape[1]-win_w+1
    frame_y_range = frame_array.shape[0]-win_h+1
    dbt_x_range = dbt_array.shape[1]-win_w+1
    dbt_y_range = dbt_array.shape[0]-win_h+1
    for x in range(frame_x_range):
        for y in range(frame_y_range):
            win = frame_array[y:y+win_h, x:x+win_w]
            for dbt_x in range(dbt_x_range):
                for dbt_y in range(dbt_y_range):
                    # np.array_equal() is slower (rather big difference)
                    if (win == dbt_array[dbt_y:dbt_y+win_h,
                                         dbt_x:dbt_x+win_w]).all():
                        positions.append((dbt_x, dbt_y))

    # positions = find_windowsarray_in_array(frame_array,
    #                                        win_w,
    #                                        win_h,
    #                                        dbt_array)
    # print(positions)

    total_time = time.perf_counter() - start_time
    print(f"Brute force lookup of "
          f"{frame_array.shape[1]}x{frame_array.shape[0]} subarray in "
          f"{dbt_array.shape[1]}x{dbt_array.shape[0]} DBT with {win_w}x{win_h}"
          f" window size took {total_time:.3f}s")

    return positions


def find_windowsarray_in_array(wins_array, win_w, win_h, array):
    positions = []
    x_range = wins_array.shape[1] - win_w + 1
    y_range = wins_array.shape[0] - win_h + 1
    for x in range(x_range):
        for y in range(y_range):
            win = wins_array[y:y+win_h, x:x+win_w]
            x_pos, y_pos = find_in_array(win, array)
            if x_pos != -1:
                positions.append((x_pos, y_pos))
    return positions


def find_in_array(win, array):
    # print(f"find_in_array:\nwin:\n{win},\narray.shape(extended): " +
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
    # print(new_array)
    # print(f"find_in_array:\nwin: {win},\narray.shape: {array.shape}")

    for x in range(x_range):
        for y in range(y_range):
            # np.array_equal() is slower (rather big difference)
            subarray = array[y:y+win.shape[0], x:x+win.shape[1]]
            if (win == subarray).all():
                return x, y
    return -1, -1


def find_in_seq(win, sequence):
    pos = -1
    seq_range = len(sequence) - len(win) + 1
    for i in range(seq_range):
        if (win == sequence[i:i+len(win)]).all():
            pos = i
            break
    return pos


def decode_dbt_positions(wins_array, win_w, win_h, dbt_log):
    start_time = time.perf_counter()

    # TODO: Should I match every possible window? Or just one after the first
    # to check the position?

    positions = []

    x_range = wins_array.shape[1] - win_w + 1
    y_range = wins_array.shape[0] - win_h + 1
    # Check if number of possible window positions is sound
    if x_range < 1 or y_range < 1:
        raise ValueError("Windows array too small for requested window.")
    # elif x_range == 1 and y_range == 1:
    #     print("The windows array in its whole is the (single) window.")
    # else:
    #     print(f"There are {x_range*y_range} possible windows.")

    # TODO/FIXME: Make it work for (256, 256, 4, 4) array first:
    # A = (256, 256, 4, 4)
    # A1 = (256, 16, 3, 4)
    # src_dbt = io.imread("output-4x3_transposed.png")
    for x in range(x_range):
        for y in range(y_range):
            win = wins_array[y:y+win_h, x:x+win_w]
            # TODO: How to save/communicate generation data/protocol.
            # x_pos, y_pos = decode_dbt_pos(win)

            # TODO/FIXME: Make it work for (256, 256, 4, 4) array first:
            # A = (256, 256, 4, 4)
            # A1 = (256, 16, 3, 4)
            # x_pos, y_pos = decode_dbt_pos(win, src_dbt)
            x_pos, y_pos = decode_dbt_pos(win, dbt_log)
            # print((x_pos, y_pos))
            # print("="*80)

            if x_pos != -1:
                positions.append((x_pos, y_pos))

    # dbt_array = io.imread("output-256x256-4x4.png")
    total_time = time.perf_counter() - start_time
    print(f"Decoding de Bruijn torus positions according to Shiu "
          f"{wins_array.shape[1]}x{wins_array.shape[0]} subarray in "
          f"{dbt_log[-1].s}x{dbt_log[-1].r} DBT with {win_w}x{win_h}"
          f" window size took {total_time:.3f}s")

    # returns dbt position(s) (not physical position)
    return positions


# TODO/FIXME:
# * Generalize data acquisition (src_dbt, transposed, r, s, m, n, seed). -->
# Needs data recording on generation.
# * Enable recursion.
# * Make it work with type 2 arrays. Low priority because the generation ONLY
# uses type 1 arrays.

# Decoding algorithm according to Shiu ("Decoding de Bruijn arrays as
# constructed by Fan et al.")
def decode_dbt_pos(win, log):  # , src_dbt=None):
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

    # Decoding algorithm seems to be rekursive (find in step 2) and needs the
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
    # print(win)
    # print(log_entry)
    src_dbt = None
    r, s, m, n = log_entry.dimensions
    # if log[-1].transposed:
    #     r, s = s, r
    #     m, n = n, m
    dbs_seed = Torus.debruijn(n)
    dbs_seed = dbs_seed[1:]
    dbs_seed = dbs_seed + dbs_seed[:n-1]
    dbs_seed = np.array(dbs_seed) * WHITE

    # Step 1: Compute D(M)
    dm = compute_dm(win)
    # print(f"dm:\n{dm}")

    # Step 2: Find the location of D(M) in A. Get i, j.
    # if src_dbt is not None:
    if len(log) == 2:
        # print("BRUTE FORCE LOOKUP:")
        # Brute force lookup if it is the last two log entry.
        src_dbt = io.imread(log_entry.fname)
        j, i = find_in_array(dm, src_dbt)
        # print(f"BRUTE FORCE LOOKUP ENDED: {j}, {i}")
    else:
        # TODO: do recursion
        # print(f"RECURSION {len(log)}:")
        if log_entry.transposed:
            # print("Transposed!")
            i, j = decode_dbt_pos(dm.transpose(), log[:-1])
        else:
            # print("NOT transposed!")
            j, i = decode_dbt_pos(dm, log[:-1])
        # print(f"RECURSION {len(log)} ENDED:")
    # print(f"win:\n{win}")
    # print(f"r: {r}, s: {s}, m: {m}, n: {n}")
    # print(f"i: {i}, j: {j}")

    # Step 3: Calculate -a>.
    if src_dbt is None:
        src_dbt = io.imread(log_entry.fname)
    a_vec = np.zeros(win[0, ].shape, dtype=np.uint8)
    a_vec |= win[0, ]
    for i_tmp in range(i):
        a_vec ^= src_dbt[i_tmp, j:j+n]
    zero_vec = np.zeros(a_vec.shape, dtype=np.uint8)
    # print(f"a_vec:\n{a_vec}")
    # print(f"dbs_seed:\n{dbs_seed}")

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
        # print(f"g: {g}")

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
        # print(f"x_tmp: {x_tmp}")

        # Step 6: Calculate k: k = s + g + (2**n - 1) * x
        k = (s + g + (2**n - 1) * x_tmp) - 1
    # print(f"k: {k}")

    # Step 7: The top left hand corner of M is the (i,k)-th entry of A1.
    x, y = k, i
    # print(f"x: {x}, y: {y}")

    # if log[-1].transposed:
    #     x, y = y, x

    return x, y


def compute_dm(array):
    dm = []
    for y in range(array.shape[0] - 1):
        dm.append(array[y, ] ^ array[y+1, ])
    return np.vstack(dm)


if __name__ == "__main__":
    main()
