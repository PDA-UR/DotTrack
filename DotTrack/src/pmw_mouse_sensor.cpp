#include "pmw_mouse_sensor.hpp"

//unsigned long t_switch;
//unsigned long comTimer;

Timer screenUpdateTimer = Timer(100);

double relative_x = 0.0;
double relative_y = 0.0;
float last_x = 0;
float last_y = 0;
bool receiving = false;

bool frameCapture;

void setup()
{
    // Initialize the M5Stack object
    M5.begin();

    Serial.begin(115200);

    // Needed for M5Stack-SD-Updater
    Wire.begin();

    // Turn off/disconnect speaker
    // Source: https://twitter.com/Kongduino/status/980466157701423104
    M5.Speaker.end();
    debug2("speaker ok");

    // Set Brightness of M5Stack LCD display
    M5.Lcd.setBrightness(0xff);

    // Setup and use sprite object (frame buffer) to prevent flicker:
    // Because of RAM limitations it can only have a 8bit color depth
    //img.setColorDepth(8);
    //img.createSprite(W_DISP, H_DISP);

    debug2("setup()");

    // setup pins
    pinMode(PIN_NCS, OUTPUT);
    /*pinMode(PIN_MOTION, INPUT); // maybe INPUT_PULLUP is better?*/
    /*// > The motion pin is an active low output (datasheet p.18)*/
    /*digitalWrite(PIN_MOTION, HIGH);*/
    pinMode(PIN_SCLK, OUTPUT);
    pinMode(PIN_MISO, INPUT);
    pinMode(PIN_MOSI, OUTPUT);
    /*attachInterrupt(digitalPinToInterrupt(PIN_MOTION), onMovement, FALLING);*/

    debug2("pins initialized");

    // Initialize the SPI object
    SPI.begin();
    // SCLK when running on 2MHz / SPI.setFrequency(2000000L):
    // One bit should take 500ns
    // One byte should take 8*500ns = 4µs
    // Two bytes should take 16*500ns = 8µs
    /*SPI.beginTransaction(SPISettings(F_SCLK, MSBFIRST, SPI_MODE3));*/

    debug2("SPI initialized");

    // Initialize PMW3360 - Power up/startup sequence (see p. 26 of datasheet)

    // Delay to wait for NCS not to be ignored (see table on p. 26)
    delay(100); // Max VDD-VDDIO power up delay

    resetSPIPort();

    resetDevice();

    performSROMdownload();

    // TODO Configure registers (write to config registers)
    configureRegisters();

    debug2("reset device done");

    // Reads configurations from registers
    readConfigRegisters();

    ConnectToWiFi();
    ConnectToServer();

    //screenUpdateTimer = Timer(100);
    debug2("startup done");

    delay(250);
}

void loop()
{
    // IMG_CAPTURE APP
    debug3("IMG_CAPTURE");

    //sendRawOverSerial();
    if(!receiving)
    {
        captureRawImage(rawData, rawDataLength);
        sendRawOverWifi();
        receiving = true;
    }

    float x = last_x;
    float y = last_y;

    if(client.available())
    {
        String buf = client.readStringUntil(';');

        for(int i = 0; i < buf.length(); i++)
        {
            if(buf[i] == '|')
            {
                // we send values between 0 and 10000 and convert them to a 0.0 to 1.0 range
                x = (buf.substring(0, i).toInt() / 10000.0f) * W_DISP;
                y = (buf.substring(i+1, buf.length()).toInt() / 10000.0f) * H_DISP;
                if(x != last_x && y != last_y)
                {
                    relative_x = 0;
                    relative_y = 0;
                }
                last_x = x;
                last_y = y;
                break;
            }
        }
        receiving = false;
    }

    readMotionBurst(rawMotBr, motBrLength);
    updateMotBrValues();

    if(screenUpdateTimer.tick())
    {
        drawImageToDisplay();
        drawDirection();
        drawRelativePosition();

        drawCoordinates(x, y);
    }

    //M5.update();
    //delay(100);
    return;
}

void drawImageToDisplay()
{
    M5.Lcd.fillRect(0, 0, W_DISP, H_DISP, BLACK);
    // Draw raw data image data to M5Stack display
    for(int32_t x = 0; x < W_IMG; x++)
    {
        for(int32_t y = 0; y < H_IMG; y++)
        {
            // Read pixel data (multiply by 2 because the raw data values are between 0 and 127)
            uint8_t pixel = rawData[x*H_IMG+y] << 1;
            // Color needs to be encoded in 5,6,5 RGB bit format (16 bit)
            uint32_t color = (pixel >> 3) << 11 | (pixel >> 2) << 5 | (pixel >> 3);
            // Resize image pixel to use 6x6 rectangles
            // INFO: x needs to be inverted to correlate with the displays x-/y-coordinates
            // fillRect(int32_t x, int32_t y, int32_t w, int32_t h, uint32_t color)
            M5.Lcd.fillRect((W_IMG-x)*PIX_RSZ + X_OFFSET, y*PIX_RSZ + Y_OFFSET, PIX_RSZ, PIX_RSZ, color);
        }
    }
}

void drawCoordinates(float x, float y)
{
    Serial.println("Coordinates:");
    Serial.println(x);
    Serial.println(y);
    Serial.println("----------");
    //int x = rel_x * W_DISP;
    //int y = rel_y * H_DISP;
    //M5.Lcd.fillRect(0, 0, W_DISP, H_DISP, WHITE);
    M5.Lcd.fillRect(x-2, y-2, 4, 4, RED);
}

void drawDirection()
{
    if(!liftOff)
    {
        //Serial.println("Direction:");
        //Serial.println(xyDelta[0]);
        //Serial.println(xyDelta[1]);
        //Serial.println("----------");

        if(xyDelta[0] == 0 && xyDelta[1] == 0) return;
        int x = xyDelta[0] < 0 ? W_DISP - 10 : 10;
        int y = xyDelta[1] < 0 ? H_DISP - 10 : 10;
        if(xyDelta[0] == 0) x = W_DISP / 2;
        if(xyDelta[1] == 0) y = H_DISP / 2;
        M5.Lcd.fillRect(x, y, 4, 4, GREEN);
    }
    //else
    //{
    //    Serial.println("LiftOff!");
    //}
}

void drawRelativePosition()
{
    double rel_x = (relative_x / cpi) * 25.4;
    double rel_y = (relative_y / cpi) * 25.4;

    int rel_x_px = (rel_x / A4_WIDTH) * W_DISP;
    int rel_y_px = (rel_y / A4_HEIGHT) * H_DISP;

    int x = last_x + (2 * rel_x_px);
    int y = last_y + (2 * rel_y_px);

    Serial.println("Relative:");
    //Serial.println(relative_x);
    //Serial.println(relative_y);
    //Serial.println(rel_x);
    //Serial.println(rel_y);
    Serial.println(rel_x_px);
    Serial.println(rel_y_px);
    //Serial.println(x);
    //Serial.println(y);
    Serial.println("----------");

    M5.Lcd.fillRect(x-2, y-2, 4, 4, BLUE);
}
