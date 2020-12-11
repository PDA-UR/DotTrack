# Contents

 * ```img2pos.py``` Debug view application. This is a good starting point if you want to get to know the system or write your own applications. Contains a class wrapping all current functions of the microcontroller.
 * ```dottrack.py``` Contains all the image preprocessing and binarization steps, as well as a lot of configuration parameters. Normally, you only include its ```get_coords()``` function and you're good to go.
 * ```decode_dbt.py``` Functions to search for a subpattern in a De-Bruijn torus.

# Usage

Change the IP address in ```img2pos.py``` to the IP address of the computer you want to run the program on.
If the M5Stacks are set up and running the code in the "../DotTrack" subdirectory, you are good to go.
