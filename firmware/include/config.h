#pragma once

// ---- Fill these in for your setup ----

#define WIFI_SSID "your-wifi-ssid"
#define WIFI_PASSWORD "your-wifi-password"

// Django server address. For bench testing on the same LAN, use your PC's LAN IP
// (not "localhost" -- the ESP32 is a different machine), e.g. "http://192.168.1.50:8000"
#define SERVER_BASE_URL "http://192.168.1.50:8000"

// From the Django admin (Tracker > Devices > your device > API Token).
// Each physical device gets its own token -- do not reuse one across machines.
#define DEVICE_API_TOKEN "paste-the-device-token-here"

// ---- CAN (J1939) wiring ----
// TXD/RXD pins from the ESP32 to the CAN transceiver (SN65HVD230 / MCP2561).
// Adjust to whichever GPIOs you actually wired -- these are just commonly-free ones.
#define CAN_TX_GPIO GPIO_NUM_4
#define CAN_RX_GPIO GPIO_NUM_5

// ---- GPS wiring (UART) ----
#define GPS_RX_GPIO 16  // ESP32 RX <- GPS TX
#define GPS_TX_GPIO 17  // ESP32 TX -> GPS RX
#define GPS_BAUD 9600

// How often to send a bundled reading to the server.
#define SEND_INTERVAL_MS 30000
