import os
import skimage
# import numpy as np
import time
from torus import Torus
from PIL import Image
# from generate_dbt import generate_dbt
# from extract_frame import extract_frame


# in pixel
CAM_RESO = (36, 36)
# in millimeter
CAM_SIZE = (1, 1)


def main():
    # Testing:
    # generate multiple test images
    # run pipeline
    # compare to truth
    dbt_w, dbt_h, win_w, win_h = 256, 256, 4, 4
    fname = generate_dbt(dbt_w, dbt_h, win_w, win_h)
    cam_topleft = (0, 0)
    rot = 0
    subframe = get_test_frame(fname, cam_topleft, CAM_RESO, CAM_SIZE, rot=rot,
                              dbt_dpi_overwrite=(300, 300))
    # subframe.show()
    # subarray = image_to_dbt_subarray(subframe)
    # print(subarray)

    # find_sequences_in_dbt(subarray, fname, win_w, win_h)
    # Testing 2:
    # test with real images

# Image Generation:
# generate_dbt.py
# import os
# from torus import Torus


def generate_dbt(r, s, m, n):
    if r == 256 and s == 256 and m == 4 and n == 4:
        return generate_256x256_4x4_dbt()
    else:
        err_msg = ("Dimensions not supported yet. "
                   "Only 256x256/4x4 supported yet.")
        raise ValueError(err_msg)


def generate_256x256_4x4_dbt():
    fname = "output-256x256-4x4.png"
    values = [
        [0, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0, 1, 1, 1],
        [0, 0, 1, 1, 0, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 1],
        [0, 0, 1, 1, 0, 1, 1, 1, 0, 0, 1, 1, 0, 0, 1, 0],
        [1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1, 1, 0, 1, 1],
    ]
    m, n = 3, 2
    torus = Torus(values, m, n, "storage.txt")
    torus.transpose()
    torus.make()
    torus.make()
    torus.transpose()
    torus.make()
    torus.save(fname)
    return os.path.abspath(fname)


# get_test_frame.py
# from PIL import Image


# for testing the recognition pipeline
def get_test_frame(dbt_fname, cam_topleft, cam_reso, cam_size=(1, 1), rot=0,
                   dbt_dpi_overwrite=None):
    # TODO Make cam_topleft an absolut position in mm or inch. Or allow an
    # offset to test patterns being cut off
    img = Image.open(dbt_fname)

    # Convert size from millimeters to inch
    cam_size_inch = (cam_size[0]*0.039370079, cam_size[1]*0.039370079)

    # Set up DPI value
    dpi = None
    cam_dpi = (int(cam_reso[0]//cam_size_inch[0]),
               int(cam_reso[1]//cam_size_inch[1]))
    # Read out DPI value from PNG metadata.
    for key in img.info:
        if(key == "dpi"):
            dpi = img.info[key]
    if dbt_dpi_overwrite is not None:
        # Set DPI to overwrite value
        dpi = dbt_dpi_overwrite
    if dpi is None:
        # Set DPI to default value (dpi of camera/sensor)
        # TODO: Nyquist as default?? 36 --> (36/2)-1 = 17 --> 17//size
        dpi = cam_dpi

    # Calculate scaling factors & scale accordingly.
    # The ratio_scale variable is required to scale the DBT image to the wanted
    # size and in correct relation to the camera size
    ratio_scale = (int(cam_dpi[0]/dpi[0]), int(cam_dpi[1]/dpi[1]))
    # Resize to set the image size in relation to the camera size
    img = img.resize((img.size[0]*ratio_scale[0], img.size[1]*ratio_scale[1]))

    # To prevent not intended anti aliasing (3 because of Nyquist)
    safety_scale = 3
    img = img.resize((img.size[0]*safety_scale, img.size[1]*safety_scale))

    # TODO Value-/Boundschecks?
    if rot != 0:
        img = img.rotate(-rot,
                         expand=False,
                         center=(cam_topleft[0]*safety_scale,
                                 cam_topleft[1]*safety_scale),
                         translate=(0, 0))
    left, top, right, bottom = (cam_topleft[0],
                                cam_topleft[1],
                                cam_topleft[0]+cam_reso[0],
                                cam_topleft[1]+cam_reso[1])
    img = img.crop(box=(left*safety_scale,
                        top*safety_scale,
                        right*safety_scale,
                        bottom*safety_scale))
    # img.show()
    # TODO Emulate greyscale and randomize the values a bit or smooth the edges
    # of the pattern squares.
    img = img.resize(cam_reso)  # , resample=Image.NEAREST) TODO:filter needed?
    return img


# Image Analysis (extract array out of picture):
def preprocess_image(img):
    # sharpen
    # threshold
    pass


def unrotate_image(img):
    pass


def remove_helper_lines(img):
    pass


def image_to_dbt_subarray(img):
    # Testing code WITHOUT proper pixel accumulation/consolidation
    data = skimage.img_as_ubyte(img)
    return data


# Decode array (and get position):
def find_sequences_in_dbt(frame_array, dbt_fname, m, n):
    start_time = time.perf_counter()

    dbt_img = Image.open(dbt_fname)
    dbt_array = skimage.img_as_ubyte(dbt_img)

    # List comprehension for x, y and dbt_x, dbt_y produces more loops
    # Less looping ==> bit faster
    # Caching the range variables is also a tiny bit faster
    frame_x_range = frame_array.shape[0]-m+1
    frame_y_range = frame_array.shape[1]-n+1
    dbt_x_range = dbt_array.shape[0]-m+1
    dbt_y_range = dbt_array.shape[1]-n+1
    for x in range(frame_x_range):
        for y in range(frame_y_range):
            win = frame_array[x:x+m, y:y+n]
            for dbt_x in range(dbt_x_range):
                for dbt_y in range(dbt_y_range):
                    # np.array_equal() is slower (rather big difference)
                    if (win == dbt_array[dbt_x:dbt_x+m, dbt_y:dbt_y+n]).all():
                        print(dbt_x, dbt_y)

    total_time = time.perf_counter() - start_time
    print(f"Brute force lookup of",
          f"{frame_array.shape[0]}x{frame_array.shape[1]} subarray in",
          f"{dbt_array.shape[0]}x{dbt_array.shape[1]} DBT with {m}x{n} window",
          f"size took {total_time:.3f}s")


if __name__ == "__main__":
    main()
