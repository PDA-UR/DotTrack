#!/usr/bin/python3
import tkinter
import serial
from PIL import Image, ImageTk

imgsize = [36, 36]
img_byte_len = imgsize[0] * imgsize[1]
img_rsz_mltpl = 10
root = tkinter.Tk()
root.title("DotTrack - Capture Frame Streaming")
root.resizable = False
label = tkinter.Label(root)
label.pack()
ser = None
tkimg = None
# 270+ ms should be around the time it takes to capture another image.
stream_loop_delay = 135


def stream_loop():
    global tkimg
    # Read serial data
    data = ser.read_until(terminator=b"\xFE")
    # Remove terminator byte
    data = data[:-1]
    print(len(data))
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
        print("{} bytes long. Shortened to {}!".format(data_len, len(data)))
    # Fill up bytes
    elif data_len < img_byte_len:
        byte_count = 0
        while len(data) != img_byte_len:
            byte_count += 1
            data += b"\xFF"
        print("Only {} bytes long. Fill up with {} to {}!".format(data_len,
                                                                  byte_count,
                                                                  len(data)))

    # Error out if the length is still not correct
    if len(data) != img_byte_len:
        print("Under {} bytes long ({} bytes). Aborting!".format(img_byte_len,
                                                                 len(data)))
        return

    # Create image
    img = Image.frombytes("L", imgsize, data)

    # Resize img
    img = img.resize((imgsize[0] * img_rsz_mltpl, imgsize[1] * img_rsz_mltpl))

    tkimg = ImageTk.PhotoImage(img)
    label.config(image=tkimg)
    root.update_idletasks()
    root.after(stream_loop_delay, stream_loop)


def main():
    global ser
    # Open serial port
    ser = serial.Serial("/dev/ttyUSB0", 2000000, timeout=1)

    # Start stream loop and tkinter loop
    stream_loop()
    root.mainloop()

    # close serial port
    ser.close()

if __name__ == "__main__":
    main()
