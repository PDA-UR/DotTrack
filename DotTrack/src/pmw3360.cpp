#include "pmw_mouse_sensor.hpp"

bool hasMoved = false;
bool liftOff = false;
bool prevLiftOff = false;
bool cumLiftOff = liftOff;
uint8_t opMode = 0;
bool sromRun = false;

volatile bool readingMotion = false;
bool restEn = true;
bool rptMod = false;

int16_t cpi = DEFAULT_CPI;
int16_t cpiX = DEFAULT_CPI;
int16_t cpiY = DEFAULT_CPI;
uint8_t squal = 0;
uint16_t numFeatures = 0;
uint8_t rawDataSum = 0;
uint8_t avgRawData = 0;
uint8_t maxRawData = 0;
uint8_t minRawData = 0;
uint16_t shutter = 0;

//extern int32_t absX = 0;
//extern int32_t absY = 0;

uint8_t liftOffBuffer[LIFT_OFF_BUF_LEN];
uint8_t rawMotBr[motBrLength];
int16_t xyDelta[2];

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
    //delay(20); // 20

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
        //absX += xyDelta[0];
        //absY += xyDelta[1];

        relative_x -= xyDelta[0];
        relative_y -= xyDelta[1];
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
