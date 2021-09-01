#ifndef __utils__
#define __utils__

#include <M5Stack.h>
#define DEBUG_LEVEL 2

void debug(String message);
void debug2(String message);
void debug3(String message);

class Timer {
    private:
    int lastUpdate;
    int waitTime;

    public:
    Timer(int wait);
    bool tick();
};

#endif
