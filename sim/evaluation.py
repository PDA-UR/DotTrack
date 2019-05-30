from PIL import Image
import glob
import re
import time
import dt_sim as sim
import pandas as pd
import numpy as np
from pathlib import Path
# Evaluate python data types: https://stackoverflow.com/a/33283145
from ast import literal_eval
import matplotlib.pyplot as plt


def main():
    csv = Path("eval.csv")
    if not csv.exists():
        create_csv()
    create_plots()


def create_csv():
    start_time = time.perf_counter()

    # Error margin in millimeters
    # error_margin = 5  # Seems to NOT work anymore at 175, 150 and 125 dpi
    # error_margin = 6  # Seems to NOT work anymore at 175, 150 and 125 dpi
    # error_margin = 7  # Seems to work at 175, 150 and 125 dpi
    # error_margin = 8  # Seems to work at 200 dpi
    # error_margin = 9  # Seems to work at 200 dpi
    # error_margin = 10  # 7 and even more buffer
    # error_margin = 20  # get max

    # Margin of the movement area [page margin + (M5Stack size / 2) = 32]
    move_margin = (32, 32)

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

    # num_p = 0
    # num_match = 0
    # error_margins = []
    data = {"camera resolution": [],
            "camera capture area size": [],
            "printer": [],
            "r (dbt_h)": [],
            "s (dbt_w)": [],
            "m (win_h)": [],
            "n (win_w)": [],
            "dpi": [],
            "expected position": [],
            "number of windows": [],
            "decoded positions": [],
            "matching position indices": []}
    # columns = ["camera resolution", "camera capture area size",
    #            "printer maker", "printer model", "r (dbt_h)", "s (dbt_w)",
    #            "m (win_h)", "n (win_w)", "dpi", "expected position",
    #            "number of windows", "decoded DBT positions",
    #            "matching indices"]
    # add_col = ["error margin", "page margin", "M5Stack size", "move margin",
    #            "decoded real positions", "matching positions"]
    # df = pd.DataFrame()

    for file in sorted(files):
        print("=" * 80)

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
        data["r (dbt_h)"].append(r)
        data["s (dbt_w)"].append(s)
        data["m (win_h)"].append(m)
        data["n (win_w)"].append(n)
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
        data["expected position"].append(pos)
        print(pos)

        frame = Image.open(file)
        # Skip 100x100dpi images because they can't be analysed with our
        # current implementation of the bit extraction.
        if dpi == (100, 100):
            positions = np.nan
            matching_indices = np.nan
            data["number of windows"].append(np.nan)
        else:
            positions, matching_indices = sim.analyse_frame(frame,
                                                            cam_size,
                                                            dbt_log,
                                                            dpi,
                                                            win_w,
                                                            win_h,
                                                            pipeline_id)
            data["number of windows"].append(len(positions))
        data["decoded positions"].append(positions)
        data["matching position indices"].append(matching_indices)
        data["camera resolution"].append(frame.size)
        data["camera capture area size"].append(sim.CAM_SIZE)

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
    df = pd.DataFrame(data)
    df.to_csv("eval.csv")  # , index=False)

    total_time = time.perf_counter() - start_time
    print(f"Evaluation took {total_time:.3f}s")


def create_plots():
    # Handle index column: https://stackoverflow.com/a/36519122
    # Column order:
    # https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.read_csv.html
    # """
    # To instantiate a DataFrame from data with element order preserved use
    # pd.read_csv(data, usecols=['foo', 'bar'])[['foo', 'bar']] for columns in
    # ['foo', 'bar'] order or pd.read_csv(data, usecols=['foo', 'bar'])[['bar',
    # 'foo']] for ['bar', 'foo'] order.
    # """
    columns = ["camera resolution",
               "camera capture area size",
               "printer",
               "r (dbt_h)",
               "s (dbt_w)",
               "m (win_h)",
               "n (win_w)",
               "dpi",
               "expected position",
               "number of windows",
               "decoded positions",
               "matching position indices"]
    raw = pd.read_csv("eval.csv", index_col=0)[columns]

    transform_funcs = {"camera resolution": literal_eval,
                       "camera capture area size": literal_eval,
                       "printer": lambda x: x,
                       "r (dbt_h)": lambda x: x,
                       "s (dbt_w)": lambda x: x,
                       "m (win_h)": lambda x: x,
                       "n (win_w)": lambda x: x,
                       "dpi": literal_eval,
                       "expected position": literal_eval,
                       "number of windows": int,
                       "decoded positions": literal_eval,
                       "matching position indices": literal_eval}
    transformed = raw.dropna().transform(transform_funcs)

    positions = {"key": [], "index": [], "x": [], "y": [], "matches": [],
                 "error_margin": [], "expected_pos": []}
    # Error margin in millimeters
    error_margin = 5
    for k in transformed["decoded positions"].keys():
        match_list = transformed["matching position indices"][k]
        indices = [ind for ind in match_list if len(ind) > 1]

        for index, pos in enumerate(transformed["decoded positions"][k]):
            positions["key"].append(k)
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
            p = transformed["expected position"][k]
            min_x, min_y = pos[0] - error_margin, pos[1] - error_margin
            max_x, max_y = pos[0] + error_margin, pos[1] + error_margin
            if min_x <= p[0] <= max_x and min_y <= p[1] <= max_y:
                positions["expected_pos"].append(True)
            else:
                positions["expected_pos"].append(False)

    df_pos = pd.DataFrame(positions)

    # merge positions with main data frame
    df = transformed.merge(df_pos, left_index=True, right_on="key")

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
    for p in df["expected position"].unique():
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
    # print(df_pos[(df_pos["index"] == 0) & (df_pos["key"] == 1799)])
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
