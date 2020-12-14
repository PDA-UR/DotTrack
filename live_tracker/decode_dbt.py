#!/usr/bin/env python3
# coding: utf-8

# # DotTrack
# 
# (C) 2018 - 2019 Dennis Schüsselbauer (original code)  
# (C) 2020 Raphael Wimmer (porting, cleanup)
# (C) 2020 Andreas Schmid (cleanup)

from skimage import io
from torus import Torus
import numpy as np

# TODO: redundant with dottrack.py
WIN_W, WIN_H = 5, 5  # De Bruijn torus window width & height.

def decode_dbt_positions(wins_array, dbt_log):
    positions = []
    x_range = wins_array.shape[1] - WIN_W + 1
    y_range = wins_array.shape[0] - WIN_H + 1
    # Check if number of possible window positions is sound
    if x_range < 1 or y_range < 1:
        raise ValueError("Windows array too small for requested window.")

    for x in range(x_range):
        for y in range(y_range):
            win = wins_array[y:y+WIN_H, x:x+WIN_W]
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

def find_in_seq(win, sequence):
    pos = -1
    seq_range = len(sequence) - len(win) + 1
    for i in range(seq_range):
        if (win == sequence[i:i+len(win)]).all():
            pos = i
            break
    return pos

