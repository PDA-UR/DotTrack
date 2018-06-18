#include "waldo.h"
#include "cat.h"

int16_t counter_waldo = 0;
int scale = 1;
int count = 0;

uint8_t bitmap[320*240];// = new uint16_t[76800];

void updateWaldo(int16_t x_pos, int16_t y_pos)
{
  /*
  x_pos += counter_waldo;
  counter_waldo+=5;
  //M5.Lcd.fillScreen(GREEN);
  for(auto x = 0; x < 320; x+=scale){
    for(auto y = 0; y < 240; y+=scale){
      for(auto x_scale = 0; x_scale < scale; ++x_scale){
        for(auto y_scale = 0; y_scale < scale; ++y_scale){
          M5.Lcd.drawPixel(x+x_scale, y+y_scale, cat_pixel_map[(x/scale+x_pos)+(y/scale+y_pos)*500]);
        }
      }
    }
  }
  */
  for(auto i = 0; i < 240/2; ++i){
    memmove(bitmap + i*320 * sizeof(uint16_t),cat_pixel_map + i*1000 * sizeof(uint16_t) + count * sizeof(uint16_t),320 * sizeof(uint16_t));
  }
  M5.Lcd.drawBitmap(0, 0, 320, 120,bitmap);
  /*
  for(auto i = 0; i < 120; ++i){
    memmove(bitmap + (i+120)*320 * sizeof(uint16_t),cat_pixel_map + i*1000 * sizeof(uint16_t) + count * sizeof(uint16_t),320 * sizeof(uint16_t));
  }
  M5.Lcd.drawBitmap(120, 0, 320, 120,bitmap); 
*/
  count++;
}

/*
 * 
 * int array1[10] = {0,1,2,3,4,5,6,7,8,9};
int array2[5] = {0,0,0,0,0};

memmove(array2, array1 + 5 * sizeof(int), 5 * sizeof(int));
 * 
 */

void initWaldo()
{
  
}

