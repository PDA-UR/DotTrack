#include "utils.hpp"

void debug(String message){
    if (DEBUG_LEVEL >= 1){
        Serial.println(message);
    }
}

void debug2(String message){
    if (DEBUG_LEVEL >= 2){
        Serial.println(message);
    }
}

void debug3(String message){
    if (DEBUG_LEVEL >= 3){
        Serial.println(message);
    }
}

Timer::Timer(int wait)
{
    lastUpdate = 0;
    waitTime = wait;
}

bool Timer::tick()
{
    int currentTime = millis();
    if(currentTime - lastUpdate >= waitTime)
    {
        lastUpdate = currentTime;
        return true;
    }
    else
    {
        return false;
    }
}
