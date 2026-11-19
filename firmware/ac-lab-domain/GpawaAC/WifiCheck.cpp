#include "HardwareConfig.h"
#if GPAWA_WIFI_TEST
#include <Arduino.h>
#include <WiFi.h>
#include <Wire.h>
// #include <LiquidCrystal_I2C.h>
#include <hd44780.h>
#include <hd44780ioClass/hd44780_I2Cexp.h>
#include <Keypad.h>
#if __has_include("NetworkConfig.h")
#include "NetworkConfig.h"
#else
#include "NetworkConfig.example.h"
#endif
#include "PzemFrame.h"

namespace {
// LiquidCrystal_I2C screen(hw::LCD_ADDR, 16, 2);
hd44780_I2Cexp screen;
char keys[4][4] = { { '1', '2', '3', 'A' }, { '4', '5', '6', 'B' }, { '7', '8', '9', 'C' }, { '*', '0', '#', 'D' } };
byte rows[4] = { 4, 5, 6, 7 }, columns[4] = { 10, 11, 12, 13 };
Keypad pad(makeKeymap(keys), rows, columns, 4, 4);
char entry[16] = {};
uint8_t length = 0;
enum Page { NETWORK,
            SENSOR,
            HELP };
Page page = NETWORK;
bool lcdOK = false, wifiStarted = false, hasReading = false, waiting = false;
uint32_t lastReconnect = 0, lastPrint = 0, lastDraw = 0, sentAt = 0, lastPoll = 0;
uint32_t lastGood = 0, noticeAt = 0, beepAt = 0;
bool notice = false, beeping = false;
int previousStatus = -999;
uint8_t reply[25] = {};
size_t used = 0;
pz::Reading reading{};

void line(uint8_t row, const char* value) {
  if (!lcdOK) return;
  char out[17];
  snprintf(out, sizeof out, "%-16.16s", value);
  screen.setCursor(0, row);
  screen.print(out);
}
bool credentialsPresent() {
  return nettest::SSID[0] && !strstr(nettest::SSID, "REPLACE") && !strstr(nettest::PASSWORD, "REPLACE");
}
void beginWifi() {
  if (!credentialsPresent()) {
    Serial.println("Wi-Fi: edit SSID and PASSWORD in NetworkConfig.h.");
    return;
  }
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(nettest::SSID, nettest::PASSWORD);
  wifiStarted = true;
  lastReconnect = millis();
  Serial.println("Wi-Fi: connecting; no device credentials required in this test.");
}
void pollSensor() {
  // Bounded, incremental read. No reset-energy or calibration commands.
  if (waiting) {
    while (Serial1.available() && used < sizeof reply) reply[used++] = Serial1.read();
    if (used == sizeof reply || millis() - sentAt >= 300) {
      pz::Reading candidate{};
      if (pz::decode(reply, used, hw::PZEM_ADDR, candidate)) {
        reading = candidate;
        hasReading = true;
        lastGood = millis();
      }
      waiting = false;
    }
  }
  if (!waiting && millis() - lastPoll >= 1000) {
    lastPoll = millis();
    for (unsigned i = 0; i < 128 && Serial1.available(); ++i) Serial1.read();
    uint8_t request[8] = { hw::PZEM_ADDR, 4, 0, 0, 0, 10, 0, 0 };
    const uint16_t crc = pz::crc(request, 6);
    request[6] = uint8_t(crc);
    request[7] = uint8_t(crc >> 8);
    used = 0;
    Serial1.write(request, sizeof request);
    waiting = true;
    sentAt = millis();
  }
}
void keyInput() {
  char k = pad.getKey();
  if (!k) return;
  notice = false;
  if (k >= '0' && k <= '9') {
    if (length < 15) {
      entry[length++] = k;
      entry[length] = 0;
    }
  } else if (k == '*') {
    if (length) entry[--length] = 0;
  } else if (k == 'C') {
    memset(entry, 0, sizeof entry);
    length = 0;
  } else if (k == 'A') {
    page = HELP;
  } else if (k == 'B') {
    page = SENSOR;
  } else if (k == 'D') {
    page = NETWORK;
  } else if (k == '#') {
    notice = true;
    noticeAt = millis();
    // Do not log digits, send a request, grant credit or issue a success beep.
    Serial.println("Token NOT sent: diagnostic mode. Provisioning required.");
  }
}
void drawTest() {
  if (millis() - lastDraw < 180) return;
  lastDraw = millis();
  if (notice && millis() - noticeAt < 2500) {
    line(0, "Token NOT sent");
    line(1, "Provision first");
    return;
  }
  if (length) {
    line(0, entry);
    line(1, "# Send  * Delete");
    return;
  }
  if (page == HELP) {
    line(0, "No bound device");
    line(1, "D WiFi / B PZEM");
    return;
  }
  if (page == SENSOR) {
    if (!hasReading || millis() - lastGood > 3500) {
      line(0, "PZEM unavailable");
      line(1, "D: WiFi status");
      return;
    }
    char a[32], b[32];
    snprintf(a, sizeof a, "%.1fV %.1fW", reading.mv / 1000.0, reading.mw / 1000.0);
    snprintf(b, sizeof b, "%lu Wh total", (unsigned long)reading.wh);
    line(0, a);
    line(1, b);
    return;
  }
  if (!wifiStarted) {
    line(0, "Set WiFi config");
    line(1, "NetworkConfig.h");
  } else if (WiFi.status() == WL_CONNECTED) {
    line(0, "WiFi connected");
    line(1, WiFi.localIP().toString().c_str());
  } else {
    line(0, "WiFi connecting");
    line(1, "Check hotspot");
  }
}
}
void wifiCheckSetup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("\n--- gPawa Wi-Fi + keypad + PZEM diagnostics ---");
  Serial.println("NO relay control. NO credit writes. NO device API requests.");
  // The relay GPIO is deliberately untouched. Disconnect relay supply physically.
  pinMode(hw::BEEP, OUTPUT);
  digitalWrite(hw::BEEP, HIGH);
  beepAt = millis();
  beeping = true;
  beginWifi();  // Independent of LCD, device ID, storage ID, secret and CA.
  Wire.begin(hw::SDA_PIN, hw::SCL_PIN);
  Wire.setTimeOut(50);
  Wire.beginTransmission(hw::LCD_ADDR);
  lcdOK = Wire.endTransmission() == 0;
  if (lcdOK) {
    screen.init();
    screen.backlight();
    Wire.begin(hw::SDA_PIN, hw::SCL_PIN);
  } else Serial.println("LCD not found; Wi-Fi test continues on Serial Monitor.");
  Serial1.begin(9600, SERIAL_8N1, hw::RX, hw::TX);
}
void wifiCheckLoop() {
  if (beeping && millis() - beepAt >= 90) {
    digitalWrite(hw::BEEP, LOW);
    beeping = false;
  }
  if (wifiStarted) {
    const int status = (int)WiFi.status();
    if (status != previousStatus) {
      previousStatus = status;
      if (status == WL_CONNECTED) {
        Serial.print("Wi-Fi OK. Local IP: ");
        Serial.println(WiFi.localIP());
        Serial.printf("Signal: %d dBm\n", WiFi.RSSI());
        Serial.println("Wi-Fi association only; TLS and Django auth not tested.");
      } else Serial.printf("Wi-Fi not connected (status %d).\n", status);
    }
    if (status != WL_CONNECTED && millis() - lastReconnect >= 30000) {
      lastReconnect = millis();
      WiFi.reconnect();
      Serial.println("Wi-Fi: retrying connection.");
    }
  }
  pollSensor();
  keyInput();
  drawTest();
  if (millis() - lastPrint >= 10000) {
    lastPrint = millis();
    if (hasReading && millis() - lastGood <= 3500)
      Serial.printf("PZEM: %lu mV, %lu mA, %lu mW, %lu Wh TOTAL (not credit).\n",
                    (unsigned long)reading.mv, (unsigned long)reading.ma,
                    (unsigned long)reading.mw, (unsigned long)reading.wh);
    else Serial.println("PZEM unavailable; USB-only test can continue.");
  }
  delay(2);
}
#endif
