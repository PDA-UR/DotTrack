#!/usr/bin/python3
import tkinter
import serial
from PIL import Image, ImageTk
import threading
import dt_sim as sim

imgsize = [36, 36]
img_byte_len = imgsize[0] * imgsize[1]
img_rsz_mltpl = 10
root = tkinter.Tk()
root.title("DotTrack - Frame Capture Streaming")
root.resizable = False
label = tkinter.Label(root)
label.pack()
ser = None
tkimg = None
# 270+ ms should be around the time it takes to capture another image.
stream_loop_delay = 0

first_run = True
cam_size = sim.CAM_SIZE
dbt_w, dbt_h, win_w, win_h = sim.DBT_W, sim.DBT_H, sim.WIN_W, sim.WIN_H
dbt_log = sim.get_dbt_log(dbt_w, dbt_h, win_w, win_h)
dbt_dpi = sim.DPI
thr = None
analyse_frame = False
pipeline_id = "baseline"


def stream_loop():
    global tkimg, first_run, thr, analyse_frame
    # Read serial data
    data = ser.read_until(terminator=b"\xFE")
    # Remove terminator byte
    data = data[:-1]
    # print(len(data))
    if len(data) == img_byte_len + 1 and data[0] == 0xFD:
        # Remove header byte (indicates frame analyse request)
        data = data[1:]
        analyse_frame = True
    # if data is not None:
    #     data = data[:-1]
    # else:
    #     print("Error: data is None")
    #     return

    # Fill up or shorten bytes
    data_len = len(data)
    # Shorten bytes
    if data_len > img_byte_len:
        data = data[data_len-img_byte_len:]
        # print("{} bytes long. Shortened to {}!".format(data_len, len(data)))
    # Fill up bytes
    elif data_len < img_byte_len:
        byte_count = img_byte_len - data_len
        data += b"\xFF" * byte_count
        # print("Only {} bytes long. Fill up with {} to {}!".format(data_len,
        #                                                           byte_count,
        #                                                           len(data)))

    # Error out if the length is still not correct
    if len(data) != img_byte_len:
        # print("Under {} bytes long ({} bytes). Aborting!".format(
        #     img_byte_len,
        #     len(data)))
        return

    # Expand bytes to full range (0-255)
    data = bytes([min(b * 2, 255) for b in data])

    # Create image
    img = Image.frombytes("L", imgsize, data)

    # Analyse frame
    if analyse_frame or first_run:
        first_run = False
        if analyse_frame and (thr is None or not thr.is_alive()):
            analyse_frame = False
            thr = threading.Thread(target=print_analyse_frame,
                                   args=[img])
            thr.start()
        # Resize img
        # img = img.resize((imgsize[0] * img_rsz_mltpl,
        #                   imgsize[1] * img_rsz_mltpl))

        # tkimg = ImageTk.PhotoImage(img)
        # label.config(image=tkimg)
        # root.update_idletasks()

    # Resize img
    img = img.resize((imgsize[0] * img_rsz_mltpl,
                      imgsize[1] * img_rsz_mltpl))

    tkimg = ImageTk.PhotoImage(img)
    label.config(image=tkimg)
    root.update_idletasks()
    root.after(stream_loop_delay, stream_loop)


def print_analyse_frame(img):
    real_positions, matching_indices = sim.analyse_frame(img,
                                                         cam_size,
                                                         dbt_log,
                                                         dbt_dpi,
                                                         win_w,
                                                         win_h,
                                                         pipeline_id)
    print(matching_indices)
    print(real_positions)


def main():
    global ser, thr
    # Open serial port
    # ser = serial.Serial("/dev/ttyUSB0", 2000000, timeout=1)
    # ser = serial.Serial("/dev/ttyUSB0", 250000, timeout=1)
    ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=1)

    # Start stream loop and tkinter loop
    stream_loop()
    root.mainloop()

    # close serial port
    ser.close()

    # wait for threads to finish running
    if thr is not None:
        thr.join()


if __name__ == "__main__":
    main()
