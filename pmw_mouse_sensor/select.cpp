#include "select.h"

namespace Select {

  bool initialized = false;

  double h = 0;
  double s = 1;
  double v = 1;

  char c = 'A';
  char num = '0';

  Tools::rgb rgb = Tools::rgb();
  Tools::hsv hsv = Tools::hsv();

  Tools::rgb rgb_text = Tools::rgb();
  Tools::hsv hsv_text = Tools::hsv();

void updateSelect(int32_t x, int32_t y){

  c += x;
  h += x*5;

  num += y;
  s += y * 0.05;

  if(h < 0 ){ h += 359;}
  if(s < 0 ){ s = 0;}
  if(v < 0 ){ v = 0;}

  if(h > 359 ){ h -= 359;}
  if(s > 1 ){ s = 1;}
  if(v > 1 ){ v = 1;}

  hsv.h = h;
  hsv.s = s;
  hsv.v = v;

  double text_h = h + 180;
  if(text_h < 0 ){ text_h += 359;}
  if(text_h > 359 ){ text_h -= 359;}

  double text_s = 1 - s;

  hsv_text.h = text_h;
  hsv_text.s = text_s;
  hsv_text.v = v;

  rgb = Tools::hsv2rgb(hsv);

  rgb_text = Tools::hsv2rgb(hsv_text);

  uint16_t color = Tools::get_rgb(rgb);

  uint16_t color_text = Tools::get_rgb(rgb_text);
  
  M5.Lcd.fillScreen(color);

  M5.Lcd.drawChar(10, 50,c, color_text,color,20);
  M5.Lcd.drawChar(120, 50,num, color_text,color,20);
}

void initSelect(){
  if(initialized){return;}
  initialized = true;
}

}
