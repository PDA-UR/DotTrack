import os
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch, mm
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader


def main():
    # Used for testpage PDFs
    # create_png_dpi_examples("output-256x256-4x4.png")

    create_pdf("output-256x256_4x4.png")
    create_pdf("output-8192x4096_5x5.png", (150, 150))


# Set dpi value in the PNG metadata (does not seem to be used by a lot of
# software but inkscape does).
def set_img_dpi(img, fname, dpi):
    # img = Image.open(fname)
    base, ext = os.path.splitext(fname)
    img.save(base+f"_{dpi[0]}x{dpi[1]}dpi"+ext, dpi=dpi)


# Used for testpage.pdf
def create_png_dpi_examples(fname):
    dbt_img = Image.open(fname)
    print(f"dbt_img.mode: {dbt_img.mode}")

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


def create_pdf(fname, dpi=(150, 150), pagesize=A4, margin=(5, 5),
               save_cropped_img=False, max_print_dpi=None):
    """Create a PDF file from a de Bruijn torus image.

    @param fname: File name of the de Bruijn torus image that should be placed
    on the PDF file.
    @type  fname: str

    @param dpi: The dpi with which the de Bruijn torus image should be placed.
    It is a tuple with two elements. The first element holds the dpi on the
    x-axis and the second element the dpi on the y-axis.
    @type  dpi: tuple

    @param pagesize: This is the pagesize of the PDF. It is a tuple with two
    elements (width and height). It uses reportlab unit system therefore you
    should be using the pagesizes of the reportlab library:
    e.g. `from reportlab.lib.pagesizes import A4`.
    @type  pagesize: tuple

    @param margin: This is the margin used to determine the printable area. It
    is a tuple with two elements. The tuple holds the horizontal and vertical
    distance in millimeters from the edge of the paper to the start of the area
    where the printer can start printing. The border is included so better use
    a sensible value at least a little bit greater than the absolute minimum.
    @type  margin: tuple

    @param save_cropped_img: Determines if the cropped image will be saved to
    the filesystem. If the image is not being cropped there will be nothing to
    save.
    @type  save_cropped_img: bool

    @param max_print_dpi: If set it will check and raise a ValueError if the
    printing dpi is below the theoretical minimum (Nyquist-Shannon sampling
    theorem) to accurately print the image. It is a tuple with two elements.
    The tuple holds the horizontal and vertical printer dpi. Does nothing if it
    is not set.
    @type  max_print_dpi: tuple
    """

    # 1. General setup
    out_fname = os.path.splitext(fname)[0] + ".pdf"
    c = canvas.Canvas(out_fname, pagesize=pagesize)

    # Calculate printable area bounds for bounds check
    x_bounds = (margin[0]*mm, pagesize[0] - margin[0]*mm)
    y_bounds = (margin[1]*mm, pagesize[1] - margin[1]*mm)
    # Calculate printable areas width / height
    print_w = x_bounds[1] - x_bounds[0]
    print_h = y_bounds[1] - y_bounds[0]

    # Check if max_print_dpi (when set) is enough to be able to print the
    # patterns / pattern-dpi accurately (at least theoretically; uses the
    # Nyquist-Shannon sampling theorem for estimation).
    if max_print_dpi is not None:
        if max_print_dpi[0] <= dpi[0]*2 or max_print_dpi[1] <= dpi[1]*2:
            raise ValueError("The printers DPI/resolution is too low to" +
                             " print the pattern accurately.")

    # 2. Set image size to the given dpi
    # Get image
    img = Image.open(fname)

    # This should be top left coordinates (because (0, 0) is bottom left) but
    # on/within the printable area.
    x, y = x_bounds[0], y_bounds[1]
    # h is inverted because the PDFs origin is in the bottom left corner and
    # positive values will go up towards the top.
    w, h = (img.size[0]/dpi[0])*inch, -((img.size[1]/dpi[1])*inch)

    # 3. Crop image (if necessary)
    crop_x = w > print_w
    crop_y = h < -print_h
    # Calculate values for the crop operation on the x-axis
    if crop_x:
        # Get number of pixels that fit on the x-axis of the printable area
        px_w = int((print_w / inch) * dpi[0])
        # Set new width for image placement in the pdf
        w = (px_w / dpi[0]) * inch
    # Calculate values for the crop operation on the y-axis
    if crop_y:
        # Get number of pixels that fit on the y-axis of the printable area
        px_h = int((print_h / inch) * dpi[1])
        # Set new height for image placement in the pdf
        h = -((px_h / dpi[1]) * inch)

    # Execute the crop operation
    if crop_x or crop_y:
        left = 0
        top = 0
        if crop_x:
            right = px_w
        else:
            right = img.size[0]
        if crop_y:
            bottom = px_h
        else:
            bottom = img.size[1]
        img = img.crop(box=(left, top, right, bottom))

        # Save the cropped image
        if save_cropped_img:
            fname = os.path.splitext(fname)[0] + "_crop" + ".png"
            img.convert("1").save(fname)

    # TODO: calculate the scaling factor to see that it does not morph the
    # pattern pixels in weird ways.

    # 4. Place image on PDF (within printable area; clip if needed)
    c.drawImage(ImageReader(img), x, y, w, h)

    # 5. Save/Output PDF
    c.showPage()
    c.save()

    # MAYBE: 5. Start print with required settings

    # Print instructions (printing driver settings):
    # * Page Handling > Page Scaling: None
    # * Image Quality > Resolution: 1200x1200 DPI (best use max resolution)


if __name__ == "__main__":
    main()
