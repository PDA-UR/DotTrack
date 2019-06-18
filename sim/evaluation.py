from PIL import Image
import glob
import re
import time
import math
import dt_sim as sim
import pandas as pd
import numpy as np
from pathlib import Path
# Evaluate python data types: https://stackoverflow.com/a/33283145
from ast import literal_eval
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# Page size / page format
PAGE_SIZE = (A4[0] / mm, A4[1] / mm)
# Page margin
PAGE_MARGIN = (5, 5)
# Size of M5Stack
M5_SIZE = (54, 54)
# Error margin in millimeters
ERROR_MARGIN = 5
# Error radius in millimeters
ERROR_RADIUS = 5


def main():
    # Create raw.csv
    fname = "raw.csv"
    csv = Path(fname)
    if not csv.exists():
        create_csv(fname)

    # Create submatrix.csv (carefull should take up ~500MB)
    # submatrix_fname = "submatrix.csv"
    # submatrix_csv = Path(submatrix_fname)
    # if not submatrix_csv.exists():
    #     create_submatrix_csv(submatrix_fname)

    # TODO: Create plots and calc output
    # create_plots(fname, submatrix_fname)

    # Prints important data
    filter_data()


# Creates raw data csv file
def create_csv(fname="raw.csv"):
    # Error margin in millimeters
    # error_margin = 5  # Seems to NOT work anymore at 175, 150 and 125 dpi
    # error_margin = 6  # Seems to NOT work anymore at 175, 150 and 125 dpi
    # error_margin = 7  # Seems to work at 175, 150 and 125 dpi
    # error_margin = 8  # Seems to work at 200 dpi
    # error_margin = 9  # Seems to work at 200 dpi
    # error_margin = 10  # 7 and even more buffer
    # error_margin = 20  # get max

    # Margin of the movement area (start position of image capture)
    move_margin = (M5_SIZE[0] / 2 + PAGE_MARGIN[0],
                   M5_SIZE[1] / 2 + PAGE_MARGIN[1])

    # dt_sim.py values
    dbt_w, dbt_h, win_w, win_h = sim.DBT_W, sim.DBT_H, sim.WIN_W, sim.WIN_H
    dbt_log = sim.get_dbt_log(dbt_w, dbt_h, win_w, win_h)
    cam_size = sim.CAM_SIZE
    pipeline_id = "baseline"

    # RegEx patterns
    # Pattern to find printer name in file name.
    printer_pattern = r"pos_(.*?)_"
    # Pattern to find DBT dimensions in file name.
    dbt_dims_pattern = r"_(\d+)x(\d+)_(\d+)x(\d+)_"
    # Pattern to find dpi value in file name.
    dpi_pattern = r"(\d+)x(\d+)dpi"
    # Pattern to find pos value in file name.
    pos_pattern = r"(\d+\.\d+)x(\d+\.\d+)pos"

    glob_pattern = "*/**/*.png"
    # glob_pattern = "BrotherHLL8360CDW/8192x4096_5x5_400x400dpi/*"
    # glob_pattern = "LexmarkMS510dn/8192x4096_5x5_400x400dpi/*"
    # glob_pattern = "BrotherHLL8360CDW/8192x4096_5x5_200x200dpi/*"
    # glob_pattern = "LexmarkMS510dn/8192x4096_5x5_200x200dpi/*"
    # glob_pattern = "BrotherHLL8360CDW/8192x4096_5x5_175x175dpi/*"
    # glob_pattern = "LexmarkMS510dn/8192x4096_5x5_175x175dpi/*"
    # glob_pattern = "BrotherHLL8360CDW/8192x4096_5x5_150x150dpi/*"
    # glob_pattern = "LexmarkMS510dn/8192x4096_5x5_150x150dpi/*"
    # glob_pattern = "BrotherHLL8360CDW/8192x4096_5x5_125x125dpi/*"
    # glob_pattern = "LexmarkMS510dn/8192x4096_5x5_125x125dpi/*"
    # glob_pattern = "*/8192x4096_5x5_100x100dpi/*"
    files = glob.glob(glob_pattern, recursive=True)

    # dictionary for raw data
    data = {"r": [],
            "s": [],
            "m": [],
            "n": [],
            "page_size": [],
            "page_margin": [],
            "cam_reso": [],
            "cap_area": [],
            "m5_size": [],
            "printer": [],
            "dpi": [],
            "num_win": [],
            "true_pos": [],
            "dbt_positions": [],
            "real_positions": [],
            "matching_indices": [],
            "runtime": []}

    # column names to correct header order
    columns = ["r",
               "s",
               "m",
               "n",
               "page_size",
               "page_margin",
               "cam_reso",
               "cap_area",
               "m5_size",
               "printer",
               "dpi",
               "num_win",
               "true_pos",
               "dbt_positions",
               "real_positions",
               "matching_indices",
               "runtime"]

    # columns = ["cam_reso", "cap_area",
    #            "printer maker", "printer model", "r (dbt_h)", "s (dbt_w)",
    #            "m (win_h)", "n (win_w)", "dpi", "true_pos",
    #            "num_win", "decoded DBT positions",
    #            "matching indices"]
    # add_col = ["error margin", "page margin", "M5Stack size", "move margin",
    #            "decoded real positions", "matching positions"]
    # df = pd.DataFrame()

    file_counter = 0
    for file in sorted(files):
        file_counter += 1
        print("=" * 80)
        print(f"File {file_counter} of {len(files)}")

        printer = re.findall(printer_pattern, file)[0]
        if len(printer) == 0:
            raise Exception("No printer name found in filename.")
        data["printer"].append(printer)
        print(printer)

        dbt_dims = re.findall(dbt_dims_pattern, file)
        if len(dbt_dims) == 0:
            raise Exception("No DBT dimensions found in filename.")
        dbt_w, dbt_h, win_w, win_h = tuple([int(dim) for dim in dbt_dims[-1]])
        r, s, m, n = dbt_h, dbt_w, win_h, win_w
        data["r"].append(r)
        data["s"].append(s)
        data["m"].append(m)
        data["n"].append(n)
        print(r, s, m, n)

        dpi = re.findall(dpi_pattern, file)
        if len(dpi) == 0:
            raise Exception("No dpi value found in filename.")
        dpi = tuple([int(xy) for xy in dpi[-1]])
        data["dpi"].append(dpi)
        print(dpi)

        pos = re.findall(pos_pattern, file)
        if len(pos) == 0:
            raise Exception("No position value found in filename.")
        pos = tuple([float(xy) for xy in pos[-1]])
        # Calculate estimated absolute position
        pos = pos[0] + move_margin[0], pos[1] + move_margin[1]
        data["true_pos"].append(pos)
        print(pos)

        frame = Image.open(file)
        # Skip 100x100dpi images because they can't be analysed with our
        # current implementation of the bit extraction.
        if dpi == (100, 100):
            # Fill empty values
            dbt_positions = np.nan
            positions = np.nan
            matching_indices = np.nan
            data["runtime"].append(np.nan)
            data["num_win"].append(np.nan)
        else:
            # Performance timer
            start_time = time.perf_counter()
            # Image analysis
            dbt_positions, positions, matching_indices = sim.analyse_frame(
                frame,
                cam_size,
                dbt_log,
                dpi,
                win_w,
                win_h,
                pipeline_id)
            total_time = time.perf_counter() - start_time
            # Append results
            data["runtime"].append(total_time)
            print(f"Image analysis took {total_time:.3f}s")
            data["num_win"].append(len(positions))
        data["dbt_positions"].append(dbt_positions)
        data["real_positions"].append(positions)
        data["matching_indices"].append(matching_indices)
        # Fill static content
        data["page_size"].append(PAGE_SIZE)
        data["page_margin"].append(PAGE_MARGIN)
        data["cam_reso"].append(frame.size)
        data["cap_area"].append(sim.CAM_SIZE)
        data["m5_size"].append(M5_SIZE)

    #     for p in positions:
    #         num_p += 1
    #         min_x, min_y = pos[0] - error_margin, pos[1] - error_margin
    #         max_x, max_y = pos[0] + error_margin, pos[1] + error_margin
    #         if min_x <= p[0] <= max_x and min_y <= p[1] <= max_y:
    #             print(f"{pos} & {p} was matched correctly with an error " +
    #                   f"margin of {error_margin} mm.")
    #             num_match += 1
    #             error_margins.append((pos[0] - p[0], pos[1] - p[1]))

    # print(num_p, num_match, num_match / num_p)
    # print(f"Total number of positions: {num_p}")
    # print(f"Total number of matching positions: {num_match}")
    # print(f"Accuracy percentage (num_match / num_p): {num_match / num_p:%}")
    # print(f"Error margins:\n{error_margins}")

    # for v, k in enumerate(data):
    #     print(v)
    #     print(len(v))
    df = pd.DataFrame(data)[columns]
    df.to_csv(fname, index=False)
    # TODO: Make it create (if not present) or read (if present) and return df
    # return df


# TODO: creating it dynamically from raw seems to be better??? -> Do that
def create_submatrix_csv(submatrix_fname=None):
    # Create raw.csv if neccessary
    fname = "raw.csv"
    csv = Path(fname)
    if not csv.exists():
        create_csv(fname)

    # Handle index column: https://stackoverflow.com/a/36519122
    # Column order:
    # https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.read_csv.html
    # """
    # To instantiate a DataFrame from data with element order preserved use
    # pd.read_csv(data, usecols=['foo', 'bar'])[['foo', 'bar']] for columns in
    # ['foo', 'bar'] order or pd.read_csv(data, usecols=['foo', 'bar'])[['bar',
    # 'foo']] for ['bar', 'foo'] order.
    # """
    raw = pd.read_csv(fname)  # , index_col=0)[columns]

    # Transform (string) values
    transform_funcs = {"r": int,
                       "s": int,
                       "m": int,
                       "n": int,
                       "page_size": literal_eval,
                       "page_margin": literal_eval,
                       "cam_reso": literal_eval,
                       "cap_area": literal_eval,
                       "m5_size": literal_eval,
                       "printer": str,
                       "dpi": literal_eval,
                       "num_win": int,
                       "true_pos": literal_eval,
                       "dbt_positions": literal_eval,
                       "real_positions": literal_eval,
                       "matching_indices": literal_eval,
                       "runtime": float}
    raw = raw.dropna().transform(transform_funcs)
    sm = raw.copy()

    # Create merge additions
    # Create dictionary for additions
    merge_add = {"ia_id": [],
                 "true_x": [],
                 "true_y": [],
                 "true_pos_dist": [],
                 "index": [],
                 "dbt_pos": [],
                 "dbt_x": [],
                 "dbt_y": [],
                 "real_pos": [],
                 "real_x": [],
                 "real_y": [],
                 "matches": [],
                 "matches_len": [],
                 "error_margin": [],
                 "err_margin_match": [],
                 "error_radius": [],
                 "err_radius_match": [],
                 "runtime_mean": []}

    # Iterate over all image analysis ids (1600; 200 dropped)
    for ia_id in sm["real_positions"].keys():
        # Setup for submatrix loop

        # Extract true_x and true_y
        true_x, true_y = sm["true_pos"][ia_id]

        # Extract matching_indices
        matching_indices = sm["matching_indices"][ia_id]
        # Extract indices that match
        indices = [ind for ind in matching_indices if len(ind) > 1]

        # Extract runtime_mean
        runtime = sm["runtime"][ia_id]
        num_win = sm["num_win"][ia_id]
        runtime_mean = runtime / num_win

        # Iterate over available submatrizes (adds up to 90000)
        for index, pos in enumerate(sm["real_positions"][ia_id]):
            # Add values to addition dictionary
            # Add image analysis id
            merge_add["ia_id"].append(ia_id)

            # Add true_x, true_y
            merge_add["true_x"].append(true_x)
            merge_add["true_y"].append(true_y)

            # Calculate and add true_pos_dist
            # TODO: dist_x, dist_y of any use?
            dist_x = true_x - pos[0]
            dist_y = true_y - pos[1]
            true_pos_dist = math.sqrt(dist_x**2 + dist_y**2)
            merge_add["true_pos_dist"].append(true_pos_dist)

            # Add submatrix index
            merge_add["index"].append(index)
            # Add position values
            dbt_pos = sm["dbt_positions"][ia_id][index]
            merge_add["dbt_pos"].append(dbt_pos)
            merge_add["dbt_x"].append(dbt_pos[0])
            merge_add["dbt_y"].append(dbt_pos[1])
            merge_add["real_pos"].append(pos)
            merge_add["real_x"].append(pos[0])
            merge_add["real_y"].append(pos[1])

            # Add matches list
            if len(matching_indices) == 0:
                # Handle 125 dpi
                merge_add["matches"].append(np.nan)
                merge_add["matches_len"].append(np.nan)
            else:
                # Extract matches
                m = []
                for matches in indices:
                    if index in matches:
                        m = matches
                        break
                # Add matches_len
                merge_add["matches"].append(m)
                merge_add["matches_len"].append(len(m))

            # Add error_margin
            merge_add["error_margin"].append(ERROR_MARGIN)
            # Calculate and add err_margin_match
            min_x, min_y = pos[0] - ERROR_MARGIN, pos[1] - ERROR_MARGIN
            max_x, max_y = pos[0] + ERROR_MARGIN, pos[1] + ERROR_MARGIN
            if min_x <= true_x <= max_x and min_y <= true_y <= max_y:
                merge_add["err_margin_match"].append(True)
            else:
                merge_add["err_margin_match"].append(False)

            # Add error_radius
            merge_add["error_radius"].append(ERROR_RADIUS)
            # Calculate and add err_radius_match
            if true_pos_dist <= ERROR_RADIUS:
                merge_add["err_radius_match"].append(True)
            else:
                merge_add["err_radius_match"].append(False)

            # Add runtime_mean
            merge_add["runtime_mean"].append(runtime_mean)

    # Create data frame out of addition dictionary
    merge_df = pd.DataFrame(merge_add)

    # Fix column order
    columns = ["r",
               "s",
               "m",
               "n",
               "page_size",
               "page_margin",
               "cam_reso",
               "cap_area",
               "m5_size",
               "printer",
               "dpi",
               "num_win",
               "ia_id",
               "true_pos",
               "true_x",
               "true_y",
               "true_pos_dist",
               "index",
               "dbt_positions",
               "dbt_pos",
               "dbt_x",
               "dbt_y",
               "real_positions",
               "real_pos",
               "real_x",
               "real_y",
               "matching_indices",
               "matches",
               "matches_len",
               "error_margin",
               "err_margin_match",
               "error_radius",
               "err_radius_match",
               "runtime",
               "runtime_mean"]

    # Merge additions with main data frame (gobble up the old junk :D)
    sm = sm.merge(merge_df, left_index=True, right_on="ia_id")[columns]
    # Save to file (if filename given)
    if submatrix_fname is not None:
        sm.to_csv(submatrix_fname, index=False)
    # TODO: Make it create (if not present) or read (if present) and return sm
    return sm, raw


def filter_data():
    # ~6s runtime
    sm, raw = create_submatrix_csv()
    # # Performance timer
    # start_time = time.perf_counter()
    # total_time = time.perf_counter() - start_time
    # print(f"THIS took {total_time:.3f}s")

    # Drop 100 dpi values (no image analysis possible)
    # raw = raw.dropna()

    # Calculate overall_runtime_mean (Gesamtdurchschnittswert der Laufzeit)
    overall_runtime_mean = raw.runtime.sum() / raw.num_win.sum()
    print("Overall runtime mean for single submatrix (in s):")
    print(overall_runtime_mean)
    # Ist NICHT aussagekräftig weil wir die Analyse grundsätzlich beschränken
    # können wie wir wollen
    # print(raw.runtime.sum() / len(raw))

    print("dpi specific runtime mean (in s):")
    for dpi in raw.dpi.unique():
        dpi_df = raw[raw.dpi == dpi]
        # print("mean for single call / image analysis: ", end="")
        # per img analysis
        # print(dpi, dpi_df.runtime.sum() / len(dpi_df))
        # print("mean for single submatrix: ", end="")
        # per submatrix
        print(dpi, dpi_df.runtime.sum() / dpi_df.num_win.sum())

    # Filter for "good" and "bad" results
    # good_margin = sm[sm.err_margin_match]
    # bad_margin = sm[~sm.err_margin_match]
    good_radius = sm[sm.err_radius_match]
    bad_radius = sm[~sm.err_radius_match]

    # # Calculate margin means (Gesamtdurchschnittswert der guten/schlechten
    # # Ergebnisse mit Quadratauswahl)
    # print("Overall good results mean (margin):")
    # print(len(good_margin))  # count
    # good_margin_mean = len(good_margin) / len(sm)  # mean
    # print(good_margin_mean)  # mean
    # print("Overall bad results mean (margin):")
    # print(len(bad_margin))  # count
    # bad_margin_mean = len(bad_margin) / len(sm)  # mean
    # print(bad_margin_mean)  # mean

    # Calculate radius means (Gesamtdurchschnittswert der guten/schlechten
    # Ergebnisse mit Radiusauswahl)
    print("Overall good results mean (radius):")
    print(len(good_radius))  # count
    good_radius_mean = len(good_radius) / len(sm)  # mean
    print(good_radius_mean)  # mean
    # print("Overall bad results mean (radius):")
    # print(len(bad_radius), len(sm))  # count
    # bad_radius_mean = len(bad_radius) / len(sm)  # mean
    # print(bad_radius_mean)  # mean

    probs = {"printer": [], "dpi": [], "prob": []}
    # Calculate good result means for every dpi
    print(f"Mean for every dpi (radius)")
    for p_label in ["both"] + sm.printer.unique().tolist():
        # filter for printer
        if p_label == "both":
            sm_p = sm
            good_radius_p = good_radius
        else:
            sm_p = sm[sm.printer == p_label]
            good_radius_p = good_radius[good_radius.printer == p_label]

        for dpi in sm_p.dpi.unique():

            # print(f"Mean for {dpi} dpi (margin)")
            # good_margin_dpi = good_margin[good_margin.dpi == dpi]
            # print(len(good_margin_dpi), len(sm_dpi))  # count
            # print(len(good_margin_dpi)/len(sm_dpi))  # mean

            # filter for dpi
            sm_dpi = sm_p[sm_p.dpi == dpi]
            good_radius_dpi = good_radius_p[good_radius_p.dpi == dpi]

            # save prob
            probs["dpi"].append(dpi)
            prob = len(good_radius_dpi) / len(sm_dpi)
            probs["prob"].append(prob)
            probs["printer"].append(p_label)
            # print(dpi, len(good_radius_dpi), len(sm_dpi))  # count
            # print(len(good_radius_dpi) / len(sm_dpi))  # mean

    # Create probability data frame
    probs = pd.DataFrame(probs)
    print(probs)
    print(probs.to_latex())

    # Values for diagrams
    dpis = raw.dpi.unique()
    # Prepend 100 dpi values
    dpis = [(100, 100)] + dpis.tolist()
    dpis_xs = [x for x, y in dpis]
    num_wins = raw.num_win.unique()
    num_wins = [0] + num_wins.tolist()

    num_win_sums = []
    for dpi in raw.dpi.unique():
        num_win_sums.append(raw[raw.dpi == dpi].num_win.sum())
    num_win_sums = [0] + num_win_sums

    # TODO Do NOT use variables just use plt to continously draw a figure and
    # then save it with savefig("fname") (there are also LaTeX-friendly
    # postscript formates to export to)
    plt.plot(dpis_xs, num_win_sums, "--")
    plt.scatter(dpis_xs, num_win_sums, marker="^")
    plt.xlabel("Musterauflösungen (in dpi)")
    plt.ylabel("Anzahl Submatrizen (insgesamt)")
    plt.savefig("fig_dpis_num_win_sums.pdf")
    plt.close()

    plt.plot(dpis_xs, num_wins, "--")
    plt.scatter(dpis_xs, num_wins, marker="^")
    plt.xlabel("Musterauflösungen (in dpi)")
    plt.ylabel("Anzahl Submatrizen")
    plt.savefig("fig_dpis_num_wins.pdf")

    return

    # runtime_mean_complete = raw.runtime.

    # Probability for every dpi and split into printers
    # Create dictionary for creation of probability data frame
    probs = {"printer": [],
             "dpi": [],
             "dpi_x": [],
             "dpi_y": [],
             "nrows_margin": [],
             "prob_margin": [],
             "nrows_radius": [],
             "prob_radius": []}

    # EIN gutes ergb das mit dem bro dru gedruckt wurde und die dpi von 150 hat
    # p_lables = sm.printer.unique()

    # Iterate over printer labels (include both -> not filter)
    printer_labels = ["both"] + sm.printer.unique()
    for p_label in printer_labels:
        # Select printers (filter them)
        if p_label != "both":
            p_margin = good_margin[good_margin.printer == p_label]
            p_radius = good_radius[good_radius.printer == p_label]
            p_sm = sm[sm.printer == p_label]
        else:
            p_filt_margin = good_margin
            p_filt_radius = good_radius
            p_sm = sm

        # Iterate over dpis
        for dpi in sm.dpi.unique():
            dpi_x, dpi_y = dpi
            # filter dpis
            # zahl der guten

    # Iterate over dpis
    for dpi in sm.dpi.unique():
        dpi_x, dpi_y = dpi
        # Iterate over printer labels (include both -> not filter)
        printer_labels = ["both"] + sm.printer.unique()
        for p_label in printer_labels:
            # TODO split in good and bad? But those are complementary so it
            # doesn't mather too much as long as one of those is shown.
            if p_label != "both":
                # Filter for printer
                p_filt_margin = good_margin[good_margin.printer == p_label]
                p_filt_radius = good_radius[good_radius.printer == p_label]
                nrows_good_margin = len(good_margin)
                nrows_good_radius = len(good_radius)
                nrows = len(sm)
            else:
                nrows_margin = len()
                p_filter = good_margin[good_margin.printer == p_label]
                nrows_margin = len(good_margin[p_filter])
                p_filter = good_radius[good_radius.printer == p_label]
                nrows_radius = len(good_radius[p_filter])
                nrows()
            # nrows = len(p[(p.dpi == dpi)])
            nrows = len(sm)
            prob_margin = nrows_good_margin / nrows

            # Fill dictionary with values
            probs["printer"].append(p_label)
            probs["dpi"].append(dpi)
            probs["dpi_x"].append(dpi_x)
            probs["dpi_y"].append(dpi_y)
            probs["nrows_margin"].append(nrows_margin)
            probs["prob_margin"].append(prob_margin)
            probs["nrows_radius"].append(nrows_radius)
            probs["prob_radius"].append(prob_radius)

    # Create probability data frame
    probs = pd.DataFrame(probs)
    print(probs)


def create_plots(fname="raw.csv", submatrix_fname="submatrix.csv"):
    # ~6s runtime
    sm, raw = create_submatrix_csv()
    # Performance timer
    start_time = time.perf_counter()
    total_time = time.perf_counter() - start_time
    print(f"THIS took {total_time:.3f}s")
    # # Import raw csv
    # raw = pd.read_csv(fname)
    # transform_funcs = {"r": int,
    #                    "s": int,
    #                    "m": int,
    #                    "n": int,
    #                    "page_size": literal_eval,
    #                    "page_margin": literal_eval,
    #                    "cam_reso": literal_eval,
    #                    "cap_area": literal_eval,
    #                    "m5_size": literal_eval,
    #                    "printer": str,
    #                    "dpi": literal_eval,
    #                    "num_win": int,
    #                    "true_pos": literal_eval,
    #                    "dbt_positions": literal_eval,
    #                    "real_positions": literal_eval,
    #                    "matching_indices": literal_eval,
    #                    "runtime": float}
    # raw = raw.dropna().transform(transform_funcs)

    # # Import submatrix csv
    # submatrix = pd.read_csv(submatrix_fname)
    # transform_funcs = {"r": int,
    #                    "s": int,
    #                    "m": int,
    #                    "n": int,
    #                    "page_size": literal_eval,
    #                    "page_margin": literal_eval,
    #                    "cam_reso": literal_eval,
    #                    "cap_area": literal_eval,
    #                    "m5_size": literal_eval,
    #                    "printer": str,
    #                    "dpi": literal_eval,
    #                    "num_win": int,
    #                    "ia_id": int,
    #                    "true_pos": literal_eval,
    #                    "true_x": float,
    #                    "true_y": float,
    #                    "true_pos_dist": float,
    #                    "index": int,
    #                    "dbt_positions": literal_eval,
    #                    "dbt_pos": literal_eval,
    #                    "dbt_x": int,
    #                    "dbt_y": int,
    #                    "real_positions": literal_eval,
    #                    "real_pos": literal_eval,
    #                    "real_x": float,
    #                    "real_y": float,
    #                    "matching_indices": literal_eval,
    #                    "matches": literal_eval,
    #                    "matches_len": float,
    #                    "error_margin": int,
    #                    "err_margin_match": bool,
    #                    "error_radius": int,
    #                    "err_radius_match": bool,
    #                    "runtime": float,
    #                    "runtime_mean": float}
    # submatrix = submatrix.transform(transform_funcs)
    df = sm

    # probability "correct"/expected position of every printer and dpi (w/o
    # 100)
    probs = {"printer": [], "dpi": [], "prob": []}
    for p_label in df.printer.unique():
        p = df[df.printer == p_label]
        for dpi in p.dpi.unique():
            nrows_exp = len(p[(p.dpi == dpi) & p.err_margin_match])
            nrows = len(p[(p.dpi == dpi)])
            prob = nrows_exp / nrows
            probs["printer"].append(p_label)
            probs["dpi"].append(dpi)
            probs["prob"].append(prob)
    probs = pd.DataFrame(probs)
    print(probs)
    # Maybe create a plot with the probability on the y axis and the dpi from
    # 100 to 400 on the x axis

    ideal_pos = {"x": [], "y": []}
    for p in df["true_pos"].unique():
        ideal_pos["x"].append(p[0])
        ideal_pos["y"].append(p[1])
    ideal_pos = pd.DataFrame(ideal_pos)
    plt.scatter(ideal_pos["x"], ideal_pos["y"]).get_figure().show()
    # Maybe try to "connect" ideal positions with measured x and y values.

    # df[(df.dpi == (125, 125)) & (df.printer == "LexmarkMS510dn") &
    #    df.err_margin_match]
    for p_label in ["LexmarkMS510dn"]:  # df.printer.unique():
        p = df[df.printer == p_label]
        for dpi in [(125, 125)]:  # p.dpi.unique():
            f = p[(p.dpi == dpi) & p.err_margin_match]
            f_inv = p[(p.dpi == dpi) &
                      p.err_margin_match.apply(lambda x: not x)]
            plt.scatter(f_inv["x"], f_inv["y"]).get_figure().show()
            plt.scatter(f["x"], f["y"]).get_figure().show()

    # Draw scatter plots over each other
    # All X and Y positions
    # plt.scatter(df_pos["x"], df_pos["y"]).get_figure().show()
    # Only "correct" positions
    # filtered_inv = df_pos[df_pos["err_margin_match"].apply(lambda x: not x)]
    # filtered = df_pos[df_pos["err_margin_match"]]
    # plt.scatter(filtered_inv["x"], filtered_inv["y"]).get_figure().show()
    # plt.scatter(filtered["x"], filtered["y"]).get_figure().show()

    # print(df_pos[df_pos["err_margin_match"]])
    # print(df_pos[df_pos["err_margin_match"] &
    #              df_pos["matches"].apply(lambda x: x != [])])
    # print(df_pos[(df_pos["index"] == 0) & (df_pos["ia_id"] == 1799)])
    # print(df_pos[pd.notna(df_pos["matches"]) &
    #              df_pos["matches"].apply(lambda x: x != [])])

    # Prediction with matching indices:
    # - All match group
    # - Single "len>1" match group
    #   - Correct position
    #   - Incorrect position
    # - Several "len>1" match group
    #   - Every length level (from longest to shortest)
    #     - Single group
    #       - Correct position
    #       - Incorrect position
    #     - Several groups
    #       - Correct position
    #       - Incorrect position


if __name__ == "__main__":
    main()
