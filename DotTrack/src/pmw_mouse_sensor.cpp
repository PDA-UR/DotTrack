#include "pmw_mouse_sensor.hpp"

//unsigned long t_switch;
unsigned long comTimeStamp;

WiFiUDP Udp;
bool isAP;
IPAddress serverIP(192, 168, 4, 1);
unsigned int serverPort = 2390;
IPAddress remoteIP(0, 0, 0, 0);

void setup()
{
    // Initialize the M5Stack object
    M5.begin();

    // Turn off/disconnect speaker
    // Source: https://twitter.com/Kongduino/status/980466157701423104
    M5.Speaker.end();

    // Set Brightness of M5Stack LCD display
    M5.Lcd.setBrightness(0xff);

    // fill lift off buffer with default values
    for(auto i = 0; i < LIFT_OFF_BUF_LEN; i++)
    {
        liftOffBuffer[i] = liftOff;
    }

    /*Serial.begin(9600);*/
    // 115200 is the baudrate used by the M5Stack library
    Serial.begin(115200);
    /*Serial.begin(250000);*/
    /*Serial.begin(2000000);*/

    if(SIMULATE_INPUT == 1){ return;}

    if(DEBUG_LEVEL >= 2) Serial.println("setup()");

    // setup pins
    pinMode(PIN_NCS, OUTPUT);
    /*pinMode(PIN_MOTION, INPUT); // maybe INPUT_PULLUP is better?*/
    /*// > The motion pin is an active low output (datasheet p.18)*/
    /*digitalWrite(PIN_MOTION, HIGH);*/
    pinMode(PIN_SCLK, OUTPUT);
    pinMode(PIN_SCLK, OUTPUT);
    pinMode(PIN_MOSI, OUTPUT);
    /*attachInterrupt(digitalPinToInterrupt(PIN_MOTION), onMovement, FALLING);*/

    if(DEBUG_LEVEL >= 2) Serial.println("pins initialized");

    // Initialize the SPI object
    SPI.begin();
    // SCLK when running on 2MHz / SPI.setFrequency(2000000L):
    // One bit should take 500ns
    // One byte should take 8*500ns = 4µs
    // Two bytes should take 16*500ns = 8µs
    /*SPI.beginTransaction(SPISettings(F_SCLK, MSBFIRST, SPI_MODE3));*/

    if(DEBUG_LEVEL >= 2) Serial.println("SPI initialized");

    // Initialize PMW3360 - Power up/startup sequence (see p. 26 of datasheet)

    // Delay to wait for NCS not to be ignored (see table on p. 26)
    delay(100); // Max VDD-VDDIO power up delay

    resetSPIPort();

    resetDevice();

    performSROMdownload();

    // TODO Configure registers (write to config registers)
    configureRegisters();

    if(DEBUG_LEVEL >= 2) Serial.println("reset device done");

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

    if(DEBUG_LEVEL >= 2) Serial.println("startup done");

    initComplete = true;

    // Start with frame capture burst mode
    frameCapture = true;
    // Delay for Frame Capture burst mode (only needed once after power up/reset)
    if(frameCapture) delay(250);

    /*t_switch = millis() + 3000;*/

    // Capture single frame
    /*delay(250);*/
    /*sendRawOverSerial();*/

    // Setup WiFi

    // Deletes old config (see esp32 WiFiUDPClient example)
    WiFi.disconnect(true);
    // TODO Register event handler
    WiFi.onEvent(handleWiFiEvent);

    if(DEBUG_LEVEL >= 3) printWiFiStatus();
    if(DEBUG_LEVEL >= 1) Serial.println("Press middle button to enter server mode...");
    unsigned long t = millis();
    while(millis() < t + 3000)
    {
        if(M5.BtnB.wasPressed())
        {
            isAP = true;
            break;
        }
        M5.update();
    }
    if(isAP)
    {
        // TODO Configure IP (does not always take effect)
        IPAddress subnet = IPAddress(255, 255, 255, 0);
        WiFi.config(serverIP, serverIP, subnet);
        WiFi.softAPConfig(serverIP, serverIP, subnet);
        WiFi.softAP(AP_SSID, AP_PASS);

        if(DEBUG_LEVEL >= 2) Serial.println("Starting UDP Server");
    }
    else
    {
        // Attempt to connect to Wifi network:
        if(DEBUG_LEVEL >= 1)
        {
            Serial.print("Attempting to connect to SSID: ");
            Serial.println(AP_SSID);
        }
        while (WiFi.begin(AP_SSID, AP_PASS) != WL_CONNECTED)
        {
            if(DEBUG_LEVEL >= 1) Serial.print(".");
            delay(1000);
        }
        if(DEBUG_LEVEL >= 2) Serial.println("Connected to wifi");
        // Set remote IP for sending
        remoteIP = serverIP;
    }
    Udp.begin(serverPort);

    // Initialize send / receive delay
    comTimeStamp = millis();

    if(DEBUG_LEVEL >= 3)
    {
        delay(3000);
        printWiFiStatus();
    }
}

// WiFi event handler
void handleWiFiEvent(WiFiEvent_t event)
{
    if(DEBUG_LEVEL >= 3) Serial.print("WiFiEvent: ");
    // Events listed in esp_event.h (~/.platformio/packages/framework-arduinoespressif32/tools/sdk/include/esp32/esp_event.h)
    switch(event)
    {
        case SYSTEM_EVENT_WIFI_READY:               /**< ESP32 WiFi ready */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_WIFI_READY");
            break;
        case SYSTEM_EVENT_SCAN_DONE:                /**< ESP32 finish scanning AP */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_SCAN_DONE");
            break;
        case SYSTEM_EVENT_STA_START:                /**< ESP32 station start */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_STA_START");
            break;
        case SYSTEM_EVENT_STA_STOP:                 /**< ESP32 station stop */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_STA_STOP");
            break;
        case SYSTEM_EVENT_STA_CONNECTED:            /**< ESP32 station connected to AP */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_STA_CONNECTED");
            // TODO Set up connection values.
            break;
        case SYSTEM_EVENT_STA_DISCONNECTED:         /**< ESP32 station disconnected from AP */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_STA_DISCONNECTED");
            // TODO Periodically scan and / or reconnect.
            break;
        case SYSTEM_EVENT_STA_AUTHMODE_CHANGE:      /**< the auth mode of AP connected by ESP32 station changed */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_STA_AUTHMODE_CHANGE");
            break;
        case SYSTEM_EVENT_STA_GOT_IP:               /**< ESP32 station got IP from connected AP */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_STA_GOT_IP");
            break;
        case SYSTEM_EVENT_STA_LOST_IP:              /**< ESP32 station lost IP and the IP is reset to 0 */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_STA_LOST_IP");
            break;
        case SYSTEM_EVENT_STA_WPS_ER_SUCCESS:       /**< ESP32 station wps succeeds in enrollee mode */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_STA_WPS_ER_SUCCESS");
            break;
        case SYSTEM_EVENT_STA_WPS_ER_FAILED:        /**< ESP32 station wps fails in enrollee mode */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_STA_WPS_ER_FAILED");
            break;
        case SYSTEM_EVENT_STA_WPS_ER_TIMEOUT:       /**< ESP32 station wps timeout in enrollee mode */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_STA_WPS_ER_TIMEOUT");
            break;
        case SYSTEM_EVENT_STA_WPS_ER_PIN:           /**< ESP32 station wps pin code in enrollee mode */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_STA_WPS_ER_PIN");
            break;
        case SYSTEM_EVENT_AP_START:                 /**< ESP32 soft-AP start */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_AP_START");
            break;
        case SYSTEM_EVENT_AP_STOP:                  /**< ESP32 soft-AP stop */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_AP_STOP");
            break;
        case SYSTEM_EVENT_AP_STACONNECTED:          /**< a station connected to ESP32 soft-AP */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_AP_STACONNECTED");
            // TODO Set up connection values.
            break;
        case SYSTEM_EVENT_AP_STADISCONNECTED:       /**< a station disconnected from ESP32 soft-AP */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_AP_STADISCONNECTED");
            // TODO
            break;
        case SYSTEM_EVENT_AP_STAIPASSIGNED:         /**< ESP32 soft-AP assign an IP to a connected station */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_AP_STAIPASSIGNED");
            // TODO Set up connection values.
            break;
        case SYSTEM_EVENT_AP_PROBEREQRECVED:        /**< Receive probe request packet in soft-AP interface */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_AP_PROBEREQRECVED");
            break;
        case SYSTEM_EVENT_GOT_IP6:                  /**< ESP32 station or ap or ethernet interface v6IP addr is preferred */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_GOT_IP6");
            break;
        case SYSTEM_EVENT_ETH_START:                /**< ESP32 ethernet start */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_ETH_START");
            break;
        case SYSTEM_EVENT_ETH_STOP:                 /**< ESP32 ethernet stop */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_ETH_STOP");
            break;
        case SYSTEM_EVENT_ETH_CONNECTED:            /**< ESP32 ethernet phy link up */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_ETH_CONNECTED");
            break;
        case SYSTEM_EVENT_ETH_DISCONNECTED:         /**< ESP32 ethernet phy link down */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_ETH_DISCONNECTED");
            break;
        case SYSTEM_EVENT_ETH_GOT_IP:               /**< ESP32 ethernet got IP from connected AP */
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_ETH_GOT_IP");
            break;
        case SYSTEM_EVENT_MAX:
            if(DEBUG_LEVEL >= 3) Serial.println("SYSTEM_EVENT_MAX");
            break;
    }
}

void sendDataUdp()
{
    // send a reply, to the IP address and port that sent us the packet we received
    if(remoteIP == IPAddress(0, 0, 0, 0))
    {
        if(DEBUG_LEVEL >= 3) Serial.println("Abort sending to local UDP port");
        return;
    }
    Udp.beginPacket(remoteIP, serverPort);

    for(auto i = 0; i < packetBufferLen / 2; i++)
    {
        auto posX = i;
        auto posY = i + packetBufferLen / 2;
        auto shift = i * packetBufferLen;
        packetBuffer[posX] = (byte)(absX >> shift);
        packetBuffer[posY] = (byte)(absY >> shift);
    }

    Udp.write(packetBuffer, packetBufferLen);
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

        if(remoteIP == WiFi.localIP() || packetSize != packetBufferLen)
        {
            if(DEBUG_LEVEL >= 3) Serial.println("Listening to local ip or incorrect buffer length. Flushing and aborting.");
            Udp.flush();
            return;
        }

        // read the packet into packetBufffer
        Udp.read(packetBuffer, packetBufferLen);

        trackX = 0;
        trackY = 0;
        for(auto i = 0; i < packetBufferLen / 2; i++)
        {
            auto posX = i;
            auto posY = i + packetBufferLen / 2;
            auto shift = i * packetBufferLen;
            trackX = (packetBuffer[posX] << shift) | trackX;
            trackY = (packetBuffer[posY] << shift) | trackY;
        }
        if(DEBUG_LEVEL >= 2)
        {
            Serial.println("Parsed packet:");
            Serial.println("X:\t" + String(trackX));
            Serial.println("Y:\t" + String(trackY));
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
    // Source: https://math.stackexchange.com/a/1596518
    double rad = atan2f(trackX - absX, trackY - absY);
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
        Serial.print("trackX: ");
        Serial.println(trackX);
        Serial.print("trackY: ");
        Serial.println(trackY);
        Serial.print("absX: ");
        Serial.println(absX);
        Serial.print("absY: ");
        Serial.println(absY);
        Serial.print("rad: ");
        Serial.println(rad);
        Serial.print("deg: ");
        Serial.println(deg);
    }
}

void loop()
{
    if(millis() - comTimeStamp > COM_DELAY)
    {
        // Handle WiFi communication
        receiveDataUdp();
        sendDataUdp();
        calcBearing();
        comTimeStamp = millis();
    }


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
            Select::updateSelect(xyDelta[0], xyDelta[1]);
            break;
        case 2:
            //Waldo::updateWaldo(xyDelta[0], xyDelta[1]);
            Serial.println("Waldo App");
            break;
        case 3:
            drawImageToDisplay();
            break;
        default:
            M5.Lcd.setTextSize(1);
            M5.Lcd.setTextColor(WHITE, BLACK);
            M5.Lcd.setCursor(0,0);
            M5.Lcd.println("Error: \"app\" value unknown!");
    }

    if(printMotBrToDisplay && app != 3)
    {
        drawMotBrToDisplay();
    }

    if(M5.BtnA.wasPressed())
    {
        prevApp = app;
        app = 0;
        M5.Lcd.fillScreen(BLACK);
    }
    if(M5.BtnB.wasPressed())
    {
        preventAppExit = !preventAppExit;
    }
    if(M5.BtnC.wasPressed())
    {
        printMotBrToDisplay = !printMotBrToDisplay;
        M5.Lcd.fillScreen(BLACK);
    }

    M5.update();

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
    if(DEBUG_LEVEL >= 2) Serial.println("performSROMdownload()");

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
    if(DEBUG_LEVEL >= 2) Serial.println("SROM_ID RETURN: " + String(i));
}

void configureRegisters()
{
    if(DEBUG_LEVEL >= 2) Serial.println("configureRegisters()");

    // TODO Configure registers (write to config registers)

    // disable Rest mode
    /*writeRegister(REGISTER_CONFIG2, 0x00);*/
    /*if(DEBUG_LEVEL >= 2) Serial.println("disable Rest mode");*/

    // Set lift detection height threshold
    writeRegister(REGISTER_LIFT_CONFIG, 0x03); // 0x03 = nominal height + 3mm (default: 0x02 = nominal height + 2mm)
    if(DEBUG_LEVEL >= 2) Serial.println("set lift detection");
}

// interrupt callback for motion pin
void onMovement()
{
    if(DEBUG_LEVEL >= 3) Serial.println("onMovement()");

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
    M5.Lcd.setTextSize(1);
    M5.Lcd.setTextColor(WHITE, BLACK);
    M5.Lcd.setCursor(0,0);
    // Draw motion bit and registers if MOT bit is set
    if(hasMoved)
    {
        M5.Lcd.println("MOT: Motion occurred");
        M5.Lcd.println("Delta X: " + String(xyDelta[0]) + "      ");
        M5.Lcd.println("Delta Y: " + String(xyDelta[1]) + "      ");

        // TODO Figure out xyDelta sending
        /*Serial.write(xyDelta[0]);*/
        /*Serial.write(xyDelta[1]);*/
        /*Serial.write(0xFE);*/
    }
    else
    {
        M5.Lcd.println("MOT: No motion      ");
        M5.Lcd.println("Delta X: 0     ");
        M5.Lcd.println("Delta Y: 0     ");
    }

    // Draw absoulte position (currently determined with relative tracking)
    M5.Lcd.println("Absolute X: " + String(absX) + "            ");
    M5.Lcd.println("Absolute Y: " + String(absY) + "            ");

    // Draw Lift_Stat bit
    if(liftOff)
    {
        M5.Lcd.println("Lift_Stat: Chip lifted    ");
    }
    else
    {
        M5.Lcd.println("Lift_Stat: Chip on surface");
    }

    // Draw cumulative lift of state (lift off buffer)
    if(cumLiftOff)
    {
        M5.Lcd.println("Cumulative Lift State: Chip lifted    ");
    }
    else
    {
        M5.Lcd.println("Cumulative Lift State: Chip on surface");
    }

    // Draw OP_Mode[1:0] bit
    switch(opMode)
    {
        case 0:
            M5.Lcd.println("OP_Mode: Run mode       ");
            break;
        case 1:
            M5.Lcd.println("OP_Mode: Rest 1         ");
            break;
        case 2:
            M5.Lcd.println("OP_Mode: Rest 2         ");
            break;
        case 3:
            M5.Lcd.println("OP_Mode: Rest 3         ");
            break;
        default:
            M5.Lcd.println("OP_Mode evaluation error");
    }

    // Draw Observation/SROM_RUN value
    if(sromRun)
    {
        M5.Lcd.println("SROM_RUN: SROM running    ");
    }
    else
    {
        M5.Lcd.println("SROM_RUN: SROM not running");
    }

    // Draw SQUAL value / number of features
    M5.Lcd.println("SQUAL: " + String(squal) + "   ");
    M5.Lcd.println("Number of Features: " + String(numFeatures) + "     ");

    // Draw Raw_Data_Sum value
    M5.Lcd.println("Raw_Data_Sum: " + String(rawDataSum) + "   ");
    M5.Lcd.println("Average Raw Data: " + String(avgRawData) + "   ");

    // Draw Maximum_Raw_Data value
    M5.Lcd.println("Maximum_Raw_Data: " + String(maxRawData) + "   ");

    // Draw Minimum_Raw_Data value
    M5.Lcd.println("Minimum_Raw_Data: " + String(minRawData) + "   ");

    // Draw Shutter value
    M5.Lcd.println("Shutter: " + String(shutter) + "     ");
}

// Send motion burst values over serial
void sendMotBrOverSerial()
{
    // Send motion bit and registers if MOT bit is set
    if(hasMoved)
    {
        if(DEBUG_LEVEL >= 3) Serial.println("MOT: Motion occurred");
        if(DEBUG_LEVEL >= 1) Serial.println("Delta X: " + String(xyDelta[0]));
        if(DEBUG_LEVEL >= 1) Serial.println("Delta Y: " + String(xyDelta[1]));

        // TODO Figure out xyDelta sending
        /*Serial.write(xyDelta[0]);*/
        /*Serial.write(xyDelta[1]);*/
        /*Serial.write(0xFE);*/
    }
    else
    {
        if(DEBUG_LEVEL >= 3) Serial.println("MOT: No motion");
        if(DEBUG_LEVEL >= 1) Serial.println("Delta X: 0");
        if(DEBUG_LEVEL >= 1) Serial.println("Delta Y: 0");
    }

    // Send absoulte position (currently determined with relative tracking)
    if(DEBUG_LEVEL >= 3) Serial.println("Absolute X: " + String(absX));
    if(DEBUG_LEVEL >= 3) Serial.println("Absolute Y: " + String(absY));

    // Send Lift_Stat bit
    if(liftOff)
    {
        if(DEBUG_LEVEL >= 2) Serial.println("Lift_Stat: Chip lifted");
    }
    else
    {
        if(DEBUG_LEVEL >= 2) Serial.println("Lift_Stat: Chip on surface");
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
    if(DEBUG_LEVEL >= 3)
    {
        if(sromRun)
        {
            Serial.println("SROM_RUN: SROM running");
        }
        else
        {
            Serial.println("SROM_RUN: SROM not running");
        }
    }

    // Send SQUAL value / number of features
    if(DEBUG_LEVEL >= 3) Serial.println("SQUAL: " + String(squal));
    if(DEBUG_LEVEL >= 3) Serial.println("Number of Features: " + String(numFeatures));

    // Send Raw_Data_Sum value
    if(DEBUG_LEVEL >= 3) Serial.println("Raw_Data_Sum: " + String(rawDataSum));
    if(DEBUG_LEVEL >= 2) Serial.println("Average Raw Data: " + String(avgRawData));

    // Send Maximum_Raw_Data value
    if(DEBUG_LEVEL >= 3) Serial.println("Maximum_Raw_Data: " + String(maxRawData));

    // Send Minimum_Raw_Data value
    if(DEBUG_LEVEL >= 3) Serial.println("Minimum_Raw_Data: " + String(minRawData));

    // Send Shutter value
    if(DEBUG_LEVEL >= 3) Serial.println("Shutter: " + String(shutter));
}

// TODO Maybe use a array of data values and medians/averages to prevent outlier problems
void findAppPosition()
{
    if(liftOff && !prevLiftOff && !preventAppExit)
        /*if(cumLiftOff && !preventAppExit)*/
    {
        // TODO prevent flickering (app switching on the between liftOff/!liftOff)
        prevApp = app;
        app = 0;
        M5.Lcd.fillScreen(BLACK);
    }
    else if(!liftOff)
        /*else if(!cumLiftOff)*/
    {
        if(avgRawData >= 16 && avgRawData <= 22 &&
                shutter >= 128 && shutter <= 145)
        {
            prevApp = app;
            app = 1;
            M5.Lcd.fillScreen(BLACK);
        }
        else if(avgRawData >= 18 && avgRawData <= 25 &&
                shutter >= 98 && shutter <= 111)
        {
            prevApp = app;
            app = 2;
            M5.Lcd.fillScreen(BLACK);
        }
        else if(avgRawData >= 23 && avgRawData <= 30 &&
                shutter >= 89 && shutter <= 94)
        {
            prevApp = app;
            app = 3;
            M5.Lcd.fillScreen(BLACK);
        }
    }
}

void drawWelcomeScreen()
{
    /*Image::draw(muc_logo_pixel_map);*/
    M5.Lcd.setTextSize(5);
    M5.Lcd.setTextColor(RED, BLACK);
    M5.Lcd.setCursor(80, 30);
    M5.Lcd.println("Place");
    M5.Lcd.setCursor(50, 90);
    M5.Lcd.println("me on a");
    M5.Lcd.setCursor(50, 150);
    M5.Lcd.println("pattern!");
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
