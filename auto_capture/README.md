# Auto Capture

Code for the [AxiDraw V3](https://shop.evilmadscientist.com/productsmenu/846) robotic arm which was used to capture an evaluation data set by moving the mouse sensor over the pattern step by step and saving raw images.

 * ```ebb_motion.py```, ```ebb_serial.py``` and ```inkex.py```: Required libraries for the AxiDraw.
 * ```demo.py```: Moves the AxiDraw in a rectangular shape. Can be used to see if everything works.
 * ```auto_capture.py```: Legacy version of the image capturing code.
 * ```generate_dataset.py```: Current version of the image capturing code. Align the AxiDraw (holding the mouse sensor) with the (0, 0) corner of a DBT section printed on A4 paper and run this program. It will record and save raw sensor images. Actual coordinates are saved in the file names.
