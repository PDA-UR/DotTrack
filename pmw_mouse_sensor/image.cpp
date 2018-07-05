#include "image.h"
#include "tools.h"

namespace Image {
  uint16_t bitmap[38400];
  
  void draw(const uint8_t image[]){
    for(auto i = 0; i < 120; ++i){
      for(auto t = 0; t < 320; t+=1){
        auto pos = t+i*320;
        uint8_t pixel = image[pos];
        uint16_t color = Tools::get16from8(pixel);
        bitmap[pos] = color;
      }
  }
  M5.Lcd.drawBitmap(0, 0, 320, 120,bitmap);
  for(auto i = 0; i < 120; ++i){
      for(auto t = 0; t < 320; t+=1){
        auto pos = t+(i+120)*320;
        uint8_t pixel = image[pos];
        bitmap[320*i+t] = Tools::get16from8(pixel);
        }
  }
  M5.Lcd.drawBitmap(0, 120, 320, 120,bitmap);
  }
}

