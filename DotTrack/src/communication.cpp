#include "pmw_mouse_sensor.hpp"

int PORT_IMAGE = 8090;
int PORT_COORD = 9090;

WiFiClient client;
WiFiUDP udp;

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
    while (!client.connect(HOST_IP, PORT_IMAGE)) //serverIP
    {
        debug2("connection failed");

        //PORT_IMAGE++;
        //PORT_COORD++;
        delay(1000);
    }

    udp.begin(PORT_COORD);
 
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

void sendCoordinates(int x, int y)
{
    char buffer[50];
    sprintf(buffer, "x:%d|y:%d;", x, y);
    int len;
    uint8_t buffer_uint[50];
    for(int i = 0; i < 50; i++)
    {
        buffer_uint[i] = (uint8_t) buffer[i];
        if(buffer[i] == ';')
        {
            len = i+1;
            break;
        }
    }

    udp.beginPacket(HOST_IP, PORT_COORD);
    udp.write(buffer_uint, len);
    udp.endPacket();
}
