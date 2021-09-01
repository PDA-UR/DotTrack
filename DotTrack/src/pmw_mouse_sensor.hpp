#ifndef __pmw_mouse_sensor_hpp__
#define __pmw_mouse_sensor_hpp__

#include <Arduino.h>
#include <M5Stack.h>
#include <M5StackUpdater.h>
#include <SPI.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <math.h>
#include "waldo.hpp"
#include "image.hpp"
#include "tools.hpp"
#include "config.hpp"
#include "utils.hpp"

// ESP32 Pins (M5STACK)
//#define PIN0 0 // Motion
#define PIN17 17 // NCS
#define PIN18 18 // SCK
#define PIN19 19 // MISO
#define PIN23 23 // MOSI
// mapped to better pin names
//#define PIN_MOTION PIN0
#define PIN_NCS PIN17
#define PIN_SCLK PIN18
#define PIN_MISO PIN19
#define PIN_MOSI PIN23

// Minimum CPI
#define MIN_CPI 100
#define DEFAULT_CPI 5000
#define MAX_CPI 12000

// Frame capture data variables
#define W_IMG 36
#define H_IMG 36
#define IMG_SIZE 1296 // W_IMG * H_IMG --> 36 * 36 = 1296

// A4 size in mm
#define A4_WIDTH 290
#define A4_HEIGHT 200

// enum for sensor values
#define AVG 0
#define SHTR 3
 

// Lift off buffer length
#define LIFT_OFF_BUF_LEN 5

// M5Stack
// M5Stack Display: 320x240
#define W_DISP 320
#define H_DISP 240

// maximum resolution for 16 bit color depth
#define W_WINDOW 230
#define H_WINDOW 230

// Resize factor for every image pixel to maximize display size
#define PIX_RSZ 6 // H_DISP / H_IMG --> 240 / 36 = 6
// Offsets to center image on the display
#define X_OFFSET 52 // (W_DISP - W_IMG * PIX_RSZ) / 2 --> (320-36*6) / 2 = 52
#define Y_OFFSET 12 // (H_DISP - H_IMG * PIX_RSZ) / 2 --> (240-36*6) / 2 = 12

const unsigned short rawDataLength = IMG_SIZE;
// Read motion burst mode
const unsigned short motBrLength = 12;

// Create sprite object (frame buffer)
extern TFT_eSprite img; // = TFT_eSprite(&M5.Lcd);

// if true prints motion burst data to display
extern bool printMotBrToDisplay;
// prevents apps being exited from liftOff state
//extern bool preventAppExit = false;

// set true by the motion interrupt when new motion data is available, set false when motion data has been processed
extern bool hasMoved;
// false when on ground, true when lift off ground (according to Lift_Stat bit in Motion register)
extern bool liftOff;
// LO state from previous loop
extern bool prevLiftOff;
// cumulative lift off state (switches to true if liftOffBuffer is all true and reverse)
extern bool cumLiftOff;
// values between  (according to OP_Mode bit in Motion register)
extern uint8_t opMode;
// SROM_RUN value (Observation byte/register)
// true/1 = SROM running
// false/0 = SROM NOT running
extern bool sromRun;
// Rest_En value
// false = rest mode disabled
// true = rest mode enabled [default]
extern bool restEn;
// Rpt_Mod value
// false = X CPI == Y CPI [default]
// true = X and Y CPI can be configured independently
extern bool rptMod;
// CPI (counts per inch) value (-1 = disabled [see Rpt_Mod p. 39])
extern int16_t cpi;
// X axis CPI (counts per inch) value (-1 = disabled [see Rpt_Mod p. 39])
extern int16_t cpiX;
// Y axis CPI (counts per inch) value (-1 = disabled [see Rpt_Mod p. 39])
extern int16_t cpiY;
// SQUAL value
extern uint8_t squal;
// Number of surface features (calculated from SQUAL value)
extern uint16_t numFeatures;
// Raw_Data_Sum value
extern uint8_t rawDataSum;
// Average Raw Data (calculated from Raw_Data_Sum value)
extern uint8_t avgRawData;
// Maximum_Raw_Data value
extern uint8_t maxRawData;
// Minimum_Raw_Data value
extern uint8_t minRawData;
// Shutter value
extern uint16_t shutter;

extern int angle;
extern double relative_x;
extern double relative_y;
extern float last_x, last_y;
extern bool receiving;

extern WiFiClient client;

// INFO: volatile not needed when using polling (and not using interrupts)
// set to true when reading motion registers (motion & delta registers) was initialized (see datasheet p. 30)
extern volatile bool readingMotion;

// lift off buffer
extern uint8_t liftOffBuffer[LIFT_OFF_BUF_LEN];
// Raw data image data
extern uint8_t rawData[IMG_SIZE];
// Raw motion burst data
extern uint8_t rawMotBr[motBrLength];
// movement distance since last update, [0] = x, [1] = y, expected values: around -1 to 1 (but can be more extreme)
extern int16_t xyDelta[2];

void resetSPIPort();
void resetDevice();
void performSROMdownload();
void configureRegisters();
void readConfigRegisters();
void captureRawImage(uint8_t* result, int resultLength);
void drawImageToDisplay();
void drawImageToDisplay_old();
void sendRawOverSerial();
void readMotionBurst(uint8_t* result, int resultLength);
void updateMotBrValues();
void evalLiftOffBuffer();

void decodeWifiAnswer();

void GetPorts();
void ConnectToWiFi();
void ConnectToServer();
void sendRawOverWifi();
void sendCoordinates(int x, int y, bool liftOff);
void drawCoordinates(float x, float y);
void drawDirection();
void updateRelativePosition();
void drawRelativePosition();
void drawEye();


#endif
