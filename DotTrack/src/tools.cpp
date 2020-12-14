#include "tools.hpp"

namespace Tools {

  // rgb to hsv code by https://stackoverflow.com/questions/3018313/algorithm-to-convert-rgb-to-hsv-and-hsv-to-rgb-in-range-0-255-for-both

hsv rgb2hsv(rgb in)
{
    hsv         out;
    double      min, max, delta;

    min = in.r < in.g ? in.r : in.g;
    min = min  < in.b ? min  : in.b;

    max = in.r > in.g ? in.r : in.g;
    max = max  > in.b ? max  : in.b;

    out.v = max;                                // v
    delta = max - min;
    if (delta < 0.00001)
    {
        out.s = 0;
        out.h = 0; // undefined, maybe nan?
        return out;
    }
    if( max > 0.0 ) { // NOTE: if Max is == 0, this divide would cause a crash
        out.s = (delta / max);                  // s
    } else {
        // if max is 0, then r = g = b = 0              
        // s = 0, h is undefined
        out.s = 0.0;
        out.h = 0;                            // its now undefined TODO: was NaN
        return out;
    }
    if( in.r >= max )                           // > is bogus, just keeps compilor happy
        out.h = ( in.g - in.b ) / delta;        // between yellow & magenta
    else
    if( in.g >= max )
        out.h = 2.0 + ( in.b - in.r ) / delta;  // between cyan & yellow
    else
        out.h = 4.0 + ( in.r - in.g ) / delta;  // between magenta & cyan

    out.h *= 60.0;                              // degrees

    if( out.h < 0.0 )
        out.h += 360.0;

    return out;
}


rgb hsv2rgb(hsv in)
{
    double      hh, p, q, t, ff;
    long        i;
    rgb         out;

    if(in.s <= 0.0) {       // < is bogus, just shuts up warnings
        out.r = in.v;
        out.g = in.v;
        out.b = in.v;
        return out;
    }
    hh = in.h;
    if(hh >= 360.0) hh = 0.0;
    hh /= 60.0;
    i = (long)hh;
    ff = hh - i;
    p = in.v * (1.0 - in.s);
    q = in.v * (1.0 - (in.s * ff));
    t = in.v * (1.0 - (in.s * (1.0 - ff)));

    switch(i) {
    case 0:
        out.r = in.v;
        out.g = t;
        out.b = p;
        break;
    case 1:
        out.r = q;
        out.g = in.v;
        out.b = p;
        break;
    case 2:
        out.r = p;
        out.g = in.v;
        out.b = t;
        break;

    case 3:
        out.r = p;
        out.g = q;
        out.b = in.v;
        break;
    case 4:
        out.r = t;
        out.g = p;
        out.b = in.v;
        break;
    case 5:
    default:
        out.r = in.v;
        out.g = p;
        out.b = q;
        break;
    }
    return out;     
}

uint16_t get_rgb(rgb in){
  double r = in.r;
  double g = in.g;
  double b = in.b;

  uint16_t red = r * 0b00010000;
  uint16_t green = g * 0b00100000;
  uint16_t blue = b * 0b00010000;
  uint16_t color_16 = (red << 11) | (green << 5) | blue;
  return color_16;
}

uint16_t get16from8(uint8_t color){
  uint8_t red = color >> 5;
  uint8_t green = (color << 3) >> 5;
  uint8_t blue = (color << 6) >> 6;
  uint8_t red_16 = red << 2; // from 3bit to 5 bit
  uint8_t green_16 = green << 3; // from 3bit to 6 bit
  uint8_t blue_16 = blue << 3; // from 2bit to 5 bit
  uint16_t color_16 = (red_16 << 11) | (green_16 << 5) | blue_16;
  return color_16;
}

  void pushOnBuffer(uint8_t element, uint8_t* buffer, int buf_len)
  {
    for(auto i = buf_len - 1; i > 0; i--)
    {
      buffer[i] = buffer[i - 1];
    }
    buffer[0] = element;
  }
}

