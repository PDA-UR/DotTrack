#include "select.h"

namespace Select {

  bool initialized = false;

  double h = 0;
  double s = 1;
  double v = 1;

  Tools::rgb rgb = Tools::rgb();
  Tools::hsv hsv = Tools::hsv();

void updateSelect(int32_t x, int32_t y){

  if(digitalRead(19) > 0){
    h-=5;
  }
  if(digitalRead(21) > 0){
    s+=0.1;
  }
   if(digitalRead(22) > 0){
    s-=0.1;
  }
  if(digitalRead(3) > 0){
    h+=5;
  }

  if(h < 0 ){ h = 0;}
  if(s < 0 ){ s = 0;}
  if(v < 0 ){ v = 0;}

  if(h > 359 ){ h = 359;}
  if(s > 1 ){ s = 1;}
  if(v > 1 ){ v = 1;}

  hsv.h = h;
  hsv.s = s;
  hsv.v = v;

  rgb = Tools::hsv2rgb(hsv);

  uint16_t color = Tools::get_rgb(rgb);
  
  M5.Lcd.fillScreen(color);
}

void initSelect(){
  if(initialized){return;}
  initialized = true;
  
  pinMode(19, INPUT);
  pinMode(21, INPUT);
  pinMode(22, INPUT);
  pinMode(3, INPUT);
}

}
