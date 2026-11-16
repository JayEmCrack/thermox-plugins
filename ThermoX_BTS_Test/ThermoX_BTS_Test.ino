/*
  ThermoX BTS7960 test - finds out why M+ / M- stays at 0 V
  Target board : ESP32 DevKit 30-pin (Arduino-ESP32 core 3.x), "ESP32 Dev Module"
  Library      : U8g2 (same as ThermoX.ino). No temperature sensor and no fan signal is needed.

  What it does:
   1. At power-up it tests the four ESP32 pins that go to the BTS7960 (R_EN, RPWM, LPWM, L_EN):
      each pin is driven HIGH and LOW and read back (finds a short), then read with a weak pull-up
      (shows whether the BTS7960 is seen on the other end of the wire).
   2. Button 1 switches the BTS7960 on through RPWM, button 2 through LPWM. The outputs are plain
      HIGH / LOW (no PWM), so a multimeter shows steady voltages. Press the same button again to stop.
      It stops by itself after 60 s. The other direction is refused for 30 s after a stop.
   3. The Serial Monitor (115200 baud) and the OLED say what to measure and what it must read.

  Serial commands: r = RPWM on, l = LPWM on, x = off, t = repeat the pin test (only while off).
  The fan output is at 100 % all the time, so the Peltier hot side always has air.
  Pins are the same as ThermoX.ino. Flash ThermoX.ino again when the BTS7960 works.
*/
#include <Arduino.h>
#include <Wire.h>
#include <U8g2lib.h>

// ---------------- Pins (as in ThermoX.ino) ----------------
constexpr uint8_t PIN_BTN_DOWN = 18;   // Button 1
constexpr uint8_t PIN_BTN_UP   = 33;   // Button 2
constexpr uint8_t PIN_SDA      = 21;
constexpr uint8_t PIN_SCL      = 22;
constexpr uint8_t PIN_LPWM     = 27;   // BTS7960 LPWM (header pin 2), board hole A19
constexpr uint8_t PIN_RPWM     = 26;   // BTS7960 RPWM (header pin 1), board hole A18
constexpr uint8_t PIN_LEN      = 13;   // BTS7960 L_EN (header pin 4), board hole A22
constexpr uint8_t PIN_REN      = 25;   // BTS7960 R_EN (header pin 3), board hole A17
constexpr uint8_t PIN_FAN_PWM  = 23;

constexpr uint32_t RUN_MAX_MS = 60000;       // a test run stops by itself after this
constexpr uint32_t REVERSE_REST_MS = 30000;  // rest before the other direction (protects the Peltier)

U8G2_SH1107_PIMORONI_128X128_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);

// The four signals, in the order of the BTS7960 header pins 1..4
const char*   SIG_NAME[4] = {"RPWM", "LPWM", "R_EN", "L_EN"};
const uint8_t SIG_PIN[4]  = {PIN_RPWM, PIN_LPWM, PIN_REN, PIN_LEN};
const char*   SIG_HOLE[4] = {"A18", "A19", "A17", "A22"};

uint8_t  dir = 0;                // 0 = off, 1 = RPWM on, 2 = LPWM on
uint8_t  lastDir = 0;            // direction of the last run
uint32_t runSince = 0, lastStop = 0;
bool     shortFound = false;     // the pin test found a pin that does not follow
uint8_t  seenMask = 0;           // bit i: the BTS7960 was seen on signal i
bool     btnLast[2] = {HIGH, HIGH};
uint32_t btnSince[2] = {0, 0};

// ---------------- Outputs ----------------
void allOff() {
  digitalWrite(PIN_RPWM, LOW); digitalWrite(PIN_LPWM, LOW);
  digitalWrite(PIN_REN, LOW);  digitalWrite(PIN_LEN, LOW);
}

void driveDir(uint8_t d) {
  digitalWrite(PIN_RPWM, LOW); digitalWrite(PIN_LPWM, LOW);   // both inputs low first
  if (d == 0) { digitalWrite(PIN_REN, LOW); digitalWrite(PIN_LEN, LOW); return; }
  digitalWrite(PIN_REN, HIGH); digitalWrite(PIN_LEN, HIGH);    // both halves must be enabled
  digitalWrite(d == 1 ? PIN_RPWM : PIN_LPWM, HIGH);
}

// ---------------- Pin test ----------------
// Only one pin is active at a time and both enables are never high together with an input,
// so the BTS7960 output stays off during this test.
void pinTest() {
  shortFound = false; seenMask = 0;
  for (int i = 0; i < 4; i++) { pinMode(SIG_PIN[i], OUTPUT); digitalWrite(SIG_PIN[i], LOW); }
  delay(20);
  Serial.println();
  Serial.println("=== ESP32 pin test (the four BTS7960 signals) ===");
  for (int i = 0; i < 4; i++) {
    uint8_t p = SIG_PIN[i];
    digitalWrite(p, HIGH); delay(5);
    bool highOk = digitalRead(p) == HIGH;
    digitalWrite(p, LOW); delay(5);
    bool lowOk = digitalRead(p) == LOW;
    pinMode(p, INPUT_PULLUP); delay(10);
    bool seen = digitalRead(p) == LOW;          // the BTS7960 input pulls the weak pull-up down
    pinMode(p, OUTPUT); digitalWrite(p, LOW);
    if (seen) seenMask |= (uint8_t)(1U << i);
    if (!highOk || !lowOk) shortFound = true;
    Serial.printf("%s  GPIO%-2u  hole %s  BTS7960 header pin %d : ", SIG_NAME[i], (unsigned)p, SIG_HOLE[i], i + 1);
    if (!highOk)      Serial.println("FAULT - stays LOW when driven HIGH: shorted to GND (solder bridge on the board?)");
    else if (!lowOk)  Serial.println("FAULT - stays HIGH when driven LOW: shorted to 3.3 V / 5 V or to the next pin");
    else if (seen)    Serial.println("ESP32 pin OK, and the BTS7960 is seen on this wire");
    else              Serial.println("ESP32 pin OK, but nothing is seen on this wire (see the note)");
  }
  if (shortFound) {
    Serial.println("RESULT: a pin is shorted. Fix it first; the test will not switch the BTS7960 on.");
  } else if (seenMask == 0x0F) {
    Serial.println("RESULT: all four pins work and all four wires reach the BTS7960.");
  } else {
    Serial.println("RESULT: the ESP32 pins work. NOTE: on a wire where nothing is seen, the Dupont wire is loose,");
    Serial.println("        broken or on the wrong header pin - or this BTS7960 board has no pull-down resistors.");
    Serial.println("        Check those wires with the meter (step 3 below).");
  }
}

void printHelp() {
  Serial.println();
  Serial.println("Button 1 or 'r' = RPWM on | Button 2 or 'l' = LPWM on | same button again or 'x' = off | 't' = pin test");
}

void printMeasure() {
  Serial.println();
  Serial.printf(">>> %s is ON (plain HIGH, no PWM). Meter on DC volts. Measure ON THE BTS7960:\n", dir == 1 ? "RPWM" : "LPWM");
  Serial.println("  1. B+  to B-  : about 12 V   (0 V: F1 fuse, SW1, wires X24 -> B+ and X26 -> B-)");
  Serial.println("  2. VCC to GND : about 5 V    (header pin 7 to pin 8; 0 V: wire A24, LM2596 output)");
  Serial.printf ("  3. to GND (header pin 8): R_EN pin 3 = 3.3 V, L_EN pin 4 = 3.3 V, RPWM pin 1 = %s, LPWM pin 2 = %s\n",
                 dir == 1 ? "3.3 V" : "0 V", dir == 2 ? "3.3 V" : "0 V");
  Serial.println("  4. M+  to M-  : about 12 V (plus or minus). Put BOTH probes on M+ and M-, not one on GND.");
  Serial.println("  1, 2 and 3 are right but 4 is 0 V: move the BTS7960 VCC wire from 5 V to 3.3 V and test again.");
}

void stopRun(const char* why) {
  if (dir != 0) { lastDir = dir; lastStop = millis(); }
  dir = 0; driveDir(0);
  Serial.printf(">>> OFF (%s)\n", why);
}

void startRun(uint8_t d) {
  uint32_t now = millis();
  if (dir != 0) { stopRun(dir == d ? "same button again" : "other button"); return; }
  if (shortFound) { Serial.println(">>> refused: the pin test found a short. Fix it, then send 't'."); return; }
  if (lastDir != 0 && lastDir != d && now - lastStop < REVERSE_REST_MS) {
    Serial.printf(">>> refused: wait %lu s before the other direction\n",
                  (unsigned long)((REVERSE_REST_MS - (now - lastStop)) / 1000 + 1));
    return;
  }
  dir = d; runSince = now; driveDir(d);
  printMeasure();
}

// ---------------- Inputs ----------------
bool pressed(uint8_t i, uint8_t pin) {          // true once per press (30 ms debounce)
  bool s = digitalRead(pin); uint32_t now = millis();
  if (s != btnLast[i] && now - btnSince[i] > 30) {
    btnSince[i] = now; btnLast[i] = s;
    return s == LOW;
  }
  return false;
}

void handleSerial() {
  while (Serial.available()) {
    char c = (char)tolower(Serial.read());
    if (c == 'r') startRun(1);
    else if (c == 'l') startRun(2);
    else if (c == 'x') stopRun("by command");
    else if (c == 't') { if (dir == 0) { pinTest(); printHelp(); } else Serial.println(">>> switch off first ('x')"); }
    else if (c == '?' || c == 'h') printHelp();
  }
}

// ---------------- Output ----------------
// While running, the four pins are read back: a pin that does not follow is shorted.
bool pinsFollow() {
  bool ok = digitalRead(PIN_REN) == HIGH && digitalRead(PIN_LEN) == HIGH;
  ok = ok && (digitalRead(PIN_RPWM) == (dir == 1 ? HIGH : LOW));
  ok = ok && (digitalRead(PIN_LPWM) == (dir == 2 ? HIGH : LOW));
  return ok;
}

void printStatus() {
  static uint32_t t0 = 0;
  if (millis() - t0 < 2000) return;
  t0 = millis();
  Serial.printf("# %s | ESP32 pins now: R_EN=%d RPWM=%d LPWM=%d L_EN=%d | BTN1 %s BTN2 %s",
                dir == 0 ? "OFF" : dir == 1 ? "RPWM ON" : "LPWM ON",
                digitalRead(PIN_REN), digitalRead(PIN_RPWM), digitalRead(PIN_LPWM), digitalRead(PIN_LEN),
                digitalRead(PIN_BTN_DOWN) == LOW ? "DOWN" : "up", digitalRead(PIN_BTN_UP) == LOW ? "DOWN" : "up");
  if (dir != 0) Serial.printf(" | %lu s | M+ to M- must be about 12 V", (unsigned long)((millis() - runSince) / 1000));
  Serial.println();
}

void drawOled() {
  static uint32_t t0 = 0;
  if (millis() - t0 < 300) return;
  t0 = millis();
  char b[32];
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tr);
  oled.drawStr(2, 12, "BTS7960 TEST");
  oled.drawHLine(0, 16, 128);
  if (dir == 0) {
    oled.drawStr(2, 30, "OFF");
    oled.drawStr(2, 44, "Button 1 = RPWM on");
    oled.drawStr(2, 58, "Button 2 = LPWM on");
  } else {
    snprintf(b, sizeof b, "%s ON  %lu s", dir == 1 ? "RPWM" : "LPWM", (unsigned long)((millis() - runSince) / 1000));
    oled.drawStr(2, 30, b);
    oled.drawStr(2, 44, "Measure M+ to M-:");
    oled.drawStr(2, 58, "must be about 12 V");
  }
  snprintf(b, sizeof b, "REN%d RPW%d LPW%d LEN%d", digitalRead(PIN_REN), digitalRead(PIN_RPWM),
           digitalRead(PIN_LPWM), digitalRead(PIN_LEN));
  oled.drawStr(2, 76, b);
  oled.drawStr(2, 94, shortFound ? "PIN TEST: SHORT!" : "ESP32 pins: OK");
  if (!shortFound) {
    snprintf(b, sizeof b, "BTS seen on %d of 4", (int)((seenMask & 1) + ((seenMask >> 1) & 1) + ((seenMask >> 2) & 1) + ((seenMask >> 3) & 1)));
    oled.drawStr(2, 108, b);
  }
  oled.drawStr(2, 124, "Serial 115200 = help");
  oled.sendBuffer();
}

// ---------------- Arduino ----------------
void setup() {
  for (int i = 0; i < 4; i++) { pinMode(SIG_PIN[i], OUTPUT); digitalWrite(SIG_PIN[i], LOW); }
  pinMode(PIN_FAN_PWM, OUTPUT); digitalWrite(PIN_FAN_PWM, HIGH);   // fan at 100 %
  pinMode(PIN_BTN_DOWN, INPUT_PULLUP); pinMode(PIN_BTN_UP, INPUT_PULLUP);
  Serial.begin(115200);
  delay(300);
  Wire.begin(PIN_SDA, PIN_SCL);
  oled.setI2CAddress(0x3C << 1);
  oled.begin();
  Serial.println();
  Serial.println("ThermoX BTS7960 test");
  pinTest();
  printHelp();
}

void loop() {
  if (pressed(0, PIN_BTN_DOWN)) startRun(1);
  if (pressed(1, PIN_BTN_UP))   startRun(2);
  handleSerial();
  if (dir != 0) {
    if (millis() - runSince > RUN_MAX_MS) stopRun("60 s are over");
    else if (!pinsFollow()) { stopRun("a pin does not follow"); shortFound = true;
                              Serial.println(">>> FAULT: a signal pin is shorted. Send 't' for the pin test."); }
  }
  printStatus();
  drawOled();
}
