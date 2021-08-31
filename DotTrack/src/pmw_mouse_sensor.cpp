#include "pmw_mouse_sensor.hpp"

#define MODE_EYE 0
#define MODE_RAW 1
#define MODE_WALDO 0
#define MODE_STREAM 0 // don't send coordinates, otherwise like raw mode

Timer screenUpdateTimer = Timer(20);
Timer coordUpdateTimer = Timer(20);

extern TFT_eSprite img = TFT_eSprite(&M5.Lcd);
double relative_x = 0.0;
double relative_y = 0.0;
float last_x = 0;
float last_y = 0;
float last_x_rel = 0;
float last_y_rel = 0;
int angle = 0;
bool receiving = false;
int eyeAngle = 0;
int distance = 0;

bool frameCapture;

bool wasLiftOff = false;

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

    debug2("setup()");

    // setup pins
    pinMode(PIN_NCS, OUTPUT);
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

    // we can decide between using the whole screen OR 16 bit colors
    // therefore we use 8 bit for waldo and googly eyes
    // and 16 bit crop for raw image
    if(!MODE_RAW && !MODE_STREAM){
        img.setColorDepth(8);
        img.createSprite(W_DISP, H_DISP);
    }
    else
    {
        img.createSprite(W_WINDOW, H_WINDOW);
    }

    ConnectToWiFi();
    GetPorts();
    ConnectToServer();

    debug2("startup done");

    delay(250);
}

void decodeWifiAnswer(String str)
{
    if(MODE_STREAM) return;

    float x = last_x;
    float y = last_y;

    int lastSubstringPosition = 0;
    int counter = 0;

    if(str == "failed") return;

    for(int i = 0; i < str.length(); i++)
    {
        if(str[i] == '|' || str[i] == ';')
        {
            // we send values between 0 and 10000 and convert them to a 0.0 to 1.0 range
            if(counter == 0) x = (str.substring(lastSubstringPosition, i).toInt() / 10000.0f);
            else if(counter == 1) y = (str.substring(lastSubstringPosition, i).toInt() / 10000.0f);
            else if(counter == 2) angle = str.substring(lastSubstringPosition, i).toInt();
            else if(counter == 3) eyeAngle = str.substring(lastSubstringPosition, i).toInt();
            else if(counter == 4) distance = str.substring(lastSubstringPosition, i).toInt();

            lastSubstringPosition = i+1;
            counter++;
        }
    }

    x *= W_DISP;
    y *= H_DISP;

    if(x != last_x && y != last_y)
    {
        relative_x = 0;
        relative_y = 0;

        last_x_rel = x / W_DISP;
        last_y_rel = y / H_DISP;
    }
    last_x = x;
    last_y = y;
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
        sendRawOverSerial();
        receiving = true;
    }

    if(client.available())
    {
        String buf = client.readStringUntil('\n');
        decodeWifiAnswer(buf);
        receiving = false;
    }

    if(!MODE_STREAM)
    {
        readMotionBurst(rawMotBr, motBrLength);
        updateMotBrValues();
        updateRelativePosition();

        if(coordUpdateTimer.tick())
        {
            if(last_x_rel != 0 && last_y_rel != 0)
            {
                sendCoordinates((int)(last_x_rel * 10000), (int)(last_y_rel * 10000), liftOff);
            }
        }
    }
    
    if(MODE_WALDO)
    {
        if(!liftOff)
        {
            if(wasLiftOff)
            {
                Waldo::setNewPosition((last_x / W_DISP) * 1000, (last_y / H_DISP) * 1000);
            }
            wasLiftOff = false;
        }
        else
        {
            wasLiftOff = true;
        }
    }

    if(screenUpdateTimer.tick())
    {
        if(MODE_RAW || MODE_STREAM)
        {
            drawImageToDisplay();
            // as we are in 16 bit mode, we only have a section of the screen available
            // so we at least center the raw image
            img.pushSprite(X_OFFSET, Y_OFFSET);
        }
        if(MODE_EYE)
        {
            drawEye();
            img.pushSprite(0, 0);
        }
        if(MODE_WALDO)
        {
            Waldo::updateWaldo(img, xyDelta[0], xyDelta[1]);
            img.pushSprite(0, 0);
        }
    }

    M5.update();
    //delay(100);
    return;
}

void drawImageToDisplay()
{
    img.fillRect(0, 0, W_DISP, H_DISP, BLACK);

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
            img.fillRect((W_IMG-x)*PIX_RSZ, y*PIX_RSZ, PIX_RSZ, PIX_RSZ, color);
        }
    }
}

// draws directly to the LCD
// we can have 16 bit / full screen in this mode
// but the image flickers because there's no buffering
void drawImageToDisplay_old()
{
    //M5.Lcd.fillRect(0, 0, W_DISP, H_DISP, BLACK);

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
    img.fillRect(x-2, y-2, 4, 4, RED);
}

void drawEye()
{
    float a = ((angle + eyeAngle) / 360.0) * 2 * PI;
    int x = sin(a) * -40;
    int y = cos(a) * -40;

    uint8_t tmpColor;
    if(distance < 60) tmpColor = 255;
    else tmpColor = 0;

    uint32_t bgColor = (tmpColor >> 3) << 11 | (tmpColor >> 2) << 5 | (tmpColor >> 3);

    img.fillRect(0, 0, W_DISP, H_DISP, bgColor); // BLACK
    img.fillCircle(160, 120, 105, BLACK);
    img.fillCircle(160, 120, 100, WHITE);
    img.fillCircle(160 + x, 120 + y, 60, BLACK);
}

void drawDirection()
{
    if(!liftOff)
    {
        if(xyDelta[0] == 0 && xyDelta[1] == 0) return;
        int x = xyDelta[0] < 0 ? W_DISP - 10 : 10;
        int y = xyDelta[1] < 0 ? H_DISP - 10 : 10;
        if(xyDelta[0] == 0) x = W_DISP / 2;
        if(xyDelta[1] == 0) y = H_DISP / 2;
        img.fillRect(x, y, 4, 4, GREEN);
    }
}

void updateRelativePosition()
{
    double rel_x = (relative_x / cpi) * 25.4;
    double rel_y = (relative_y / cpi) * 25.4;

    int rel_x_px = (rel_x / A4_WIDTH) * W_DISP;
    int rel_y_px = (rel_y / A4_HEIGHT) * H_DISP;

    int x = last_x + (rel_x_px / 2); // * 2
    int y = last_y + (rel_y_px / 2);

    last_x_rel = (float)x / (float)W_DISP;
    last_y_rel = (float)y / (float)H_DISP;
}

void drawRelativePosition()
{
    double rel_x = (relative_x / cpi) * 25.4;
    double rel_y = (relative_y / cpi) * 25.4;

    int rel_x_px = (rel_x / A4_WIDTH) * W_DISP;
    int rel_y_px = (rel_y / A4_HEIGHT) * H_DISP;

    int x = last_x + (2 * rel_x_px);
    int y = last_y + (2 * rel_y_px);

    img.fillRect(x-2, y-2, 4, 4, BLUE);
}
