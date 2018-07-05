#include "simulator.hpp"

namespace Simulator {
    bool initialized = false;
    
  int16_t x = 0;
  int16_t y = 0;
  
  void update(){
    init();
      x = 0;
      y = 0;

      if(digitalRead(19) > 0){
        y = 1;
      }
      if(digitalRead(21) > 0){
        x = 1;
      }
       if(digitalRead(22) > 0){
        x = -1;
      }
      if(digitalRead(3) > 0){
        y = -1;
      }
  }

  void init(){
    if(initialized){return;}
    initialized = true;

    pinMode(19, INPUT);
    pinMode(21, INPUT);
    pinMode(22, INPUT);
    pinMode(3, INPUT);
  }
  
  int16_t get_x(){return x;}
  int16_t get_y(){return y;}
}
