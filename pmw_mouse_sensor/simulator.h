#ifndef __simulator__
#define __simulator__

#include <M5Stack.h>

namespace Simulator {
  void update();
  void init();

  int16_t get_x();
  int16_t get_y();
}

#endif
