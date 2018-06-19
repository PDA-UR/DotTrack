#ifndef __waldo__
#define __waldo__

#include <M5Stack.h>

void updateWaldo(int16_t x, int16_t y);

void initWaldo();

uint16_t get16from8(uint8_t color);

#endif

