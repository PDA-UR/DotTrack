import os
import skimage
# import numpy as np
import time
from torus import Torus
from PIL import Image


def main():
    # Testing:
    # generate multiple test images
    # run pipeline
    # compare to truth
    dbt_w, dbt_h, win_w, win_h = 256, 256, 4, 4
    fname = generate_dbt(dbt_w, dbt_h, win_w, win_h)
    sf_x, sf_y, sf_w, sf_h = 127, 127, 10, 10
    rot = 0
    subframe = get_test_frame(fname, sf_x, sf_y, sf_w, sf_h, rot)
    subframe.show()
    subarray = image_to_dbt_subarray(subframe)
    # print(subarray)

    find_sequences_in_dbt(subarray, fname, win_w, win_h)
    # Testing 2:
    # test with real images


# Image Generation:
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


# for testing the recognition pipeline
def get_test_frame(fname, x, y, w, h, rot=0, scale=1):
    img = Image.open(fname)
    # TODO Value-/Boundschecks
    rot_scale = 1
    if rot != 0:
        rot_scale = 3  # TODO: what scaling is proper (emulates DPI best)
        w, h = img.size
        img = img.resize((w * rot_scale, h * rot_scale))
        # img.show()
        img = img.rotate(-rot, expand=False, center=(x*rot_scale, y*rot_scale),
                         translate=(0, 0))
        # img.show()
    left, upper, right, lower = x, y, x+w, y+h
    img = img.crop(box=(left*rot_scale,
                        upper*rot_scale,
                        right*rot_scale,
                        lower*rot_scale))
    # TODO scale back down when image was rotated
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
