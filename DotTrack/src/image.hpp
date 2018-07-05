#ifndef __image__
#define __image__

#include <M5Stack.h>

namespace Image {
  extern uint16_t bitmap[38400];
  void draw(const uint8_t image[]);

  
}


#endif

