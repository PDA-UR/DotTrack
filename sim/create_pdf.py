import os
import skimage
# import numpy as np
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch, mm
from reportlab.lib.pagesizes import A4


def main():
    # Used for testpage PDFs
    create_png_dpi_examples("output-256x256-4x4.png")

    # create_pdf("output-256x256-4x4.png", (36, 36), (1, 1), A4, (5, 5),
    #            (1200, 1200))


# Set dpi value in the PNG metadata (does not seem to be used by a lot of
# software but inkscape does).
def set_img_dpi(img, fname, dpi):
    # img = Image.open(fname)
    base, ext = os.path.splitext(fname)
    img.save(base+f"_{dpi[0]}x{dpi[1]}dpi"+ext, dpi=dpi)


# Used for testpage.pdf
def create_png_dpi_examples(fname):
    dbt_img = Image.open(fname)

    # Camera resolution in pixel.
    cam_reso = (36, 36)
    # Camera capture area in millimeters.
    cam_size = (1, 1)
    # Convert size from millimeters to inch.
    cam_size_inch = (cam_size[0]*0.039370079, cam_size[1]*0.039370079)

    num_ppx_threshold = (5, 5)
    # num_ppx_sample = []
    for num_ppx in range(num_ppx_threshold[0], int(cam_reso[0]/3 + 1)):
        dpi = (int(1 / (cam_size_inch[0] / num_ppx)),
               int(1 / (cam_size_inch[1] / num_ppx)))
        set_img_dpi(dbt_img, fname, dpi)


def create_pdf(dbt_fname="output-256x256-4x4.png", sensor_reso=(36, 36),
               capture_area=(1, 1), pagesize=A4, printable_area=(5, 5),
               max_print_dpi=(1200, 1200)):
    # Variables:
    # dbt_fname = "output-256x256-4x4.png"  # file name of de Bruijn torus
    # image (with a 1:1 dot-pixel-ratio) that should be placed on the pdf
    # sensor_reso = (36, 36)  # (w, h) of sensor image in pixel (resolution)
    # capture_area = (1mm, 1mm)  # (w, h) of captured area in millimeters
    # pagesize = A4  # pagesize of the output PDF (use reportlab.lib.pagesizes;
    # the short edge seems to be always the first element of the tuple ->
    # portrait orientation is assumed)
    # printable_area = (5mm, 5mm)  # (horizontal, vertical) distance in
    # millimeters from the edge of the paper to the start of the area where the
    # printer can start printing. The border is included so better use a
    # sensible value at least a little bit greater than the absolute minimum.
    # MAYBE: max_print_dpi = (1200, 1200)  # (horizontal, vertical) printer dpi
    # from edge to printable area in millimeters
    # Print instructions (printing driver settings):
    # * Page Handling > Page Scaling: None
    # * Image Quality > Resolution: 1200x1200 DPI (best use max resolution)

    # 0. General setup
    out_fname = os.path.splitext(dbt_fname)[0] + ".pdf"
    c = canvas.Canvas(out_fname, pagesize=pagesize)

    # 1. Calculate pattern-pixel-DPI
    # Calculate effective/readable pixels with the Nyquist-Shannon sampling
    # theorem (for practical reasons we try not to completely max out the
    # theoretical sample rate but be save and divide by 3).
    nyq_reso = (sensor_reso[0]/3, sensor_reso[1]/3)
    # Convert capture_area to inch.
    capture_area = (capture_area[0]*0.03937008, capture_area[1]*0.03937008)
    # Calculate pattern-pixel-DPI.
    # Use p_dpi to check that the pattern/image dpi/density is not to big but
    # still close to that density.
    p_dpi = (1/(capture_area[0]/nyq_reso[0]), 1/(capture_area[1]/nyq_reso[1]))
    # Check if max_print_dpi is enough to be able to print the patterns /
    # pattern-dpi accurately (also uses the Nyquist-Shannon sampling theorem).
    if max_print_dpi[0] <= p_dpi[0]*2 or max_print_dpi[1] <= p_dpi[1]*2:
        raise ValueError(("The printers DPI/resolution is to low to print the",
                          "pattern accurately."))

    # 2. Set image size to that DPI (check if printer dpi can handle this)
    # Get image
    dbt_img = Image.open(dbt_fname)
    # Get image size
    dbt_img_size = dbt_img.size
    # Calculate printable area bounds for bounds check
    pa_x_bounds = (printable_area[0]*mm, pagesize[0] - printable_area[0]*mm)
    pa_y_bounds = (printable_area[1]*mm, pagesize[1] - printable_area[1]*mm)

    # This should be top left coordinates (because (0, 0) is bottom left) but
    # on/within the printable area.
    x, y = pa_x_bounds[0], pa_y_bounds[1]
    # h is inverted because the PDFs origin is in the bottom left corner and
    # positive values will go up towards the top.
    w, h = (dbt_img_size[0]/p_dpi[0])*inch, -(dbt_img_size[1]/p_dpi[1])*inch
    # TODO/FIXME/URGENT: Make bounds check and crop image accordingly
    # x+w, y-h
    # TODO: calculate the scaling factor to see that it does not morph the
    # pattern pixels in weird ways.

    # 3. Place image on PDF (within printable area; clip if needed)
    c.drawImage(dbt_fname, x, y, w, h)

    # 4. Output PDF
    c.showPage()
    c.save()

    # MAYBE: 5. Start print with required settings


# ===============================================================================
# # TODO: def create_image(pattern, dpi):
# # Consts
# GS_WHITE = 255  # white in greyscale
# GS_BLACK = 0  # black in greyscale
# # Variables
# out_file_png = "test.png"
# out_file_pdf = "test.pdf"
# out_format = "PNG"
# mode = "L"  # "L": 8bit B/W Colors (for EPS) "1": 1bit B/W (for BMP, PPM)
# bg_color = "white"  # default: "black"
# fill_color = "black"
# # TODO base img_size on sequence matrix
# img_size = (16, 16)  # number of pixels on (x, y)
# w, h = img_size
# dpi = (500, 500)  # dpi is basically pixels per inch

# data = np.zeros((h, w), dtype=np.uint8)
# for i in range(0, w, 2):
#     data[i, i] = GS_WHITE
# img = Image.fromarray(data, mode)
# img.save(out_file_png, format=out_format, dpi=dpi)
# img.show()


# c = canvas.Canvas(out_file_pdf, pagesize=A4)
# # use image from testarray (data)
# pdf_x, pdf_y = 350, 400  # (0, 0) is bottom left
# pdf_img_w, pdf_img_h = w, h  # 8, 8
# c.drawImage(out_file_png, pdf_x, pdf_y, pdf_img_w, pdf_img_h,
#             preserveAspectRatio=True, anchor="nw")
# # The showPage method finishes the current page. All additional drawing will
# # be done on another page.
# c.showPage()
# c.save()
# ===============================================================================

# ===============================================================================
# out_file_pdf = "test.pdf"
# c = canvas.Canvas(out_file_pdf, pagesize=A4)
# # use image from DBT-repo (output-5x5.png)
# pdf_x, pdf_y = 0, 0  # (0, 0) is bottom left
# pdf_img_w, pdf_img_h = 8192, 4096  # 8, 8


# # If results are not multiples of the input w, h it might scale the pixels
# # weirdly so maybe just stick to multiples (e.g. half or double size)
# def scale(w, h, scaler):
#     w *= scaler
#     h *= scaler
#     return int(w), int(h)


# scaler = 1  # .5 scale down/half pixel size; 2 scale up/double pixel size
# pdf_img_w, pdf_img_h = scale(pdf_img_w, pdf_img_h, scaler)
# out_file_png = "output-5x5.png"
# c.drawImage(out_file_png, pdf_x, pdf_y, pdf_img_w, pdf_img_h)
# c.showPage()
# c.save()
# ===============================================================================

# Multiplier
# multiplier = 1  # ~6x6mm should grow to ~12x12cm
# img_size = img_size[0] * multiplier, img_size[1] * multiplier

# sequence = []
# sequence.append((1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0)*multiplier)
# sequence.append((1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0)*multiplier)
# sequence.append((1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0)*multiplier)
# sequence.append((1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0)*multiplier)
# sequence.append((1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0)*multiplier)
# sequence.append((0, 0, 0, 0, 1, 1, 1, 1, 0, 1, 1, 0, 0, 1, 0, 1)*multiplier)
# sequence.append((1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0)*multiplier)
# sequence.append((0, 0, 0, 0, 1, 1, 1, 1, 0, 1, 1, 0, 0, 1, 0, 1)*multiplier)
# sequence.append((1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0)*multiplier)
# sequence.append((1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0)*multiplier)
# sequence.append((0, 0, 0, 0, 1, 1, 1, 1, 0, 1, 1, 0, 0, 1, 0, 1)*multiplier)
# sequence.append((1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0)*multiplier)
# sequence.append((1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0)*multiplier)
# sequence.append((1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0)*multiplier)
# sequence.append((0, 0, 0, 0, 1, 1, 1, 1, 0, 1, 1, 0, 0, 1, 0, 1)*multiplier)
# sequence.append((0, 0, 0, 0, 1, 1, 1, 1, 0, 1, 1, 0, 0, 1, 0, 1)*multiplier)
# sequence *= multiplier

# """
# (T, T, T, T, F, F, F, F, T, F, F, T, T, F, T, F)
# (T, T, T, T, F, F, F, F, T, F, F, T, T, F, T, F)
# (T, T, T, T, F, F, F, F, T, F, F, T, T, F, T, F)
# (T, T, T, T, F, F, F, F, T, F, F, T, T, F, T, F)
# (T, T, T, T, F, F, F, F, T, F, F, T, T, F, T, F)
# (F, F, F, F, T, T, T, T, F, T, T, F, F, T, F, T)
# (T, T, T, T, F, F, F, F, T, F, F, T, T, F, T, F)
# (F, F, F, F, T, T, T, T, F, T, T, F, F, T, F, T)
# (T, T, T, T, F, F, F, F, T, F, F, T, T, F, T, F)
# (T, T, T, T, F, F, F, F, T, F, F, T, T, F, T, F)
# (F, F, F, F, T, T, T, T, F, T, T, F, F, T, F, T)
# (T, T, T, T, F, F, F, F, T, F, F, T, T, F, T, F)
# (T, T, T, T, F, F, F, F, T, F, F, T, T, F, T, F)
# (T, T, T, T, F, F, F, F, T, F, F, T, T, F, T, F)
# (F, F, F, F, T, T, T, T, F, T, T, F, F, T, F, T)
# (F, F, F, F, T, T, T, T, F, T, T, F, F, T, F, T)
# """


# # Create image and drawable image
# img = Image.new(mode, img_size, bg_color)
# draw = ImageDraw.Draw(img)

# # Draw sequence matrix
# for i in range(len(sequence)):
#     for j in range(len(sequence[i])):
#         if sequence[i][j] == 1:
#             # Without multiplier
#             draw.rectangle([(i, j), (i, j)], fill=fill_color)
#             # With multiplier
#             # for m in range(1, multiplier+1):
#                 # draw.rectangle([(i*m, j), (i*m, j)], fill=fill_color)


# img.save(out_file, format=out_format, dpi=dpi)
# img.show()

if __name__ == "__main__":
    main()
