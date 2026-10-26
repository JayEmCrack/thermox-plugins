/*
  ThermoX Bench - hardware test for the ThermoX one-board PCB
  Target board : ESP32 DevKit 30-pin (Arduino-ESP32 core 3.x)
  Libraries    : OneWire, DallasTemperature, U8g2 (same as ThermoX.ino)

  Flash this first, before ThermoX.ino, to check every part of a newly built board one by one.
  Open the Serial Monitor at 115200 baud (line ending: any). The OLED shows the same live values.

  Live values, every second: water temperature, battery voltage, charger, buttons, fan rpm, Peltier.
  Commands (type the letter, press Enter):
    f   fan test: 0 %, 50 %, 100 % for 4 s each, prints the rpm of each step
    h   Peltier HEAT test: 30 % power for 10 s, fan at 100 %
    c   Peltier COOL test: 30 % power for 10 s, fan at 100 %
    x   stop everything (Peltier and fan off)
    o   OLED test pattern for 3 s
    ?   this help

  Safety, so a wiring mistake cannot overheat anything:
    - the Peltier only runs with a working temperature sensor, 10 s at 30 % at most, with the fan at 100 %
    - a Peltier test is refused while a charger is plugged in, or within 60 s of the last one
      (rest before reversing), and stops at once if the water goes above 50 C or below 5 C
  Pins are the same as ThermoX.ino.
*/
#include <Arduino.h>
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <U8g2lib.h>

// ---------------- Pins (as in ThermoX.ino) ----------------
constexpr uint8_t PIN_BTN_DOWN = 32, PIN_BTN_UP = 33;
constexpr uint8_t PIN_SDA = 21, PIN_SCL = 22;
constexpr uint8_t PIN_LPWM = 27, PIN_RPWM = 26, PIN_LEN = 13, PIN_REN = 25;
constexpr uint8_t PIN_ONEWIRE = 14;
constexpr uint8_t PIN_FAN_PWM = 23, PIN_FAN_TACH = 34;
constexpr uint8_t PIN_BATT_ADC = 35, PIN_CHG_DET = 19;

constexpr float    BATT_DIVIDER = 5.545f;      // R3 100k / R4 22k
constexpr bool     HEAT_ON_RPWM = true;        // same as ThermoX.ino
constexpr uint8_t  FAN_PULSES_PER_REV = 2;
constexpr uint32_t PWM_TEC_HZ = 20000, PWM_FAN_HZ = 25000;
constexpr uint8_t  PWM_BITS = 8;
constexpr uint8_t  TEST_DUTY = 77;             // 30 % of 255
constexpr uint32_t TEST_MS = 10000, REST_MS = 60000, FAN_STEP_MS = 4000;
constexpr float    TEST_MAX_C = 50.0f, TEST_MIN_C = 5.0f;

OneWire oneWire(PIN_ONEWIRE);
DallasTemperature ds(&oneWire);
U8G2_SH1107_PIMORONI_128X128_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);

enum Test { T_NONE, T_FAN, T_HEAT, T_COOL, T_OLED };
const char* TEST_TXT[] = {"none", "FAN", "HEAT", "COOL", "OLED"};
Test test = T_NONE;
uint32_t testSince = 0, lastTecEnd = 0;
bool tecUsed = false;
uint8_t fanDuty = 0, tecDuty = 0;
float waterC = NAN, battV = NAN;
uint16_t fanRpm = 0;
volatile uint32_t tachPulses = 0;
bool charging = false;
int fanStep = -1;                              // step of the fan test, -1 = not started

void IRAM_ATTR onTach() { tachPulses = tachPulses + 1; }

void setFan(uint8_t d) { fanDuty = d; ledcWrite(PIN_FAN_PWM, d); }

void tecStop() {
  ledcWrite(PIN_RPWM, 0); ledcWrite(PIN_LPWM, 0);
  digitalWrite(PIN_REN, LOW); digitalWrite(PIN_LEN, LOW);
  if (tecDuty) { lastTecEnd = millis(); tecUsed = true; }
  tecDuty = 0;
}

void tecDrive(bool heat, uint8_t duty) {
  bool useR = heat == HEAT_ON_RPWM;
  digitalWrite(PIN_REN, HIGH); digitalWrite(PIN_LEN, HIGH);
  ledcWrite(useR ? PIN_LPWM : PIN_RPWM, 0);   // opposite side off first
  ledcWrite(useR ? PIN_RPWM : PIN_LPWM, duty);
  tecDuty = duty;
}

void stopAll(const char* why) {
  tecStop(); setFan(0); test = T_NONE;
  Serial.printf(">> stopped: %s\n", why);
}

// ---------------- Inputs ----------------
void readSensor() {
  static bool requested = false; static uint32_t t0 = 0;
  if (!requested) { ds.requestTemperatures(); t0 = millis(); requested = true; return; }
  if (millis() - t0 < 800) return;
  float t = ds.getTempCByIndex(0);
  requested = false;
  waterC = (t != DEVICE_DISCONNECTED_C && t > -40 && t < 120) ? t : NAN;
}

void readFan() {
  static uint32_t t0 = 0; uint32_t now = millis();
  if (now - t0 < 1000) return;
  noInterrupts(); uint32_t p = tachPulses; tachPulses = 0; interrupts();
  fanRpm = (uint32_t)p * 60000UL / (now - t0) / FAN_PULSES_PER_REV;
  t0 = now;
}

void readPower() {
  battV = analogReadMilliVolts(PIN_BATT_ADC) / 1000.0f * BATT_DIVIDER;
  charging = digitalRead(PIN_CHG_DET) == HIGH;
}

// ---------------- Tests ----------------
void startTest(Test t) {
  uint32_t now = millis();
  if (t == T_HEAT || t == T_COOL) {
    if (charging)      { Serial.println(">> refused: charger plugged in"); return; }
    if (isnan(waterC)) { Serial.println(">> refused: no temperature reading (check J9 TEMP and R2)"); return; }
    if (tecUsed && now - lastTecEnd < REST_MS) {
      Serial.printf(">> refused: Peltier resting, %lu s left\n", (unsigned long)((REST_MS - (now - lastTecEnd)) / 1000 + 1));
      return;
    }
  }
  tecStop(); setFan(0);
  test = t; testSince = now; fanStep = -1;
  switch (t) {
    case T_FAN:  Serial.println(">> fan test: 0 %, 50 %, 100 %"); break;
    case T_HEAT: Serial.println(">> Peltier HEAT test: 30 % for 10 s, fan 100 %"); setFan(255); tecDrive(true, TEST_DUTY); break;
    case T_COOL: Serial.println(">> Peltier COOL test: 30 % for 10 s, fan 100 %"); setFan(255); tecDrive(false, TEST_DUTY); break;
    case T_OLED: Serial.println(">> OLED test pattern"); break;
    default: break;
  }
}

void runTest() {
  uint32_t el = millis() - testSince;
  if (test == T_FAN) {
    int stepNo = el / FAN_STEP_MS;
    if (stepNo != fanStep) {
      if (fanStep >= 0) Serial.printf("   fan %3u %%: %u rpm\n", (unsigned)(fanStep * 50), fanRpm);
      fanStep = stepNo;
      if (stepNo > 2) { stopAll("fan test done"); return; }
      setFan(stepNo == 0 ? 0 : stepNo == 1 ? 128 : 255);
    }
  } else if (test == T_HEAT || test == T_COOL) {
    if (charging) { stopAll("charger plugged in"); return; }
    if (isnan(waterC) || waterC > TEST_MAX_C || waterC < TEST_MIN_C) { stopAll("temperature out of range"); return; }
    if (el > TEST_MS) {
      tecStop();
      setFan(0);
      Serial.printf(">> %s test done. Water %.2f C. Touch the Peltier side that should be %s.\n",
                    TEST_TXT[test], waterC, test == T_HEAT ? "warm" : "cold");
      test = T_NONE;
    }
  } else if (test == T_OLED && el > 3000) {
    test = T_NONE; Serial.println(">> OLED test done");
  }
}

void handleSerial() {
  while (Serial.available()) {
    char c = tolower(Serial.read());
    switch (c) {
      case 'f': startTest(T_FAN); break;
      case 'h': startTest(T_HEAT); break;
      case 'c': startTest(T_COOL); break;
      case 'o': startTest(T_OLED); break;
      case 'x': stopAll("by command"); break;
      case '?': case 'm':
        Serial.println("f fan test | h heat test | c cool test | x stop | o OLED test | ? help"); break;
      default: break;
    }
  }
}

// ---------------- Output ----------------
void printStatus() {
  static uint32_t t0 = 0; if (millis() - t0 < 1000) return; t0 = millis();
  char t[10] = "--";
  if (!isnan(waterC)) snprintf(t, sizeof t, "%.2f", waterC);
  Serial.printf("TEMP %s C | BATT %.2f V | CHARGER %s | BTN1 %s BTN2 %s | FAN %u%% %u rpm | PELTIER %s %u%% | test %s\n",
                t, battV, charging ? "IN" : "out",
                digitalRead(PIN_BTN_DOWN) == LOW ? "DOWN" : "up", digitalRead(PIN_BTN_UP) == LOW ? "DOWN" : "up",
                fanDuty * 100U / 255, fanRpm, tecDuty ? (test == T_HEAT ? "HEAT" : "COOL") : "off",
                tecDuty * 100U / 255, TEST_TXT[test]);
}

void drawOled() {
  static uint32_t t0 = 0; if (millis() - t0 < 250) return; t0 = millis();
  char b[32];
  oled.clearBuffer();
  if (test == T_OLED) {
    for (int i = 0; i < 128; i += 8) { oled.drawFrame(i / 2, i / 2, 128 - i, 128 - i); }
    oled.setFont(u8g2_font_6x12_tr); oled.drawStr(34, 68, "OLED OK");
    oled.sendBuffer(); return;
  }
  oled.setFont(u8g2_font_6x12_tr);
  oled.drawStr(2, 12, "ThermoX BENCH");
  oled.drawHLine(0, 16, 128);
  if (isnan(waterC)) snprintf(b, sizeof b, "Temp  --  (no sensor)"); else snprintf(b, sizeof b, "Temp  %.2f C", waterC);
  oled.drawStr(2, 30, b);
  snprintf(b, sizeof b, "Batt  %.2f V", battV); oled.drawStr(2, 44, b);
  snprintf(b, sizeof b, "Charger %s", charging ? "IN" : "out"); oled.drawStr(2, 58, b);
  snprintf(b, sizeof b, "B1 %s  B2 %s", digitalRead(PIN_BTN_DOWN) == LOW ? "DOWN" : "up",
           digitalRead(PIN_BTN_UP) == LOW ? "DOWN" : "up");
  oled.drawStr(2, 72, b);
  snprintf(b, sizeof b, "Fan %u%%  %u rpm", fanDuty * 100U / 255, fanRpm); oled.drawStr(2, 86, b);
  snprintf(b, sizeof b, "Peltier %s %u%%", tecDuty ? (test == T_HEAT ? "HEAT" : "COOL") : "off", tecDuty * 100U / 255);
  oled.drawStr(2, 100, b);
  snprintf(b, sizeof b, "Test: %s", TEST_TXT[test]); oled.drawStr(2, 116, b);
  oled.sendBuffer();
}

// ---------------- Arduino ----------------
void setup() {
  Serial.begin(115200);
  pinMode(PIN_REN, OUTPUT); pinMode(PIN_LEN, OUTPUT);
  digitalWrite(PIN_REN, LOW); digitalWrite(PIN_LEN, LOW);
  ledcAttach(PIN_RPWM, PWM_TEC_HZ, PWM_BITS); ledcAttach(PIN_LPWM, PWM_TEC_HZ, PWM_BITS);
  ledcAttach(PIN_FAN_PWM, PWM_FAN_HZ, PWM_BITS);
  tecStop(); setFan(0);
  pinMode(PIN_BTN_DOWN, INPUT_PULLUP); pinMode(PIN_BTN_UP, INPUT_PULLUP);
  pinMode(PIN_FAN_TACH, INPUT);                  // external 10k pull-up (R1)
  attachInterrupt(digitalPinToInterrupt(PIN_FAN_TACH), onTach, FALLING);
  pinMode(PIN_CHG_DET, INPUT);                   // R5/R6 divider from J10
  analogSetPinAttenuation(PIN_BATT_ADC, ADC_11db);
  Wire.begin(PIN_SDA, PIN_SCL);
  oled.setI2CAddress(0x3C << 1);
  oled.begin();
  ds.begin(); ds.setWaitForConversion(false); ds.setResolution(12);
  Serial.println();
  Serial.println("ThermoX Bench ready. Commands: f fan | h heat | c cool | x stop | o OLED | ? help");
  Serial.printf("DS18B20 sensors found: %d\n", ds.getDeviceCount());
}

void loop() {
  readSensor(); readFan(); readPower();
  handleSerial();
  runTest();
  printStatus();
  drawOled();
}
