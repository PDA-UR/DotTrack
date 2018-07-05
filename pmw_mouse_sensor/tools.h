#ifndef __tools__
#define __tools__

#include <M5Stack.h>

namespace Tools {

// rgb to hsv code by https://stackoverflow.com/questions/3018313/algorithm-to-convert-rgb-to-hsv-and-hsv-to-rgb-in-range-0-255-for-both
struct rgb{
    double r;       // a fraction between 0 and 1
    double g;       // a fraction between 0 and 1
    double b;       // a fraction between 0 and 1
};

struct hsv {
    double h;       // angle in degrees
    double s;       // a fraction between 0 and 1
    double v;       // a fraction between 0 and 1
};

hsv rgb2hsv(rgb in);
rgb hsv2rgb(hsv in);

uint16_t get_rgb(rgb in);

uint16_t get16from8(uint8_t color);

void pushOnBuffer(uint8_t element, uint8_t* buffer, int buf_len);
}

#endif
