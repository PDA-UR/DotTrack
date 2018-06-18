#include "pmw_mouse_sensor.h"

unsigned long t_switch;

void setup()
{
  // Initialize the M5Stack object
  M5.begin();

  // Turn off/disconnect speaker
  // Source: https://twitter.com/Kongduino/status/980466157701423104
  M5.Speaker.end();

  // Lcd display
  /*M5.Lcd.println("This is software power off demo");*/
  /*M5.Lcd.println("Press the button A to power off.");*/

  // Set the wakeup button (also PowerOff)
  /*M5.setWakeupButton(BUTTON_A_PIN);*/

  /*Serial.begin(9600);*/
  // 115200 is the baudrate used by the M5Stack library
  Serial.begin(115200);
  /*Serial.begin(250000);*/
  /*Serial.begin(2000000);*/

  if(DEBUG_LEVEL >= 2) Serial.println("setup()");

  // setup pins
  pinMode(PIN_NCS, OUTPUT);
  pinMode(PIN_MOTION, INPUT); // maybe INPUT_PULLUP is better?
  // > The motion pin is an active low output (datasheet p.18)
  digitalWrite(PIN_MOTION, HIGH);
  pinMode(PIN_SCLK, OUTPUT);
  pinMode(PIN_MISO, INPUT);
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
  frameCapture = false;
  // Delay for Frame Capture burst mode (only needed once after power up/reset)
  if(frameCapture) delay(250);

  /*t_switch = millis() + 3000;*/

  // Capture single frame
  /*delay(250);*/
  /*sendRawOverSerial();*/
}

void loop()
{
  if(frameCapture)
  {
    captureRawImage(rawData, rawDataLength);
    drawImageToDisplay();
    /*sendRawOverSerial();*/
  }
  else
  {
    readMotionBurst(rawMotBr, motBrLength);
    updateMotBrValues();
    sendMotBrOverSerial();
    updateWaldo(0, 0);
  }

  // switch to frame capture mode when the sensor hits the ground
  if(!liftOff && prevLiftOff)
  {
    frameCapture = true;
    // Delay for Frame Capture burst mode (only needed once after power up/reset)
    t_switch = millis() + 3000;
  }
  /*// TODO liftOff is too sensitive for this task*/
  prevLiftOff = liftOff;

  if(t_switch < millis() && t_switch != 0)
  {
    frameCapture = false;
    t_switch = 0;
    resetSPIPort();
    resetDevice();
    performSROMdownload();
    configureRegisters();
    // TODO Maybe build a timer for faster resets when FC is not needed yet
    delay(250);
  }
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
      // INFO: y needs to be inverted to correlate with the displays x-/y-coordinates
      // fillRect(int32_t x, int32_t y, int32_t w, int32_t h, uint32_t color)
      M5.Lcd.fillRect(x*PIX_RSZ + X_OFFSET, (H_IMG-y)*PIX_RSZ + Y_OFFSET, PIX_RSZ, PIX_RSZ, color);
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
  }
  else
  {
    hasMoved = false;
    xyDelta[0] = 0;
    xyDelta[1] = 0;
  }
  // TODO Evaluate RData_1st Needed?
  // Evaluate Lift_Stat bit
  liftOff = motion & REG_MOTION_LIFT_STAT;
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

// Send motion burst values over serial
void sendMotBrOverSerial()
{
  // Send motion bit and registers if MOT bit is set
  if(hasMoved)
  {
    if(DEBUG_LEVEL >= 3) Serial.println("MOT: Motion occurred");
    if(DEBUG_LEVEL >= 1) Serial.println("X: " + String(xyDelta[0]));
    if(DEBUG_LEVEL >= 1) Serial.println("Y: " + String(xyDelta[1]));

    // TODO Figure out xyDelta sending
    /*Serial.write(xyDelta[0]);*/
    /*Serial.write(xyDelta[1]);*/
    /*Serial.write(0xFE);*/
  }
  else
  {
    if(DEBUG_LEVEL >= 3) Serial.println("MOT: No motion");
    if(DEBUG_LEVEL >= 1) Serial.println("X: 0");
    if(DEBUG_LEVEL >= 1) Serial.println("Y: 0");
  }

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
