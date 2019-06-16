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
    fname = "raw.csv"
    submatrix_fname = "submatrix.csv"
    csv = Path(fname)
    if not csv.exists():
        create_csv(fname)
    submatrix_csv = Path(submatrix_fname)
    if not submatrix_csv.exists():
        create_submatrix_csv(submatrix_fname)
    # TODO: Create plots and calc output
    # create_plots(fname)


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
    move_margin = (M5_SIZE[0] / 2 - PAGE_MARGIN[0],
                   M5_SIZE[1] / 2 - PAGE_MARGIN[1])

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


def create_submatrix_csv(submatrix_fname="submatrix.csv"):
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
    submatrix = raw.dropna().transform(transform_funcs)

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
    for ia_id in submatrix["real_positions"].keys():
        # Setup for submatrix loop

        # Extract true_x and true_y
        true_x, true_y = submatrix["true_pos"][ia_id]

        # Extract matching_indices
        matching_indices = submatrix["matching_indices"][ia_id]
        # Extract indices that match
        indices = [ind for ind in matching_indices if len(ind) > 1]

        # Extract runtime_mean
        runtime = submatrix["runtime"][ia_id]
        num_win = submatrix["num_win"][ia_id]
        runtime_mean = runtime / num_win

        # Iterate over available submatrizes (adds up to 90000)
        for index, pos in enumerate(submatrix["real_positions"][ia_id]):
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
            dbt_pos = submatrix["dbt_positions"][ia_id][index]
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
    df = submatrix.merge(merge_df, left_index=True, right_on="ia_id")[columns]
    # Save to file
    df.to_csv(submatrix_fname, index=False)
    # TODO: Make it create (if not present) or read (if present) and return df
    # return df


def create_plots(fname="raw.csv", submatrix_fname="submatrix.csv"):
    # TODO Structure anew

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
    transformed = raw.dropna().transform(transform_funcs)

    # TODO: Calc runtime mean for every submatrix
    positions = {"ia_id": [],
                 "index": [],
                 "x": [],
                 "y": [],
                 "matches": [],
                 "error_margin": [],
                 "expected_pos": []}
    # Error margin in millimeters
    # TODO Use global value (save global value to data frame?)
    error_margin = 5
    for k in transformed["real_positions"].keys():
        match_list = transformed["matching_indices"][k]
        indices = [ind for ind in match_list if len(ind) > 1]

        for index, pos in enumerate(transformed["real_positions"][k]):
            positions["ia_id"].append(k)
            positions["index"].append(index)
            positions["x"].append(pos[0])
            positions["y"].append(pos[1])

            if len(match_list) == 0:
                positions["matches"].append(np.nan)
            else:
                m = []
                for matches in indices:
                    if index in matches:
                        m = matches
                        break
                positions["matches"].append(m)

            positions["error_margin"].append(error_margin)
            # Find expected position matches:
            p = transformed["true_pos"][k]
            min_x, min_y = pos[0] - error_margin, pos[1] - error_margin
            max_x, max_y = pos[0] + error_margin, pos[1] + error_margin
            if min_x <= p[0] <= max_x and min_y <= p[1] <= max_y:
                positions["expected_pos"].append(True)
            else:
                positions["expected_pos"].append(False)

    df_pos = pd.DataFrame(positions)

    # merge positions with main data frame
    df = transformed.merge(df_pos, left_index=True, right_on="ia_id")

    # probability "correct"/expected position of every printer and dpi (w/o
    # 100)
    probs = {"printer": [], "dpi": [], "prob": []}
    for p_label in df.printer.unique():
        p = df[df.printer == p_label]
        for dpi in p.dpi.unique():
            nrows_exp = len(p[(p.dpi == dpi) & p.expected_pos])
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
    #    df.expected_pos]
    for p_label in ["LexmarkMS510dn"]:  # df.printer.unique():
        p = df[df.printer == p_label]
        for dpi in [(125, 125)]:  # p.dpi.unique():
            f = p[(p.dpi == dpi) & p.expected_pos]
            f_inv = p[(p.dpi == dpi) & p.expected_pos.apply(lambda x: not x)]
            plt.scatter(f_inv["x"], f_inv["y"]).get_figure().show()
            plt.scatter(f["x"], f["y"]).get_figure().show()

    # Draw scatter plots over each other
    # All X and Y positions
    # plt.scatter(df_pos["x"], df_pos["y"]).get_figure().show()
    # Only "correct" positions
    filtered_inv = df_pos[df_pos["expected_pos"].apply(lambda x: not x)]
    filtered = df_pos[df_pos["expected_pos"]]
    plt.scatter(filtered_inv["x"], filtered_inv["y"]).get_figure().show()
    plt.scatter(filtered["x"], filtered["y"]).get_figure().show()

    # print(df_pos[df_pos["expected_pos"]])
    # print(df_pos[df_pos["expected_pos"] &
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
