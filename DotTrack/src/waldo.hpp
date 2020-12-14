#ifndef __waldo__
#define __waldo__

#include <M5Stack.h>
#include "tools.hpp"

namespace Waldo {

void setNewPosition(int16_t x, int16_t y);

void updateWaldo(TFT_eSprite img, int32_t x, int32_t y);

void initWaldo();

uint16_t get16from8(uint8_t color);

}

#endif

