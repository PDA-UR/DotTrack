#include "pmw_mouse_sensor.hpp"

WiFiClient client;
IPAddress serverIP = IPAddress(192, 168, 178, 77);
uint8_t rawData[IMG_SIZE];

void ConnectToWiFi()
{
    WiFi.mode(WIFI_STA);

    delay(100);

    uint8_t i = 0;

    if(DEBUG_LEVEL >= 2)
    {
        Serial.print("Connecting to ");
        Serial.print(ssid);
        Serial.print(" with PW ");
        Serial.println(pw);
    }

    WiFi.begin(ssid, pw);
    while (true)
    {
        if(WiFi.status() == WL_CONNECTED) break;

        if(DEBUG_LEVEL >= 2) Serial.print('.');

        delay(500);

        if ((++i % 20) == 0)
        {
            debug2("trying to connect");
        }
    }

    debug2("Connected. IP address: ");
    if(DEBUG_LEVEL >= 2) Serial.println(WiFi.localIP());
}

void ConnectToServer()
{
    while (!client.connect(serverIP, 8090)) 
    {
        debug2("connection failed");
 
        delay(1000);
    }
 
    debug2("Connected!");
}

void sendRawOverWifi()
{
    if(!client.connected()) ConnectToServer();
    client.write(rawData, rawDataLength);
    // Paket termination byte TODO improve this (header terminate bytes)
    client.write(0xFE);
}

// DEPRECATED
// send a 36x36px greyscale raw image with 8bit depth over Serial connection to the PC
// use the included python script (dottrack_stream.py) to view the image
void sendRawOverSerial()
{
    Serial.write(rawData, rawDataLength);
    // Paket termination byte TODO improve this (header terminate bytes)
    Serial.write(0xFE);
}
