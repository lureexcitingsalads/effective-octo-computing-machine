// Equipment tracker firmware -- v1 / bench-test scope.
//
// Reads J1939 hours + active fault codes off the CAN bus (listen-only, never transmits),
// plus GPS position/speed and vibration from the accelerometer, and POSTs a bundled
// reading to the Django ingestion endpoint over WiFi every SEND_INTERVAL_MS.
//
// Deliberately NOT in this version: PM2.5/temperature sensors, SD-card buffering, and the
// LoRa mesh relay path. Those come after this basic "device talks to the website" path is
// proven on the bench. See config.h for the values you need to fill in before flashing.

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <TinyGPSPlus.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include "driver/twai.h"

#include "config.h"

HardwareSerial gpsSerial(1);
TinyGPSPlus gps;
Adafruit_MPU6050 mpu;
bool mpuReady = false;

double latestHours = -1;
bool hoursUpdated = false;

struct PendingFault {
  uint32_t spn;
  uint8_t fmi;
  bool active;
};
PendingFault pendingFaults[8];
int pendingFaultCount = 0;

unsigned long lastSendTime = 0;

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(500);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println(" connected, IP: " + WiFi.localIP().toString());
  } else {
    Serial.println(" failed -- will retry in the loop");
  }
}

void setupCan() {
  twai_general_config_t g_config =
      TWAI_GENERAL_CONFIG_DEFAULT(CAN_TX_GPIO, CAN_RX_GPIO, TWAI_MODE_LISTEN_ONLY);
  // 250 kbit/s is the common J1939 default; some platforms run 500 kbit/s instead --
  // check the target machine if this never sees traffic.
  twai_timing_config_t t_config = TWAI_TIMING_CONFIG_250KBITS();
  twai_filter_config_t f_config = TWAI_FILTER_CONFIG_ACCEPT_ALL();

  if (twai_driver_install(&g_config, &t_config, &f_config) != ESP_OK) {
    Serial.println("TWAI driver install failed");
    return;
  }
  if (twai_start() != ESP_OK) {
    Serial.println("TWAI start failed");
    return;
  }
  Serial.println("TWAI (CAN) started in listen-only mode -- this device never transmits onto the bus");
}

// J1939 29-bit ID: priority(3) | reserved(1) | data page(1) | PF(8) | PS(8) | source addr(8).
// For PDU2 (broadcast) PGNs -- which both 65253 and 65226/65227 are -- PGN = bits 8-25 of the
// ID, PS included. This shortcut does NOT hold for PDU1 (peer-to-peer) PGNs; if you ever add
// one of those, the destination address (PS) needs to be masked out first.
uint32_t extractPGN(uint32_t canId) {
  return (canId >> 8) & 0x3FFFF;
}

void handleHoursMessage(const twai_message_t &msg) {
  // PGN 65253 (0xFEE5), SPN 247: engine total hours, bytes 0-3, little-endian, 0.05 hr/bit.
  if (msg.data_length_code < 4) return;
  uint32_t raw = (uint32_t)msg.data[0] | ((uint32_t)msg.data[1] << 8) |
                 ((uint32_t)msg.data[2] << 16) | ((uint32_t)msg.data[3] << 24);
  if (raw == 0xFFFFFFFF) return;  // "not available" per spec
  latestHours = raw * 0.05;
  hoursUpdated = true;
}

void queueFault(uint32_t spn, uint8_t fmi, bool active) {
  for (int i = 0; i < pendingFaultCount; i++) {
    if (pendingFaults[i].spn == spn && pendingFaults[i].fmi == fmi) {
      pendingFaults[i].active = active;
      return;
    }
  }
  if (pendingFaultCount < 8) {
    pendingFaults[pendingFaultCount++] = {spn, fmi, active};
  }
}

void handleDM1Message(const twai_message_t &msg) {
  // PGN 65226 (0xFECA), DM1 -- active diagnostic trouble codes.
  // Bytes 0-1: lamp status (not used here). Bytes 2+: 4-byte DTC entries.
  // Per DTC: SPN low byte, SPN mid byte, [SPN top 3 bits | FMI 5 bits], [SPN conv | occurrence count].
  for (int i = 2; i + 3 < msg.data_length_code; i += 4) {
    uint8_t b1 = msg.data[i];
    uint8_t b2 = msg.data[i + 1];
    uint8_t b3 = msg.data[i + 2];
    if (b1 == 0xFF && b2 == 0xFF && b3 == 0xFF) continue;  // empty slot
    uint32_t spn = (uint32_t)b1 | ((uint32_t)b2 << 8) | ((uint32_t)(b3 & 0xE0) << 11);
    uint8_t fmi = b3 & 0x1F;
    queueFault(spn, fmi, true);
  }
}

void pollCan() {
  twai_message_t message;
  while (twai_receive(&message, 0) == ESP_OK) {
    if (!(message.flags & TWAI_MSG_FLAG_EXTD)) continue;  // J1939 is always 29-bit extended IDs
    uint32_t pgn = extractPGN(message.identifier);
    if (pgn == 65253) {
      handleHoursMessage(message);
    } else if (pgn == 65226) {
      handleDM1Message(message);
    }
  }
}

void pollGps() {
  while (gpsSerial.available() > 0) {
    gps.encode(gpsSerial.read());
  }
}

bool sendReading() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected, skipping send");
    return false;
  }

  JsonDocument doc;
  doc["device_id"] = WiFi.macAddress();

  if (hoursUpdated) {
    doc["engine_hours"] = latestHours;
  }

  if (gps.location.isValid() && gps.location.isUpdated()) {
    doc["latitude"] = gps.location.lat();
    doc["longitude"] = gps.location.lng();
    if (gps.speed.isValid()) {
      doc["speed_kph"] = gps.speed.kmph();
    }
  }

  if (mpuReady) {
    sensors_event_t accel, gyro, temp;
    mpu.getEvent(&accel, &gyro, &temp);
    double magnitude = sqrt(accel.acceleration.x * accel.acceleration.x +
                            accel.acceleration.y * accel.acceleration.y +
                            accel.acceleration.z * accel.acceleration.z) /
                       9.81;
    doc["vibration_magnitude"] = magnitude;
  }

  if (pendingFaultCount > 0) {
    JsonArray faults = doc["faults"].to<JsonArray>();
    for (int i = 0; i < pendingFaultCount; i++) {
      JsonObject f = faults.add<JsonObject>();
      f["spn"] = pendingFaults[i].spn;
      f["fmi"] = pendingFaults[i].fmi;
      f["active"] = pendingFaults[i].active;
    }
  }

  String payload;
  serializeJson(doc, payload);

  HTTPClient http;
  http.begin(String(SERVER_BASE_URL) + "/api/ingest/");
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", String("Bearer ") + DEVICE_API_TOKEN);
  int status = http.POST(payload);
  String response = http.getString();
  http.end();

  Serial.printf("POST /api/ingest/ -> %d: %s\n", status, response.c_str());

  if (status == 200) {
    hoursUpdated = false;
    pendingFaultCount = 0;
    return true;
  }
  return false;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\nEquipment tracker firmware starting");

  Wire.begin();
  if (mpu.begin()) {
    mpuReady = true;
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    Serial.println("MPU6050 ready");
  } else {
    Serial.println("MPU6050 not found -- check wiring; continuing without it");
  }

  gpsSerial.begin(GPS_BAUD, SERIAL_8N1, GPS_RX_GPIO, GPS_TX_GPIO);

  connectWiFi();
  setupCan();
}

void loop() {
  pollCan();
  pollGps();

  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  if (millis() - lastSendTime > SEND_INTERVAL_MS) {
    sendReading();
    lastSendTime = millis();
  }
}
