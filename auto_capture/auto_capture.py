#!/usr/bin/env python3

import ebb_motion
import ebb_serial
import time
import math
# from reportlab.lib.pagesizes import A4
# from reportlab.lib.units import mm
import numpy as np
import serial
from PIL import Image
# import dt_sim as sim


class AutoCapture(object):

    """Automatically capture camera/sensor frames with help of the AxiDraw."""

    def __init__(self, w, h, win_w, win_h, dpi, m5stack_port="/dev/ttyUSB0"):
        """Initialize AutoCapture object.

        @return: AutoCapture object.
        @rtype : <class 'auto_capture.AutoCapture'>
        """
        self._pdf_id = 0
        self._init_axidraw()
        self._init_m5stack(m5stack_port)
        self._init_misc()

    # Setup AxiDraw
    def _init_axidraw(self):
        self._port = ebb_serial.openPort()
        ebb_motion.sendDisableMotors(self._port)

        # Ratio experiment:
        # @152 dpi 1 pixel right and down
        # ebb_motion.doABMove(port, 20, -20, 200)
        # ebb_motion.doABMove(port, 15, -15, 200)

        # Millimeter factor (should be correlated as closely as possible to the
        # move value needed to move one millimeter). Multiply with millimeter
        # value.
        # 15 (move points to pattern pixel ratio; estimation from ratio
        # experiment)
        # (1/152) * 25.4 = 0.16710526315789473 (mm per pattern pixel)
        # 1/0.16710526315789473 = 5.984.. (=> ~6 pattern pixel per mm)
        # 15 * 6 = 90 (~90 move points per mm)
        # mm = 90
        # Further testing showed it should be less than 90
        # mm = 80
        # Manual testing with a 127dpi paper (1 pattern pixel is exactly 0.2mm)
        # showed that x- and y-axis differ a bit and that the values are
        # slightly higher than 80.
        # Also the first move to the other side on the y-axis is a bit skewed
        # (~0.2mm). There could maybe be code to compensate for the direction
        # change inaccuracy.
        # x_mm = 82
        # y_mm = 85
        # Manual testing over full DIN A4 papers yielded these results:
        self._x_mm = 80
        self._y_mm = 80
        # https://github.com/ertdfgcvb/Genau
        # This libraries README also states the same values:
        # "where 80 steps = 1mm"

        # From the "EBB (EiBotBoard) Command Set" documentation:
        # "Minimum speed is 1.31 steps/second."
        # "Maximum speed is 25k Steps/second."
        # max_vel = 25000
        # min_vel = 1.31
        # Calculate maximum and minimum millisecond divider (with added
        # padding for the maximum)
        # max_ms_per_step = int((max_vel / 1000) * 0.8)
        # min_ms_per_step = min_vel / 1000
        # Manual/Sensible maximum and minimum values for millisecond divider
        # These are not the absolute maximum and minimum values but should be
        # more than enough for our purposes.
        max_ms_per_step = 20
        min_ms_per_step = 0.1
        one_percent_vel = (max_ms_per_step - min_ms_per_step) / 100
        # max_duration does not really matter in our context
        # min_duration = 4 @ 80 move points => 20 ms/step
        # BUT:
        # our min_steps are 26 => duration = math.ceil(1.3) = 2 @ 20 ms/step

        # According to the User Guide lower percentages are better for accuracy
        # (p. 35).
        # 0% will be min_ms_per_step and 100% max_ms_per_step. That means that
        # even if self._vel_percent is 0 that the AxiDraw will still move at
        # the minimum velocity.
        # The 15% value should work pretty well for small and big distances.
        self._vel_percent = 15
        if self._vel_percent < 0 or self._vel_percent > 100:
            raise ValueError("The self._vel_percent variable " +
                             f"({self._vel_percent}) is not between " +
                             "0 and 100 (both ends included).")

        # Time divider
        # Divide by the max_steps value to get the move duration in
        # milliseconds.
        self._ms = (one_percent_vel * self._vel_percent) + min_ms_per_step

        # Direction factor. Multiply with move value to get right sign for
        # direction.
        # Assumes the AxiDraw sits to the right of the pattern paper.
        self._up, self._right = -1, -1
        self._down, self._left = 1, 1

    # Setup serial connection to M5Stack (and setup frame capturing)
    def _init_m5stack(self, port):
        # Open serial port
        self._ser = serial.Serial(port, 115200, timeout=1)
        self._imgsize = [36, 36]
        self._img_byte_len = self._imgsize[0] * self._imgsize[1]

    # Setup areas, positions, margins, misc, etc.
    def _init_misc(self):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        # Calculate restricted areas (all in millimeters unless otherwise
        # stated):
        # Margin of the page
        # TODO: Use margin value from create_pdf.py script.
        self._page_margin = (5, 5)
        # Calculate page size (in millimeters)
        # TODO: Use pagesize value from create_pdf.py script.
        self._page_size = A4[0] / mm, A4[1] / mm
        # Calculate size of printed area
        self._printed_size = (self._page_size[0] - self._page_margin[0] * 2,
                              self._page_size[1] - self._page_margin[1] * 2)
        # M5Stack size
        self._m5stack_size = (54, 54)
        # M5Stack margin
        self._m5stack_margin = (self._m5stack_size[0] / 2,
                                self._m5stack_size[1] / 2)
        # Margin of moveable area (without hitting the page_margin with the
        # M5Stack)
        self._move_margin = (self._page_margin[0] + self._m5stack_margin[0],
                             self._page_margin[1] + self._m5stack_margin[1])
        # Size of moveable area
        self._move_size = (self._page_size[0] - self._move_margin[0] * 2,
                           self._page_size[1] - self._move_margin[1] * 2)

    def _close_serial(self):
        # close serial ports/connections
        ebb_serial.closePort(self._port)
        self._ser.close()

    def _save_img(self):
        while True:
            # Read serial data
            data = self._ser.read_until(terminator=b"\xFE")

            # Remove terminator byte
            data = data[:-1]
            # Remove header byte (indicates frame analyse request)
            if len(data) == self._img_byte_len + 1 and data[0] == 0xFD:
                data = data[1:]
            # If the length is still not correct try again
            if len(data) != self._img_byte_len:
                print("Received bad data from image capture. Trying again...")
                continue
            break

        # Expand bytes to full range (0-255)
        data = bytes([min(b * 2, 255) for b in data])
        # Create image
        img = Image.frombytes("L", self._imgsize, data)
        img.show()
        # Save image
        # img.save(self._get_fname())

    # TODO/FIXME: Create schema for file name and implement it here.
    def _get_fname(self):
        # TODO: mkdir? import pathlib?
        # directory = "frames/{pdf_id}/"
        fname = "frame-"
        params = ["{self._pdf_id}"]
        params.append("{mm_pos[0]}x{mm_pos[1]}")
        params.append("{move_pos[0]}x{move_pos[1]}")
        # return directory + fname + "_".join(params)
        return fname + "_".join(params)

    def run(self):
        # 4. Calibrate AxiDraw position
        # * Maybe use AxiDraw home position if page setup/fixation allows for
        # moving the M5Stack over the edge of the page.
        input("Please move AxiDraw/M5Stack to the top left corner of the " +
              "page. The sides of the M5Stack should align with the " +
              "printable area (page margin).")
        # * Otherwise use readouts and ask the user for a manual check if the
        # position is correct.
        # TODO: Move to the top left corner of the page. (Low Prio. Not worth
        # the effort.)

        # 5. Start capturing test data.
        # TODO Maybe move this initialisation step to __init__
        # Use 5 columns and take 20 frames per column to get 100 frames total
        # per page.
        num_cols = 5
        frames_per_col = 20

        # Calculate column move deltas
        col_points = np.linspace(0, self._move_size[0], num_cols)
        # Calculate millimeter deltas for columns.
        col_deltas = np.diff(col_points)
        col_delta_sum = np.sum(col_deltas)
        print(f"col_deltas: {col_deltas}")
        print(f"col_delta_sum: {col_delta_sum}")
        # Calculate move value deltas for columns.
        col_move_deltas = (col_deltas * self._x_mm).astype(int)
        col_move_delta_sum = np.sum(col_move_deltas)
        print(f"col_move_deltas: {col_move_deltas}")
        print(f"col_move_delta_sum: {col_move_delta_sum}")
        # TODO/FIXME: What should I do with missing move steps? Add to first
        # move?
        # Maybe just ignore this.

        # Decrease the distance between frames within a column to also get an
        # idea of the accuracy of the readings.
        # Space out values logarithmically
        spaced_points = np.geomspace(self._move_size[1]+1, 1, frames_per_col)
        # Calculate millimeter deltas.
        deltas = np.abs(np.diff(spaced_points))
        delta_sum = np.sum(deltas)
        print(f"deltas: {deltas}")
        print(f"delta_sum: {delta_sum}")
        # Calculate move value deltas.
        move_deltas = (deltas * self._y_mm).astype(int)
        move_delta_sum = np.sum(move_deltas)
        print(f"move_deltas: {move_deltas}")
        print(f"move_delta_sum: {move_delta_sum}")
        # TODO/FIXME: What should I do with missing move steps? Add to first
        # move?
        # Maybe just ignore this.

        start_time = time.perf_counter()
        # Capture initial img
        # self._save_img()
        # Setup initial y_direction
        y_direction = self._down
        for col_d in col_move_deltas:
            print("="*80)
            for d in move_deltas:
                x = 0
                y = d * y_direction
                self._capture_next_img(x, y)
            # flip y_direction
            if y_direction == self._down:
                y_direction = self._up
            else:
                y_direction = self._down
            x = col_d * self._right
            y = 0
            self._capture_next_img(x, y)
        # TODO/FIXME proper fix:
        # Run last column
        print("="*80)
        for d in move_deltas:
            x = 0
            y = d * y_direction
            self._capture_next_img(x, y)

        # End AxiDraw movement
        ebb_motion.sendDisableMotors(self._port)
        self._close_serial()
        total_time = time.perf_counter() - start_time
        print(f"Auto capture took {total_time:.3f}s")

        # # Example:
        # # Move one millimeter to the right and one millimeter down.
        # x = 1*self._x_mm*self._right
        # y = 1*self._y_mm*self._down
        # duration = math.ceil(max(abs(x), abs(y)) / self._ms)
        # # Set 100ms as minimum for the duration value
        # duration = max(duration, 100)
        # ebb_motion.doABMove(self._port, y, x, duration)
        # time.sleep(math.ceil(duration / 1000))
        # # End AxiDraw movement
        # ebb_motion.sendDisableMotors(self._port)

    def _capture_next_img(self, x, y):
        self._make_move(x, y)
        self._save_img()

    def _make_move(self, x, y):
        # duration = math.ceil(max(abs(x), abs(y)) / self._ms)
        # # Set 100ms as minimum for the duration value
        # duration = max(duration, 100)
        duration = self._calc_duration(x, y)
        print(x, y, duration)
        ebb_motion.doABMove(self._port, y, x, duration)
        time.sleep(math.ceil(duration / 1000))

    def _calc_duration(self, x, y):
        axis_steps_1 = y + x
        axis_steps_2 = y - x
        max_steps = max(abs(axis_steps_1), abs(axis_steps_2))
        duration = math.ceil(max_steps / self._ms)
        return duration


def main():
    ac = AutoCapture(8192, 4096, 5, 5, (150, 150))
    # print(ac)
    ac.run()


if __name__ == "__main__":
    main()
