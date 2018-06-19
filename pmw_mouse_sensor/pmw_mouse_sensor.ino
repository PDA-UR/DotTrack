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

  if(SIMULATE_INPUT == 1){ return;}

  if(DEBUG_LEVEL >= 2) Serial.println("setup()");

  // setup pins
  pinMode(PIN_NCS, OUTPUT);
  pinMode(PIN_MOTION, INPUT); // maybe INPUT_PULLUP is better?
  // > The motion pin is an active low output (datasheet p.18)
  digitalWrite(PIN_MOTION, HIGH);
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
  frameCapture = false;//true;
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
    if(SIMULATE_INPUT == 0){
      readMotionBurst(rawMotBr, motBrLength);
      sendMotBrOverSerial();
    }
    Simulator::update();
    int16_t x = Simulator::get_x();
    int16_t y = Simulator::get_y();
    //Waldo::updateWaldo(x, y);
    Select::updateSelect(x,y);
  }

  if(SIMULATE_INPUT == 1){ return;}

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
    Serial.println("reset readingMotion");
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
  if(DEBUG_LEVEL >= 2) {
    Serial.print("SROM_ID RETURN: ");
    Serial.println(i);
  }
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
    liftOff = (bool)(motion & REG_MOTION_LIFT_STAT);
    if(DEBUG_LEVEL >= 3) { Serial.print("Lift_Stat: "); Serial.println(liftOff); }

    // Evaluate OP_Mode[1:0] bits
    opMode = (motion & REG_MOTION_OP_MODE) >> 1;
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
      if(DEBUG_LEVEL >= 1) Serial.println("X: " + String(xyDelta[0]));
      if(DEBUG_LEVEL >= 1) Serial.println("Y: " + String(xyDelta[0]));
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
  // FIXME: black lines
  // TODO: offset
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
// use the included python script to view the image
void sendRawOverSerial()
{
  /*uint8_t* rawResult = (uint8_t*) malloc(rawDataLength * sizeof(uint8_t));*/
  /*captureRawImage(rawResult, rawDataLength);*/


  // Original approach
  /*Serial.write(0xFD);*/
  /*for(int i = 0; i < rawDataLength; i++)*/
  /*{*/
    /*Serial.write(rawResult[i]);*/
    /*yield; // make sure WDT does not block*/
  /*}*/
  /*Serial.write(0xFE);*/
  // New approach
  // TODO The interrupt on onMovement() seems to interrupt the Serial.write()
  // Look into: https://stackoverflow.com/a/10570704
  /*if(DEBUG_LEVEL >= 2) Serial.println("rawDataLength (expected bytes): " + String(rawDataLength));*/
  /*int bytesSent = Serial.write(rawResult, rawDataLength);*/
  /*if(DEBUG_LEVEL >= 2) Serial.println("\nbytesSent: " + String(bytesSent));*/

  Serial.write(rawData, rawDataLength);
  // Paket termination byte TODO improve this (header terminate bytes)
  Serial.write(0xFE);
  /*free(rawResult);*/
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

void sendMotBrOverSerial()
{
  // Read Motion byte
  uint8_t motion = rawMotBr[0];

  // Evaluate Lift_Stat bit
  liftOff = (bool)(motion & REG_MOTION_LIFT_STAT);
  if(DEBUG_LEVEL >= 3) { Serial.print("Lift_Stat: "); Serial.println(liftOff); }

  // Evaluate OP_Mode[1:0] bits
  opMode = (motion & REG_MOTION_OP_MODE) >> 1;
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

  // Read motion registers if MOT bit is set
  if(motion & REG_MOTION_MOT_BIT)
  {
    hasMoved = true;
    /*uint8_t resultDeltaXL = rawMotBr[2];*/
    /*uint8_t resultDeltaXH = rawMotBr[3];*/
    /*uint8_t resultDeltaYL = rawMotBr[4];*/
    /*uint8_t resultDeltaYH = rawMotBr[5];*/

    xyDelta[0] = (int16_t)((rawMotBr[3] << 8) | rawMotBr[2]);
    xyDelta[1] = (int16_t)((rawMotBr[5] << 8) | rawMotBr[4]);
    if(DEBUG_LEVEL >= 1) Serial.println("X: " + String(xyDelta[0]));
    if(DEBUG_LEVEL >= 1) Serial.println("Y: " + String(xyDelta[1]));

    // TODO Figure out xyDelta sending
    /*Serial.write(xyDelta[0]);*/
    /*Serial.write(xyDelta[1]);*/
    /*Serial.write(0xFE);*/
  }

  // Read Raw_Data_Sum byte
  // The rawMotBr[7] element should be between 0-160 (0x00 - 0xA0)
  // Therefore rawDataSum 0-126
  uint8_t rawDataSum = rawMotBr[7] * 1024 / 1296;
  if(DEBUG_LEVEL >= 1) Serial.println("RDS: " + String(rawDataSum));

  // Binary debug output
  if(DEBUG_LEVEL >= 3)
  {
    for(int i = 0; i < motBrLength; i++)
    {
      switch(i)
      {
        case 0:
          Serial.print("Motion: ");
          Serial.println(rawMotBr[i], BIN);
          break;
        case 1:
          Serial.print("Observation: ");
          Serial.println(rawMotBr[i], BIN);
          break;
        case 2:
          Serial.print("Delta_X_L: ");
          Serial.println(rawMotBr[i], BIN);
          /*Serial.println(rawMotBr[i]);*/
          break;
        case 3:
          Serial.print("Delta_X_H: ");
          Serial.println(rawMotBr[i], BIN);
          break;
        case 4:
          Serial.print("Delta_Y_L: ");
          Serial.println(rawMotBr[i], BIN);
          /*Serial.println(rawMotBr[i]);*/
          break;
        case 5:
          Serial.print("Delta_Y_H: ");
          Serial.println(rawMotBr[i], BIN);
          break;
        case 6:
          Serial.print("SQUAL: ");
          Serial.println(rawMotBr[i], BIN);
          break;
        case 7:
          Serial.print("Raw_Data_Sum: ");
          Serial.println(rawMotBr[i], BIN);
          break;
        case 8:
          Serial.print("Maximum_Raw_Data: ");
          Serial.println(rawMotBr[i], BIN);
          break;
        case 9:
          Serial.print("Minimum_Raw_Data: ");
          Serial.println(rawMotBr[i], BIN);
          break;
        case 10:
          Serial.print("Shutter_Upper: ");
          Serial.println(rawMotBr[i], BIN);
          break;
        case 11:
          Serial.print("Shutter_Lower: ");
          Serial.println(rawMotBr[i], BIN);
          break;
        default:
          Serial.print("Error: ");
          Serial.println(rawMotBr[i], BIN);
      }
    }
  }
}
