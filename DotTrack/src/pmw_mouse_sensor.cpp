#include "pmw_mouse_sensor.hpp"

//unsigned long t_switch;
unsigned long comTimer;

WiFiUDP Udp;
bool isAP;
IPAddress serverIP(192, 168, 4, 1);
unsigned int serverPort = 2390;
IPAddress remoteIP(0, 0, 0, 0);

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


void setup()
{
    // Initialize the M5Stack object
    M5.begin();
    // Needed for M5Stack-SD-Updater
    Wire.begin();

    // Load SD Cards menu.bin which lets you load the other binaries
    if(digitalRead(BUTTON_A_PIN) == 0) {
        // Will load menu binary
        updateFromFS(SD);
        ESP.restart();
    }

    // Turn off/disconnect speaker
    // Source: https://twitter.com/Kongduino/status/980466157701423104
    M5.Speaker.end();

    // Set Brightness of M5Stack LCD display
    M5.Lcd.setBrightness(0xff);

    // Setup and use sprite object (frame buffer) to prevent flicker:
    // Because of RAM limitations it can only have a 8bit color depth
    img.setColorDepth(8);
    img.createSprite(W_DISP, H_DISP);

    // fill lift off buffer with default values
    for(auto i = 0; i < LIFT_OFF_BUF_LEN; i++)
    {
        liftOffBuffer[i] = liftOff;
    }

    /*Serial.begin(9600);*/
    // 115200 is the baudrate used by the M5Stack library
    Serial.begin(115200);
    /*Serial.begin(2000000);*/

    if(SIMULATE_INPUT == 1){ return;}

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

    // WARNING: Inhibits motion tracking (no interrupts get fired)
    // Test if PMWs SROM reports to be running:
    // 1 = SROM running
    // 0 = SROM NOT running
    /*if(DEBUG_LEVEL >= 2) {*/
    /*delay(10);  // for safety*/
    /*writeRegister(REGISTER_OBSERVATION, 0x00);*/
    /*delay(750); // T_DLY_OBS (with normal configuration)*/
    /*Serial.print("OBS RETURN: ");*/
    /*Serial.println((readRegister(REGISTER_OBSERVATION) >> 6) & 0x01);*/
    /*}*/

    // attach interrupt after startup sequence is done
    /*attachInterrupt(digitalPinToInterrupt(PIN_MOTION), onMovement, FALLING);*/
    /*if(DEBUG_LEVEL >= 2) Serial.println("motion pin interrupt attached");*/

    debug2("startup done");

    initComplete = true;

    // Start with frame capture burst mode
    frameCapture = true;
    // Delay for Frame Capture burst mode (only needed once after power up/reset)
    if(frameCapture) delay(250);

    /*t_switch = millis() + 3000;*/

    // Capture single frame
    /*delay(250);*/
    /*sendRawOverSerial();*/

    if(EYES_DEMO == 0) return;

    // Setup WiFi

    // Deletes old config (see esp32 WiFiUDPClient example)
    WiFi.disconnect(true);
    // TODO Register event handler
    WiFi.onEvent(handleWiFiEvent);

    if(DEBUG_LEVEL >= 3) printWiFiStatus();
    while(true)
    {
        img.fillSprite(BLACK);
        drawChoiceScreen();
        if(M5.BtnA.wasPressed())
        {
            break;
        }
        else if(M5.BtnC.wasPressed())
        {
            isAP = true;
            break;
        }
        M5.update();
        img.pushSprite(0, 0);
    }
    if(isAP)
    {
        // TODO Configure IP (does not always take effect)
        // WARNING: Crashes everything instantly
        //IPAddress subnet = IPAddress(255, 255, 255, 0);
        //WiFi.config(serverIP, serverIP, subnet);
        //WiFi.softAPConfig(serverIP, serverIP, subnet);
        WiFi.softAP(AP_SSID, AP_PASS);

        debug2("Starting UDP Server");

        absX = START_POS_SERV_X;
        absY = START_POS_SERV_Y;
    }
    else
    {
        // Attempt to connect to Wifi network:
        if(DEBUG_LEVEL >= 1)
        {
            Serial.print("Attempting to connect to SSID: ");
            Serial.println(AP_SSID);
        }
        unsigned long t = millis();
        while(true)
        {
            if(millis() - t > 1000)
            {
                t = millis();
                if(DEBUG_LEVEL >= 1) Serial.print(".");
                if(WiFi.begin(AP_SSID, AP_PASS) == WL_CONNECTED)
                {
                    break;
                }
            }
            img.fillSprite(BLACK);
            drawConnectScreen();
            //if(M5.BtnA.wasPressed())
            //{
            //    if(DEBUG_LEVEL >= 1) Serial.println("Become server!");
            //    //isAP = true;
            //}
            //M5.update();
            img.pushSprite(0, 0);
        }
        if(DEBUG_LEVEL >= 2) Serial.println("Connected to wifi");
        // Set remote IP for sending
        remoteIP = serverIP;

        absX = START_POS_CLI_X;
        absY = START_POS_CLI_Y;
    }
    Udp.begin(serverPort);

    // Initialize send / receive delay
    comTimer = millis();

    if(DEBUG_LEVEL >= 3)
    {
        delay(3000);
        printWiFiStatus();
    }
}

// WiFi event handler
void handleWiFiEvent(WiFiEvent_t event)
{
    debug3("WiFiEvent: ");
    // Events listed in esp_event.h (~/.platformio/packages/framework-arduinoespressif32/tools/sdk/include/esp32/esp_event.h)
    switch(event)
    {
        case SYSTEM_EVENT_WIFI_READY:               /**< ESP32 WiFi ready */
            debug3("SYSTEM_EVENT_WIFI_READY");
            break;
        case SYSTEM_EVENT_SCAN_DONE:                /**< ESP32 finish scanning AP */
            debug3("SYSTEM_EVENT_SCAN_DONE");
            break;
        case SYSTEM_EVENT_STA_START:                /**< ESP32 station start */
            debug3("SYSTEM_EVENT_STA_START");
            break;
        case SYSTEM_EVENT_STA_STOP:                 /**< ESP32 station stop */
            debug3("SYSTEM_EVENT_STA_STOP");
            break;
        case SYSTEM_EVENT_STA_CONNECTED:            /**< ESP32 station connected to AP */
            debug3("SYSTEM_EVENT_STA_CONNECTED");
            // TODO Set up connection values.
            break;
        case SYSTEM_EVENT_STA_DISCONNECTED:         /**< ESP32 station disconnected from AP */
            debug3("SYSTEM_EVENT_STA_DISCONNECTED");
            // TODO Periodically scan and / or reconnect.
            break;
        case SYSTEM_EVENT_STA_AUTHMODE_CHANGE:      /**< the auth mode of AP connected by ESP32 station changed */
            debug3("SYSTEM_EVENT_STA_AUTHMODE_CHANGE");
            break;
        case SYSTEM_EVENT_STA_GOT_IP:               /**< ESP32 station got IP from connected AP */
            debug3("SYSTEM_EVENT_STA_GOT_IP");
            break;
        case SYSTEM_EVENT_STA_LOST_IP:              /**< ESP32 station lost IP and the IP is reset to 0 */
            debug3("SYSTEM_EVENT_STA_LOST_IP");
            break;
        case SYSTEM_EVENT_STA_WPS_ER_SUCCESS:       /**< ESP32 station wps succeeds in enrollee mode */
            debug3("SYSTEM_EVENT_STA_WPS_ER_SUCCESS");
            break;
        case SYSTEM_EVENT_STA_WPS_ER_FAILED:        /**< ESP32 station wps fails in enrollee mode */
            debug3("SYSTEM_EVENT_STA_WPS_ER_FAILED");
            break;
        case SYSTEM_EVENT_STA_WPS_ER_TIMEOUT:       /**< ESP32 station wps timeout in enrollee mode */
            debug3("SYSTEM_EVENT_STA_WPS_ER_TIMEOUT");
            break;
        case SYSTEM_EVENT_STA_WPS_ER_PIN:           /**< ESP32 station wps pin code in enrollee mode */
            debug3("SYSTEM_EVENT_STA_WPS_ER_PIN");
            break;
        case SYSTEM_EVENT_AP_START:                 /**< ESP32 soft-AP start */
            debug3("SYSTEM_EVENT_AP_START");
            break;
        case SYSTEM_EVENT_AP_STOP:                  /**< ESP32 soft-AP stop */
            debug3("SYSTEM_EVENT_AP_STOP");
            break;
        case SYSTEM_EVENT_AP_STACONNECTED:          /**< a station connected to ESP32 soft-AP */
            debug3("SYSTEM_EVENT_AP_STACONNECTED");
            // TODO Set up connection values.
            break;
        case SYSTEM_EVENT_AP_STADISCONNECTED:       /**< a station disconnected from ESP32 soft-AP */
            debug3("SYSTEM_EVENT_AP_STADISCONNECTED");
            // TODO
            break;
        case SYSTEM_EVENT_AP_STAIPASSIGNED:         /**< ESP32 soft-AP assign an IP to a connected station */
            debug3("SYSTEM_EVENT_AP_STAIPASSIGNED");
            // TODO Set up connection values.
            break;
        case SYSTEM_EVENT_AP_PROBEREQRECVED:        /**< Receive probe request packet in soft-AP interface */
            debug3("SYSTEM_EVENT_AP_PROBEREQRECVED");
            break;
        case SYSTEM_EVENT_GOT_IP6:                  /**< ESP32 station or ap or ethernet interface v6IP addr is preferred */
            debug3("SYSTEM_EVENT_GOT_IP6");
            break;
        case SYSTEM_EVENT_ETH_START:                /**< ESP32 ethernet start */
            debug3("SYSTEM_EVENT_ETH_START");
            break;
        case SYSTEM_EVENT_ETH_STOP:                 /**< ESP32 ethernet stop */
            debug3("SYSTEM_EVENT_ETH_STOP");
            break;
        case SYSTEM_EVENT_ETH_CONNECTED:            /**< ESP32 ethernet phy link up */
            debug3("SYSTEM_EVENT_ETH_CONNECTED");
            break;
        case SYSTEM_EVENT_ETH_DISCONNECTED:         /**< ESP32 ethernet phy link down */
            debug3("SYSTEM_EVENT_ETH_DISCONNECTED");
            break;
        case SYSTEM_EVENT_ETH_GOT_IP:               /**< ESP32 ethernet got IP from connected AP */
            debug3("SYSTEM_EVENT_ETH_GOT_IP");
            break;
        case SYSTEM_EVENT_MAX:
            debug3("SYSTEM_EVENT_MAX");
            break;
    }
}

void sendDataUdp()
{
    // send a reply, to the IP address and port that sent us the packet we received
    if(remoteIP == IPAddress(0, 0, 0, 0))
    {
        debug3("Abort sending to local UDP port");
        return;
    }
    Udp.beginPacket(remoteIP, serverPort);

    // Fill packetBuffer
    auto len = packetBufLen - sizeof(bool);
    // Write absX, absY (each int32_t = 8 bytes) to packetBuffer
    for(auto i = 0; i < len / 2; i++)
    {
        auto posX = i;
        auto posY = i + len / 2;
        auto shift = i * len;
        packetBuffer[posX] = (byte)(absX >> shift);
        packetBuffer[posY] = (byte)(absY >> shift);
    }
    // Write liftOff (bool = 1 byte) to packetBuffer
    packetBuffer[len] = liftOff;

    Udp.write(packetBuffer, packetBufLen);
    Udp.endPacket();
}

void receiveDataUdp()
{
    int packetSize = Udp.parsePacket();
    if (packetSize)
    {
        // Set remote IP for sending
        remoteIP = Udp.remoteIP();
        uint16_t remotePort = Udp.remotePort();
        if(DEBUG_LEVEL >= 3)
        {
            Serial.print("Received packet of size ");
            Serial.println(packetSize);
            Serial.print("From ");
            Serial.print(remoteIP);
            Serial.print(", port ");
            Serial.println(remotePort);
        }

        if(remoteIP == WiFi.localIP() || packetSize != packetBufLen)
        {
            debug3("Listening to local ip or incorrect buffer length. Flushing and aborting.");
            Udp.flush();
            return;
        }

        // read the packet into packetBuffer
        Udp.read(packetBuffer, packetBufLen);

        // Empty packetBuffer
        trackX = 0;
        trackY = 0;
        // Read from packetBuffer into trackX, trackY (each int32_t = 8 bytes)
        auto len = packetBufLen - sizeof(bool);
        for(auto i = 0; i < len / 2; i++)
        {
            auto posX = i;
            auto posY = i + len / 2;
            auto shift = i * len;
            trackX = (packetBuffer[posX] << shift) | trackX;
            trackY = (packetBuffer[posY] << shift) | trackY;
        }
        // Read from packetBuffer into trackLiftOff (bool = 1 byte)
        trackLiftOff = (bool)packetBuffer[len];
        if(DEBUG_LEVEL >= 2)
        {
            Serial.println("Parsed packet:");
            Serial.println("X:\t" + String(trackX));
            Serial.println("Y:\t" + String(trackY));
            Serial.println("LO:\t" + String(trackLiftOff));
        }
    }
}

void printWiFiStatus()
{
    if(DEBUG_LEVEL >= 3)
    {
        Serial.print("WiFi.localIP: ");
        Serial.println(WiFi.localIP());
        Serial.print("WiFi.localIPv6: ");
        Serial.println(WiFi.localIPv6());
        Serial.print("WiFi.gatewayIP: ");
        Serial.println(WiFi.gatewayIP());
        Serial.print("WiFi.dnsIP: ");
        Serial.println(WiFi.dnsIP());
        Serial.print("WiFi.softAPIP: ");
        Serial.println(WiFi.softAPIP());
        Serial.print("WiFi.softAPIPv6: ");
        Serial.println(WiFi.softAPIPv6());
    }
}

void calcBearing()
{
    float deltaX = absX - trackX;
    float deltaY = absY - trackY;

    // Calculate distance
    trackDist = sqrt(pow(deltaX, 2) + pow(deltaY, 2));

    if(deltaX == 0 && deltaY == 0)
    {
        return;
    }
    // Source: https://math.stackexchange.com/a/1596518
    double rad = atan2f(deltaY, deltaX);
    circleX = (int32_t)(cos(rad) * 50);
    circleY = (int32_t)(sin(rad) * 50);

    int32_t deg = degrees(rad);
    if(deg < 0)
    {
        deg += 360;
    }

    if(trackLiftOff)
    {
        trackBearing = -1;
    }
    else
    {
        trackBearing = deg;
    }

    if(DEBUG_LEVEL >= 2)
    {
        Serial.print("rad: ");
        Serial.println(rad);
        Serial.print("deg: ");
        Serial.println(deg);
        Serial.print("trackBearing: ");
        Serial.println(trackBearing);
        Serial.print("circleX: ");
        Serial.println(circleX);
        Serial.print("circleY: ");
        Serial.println(circleY);
        Serial.println("trackDist: " + String(trackDist));
    }
}

void drawEye()
{
    img.fillCircle(160, 120, EYE_SCLERA_RADIUS, EYE_SCLERA_COLOR);

    if(trackLiftOff || liftOff)
    {
        // Draw eye in the middle
        img.fillCircle(160, 120, EYE_IRIS_RADIUS, EYE_IRIS_COLOR);
    }
    else
    {
        // Draw eye at the bearing
        img.fillCircle(160+circleX, 120+circleY, EYE_IRIS_RADIUS, EYE_IRIS_COLOR);

        // Draw proximity indicator
        if(trackDist < MAX_PROXIMITY_CPI)
        {
            debug3("Draw proximity indicator: ");
            // Right (0°)
            if(trackBearing > 315 || trackBearing <= 45)
            {
                debug3("RIGHT (0 degrees)");
                img.fillRect(320-10, 0, 10, 240, GREEN);
            }
            // Bottom (90°)
            else if(trackBearing > 45 && trackBearing <= 135)
            {
                debug3("BOTTOM (90 degrees)");
                img.fillRect(0, 240-10, 320, 10, GREEN);
            }
            // Left (180°)
            else if(trackBearing > 135 && trackBearing <= 225)
            {
                debug3("LEFT (180 degrees)");
                img.fillRect(0, 0, 10, 240, GREEN);
            }
            // Top (270°)
            else if(trackBearing > 225 && trackBearing <= 315)
            {
                debug3("TOP (270 degrees)");
                img.fillRect(0, 0, 320, 10, GREEN);
            }
        }
    }
}

void loop()
{
    if(EYES_DEMO == 1)
    {
        // Reset sprite to a black background
        img.fillSprite(BLACK);

        if(millis() - comTimer > COM_DELAY)
        {
            // Handle WiFi communication
            receiveDataUdp();
            sendDataUdp();
            calcBearing();
            comTimer = millis();
            if(DEBUG_LEVEL >= 3)
            {
                Serial.print("Estimated X (in cm): ");
                Serial.println(((double)absX / cpi) * 2.54);
                Serial.print("Estimated Y (in cm): ");
                Serial.println(((double)absY / cpi) * 2.54);
            }
        }

        // Draw eye and proximity indicator
        drawEye();

        readMotionBurst(rawMotBr, motBrLength);
        updateMotBrValues();

        // M5Stack #8
        //int avg_threshold = 2;
        //int shutter_threshold = 10;
        //int left[] = {15, 110, 20, 110};
        //int mid[] = {20, 120, 20, 100};
        //int right[] = {24, 120, 32, 85};
        // M5Stack #7
        int avg_threshold = 3;
        int shutter_threshold = 10;
        int left[] = {16, 110, 20, 130};
        int mid[] = {22, 120, 20, 110};
        int right[] = {28, 120, 32, 90};

        // Points are ~ 9cm apart -> 9*2.54 = 3,54in -> 3.54*5000 = 17716cpi
        if(!liftOff)
        {
            if(left[AVG] - avg_threshold <= avgRawData && avgRawData <= left[AVG] + avg_threshold &&
                left[SHTR] - shutter_threshold <= shutter && shutter <= left[SHTR] + shutter_threshold)
            //if(avgRawData >= 11 && avgRawData <= 18 &&
            //   shutter >= 106 && shutter <= 139)
            //if(avgRawData >= 56 && avgRawData <= 65 &&
               //shutter >= 120 && shutter <= 129)
            {
                debug3("Reset to left position");
                absX = POS1_X;
                absY = POS1_Y;
            }
            else if(mid[AVG] - avg_threshold <= avgRawData && avgRawData <= mid[AVG] + avg_threshold &&
                mid[SHTR] - shutter_threshold <= shutter && shutter <= mid[SHTR] + shutter_threshold)
            //else if(avgRawData >= 15 && avgRawData <= 20 &&
            //        shutter >= 85 && shutter <= 105)
            //else if(avgRawData >= 66 && avgRawData <= 75 &&
                    //shutter >= 90 && shutter <= 100)
            {
                debug3("Reset to center position");
                absX = POS2_X;
                absY = POS2_Y;
            }
            else if(right[AVG] - avg_threshold <= avgRawData && avgRawData <= right[AVG] + avg_threshold &&
                right[SHTR] - shutter_threshold <= shutter && shutter <= right[SHTR] + shutter_threshold)
            //else if(avgRawData >= 20 && avgRawData <= 30 &&
            //        shutter >= 75 && shutter <= 90)
            //else if(avgRawData >= 82 && avgRawData <= 90 &&
                    //shutter >= 77 && shutter <= 87)
            {
                debug3("Reset to right position");
                absX = POS3_X;
                absY = POS3_Y;
            }
        }

        if(printMotBrToDisplay)
        {
            drawMotBrToDisplay();
        }
        if(M5.BtnC.wasPressed())
        {
            printMotBrToDisplay = !printMotBrToDisplay;
        }
        M5.update();

        // Draw sprite to display
        img.pushSprite(0, 0);

        return;
    }

    // not EYES_DEMO:

    // Reset sprite to a black background
    img.fillSprite(BLACK);

    if(app == 3)
    {
        captureRawImage(rawData, rawDataLength);
    }
    else
    {
        if(prevApp == 3)
        {
            // Set prevApp to its default value to prevent further resets
            prevApp = 0;
            resetSPIPort();
            resetDevice();
            performSROMdownload();
            configureRegisters();
            // TODO Maybe build a timer for faster resets when FC is not needed yet
            delay(250);
        }
        readMotionBurst(rawMotBr, motBrLength);
        updateMotBrValues();
        findAppPosition();
    }

    switch(app)
    {
        case 0:
            drawWelcomeScreen();
            break;
        case 1:
            Select::updateSelect(img, xyDelta[0], xyDelta[1]);
            break;
        case 2:
            Waldo::updateWaldo(img, xyDelta[0], xyDelta[1]);
            break;
        case 3:
            drawImageToDisplay();
            break;
        default:
            img.setTextSize(1);
            img.setTextColor(WHITE, BLACK);
            img.setCursor(0,0);
            img.println("Error: \"app\" value unknown!");
    }

    if(printMotBrToDisplay && app != 3)
    {
        drawMotBrToDisplay();
    }

    if(M5.BtnA.wasPressed())
    {
        prevApp = app;
        app = 0;
        //M5.Lcd.fillScreen(BLACK);
    }
    if(M5.BtnB.wasPressed())
    {
        preventAppExit = !preventAppExit;
    }
    if(M5.BtnC.wasPressed())
    {
        printMotBrToDisplay = !printMotBrToDisplay;
        //M5.Lcd.fillScreen(BLACK);
    }

    M5.update();

    if(app != 3)
    {
        // Draw sprite to display
        img.pushSprite(0, 0);
    }

    /*if(frameCapture)*/
    /*{*/
    /*captureRawImage(rawData, rawDataLength);*/
    /*drawImageToDisplay();*/
    /*}*/
    /*else*/
    /*{*/
    /*readMotionBurst(rawMotBr, motBrLength);*/
    /*updateMotBrValues();*/
    /*drawMotBrToDisplay();*/
    /*}*/

    /*if(M5.BtnC.wasPressed())*/
    /*{*/
    /*M5.Lcd.fillScreen(BLACK);*/
    /*if(frameCapture)*/
    /*{*/
    /*resetSPIPort();*/
    /*resetDevice();*/
    /*performSROMdownload();*/
    /*configureRegisters();*/
    /*// TODO Maybe build a timer for faster resets when FC is not needed yet*/
    /*delay(250);*/
    /*}*/
    /*frameCapture = !frameCapture;*/
    /*}*/
    /*M5.update();*/

    /*// switch to frame capture mode when the sensor hits the ground*/
    /*if(!liftOff && prevLiftOff)*/
    /*{*/
    /*frameCapture = true;*/
    /*// Delay for Frame Capture burst mode (only needed once after power up/reset)*/
    /*t_switch = millis() + 3000;*/
    /*}*/
    /*// TODO liftOff is too sensitive for this task*/
    /*prevLiftOff = liftOff;*/

    /*if(t_switch < millis() && t_switch != 0)*/
    /*{*/
    /*frameCapture = false;*/
    /*t_switch = 0;*/
    /*resetSPIPort();*/
    /*resetDevice();*/
    /*performSROMdownload();*/
    /*configureRegisters();*/
    /*// TODO Maybe build a timer for faster resets when FC is not needed yet*/
    /*delay(250);*/
    /*}*/
}

void writeRegister(uint8_t address, uint8_t data)
{
    if(DEBUG_LEVEL >= 3)
    {
        Serial.print("writeRegister: 0x");
        Serial.println(address, HEX);
    }
    if(readingMotion) readingMotion = false;
    address |= WRITE_MASK;

    SPI.beginTransaction(SPISettings(F_SCLK, MSBFIRST, SPI_MODE3));
    digitalWrite(PIN_NCS, LOW);
    delayMicroseconds(T_NCS_SCLK);

    SPI.write16((uint16_t)((address << 8) | data));

    delayMicroseconds(T_SCLK_NCS_WRITE);
    digitalWrite(PIN_NCS, HIGH);
    SPI.endTransaction();

    // TODO Maybe add delay (T_SWW/T_SWR) for next read/write operation (see
    // Figure 20 / p.21)
    // This basic approach might unnecessarily stall execution.
    // Be careful with burst mode being active.
    delayMicroseconds(T_SWW);
}

uint8_t readRegister(uint8_t address)
{
    if(DEBUG_LEVEL >= 3)
    {
        Serial.print("readRegister: 0x");
        Serial.println(address, HEX);
    }
    // reset readingMotion if another register is read
    if(readingMotion &&
            address != REGISTER_MOTION &&
            address != REGISTER_DELTA_X_L &&
            address != REGISTER_DELTA_X_H &&
            address != REGISTER_DELTA_Y_L &&
            address != REGISTER_DELTA_Y_H)
    {
        readingMotion = false;
    }

    uint16_t result;

    address &= READ_MASK;

    SPI.beginTransaction(SPISettings(F_SCLK, MSBFIRST, SPI_MODE3));
    digitalWrite(PIN_NCS, LOW);
    delayMicroseconds(T_NCS_SCLK);

    // TODO Use T_SRAD between write of address byte and read of data byte
    // TODO try SPI.transfer(address)
    /*result = SPI.transfer16((uint16_t)((address << 8) & 0xFF00));*/
    SPI.transfer(address);
    // Delay (T_SRAD) between write of address byte and read of data byte (see
    // Figure 16 / p.20 and Figure 20 / p.21)
    delayMicroseconds(T_SRAD);
    result = SPI.transfer(0);

    delayMicroseconds(T_SCLK_NCS_READ);
    digitalWrite(PIN_NCS, HIGH);
    SPI.endTransaction();

    // TODO Maybe add delay (T_SRR/T_SRW) for next read/write operation (see
    // Figure 20 / p.21)
    // This basic approach might unnecessarily stall execution.
    // Be careful with burst mode being active.
    delayMicroseconds(T_SRW);

    return (uint8_t) (result & 0x00FF);
}

// Drive NCS high, and then low to reset the SPI port.
void resetSPIPort()
{
    digitalWrite(PIN_NCS, HIGH);
    delay(100); // to ensure that the high-low switch will be registered
    digitalWrite(PIN_NCS, LOW);
}

void resetDevice()
{
    // Write 0x5A to Power_Up_Reset register (or, alternatively toggle the NRESET pin).
    writeRegister(REGISTER_POWER_UP_RESET, 0x5A);

    // Wait for at least 50ms.
    delay(50);

    // Read from registers 0x02, 0x03, 0x04, 0x05 and 0x06 one time regardless of the motion pin state.
    readRegister(REGISTER_MOTION);
    readRegister(REGISTER_DELTA_X_L);
    readRegister(REGISTER_DELTA_X_H);
    readRegister(REGISTER_DELTA_Y_L);
    readRegister(REGISTER_DELTA_Y_H);
}

void performSROMdownload()
{
    debug2("performSROMdownload()");

    // disable Rest mode
    writeRegister(REGISTER_CONFIG2, 0x00);
    // initialize
    writeRegister(REGISTER_SROM_ENABLE, 0x1d);
    delay(10);
    // start SROM download
    writeRegister(REGISTER_SROM_ENABLE, 0x18);

    // Prepare burst mode
    SPI.beginTransaction(SPISettings(F_SCLK, MSBFIRST, SPI_MODE3));
    digitalWrite(PIN_NCS, LOW);
    delayMicroseconds(T_NCS_SCLK);

    // Initialize SROM burst mode with address
    SPI.transfer((uint8_t)(REGISTER_SROM_LOAD_BURST | WRITE_MASK));

    // Enter burst mode
    delayMicroseconds(15);

    // Write bytes in burst mode
    for(int i = 0; i < firmwareLength; i++)
    {
        SPI.transfer(firmwareData[i]);
        if(DEBUG_LEVEL >= 3) Serial.println(firmwareData[i], HEX);
        delayMicroseconds(15);
    }

    // Exit burst mode (exiting after NCS was high for T_BEXIT delay)
    delayMicroseconds(T_SCLK_NCS_WRITE);
    digitalWrite(PIN_NCS, HIGH);
    SPI.endTransaction();
    delayMicroseconds(T_BEXIT);

    // Soonest to read REGISTER_SROM_ID (see Figure 22 / p.23)
    delayMicroseconds(200);
    uint8_t i = readRegister(REGISTER_SROM_ID);
    // Success: "4" (current firmware version)
    // Failed: "0"
    debug2("SROM_ID RETURN: " + String(i));
}

void configureRegisters()
{
    debug2("configureRegisters()");

    // TODO Configure registers (write to config registers)

    // Disable Rest mode
    // Info: Prevent LO detection not working within the first few ms after waking up from Rest2 or Rest3 mode.
    // Warning: Changes average raw data values (but may make them more consistent)
    //writeRegister(REGISTER_CONFIG2, 0x00);
    //if(DEBUG_LEVEL >= 2) Serial.println("disable Rest mode");

    // Set lift detection height threshold
    writeRegister(REGISTER_LIFT_CONFIG, 0x03); // 0x03 = nominal height + 3mm (default: 0x02 = nominal height + 2mm)
    debug2("set lift detection");
}

void readConfigRegisters()
{
    // Read CPI settings and calculate scale
    uint8_t config2 = readRegister(REGISTER_CONFIG2);
    restEn = config2 & REG_CONF2_REST_EN;
    rptMod = config2 & REG_CONF2_RPT_MOD;
    if(!rptMod)
    {
        uint8_t config1 = readRegister(REGISTER_CONFIG1);
        cpi = MIN_CPI + config1 * MIN_CPI;
        cpiX = cpiY = -1; // disable cpi values
        if(DEBUG_LEVEL >= 2)
        {
            Serial.println("CPI: " + String(cpi));
            Serial.println("Counts per centimeter: " + String(cpi * 2.54));
        }
    }
    else
    {
        // If X and Y CPI can be configured independently
        uint8_t config1 = readRegister(REGISTER_CONFIG1);
        cpiX = MIN_CPI + config1 * MIN_CPI;
        uint8_t config5 = readRegister(REGISTER_CONFIG5);
        cpiY = MIN_CPI + config5 * MIN_CPI;
        cpi = -1; // disable cpi value
        if(DEBUG_LEVEL >= 2)
        {
            Serial.println("CPI X: " + String(cpiX));
            Serial.println("CPI Y: " + String(cpiY));
        }
    }
}

// interrupt callback for motion pin
void onMovement()
{
    debug3("onMovement()");

    if(initComplete)
    {
        // Read motion registers (see datasheet p. 30)

        // Initiate reading motion registers
        if(!readingMotion)
        {
            writeRegister(REGISTER_MOTION, 0x01); // any value would be OK
            readingMotion = true;
        }

        // Read Motion register
        uint8_t motion = readRegister(REGISTER_MOTION);

        // Evaluate Lift_Stat bit
        prevLiftOff = liftOff;
        liftOff = motion & REG_MOTION_LIFT_STAT;

        // Evaluate OP_Mode[1:0] bits
        opMode = (motion & REG_MOTION_OP_MODE) >> 1;

        // Read motion registers if MOT bit is set
        if(motion & REG_MOTION_MOT_BIT)
        {
            hasMoved = true;
            uint8_t resultDeltaXL = readRegister(REGISTER_DELTA_X_L);
            uint8_t resultDeltaXH = readRegister(REGISTER_DELTA_X_H);
            uint8_t resultDeltaYL = readRegister(REGISTER_DELTA_Y_L);
            uint8_t resultDeltaYH = readRegister(REGISTER_DELTA_Y_H);

            xyDelta[0] = (int16_t)((resultDeltaXH << 8) | resultDeltaXL);
            xyDelta[1] = (int16_t)((resultDeltaYH << 8) | resultDeltaYL);
        }
        else
        {
            hasMoved = false;
            xyDelta[0] = 0;
            xyDelta[1] = 0;
        }
    }
}

// see p. 24 of datasheet
void captureRawImage(uint8_t* result, int resultLength)
{
    // TODO Implement timer for this
    // Setup burst mode (only needed once after power up/reset)
    /*delay(250);*/
    // disable Rest mode
    writeRegister(REGISTER_CONFIG2, 0x00);
    writeRegister(REGISTER_FRAME_CAPTURE, 0x83);
    writeRegister(REGISTER_FRAME_CAPTURE, 0xC5);
    delay(20);

    // Prepare burst mode
    SPI.beginTransaction(SPISettings(F_SCLK, MSBFIRST, SPI_MODE3));
    digitalWrite(PIN_NCS, LOW);
    delayMicroseconds(T_NCS_SCLK);

    // Initialize frame capture burst mode with address
    SPI.transfer(REGISTER_RAW_DATA_BURST);

    // Enter burst mode
    delayMicroseconds(T_SRAD);

    // Read bytes in burst mode
    for(int i = 0; i < resultLength && i < rawDataLength; i++)
    {
        result[i] = SPI.transfer(0);
        delayMicroseconds(T_LOAD);
    }

    // Exit burst mode (exiting after NCS was high for T_BEXIT delay)
    delayMicroseconds(T_SCLK_NCS_WRITE);
    digitalWrite(PIN_NCS, HIGH);
    SPI.endTransaction();
    delayMicroseconds(T_BEXIT);

    // Soonest to begin again (see Figure 23 / p.24)
    delayMicroseconds(180);
}

void drawImageToDisplay()
{
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

// send a 36x36px greyscale raw image with 8bit depth over Serial connection to the PC
// use the included python script (dottrack_stream.py) to view the image
void sendRawOverSerial()
{
    Serial.write(rawData, rawDataLength);
    // Paket termination byte TODO improve this (header terminate bytes)
    Serial.write(0xFE);
}

void readMotionBurst(uint8_t* result, int resultLength)
{
    // Setup motion burst mode
    writeRegister(REGISTER_MOTION_BURST, 0x01);

    // Prepare motion burst mode
    SPI.beginTransaction(SPISettings(F_SCLK, MSBFIRST, SPI_MODE3));
    digitalWrite(PIN_NCS, LOW);
    delayMicroseconds(T_NCS_SCLK);

    // Initialize motion burst mode with address
    SPI.transfer(REGISTER_MOTION_BURST);

    // Enter burst mode
    delayMicroseconds(T_SRAD_MOTBR);

    // Read bytes in burst mode
    for(int i = 0; i < resultLength && i < motBrLength; i++)
    {
        result[i] = SPI.transfer(0);
        // TODO NEEDED?
        delayMicroseconds(T_LOAD);
    }

    // Exit burst mode (exiting after NCS was high for T_BEXIT delay)
    delayMicroseconds(T_SCLK_NCS_WRITE);
    digitalWrite(PIN_NCS, HIGH);
    SPI.endTransaction();
    delayMicroseconds(T_BEXIT);

    // TODO NEEDED? Soonest to begin again (see Figure 23 / p.24)
    delayMicroseconds(250);
}

// Update needed motion burst values from raw motion burst data
void updateMotBrValues()
{
    // Read Motion byte
    uint8_t motion = rawMotBr[0];
    // Evaluate MOT bit
    if(motion & REG_MOTION_MOT_BIT)
    {
        hasMoved = true;
        xyDelta[0] = (int16_t)((rawMotBr[3] << 8) | rawMotBr[2]);
        xyDelta[1] = (int16_t)((rawMotBr[5] << 8) | rawMotBr[4]);
        absX += xyDelta[0];
        absY += xyDelta[1];
    }
    else
    {
        hasMoved = false;
        xyDelta[0] = 0;
        xyDelta[1] = 0;
    }
    // TODO Evaluate RData_1st Needed?
    // Evaluate Lift_Stat bit
    prevLiftOff = liftOff;
    liftOff = motion & REG_MOTION_LIFT_STAT;
    Tools::pushOnBuffer(liftOff, liftOffBuffer, LIFT_OFF_BUF_LEN);
    evalLiftOffBuffer();
    // Evaluate OP_Mode[1:0] bits
    opMode = (motion & REG_MOTION_OP_MODE) >> 1;
    // TODO Evaluate FRAME_RData_1st Needed?

    // Read Observation byte
    // Evaluate SROM_RUN bit
    sromRun = rawMotBr[2] & REG_OBS_SROM_RUN;

    // Read SQUAL byte
    squal = rawMotBr[6];
    numFeatures = squal * 8;

    // Read Raw_Data_Sum byte
    // The Raw_Data_Sum byte should be between 0-160 (0x00 - 0xA0)
    rawDataSum = rawMotBr[7];
    // Therefore avgRawData (after calculation) lays between 0-126
    avgRawData = rawDataSum * 1024 / 1296;

    // Read Maximum_Raw_Data byte
    maxRawData = rawMotBr[8];

    // Read Minimum_Raw_Data byte
    minRawData = rawMotBr[9];

    // Read Shutter bytes
    shutter = rawMotBr[10] << 8 | rawMotBr[11];
}

// Draw motion burst data to M5Stack display (spaces are for overwriting shorter values)
void drawMotBrToDisplay()
{
    img.setTextSize(1);
    img.setTextColor(WHITE, BLACK);
    img.setCursor(0,0);
    // Draw motion bit and registers if MOT bit is set
    if(hasMoved)
    {
        img.println("MOT: Motion occurred");
        img.println("Delta X: " + String(xyDelta[0]));
        img.println("Delta Y: " + String(xyDelta[1]));

        // TODO Figure out xyDelta sending
        /*Serial.write(xyDelta[0]);*/
        /*Serial.write(xyDelta[1]);*/
        /*Serial.write(0xFE);*/
    }
    else
    {
        img.println("MOT: No motion");
        img.println("Delta X: 0");
        img.println("Delta Y: 0");
    }

    // Draw absoulte position (currently determined with relative tracking)
    img.println("Absolute X: " + String(absX));
    img.println("Absolute Y: " + String(absY));

    // Draw Lift_Stat bit
    if(liftOff)
    {
        img.println("Lift_Stat: Chip lifted");
    }
    else
    {
        img.println("Lift_Stat: Chip on surface");
    }

    // Draw cumulative lift of state (lift off buffer)
    if(cumLiftOff)
    {
        img.println("Cumulative Lift State: Chip lifted");
    }
    else
    {
        img.println("Cumulative Lift State: Chip on surface");
    }

    // Draw OP_Mode[1:0] bit
    switch(opMode)
    {
        case 0:
            img.println("OP_Mode: Run mode");
            break;
        case 1:
            img.println("OP_Mode: Rest 1");
            break;
        case 2:
            img.println("OP_Mode: Rest 2");
            break;
        case 3:
            img.println("OP_Mode: Rest 3");
            break;
        default:
            img.println("OP_Mode evaluation error");
    }

    // Draw Observation/SROM_RUN value
    if(sromRun)
    {
        img.println("SROM_RUN: SROM running");
    }
    else
    {
        img.println("SROM_RUN: SROM not running");
    }

    // Draw SQUAL value / number of features
    img.println("SQUAL: " + String(squal));
    img.println("Number of Features: " + String(numFeatures));

    // Draw Raw_Data_Sum value
    img.println("Raw_Data_Sum: " + String(rawDataSum));
    img.println("Average Raw Data: " + String(avgRawData));

    // Draw Maximum_Raw_Data value
    img.println("Maximum_Raw_Data: " + String(maxRawData));

    // Draw Minimum_Raw_Data value
    img.println("Minimum_Raw_Data: " + String(minRawData));

    // Draw Shutter value
    img.println("Shutter: " + String(shutter));
}

// Send motion burst values over serial
void sendMotBrOverSerial()
{
    // Send motion bit and registers if MOT bit is set
    if(hasMoved)
    {
        debug3("MOT: Motion occurred");
        debug("Delta X: " + String(xyDelta[0]));
        debug("Delta Y: " + String(xyDelta[1]));

        // TODO Figure out xyDelta sending
        /*Serial.write(xyDelta[0]);*/
        /*Serial.write(xyDelta[1]);*/
        /*Serial.write(0xFE);*/
    }
    else
    {
        debug3("MOT: No motion");
        debug("Delta X: 0");
        debug("Delta Y: 0");
    }

    // Send absoulte position (currently determined with relative tracking)
    debug3("Absolute X: " + String(absX));
    debug3("Absolute Y: " + String(absY));

    // Send Lift_Stat bit
    if(liftOff)
    {
        debug2("Lift_Stat: Chip lifted");
    }
    else
    {
        debug2("Lift_Stat: Chip on surface");
    }

    // Send OP_Mode[1:0] bit
    if(DEBUG_LEVEL >= 3)
    {
        switch(opMode)
        {
            case 0:
                Serial.println("OP_Mode: Run mode");
                break;
            case 1:
                Serial.println("OP_Mode: Rest 1");
                break;
            case 2:
                Serial.println("OP_Mode: Rest 2");
                break;
            case 3:
                Serial.println("OP_Mode: Rest 3");
                break;
            default:
                Serial.println("OP_Mode evaluation error");
        }
    }

    // Send Observation/SROM_RUN value
    if(sromRun)
    {
        debug3("SROM_RUN: SROM running");
    }
    else
    {
        debug3("SROM_RUN: SROM not running");
    }

    // Send SQUAL value / number of features
    debug3("SQUAL: " + String(squal));
    debug3("Number of Features: " + String(numFeatures));

    // Send Raw_Data_Sum value
    debug3("Raw_Data_Sum: " + String(rawDataSum));
    debug3("Average Raw Data: " + String(avgRawData));

    // Send Maximum_Raw_Data value
    debug3("Maximum_Raw_Data: " + String(maxRawData));

    // Send Minimum_Raw_Data value
    debug3("Minimum_Raw_Data: " + String(minRawData));

    // Send Shutter value
    debug3("Shutter: " + String(shutter));
}

// TODO Maybe use a array of data values and medians/averages to prevent outlier problems
void findAppPosition()
{
    // orig demo values
    // int avg_threshold = 5
    // int shutter_threshold = 20
    //u_char[] left = {15, 0, 0, 135};
    //u_char[] mid = {20, 0, 0, 108};
    //u_char[] right = {26, 0, 0, 95};

//  RW demo values
// avg, max, min, shutter
    // M5Stack #8
    //int avg_threshold = 2;
    //int shutter_threshold = 10;
    //int left[] = {18, 110, 20, 150};
    //int mid[] = {20, 120, 20, 110};
    //int right[] = {25, 120, 32, 100};
    // M5Stack #7
    int avg_threshold = 2;
    int shutter_threshold = 10;
    int left[] = {18, 110, 20, 140};
    int mid[] = {22, 120, 20, 110};
    int right[] = {24, 120, 32, 90};

    if(liftOff && !prevLiftOff && !preventAppExit)
        /*if(cumLiftOff && !preventAppExit)*/
    {
        // TODO prevent flickering (app switching on the between liftOff/!liftOff)
        prevApp = app;
        app = 0;
        //M5.Lcd.fillScreen(BLACK);
    }
    else if(!liftOff && app == 0)
        /*else if(!cumLiftOff)*/
    {
        if(left[AVG] - avg_threshold <= avgRawData && avgRawData <= left[AVG] + avg_threshold &&
                left[SHTR] - shutter_threshold <= shutter && shutter <= left[SHTR] + shutter_threshold)
        {
            debug3("Switch to app 1: Select app");
            prevApp = app;
            app = 1;
        }
        else if(mid[AVG] - avg_threshold <= avgRawData && avgRawData <= mid[AVG] + avg_threshold &&
                mid[SHTR] - shutter_threshold <= shutter && shutter <= mid[SHTR] + shutter_threshold)
        {
            debug3("Switch to app 2: Magic lens app");
            prevApp = app;
            app = 2;
        }
        else if(right[AVG] - avg_threshold <= avgRawData && avgRawData <= right[AVG] + avg_threshold &&
                right[SHTR] - shutter_threshold <= shutter && shutter <= right[SHTR] + shutter_threshold)
       
        {
            debug3("Switch to app 3: Magnifying lens app");
             prevApp = app;
             app = 3;
             M5.Lcd.fillScreen(BLACK);
        }
    }
}

void drawWelcomeScreen()
{
    /*Image::draw(muc_logo_pixel_map);*/
    img.setTextSize(5);
    img.setTextColor(RED, BLACK);
    img.setCursor(80, 30);
    img.println("Place");
    img.setCursor(50, 90);
    img.println("me on a");
    img.setCursor(50, 150);
    img.println("pattern!");

    img.setTextSize(2);
    img.setTextColor(WHITE, BLACK);
    img.setCursor(40, 220);
    img.println("Quit    Lock    Debug");
}

void evalLiftOffBuffer()
{
    bool temp, tempOld;
    for(auto i = 0; i < LIFT_OFF_BUF_LEN; i++)
    {
        temp = liftOffBuffer[i];
        if(i != 0)
        {
            if(temp != tempOld)
            {
                break;
            }
            else if(i == LIFT_OFF_BUF_LEN - 1)
            {
                cumLiftOff = temp;
            }
        }
        tempOld = temp;
    }
}

void drawChoiceScreen()
{
    img.setTextSize(3);
    img.setTextColor(RED, BLACK);
    img.setCursor(15, 50);
    img.println("Choose to become");
    img.setCursor(10, 90);
    img.println("server or client!");
    img.setTextSize(2);
    img.setCursor(40, 150);
    img.println("Server spawns right,");
    img.setCursor(40, 170);
    img.println("   client left!");

    img.setTextSize(2);
    img.setTextColor(WHITE, BLACK);
    img.setCursor(35, 220);
    img.println("Client          Server");
}

void drawConnectScreen()
{
    img.setTextSize(5);
    img.setTextColor(RED, BLACK);
    img.setCursor(20, 60);
    img.println("Trying to");
    img.setCursor(20, 120);
    img.println("connect..");
    //img.setCursor(40, 90);
    //img.println("Or choose to become");
    //img.setCursor(40, 150);
    //img.println("    the server!");

    //img.setTextSize(2);
    //img.setTextColor(WHITE, BLACK);
    //img.setCursor(40, 220);
    //img.println("Server");
}
