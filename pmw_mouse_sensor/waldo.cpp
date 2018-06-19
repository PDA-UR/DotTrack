#include "waldo.h"
#include "wimmel.h"

int16_t counter_waldo = 0;
int scale = 4;
uint32_t count = 3;

int16_t x_pos = 50;
int16_t y_pos = 50;

bool initialized = false;

uint16_t bitmap[320*240/2];

auto IMAGE_SIZE = sizeof(wimmel_pixel_map);

void updateWaldo(int32_t x, int32_t y)
{
  initWaldo();

  

  if(digitalRead(19) > 0){
    y+=7;
  }
  if(digitalRead(21) > 0){
    x+=3;
  }
   if(digitalRead(22) > 0){
    x-=3;
  }
  if(digitalRead(3) > 0){
    y-=7;
  }
  x_pos += x;
  y_pos += y;

  for(auto i = 0; i < 120; ++i){
      for(auto t = 0; t < 320; t+=1){
        auto pos = x_pos+t/scale+((i+y_pos)/scale)*1000;
        if (pos >= IMAGE_SIZE){
          pos = 0;
        }
        if(pos < 0){
          pos = 0;
        }
        uint8_t pixel = wimmel_pixel_map[pos];
        uint16_t color = get16from8(pixel);
        bitmap[320*i+t] = color;
      }
  }
  M5.Lcd.drawBitmap(0, 0, 320, 120,bitmap);
  for(auto i = 0; i < 120; ++i){
      for(auto t = 0; t < 320; t+=1){
        auto pos = x_pos+t/scale+((i+y_pos+120)/scale)*1000;
        if (pos >= IMAGE_SIZE){
          pos = 0;
        }
        if(pos < 0){
          pos = 0;
        }
        uint8_t pixel = wimmel_pixel_map[pos];
        bitmap[320*i+t] = get16from8(pixel);
        }
  }
  M5.Lcd.drawBitmap(0, 120, 320, 120,bitmap);

  count+=2;
}

void initWaldo()
{
  if(initialized){return;}
  initialized = true;
  
  pinMode(19, INPUT);
  pinMode(21, INPUT);
  pinMode(22, INPUT);
  pinMode(3, INPUT);
  
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

