#!/usr/bin/env python3

import ebb_motion
import ebb_serial
import time
import math
import numpy as np
import serial
from PIL import Image
import re
import os


class AutoCapture(object):

    """Automatically capture camera/sensor frames with help of the AxiDraw."""

    def __init__(self, printer_id, pdf_fname, m5stack_port="/dev/ttyUSB0"):
        """Initialize AutoCapture object.

        @return: AutoCapture object.
        @rtype : <class 'auto_capture.AutoCapture'>
        """
        self._printer_id = printer_id
        self._pdf_fname = pdf_fname
        self._pdf_id = re.findall(r"\d+x\d+_\d+x\d+_\d+x\d+dpi",
                                  self._pdf_fname)
        if len(self._pdf_id) == 1:
            self._pdf_id = self._pdf_id[-1]
        else:
            raise ValueError(f"PDF file name ({self._pdf_fname}) does not " +
                             "contain pdf_id (or multiple).\nValid example:" +
                             "\npdf_fname: " +
                             "output-8192x4096_5x5_150x150dpi.pdf\npdf_id " +
                             "(extracted): 8192x4096_5x5_150x150dpi")
        self._m5stack_port = m5stack_port
        self._init_misc()
        self._init_axidraw()
        self._init_m5stack()

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
        self._x_mm = 80.2
        self._y_mm = 80.2
        # https://github.com/ertdfgcvb/Genau
        # This libraries README also states almost the same values:
        # "where 80 steps = 1mm"

        # From the "EBB (EiBotBoard) Command Set" documentation:
        # "Minimum speed is 1.31 steps/second."
        # "Maximum speed is 25k Steps/second."
        self._max_vel = 25000
        self._min_vel = 1.31
        # Calculate maximum and minimum millisecond divider
        self._max_ms = self._max_vel / 1000
        self._min_ms = self._min_vel / 1000
        # Manual/Sensible maximum and minimum values for millisecond divider
        # These are not the absolute maximum and minimum values but should be
        # more than enough for our purposes.
        # self._max_ms = 20
        # self._min_ms = 0.1
        # max_duration does not really matter in our context
        # min_duration = 4 @ 80 move points => 20 ms/step
        # BUT:
        # our min_steps are 26 => duration = math.ceil(1.3) = 2 @ 20 ms/step
        # TODO: Maybe use the same maximum/minimum as in the AxiDraw Inkscape
        # plugin
        # Maximum:
        # Would decrement self._ms by 1 until it is smaller than self._max_ms.
        # https://github.com/evil-mad/axidraw/blob/master/inkscape%20driver/axidraw_conf.py#L112
        # Minimum (is hardcoded):
        # If self._ms value is smaller than 0.002 it would jump to 0.
        # https://github.com/evil-mad/axidraw/blob/master/inkscape%20driver/axidraw.py#L2373
        # self._max_ms = 24.995
        # self._min_ms = 0.002

        # According to the User Guide lower percentages are better for accuracy
        # (p. 35).
        # 0% will be self._min_ms and 100% self._max_ms. That means that
        # even if self._vel_percent is 0 that the AxiDraw will still move at
        # the minimum velocity.
        # The 15% value should give pretty good accuracy and work pretty well
        # for small and big distances.
        self._vel_percent = 15
        if self._vel_percent < 0 or self._vel_percent > 100:
            raise ValueError("The self._vel_percent variable " +
                             f"({self._vel_percent}) is not between " +
                             "0 and 100 (both ends included).")

        # Time divider
        # Divide by the max_steps value to get the move duration in
        # milliseconds.
        min_max_delta = self._max_ms - self._min_ms
        self._ms = (min_max_delta * (self._vel_percent / 100)) + self._min_ms
        # TODO/FIXME: This calculation with vel_percent value does not seem to
        # do the same as the AxiDraws with the drawing speed percentage.
        # In the AxiDraw Inkscape plugin code the ms value at high resolution
        # and 15% drawing speed seems to be around ~2.41
        # Example:
        # # TODO: Not confirmed yet from AxiDraw code. Should be extremely
        # # close though because it works very well in tests.
        # steps_per_mm = 80
        # # drawing speed pecentage (needs to be between 1 and 110 [for some
        # # reason]) Default: 25
        # pen_down_speed = 15
        # # Maximum XY speed allowed when in High Resolution mode, in inches
        # # per second. Default: 8.6979, Max: 8.6979
        # SpeedLimXY_HR = 8.6979
        # # Speed given as maximum inches/second in XY plane
        # inch_per_s = pen_down_speed * SpeedLimXY_HR / 110.0
        # ms = (inch_per_s / 1000) * 25.4 * steps_per_mm  # == ~2.41010
        self._ms = 2.41

        # Direction factor. Multiply with move value to get right sign for
        # direction.
        # Assumes the AxiDraw sits to the right of the pattern paper.
        self._up, self._right = -1, -1
        self._down, self._left = 1, 1

        # Use 5 columns and take 20 frames per column to get 100 frames total
        # per page.
        num_cols = 5
        frames_per_col = 20

        # Calculate column move deltas
        x_points = np.linspace(0, self._move_size[0], num_cols)
        # Calculate millimeter deltas for columns.
        self._x_deltas = np.diff(x_points)
        # self._x_delta_sum = np.sum(self._x_deltas)
        # print(f"self._x_deltas: {self._x_deltas}")
        # print(f"self._x_delta_sum: {self._x_delta_sum}")
        # Calculate move value deltas for columns.
        # Because of rounding errors there is a difference between the full
        # page move (move_size * mm) and the move_delta_sum. Since this error
        # is very small it is ignored.
        # TODO: Maybe handle these errors better.
        self._x_move_deltas = (self._x_deltas * self._x_mm).astype(int)
        # self._x_move_delta_sum = np.sum(self._x_move_deltas)
        # print(f"self._x_move_deltas: {self._x_move_deltas}")
        # print(f"self._x_move_delta_sum: {self._x_move_delta_sum}")

        # Decrease the distance between frames within a column to also get an
        # idea of the accuracy of the readings.
        # Space out values logarithmically
        y_points = np.geomspace(self._move_size[1]+1, 1, frames_per_col)
        # Calculate millimeter deltas.
        self._y_deltas = np.abs(np.diff(y_points))
        # self._y_delta_sum = np.sum(self._y_deltas)
        # print(f"self._y_deltas: {self._y_deltas}")
        # print(f"self._y_delta_sum: {self._y_delta_sum}")
        # Calculate move value deltas.
        # Because of rounding errors there is a difference between the full
        # page move (move_size * mm) and the move_delta_sum. Since this error
        # is very small it is ignored.
        # TODO: Maybe handle these errors better.
        self._y_move_deltas = (self._y_deltas * self._y_mm).astype(int)
        # self._y_move_delta_sum = np.sum(self._y_move_deltas)
        # print(f"self._y_move_deltas: {self._y_move_deltas}")
        # print(f"self._y_move_delta_sum: {self._y_move_delta_sum}")

    # Setup serial connection to M5Stack (and setup frame capturing)
    def _init_m5stack(self):
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
        # Open serial port
        self._ser = serial.Serial(self._m5stack_port, 115200, timeout=1)

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

        # Close serial port
        self._ser.close()

        # Expand bytes to full range (0-255)
        data = bytes([min(b * 2, 255) for b in data])
        # Create image
        img = Image.frombytes("L", self._imgsize, data)
        # Save image
        img.save(self._get_fname())

    def _get_fname(self):
        # TODO: Use directories? Use pathlib?
        # directory = f"frames/{printer_id}/{pdf_id}/"
        # return directory + fname + "_".join(params)
        base_fname = "frame-"
        ext = ".png"
        params = [f"{self._rel_x:07.3f}x{self._rel_y:07.3f}pos"]
        params.append(f"{self._printer_id}")
        params.append(f"{self._pdf_id}")
        path = "/".join(params[1:]) + "/"
        # Create path if it does not exist
        if not os.path.exists(path):
            os.makedirs(path)
        return path + base_fname + "_".join(params) + ext

    def run_right_angle_check(self):
        yes = ""
        while yes not in ["y", "Y", "yes"]:
            direction = input("This is the right angle alignment check.\n" +
                              "Enter direction to move (move_size == " +
                              "distance) or skip with \"s\" or \"skip\": ")
            x, y = 0, 0
            if direction in ["s", "skip"]:
                break
            elif direction in ["l", "left"]:
                x = round(self._move_size[0] * self._x_mm * self._left)
            elif direction in ["r", "right"]:
                x = round(self._move_size[0] * self._x_mm * self._right)
            elif direction in ["d", "down"]:
                y = round(self._move_size[1] * self._y_mm * self._down)
            elif direction in ["u", "up"]:
                y = round(self._move_size[1] * self._y_mm * self._up)
            else:
                continue
            self._make_move(x, y)
            # End AxiDraw movement
            ebb_motion.sendDisableMotors(self._port)

    def run(self):
        # 4. Calibrate AxiDraw position
        self.run_right_angle_check()
        # * Maybe use AxiDraw home position if page setup/fixation allows for
        # moving the M5Stack over the edge of the page.
        input(f"AutoCapture of {self._pdf_fname} printed by " +
              f"{self._printer_id} printer. Please move AxiDraw/M5Stack to " +
              "the top left corner of the page. The sides of the M5Stack " +
              "should align with the printable area (page margin).")
        # * Otherwise use readouts and ask the user for a manual check if the
        # position is correct.
        # TODO: Move to the top left corner of the page. (Low Prio. Not worth
        # the effort.)

        # 5. Start capturing test data.
        start_time = time.perf_counter()

        # Capture initial img
        self._rel_x, self._rel_y = 0.0, 0.0
        self._save_img()
        # Setup initial y_direction
        y_direction = self._down
        # Run columns and rows
        for i, x_delta in enumerate(self._x_move_deltas):
            for j, y_delta in enumerate(self._y_move_deltas):
                x = 0
                y = y_delta * y_direction
                self._rel_y += self._y_deltas[j] * y_direction
                self._capture_next_img(x, y)
            # flip y_direction
            if y_direction == self._down:
                y_direction = self._up
            else:
                y_direction = self._down
            x = x_delta * self._right
            y = 0
            self._rel_x += self._x_deltas[i]
            self._capture_next_img(x, y)
        # TODO/FIXME proper fix:
        # Run last column
        for j, y_delta in enumerate(self._y_move_deltas):
            x = 0
            y = y_delta * y_direction
            self._rel_y += self._y_deltas[j] * y_direction
            self._capture_next_img(x, y)

        # End AxiDraw movement
        ebb_motion.sendDisableMotors(self._port)
        # self._close_serial()

        total_time = time.perf_counter() - start_time
        print(f"Auto capture took {total_time:.3f}s")

    def _capture_next_img(self, x, y):
        self._make_move(x, y)
        self._save_img()

    def _make_move(self, x, y):
        duration = self._calc_duration(x, y)
        ebb_motion.doABMove(self._port, y, x, duration)
        time.sleep(math.ceil(duration / 1000))

    def _calc_duration(self, x, y):
        # Duration calculated according to:
        # https://evil-mad.github.io/EggBot/ebb.html#XM
        axis_steps_1 = y + x
        axis_steps_2 = y - x
        max_steps = max(abs(axis_steps_1), abs(axis_steps_2))
        duration = math.ceil(max_steps / self._ms)
        return duration


def main():
    # Printer names (used in file names)
    printer_ids = ["BrotherHLL8360CDW", "LexmarkMS510dn"]
    for printer_id in printer_ids:
        # DPI values for evaluation
        dpis = [(400, 400),
                (350, 350),
                (300, 300),
                (250, 250),
                (200, 200),
                (175, 175),
                (150, 150),
                (125, 125),
                (100, 100)]
        for dpi in dpis:
            pdf_fname = f"output-8192x4096_5x5_{dpi[0]}x{dpi[1]}dpi.pdf"
            ac = AutoCapture(printer_id, pdf_fname, "/dev/ttyUSB0")
            ac.run()
    ac._close_serial()


if __name__ == "__main__":
    main()
