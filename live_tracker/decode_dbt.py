#!/usr/bin/env python3
# coding: utf-8

# # DotTrack
# 
# (C) 2018 - 2019 Dennis Schüsselbauer (original code)  
# (C) 2020 Raphael Wimmer (porting, cleanup)
# (C) 2020 - 2022 Andreas Schmid (cleanup, optimization)

from skimage import io
from torus import Torus
import numpy as np
import time

# pre-load images of the DBT to save time during runtime
dbt_cache = dict()
dbt_cache['4x3'] = io.imread('output-16x256_4x3.png')
dbt_cache['4x4'] = io.imread('output-256x256_4x4.png')
dbt_cache['5x4'] = io.imread('output-256x4096_5x4.png')
dbt_cache['3x3'] = io.imread('output-32x16_3x3.png')
dbt_cache['3x2'] = io.imread('output-4x16_3x2.png')
dbt_cache['5x5'] = io.imread('output-8192x4096_5x5.png')

# TODO: redundant with dottrack.py
WIN_W, WIN_H = 5, 5  # De Bruijn torus window width & height.

def decode_dbt_positions(wins_array, dbt_log):
    positions = []
    x_range = wins_array.shape[1] - WIN_W + 1
    y_range = wins_array.shape[0] - WIN_H + 1
    # Check if number of possible window positions is sound
    if x_range < 1 or y_range < 1:
        raise ValueError("Windows array too small for requested window.")

    # iterate over all windows in the image and decode their positions
    for x in range(x_range):
        for y in range(y_range):
            win = wins_array[y:y+WIN_H, x:x+WIN_W]
            x_pos, y_pos = decode_dbt_pos(win, dbt_log)
            if x_pos != -1: 
                # offset found position by window offset, so we get the true anchor
                x_pos -= x
                y_pos -= y
                positions.append((x_pos, y_pos))
    return positions

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
    src_dbt = None
    r, s, m, n = log_entry.dimensions
    # if log[-1].transposed:
    #     r, s = s, r
    #     m, n = n, m
    dbs_seed = Torus.debruijn(n)
    dbs_seed = dbs_seed[1:]
    dbs_seed = dbs_seed + dbs_seed[:n-1]
    dbs_seed = np.array(dbs_seed) * WHITE

    # Step 1: Compute: {dm}")
    dm = compute_dm(win)

    # Step 2: Find the location of D(M) in A. Get i, j.
    if len(log) == 2:
        # Brute force lookup if it is the last two log entry.
        src_dbt = dbt_cache['3x2']
        j, i = find_in_array(dm, src_dbt)
    else:
        # TODO: do recursion
        if log_entry.transposed:
            i, j = decode_dbt_pos(dm.transpose(), log[:-1])
        else:
            j, i = decode_dbt_pos(dm, log[:-1])

    # Step 3: Calculate -a>.
    if src_dbt is None:
        idx = log_entry.fname.split('.')[0].split('_')[1]
        src_dbt = dbt_cache[idx]

    a_vec = np.zeros(win[0, ].shape, dtype=np.uint8)
    a_vec |= win[0, ]

    dbt_slice = src_dbt[:i, j:j+n]

    b = np.bitwise_xor.reduce(dbt_slice)
    a_vec ^= b

    zero_vec = np.zeros(a_vec.shape, dtype=np.uint8)

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

        # Step 5: Solve congruence equation: g+(2**n-1)*x === j (mod s),
        # 0<=x<=s–1.

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

        # Step 6: Calculate k: k = s + g + (2**n - 1) * x
        k = (s + g + (2**n - 1) * x_tmp) - 1

    # Step 7: The top left hand corner of M is the (i,k)-th entry of A1.
    x, y = k, i

    # if log[-1].transposed:
    #     x, y = y, x

    return x, y

def compute_dm(array):
    dm = [array[y, ] ^ array[y+1, ] for y in range(array.shape[0] - 1)]
    return np.vstack(dm)

def find_in_array(win, array):
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

def find_in_seq(win, sequence):
    pos = -1
    seq_range = len(sequence) - len(win) + 1
    for i in range(seq_range):
        if (win == sequence[i:i+len(win)]).all():
            pos = i
            break
    return pos
