/*
  ThermoX - Portable Dual-Temperature Smart Water Bottle
  Target board : ESP32 (Arduino-ESP32 core 3.x)  -- NOT an Arduino Uno (see README.md)
  Libraries    : OneWire, DallasTemperature, U8g2

  Behaviour (per Chapters I-III):
   - User sets target 20..50 C in 1 C steps with two buttons (B1 = down, B2 = up)
   - DS18B20 measures water temp; BTS7960 drives one TEC1-12706 in either direction
   - Below target - hysteresis -> HEAT ; above target + hysteresis -> COOL ; else IDLE
   - Fan: full duty in COOL, ~50 % in HEAT, off when idle (after a short run-on)
   - SH1107 128x128 OLED shows water temp, target, mode, fan RPM, battery
*/
#include <Arduino.h>
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <U8g2lib.h>
#include <BluetoothSerial.h>   // ESP32 Classic Bluetooth (SPP)

// ---------------- Pins (as wired) ----------------
constexpr uint8_t PIN_BTN_DOWN = 32;   // Button 1
constexpr uint8_t PIN_BTN_UP   = 33;   // Button 2
constexpr uint8_t PIN_SDA      = 21;
constexpr uint8_t PIN_SCL      = 22;
constexpr uint8_t PIN_LPWM     = 27;   // BTS7960 LPWM
constexpr uint8_t PIN_RPWM     = 26;   // BTS7960 RPWM
constexpr uint8_t PIN_LEN      = 13;   // BTS7960 L_EN
constexpr uint8_t PIN_REN      = 25;   // BTS7960 R_EN
constexpr uint8_t PIN_ONEWIRE  = 14;   // DS18B20 data (4.7k pull-up to 3.3V)
constexpr uint8_t PIN_FAN_PWM  = 23;   // SUNON control (blue/PWM wire)
constexpr uint8_t PIN_FAN_TACH = 34;   // SUNON FG (input-only pin: needs external pull-up)

// Battery gauge: FUTURE ADDITION only. Leave false until the voltage divider is built
// on GPIO35 (not in the current pin list; see README.md).
constexpr bool    ENABLE_BATTERY_SENSE = false;
constexpr uint8_t PIN_BATT_ADC = 35;
constexpr float   BATT_DIVIDER = 2.0f;      // e.g. 100k/100k
constexpr float   BATT_EMPTY_V = 3.3f;      // per cell, 1S Li-ion
constexpr float   BATT_FULL_V  = 4.15f;

// ---------------- Tunables ----------------
constexpr float TARGET_MIN = 20.0f, TARGET_MAX = 50.0f, TARGET_DEFAULT = 25.0f;
constexpr float HYSTERESIS = 0.5f;           // C
constexpr float OVERTEMP_CUTOFF = 55.0f;     // C, hard stop
constexpr float UNDERTEMP_CUTOFF = 5.0f;     // C, hard stop (freezing)
constexpr float DUTY_TAPER_C = 5.0f;         // full power until within this band of target
constexpr uint8_t TEC_MAX_DUTY = 255;        // lower to limit current/battery draw
constexpr uint8_t TEC_MIN_DUTY = 90;         // below this the TEC does little useful work
constexpr bool    HEAT_ON_RPWM = true;       // swap if your wiring heats on LPWM instead
constexpr uint32_t DEADTIME_MS = 1000;       // pause when reversing current direction
constexpr uint32_t FAN_RUNON_MS = 30000;     // keep fan running after TEC stops
constexpr uint32_t SENSOR_FAIL_MS = 5000;
constexpr uint32_t FAN_STALL_GRACE_MS = 5000;
constexpr uint16_t FAN_MIN_RPM = 500;        // below this while commanded => stall
constexpr uint8_t  FAN_PULSES_PER_REV = 2;   // SUNON 4-wire FG standard

constexpr uint32_t PWM_TEC_HZ = 20000, PWM_FAN_HZ = 25000;
constexpr uint8_t  PWM_BITS = 8;

constexpr bool    ENABLE_BT_LOGGING = true;
constexpr char    BT_NAME[] = "ThermoX";
constexpr uint32_t LOG_PERIOD_MS = 1000;

// ---------------- Globals ----------------
BluetoothSerial SerialBT;
enum Mode : uint8_t { IDLE, HEAT, COOL, FAULT };
enum Fault : uint8_t { F_NONE, F_SENSOR, F_OVERTEMP, F_UNDERTEMP, F_FAN };
const char* MODE_TXT[]  = {"IDLE", "HEATING", "COOLING", "FAULT"};
const char* FAULT_TXT[] = {"", "SENSOR", "OVER TEMP", "TOO COLD", "FAN STALL"};

OneWire oneWire(PIN_ONEWIRE);
DallasTemperature ds(&oneWire);
U8G2_SH1107_128X128_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);

float waterC = NAN, targetC = TARGET_DEFAULT;
Mode mode = IDLE; Fault fault = F_NONE;
uint8_t tecDuty = 0, fanDuty = 0;
uint32_t lastGoodRead = 0, lastTecActive = 0, modeSince = 0, fanOnSince = 0;
volatile uint32_t tachPulses = 0;
uint16_t fanRpm = 0;
int battPct = -1;

void IRAM_ATTR onTach() { tachPulses++; }

// ---------------- Outputs ----------------
void setFan(uint8_t d) { fanDuty = d; ledcWrite(PIN_FAN_PWM, d); }

void tecStop() {
  ledcWrite(PIN_RPWM, 0); ledcWrite(PIN_LPWM, 0);
  digitalWrite(PIN_REN, LOW); digitalWrite(PIN_LEN, LOW);
  tecDuty = 0;
}

void tecDrive(Mode m, uint8_t duty) {
  bool useR = (m == HEAT) == HEAT_ON_RPWM;
  digitalWrite(PIN_REN, HIGH); digitalWrite(PIN_LEN, HIGH);
  ledcWrite(useR ? PIN_LPWM : PIN_RPWM, 0);   // opposite side off first
  ledcWrite(useR ? PIN_RPWM : PIN_LPWM, duty);
  tecDuty = duty;
}

void enterFault(Fault f) { tecStop(); setFan(255); mode = FAULT; fault = f; modeSince = millis(); }

// ---------------- Inputs ----------------
void readSensor() {
  static bool requested = false; static uint32_t t0 = 0;
  uint32_t now = millis();
  if (!requested) { ds.requestTemperatures(); t0 = now; requested = true; return; }
  if (now - t0 < 800) return;                  // 12-bit conversion ~750 ms
  float t = ds.getTempCByIndex(0);
  requested = false;
  if (t != DEVICE_DISCONNECTED_C && t > -40 && t < 120) { waterC = t; lastGoodRead = now; }
}

void readFan() {
  static uint32_t t0 = 0; uint32_t now = millis();
  if (now - t0 < 1000) return;
  noInterrupts(); uint32_t p = tachPulses; tachPulses = 0; interrupts();
  fanRpm = (uint32_t)p * 60000UL / (now - t0) / FAN_PULSES_PER_REV;
  t0 = now;
}

void readBattery() {
  if (!ENABLE_BATTERY_SENSE) return;
  static uint32_t t0 = 0; uint32_t now = millis();
  if (now - t0 < 2000) return; t0 = now;
  float v = analogReadMilliVolts(PIN_BATT_ADC) / 1000.0f * BATT_DIVIDER;
  battPct = constrain((int)((v - BATT_EMPTY_V) * 100 / (BATT_FULL_V - BATT_EMPTY_V)), 0, 100);
}

struct Btn { uint8_t pin; bool last; uint32_t since, rep; };
Btn bDown{PIN_BTN_DOWN, HIGH, 0, 0}, bUp{PIN_BTN_UP, HIGH, 0, 0};

bool btnStep(Btn& b) {           // true on press and on 150 ms auto-repeat after 600 ms hold
  bool s = digitalRead(b.pin); uint32_t now = millis(); bool fire = false;
  if (s != b.last && now - b.since > 30) {
    b.since = now; b.last = s;
    if (s == LOW) { fire = true; b.rep = now + 600; }
  } else if (s == LOW && b.last == LOW && now > b.rep) { fire = true; b.rep = now + 150; }
  return fire;
}

void handleButtons() {
  if (btnStep(bDown)) targetC = max(TARGET_MIN, targetC - 1.0f);
  if (btnStep(bUp))   targetC = min(TARGET_MAX, targetC + 1.0f);
}

// ---------------- Control ----------------
void control() {
  uint32_t now = millis();

  if (fault == F_FAN || mode == FAULT) {         // latched; clears on power cycle
    tecStop(); setFan(255); return;
  }
  if (now - lastGoodRead > SENSOR_FAIL_MS) { enterFault(F_SENSOR); return; }
  if (waterC >= OVERTEMP_CUTOFF)  { enterFault(F_OVERTEMP);  return; }
  if (waterC <= UNDERTEMP_CUTOFF) { enterFault(F_UNDERTEMP); return; }

  Mode want = mode;
  if (waterC < targetC - HYSTERESIS)      want = HEAT;
  else if (waterC > targetC + HYSTERESIS) want = COOL;
  else if (mode == HEAT && waterC >= targetC) want = IDLE;
  else if (mode == COOL && waterC <= targetC) want = IDLE;

  if (want != mode) {
    if (mode != IDLE && want != IDLE) {          // reversing: stop, wait dead time
      tecStop();
      if (now - modeSince < DEADTIME_MS) return;
    }
    mode = want; modeSince = now;
  }

  if (mode == IDLE) {
    tecStop();
    setFan((now - lastTecActive < FAN_RUNON_MS) ? 128 : 0);
  } else {
    float err = fabsf(waterC - targetC);
    uint8_t d = (err >= DUTY_TAPER_C) ? TEC_MAX_DUTY
                : (uint8_t)(TEC_MIN_DUTY + (TEC_MAX_DUTY - TEC_MIN_DUTY) * (err / DUTY_TAPER_C));
    tecDrive(mode, min<uint8_t>(d, TEC_MAX_DUTY));
    setFan(mode == COOL ? 255 : 128);            // full in cooling, ~50 % in heating
    lastTecActive = now;
  }

  // Fan stall protection: TEC without airflow overheats its heat sink
  if (fanDuty > 0) {
    if (fanOnSince == 0) fanOnSince = now;
    if (now - fanOnSince > FAN_STALL_GRACE_MS && fanRpm < FAN_MIN_RPM && mode != IDLE) enterFault(F_FAN);
  } else fanOnSince = 0;
}

// ---------------- Display ----------------
void drawBattery(int x, int y) {
  oled.drawFrame(x, y, 22, 10); oled.drawBox(x + 22, y + 3, 2, 4);
  if (battPct >= 0) oled.drawBox(x + 2, y + 2, (18 * battPct) / 100, 6);
  else { oled.setFont(u8g2_font_5x7_tr); oled.drawStr(x + 8, y + 8, "?"); }
}

void drawUI() {
  static uint32_t t0 = 0; if (millis() - t0 < 250) return; t0 = millis();
  char b[24];
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tr);
  oled.drawStr(2, 12, "ThermoX");
  drawBattery(100, 3);
  oled.drawHLine(0, 17, 128);

  oled.setFont(u8g2_font_logisoso32_tn);
  if (isnan(waterC)) snprintf(b, sizeof b, "--.-"); else snprintf(b, sizeof b, "%.1f", waterC);
  oled.drawStr(8, 62, b);
  oled.setFont(u8g2_font_9x15_tr); oled.drawStr(100, 62, "C");

  oled.setFont(u8g2_font_9x15_tr);
  snprintf(b, sizeof b, "Set: %.0f C", targetC); oled.drawStr(8, 84, b);
  oled.drawStr(8, 102, mode == FAULT ? FAULT_TXT[fault] : MODE_TXT[mode]);

  oled.setFont(u8g2_font_6x12_tr);
  snprintf(b, sizeof b, "Fan %u rpm", fanRpm); oled.drawStr(2, 124, b);
  snprintf(b, sizeof b, "%u%%", tecDuty * 100 / 255); oled.drawStr(98, 124, b);
  oled.sendBuffer();
}

// ---------------- Arduino ----------------
void setup() {
  Serial.begin(115200);
  if (ENABLE_BT_LOGGING) { SerialBT.begin(BT_NAME); SerialBT.println("ms,water_c,target_c,mode,fault,tec_duty,fan_duty,fan_rpm,batt_pct"); }
  pinMode(PIN_REN, OUTPUT); pinMode(PIN_LEN, OUTPUT);
  digitalWrite(PIN_REN, LOW); digitalWrite(PIN_LEN, LOW);
  ledcAttach(PIN_RPWM, PWM_TEC_HZ, PWM_BITS); ledcAttach(PIN_LPWM, PWM_TEC_HZ, PWM_BITS);
  ledcAttach(PIN_FAN_PWM, PWM_FAN_HZ, PWM_BITS);
  tecStop(); setFan(0);

  pinMode(PIN_BTN_DOWN, INPUT_PULLUP); pinMode(PIN_BTN_UP, INPUT_PULLUP);
  pinMode(PIN_FAN_TACH, INPUT);                  // GPIO34: external 10k pull-up to 3.3V
  attachInterrupt(digitalPinToInterrupt(PIN_FAN_TACH), onTach, FALLING);
  if (ENABLE_BATTERY_SENSE) analogSetPinAttenuation(PIN_BATT_ADC, ADC_11db);

  Wire.begin(PIN_SDA, PIN_SCL);
  oled.setI2CAddress(0x3C << 1);
  oled.begin();

  ds.begin(); ds.setWaitForConversion(false); ds.setResolution(12);
  lastGoodRead = millis();
}

void loop() {
  readSensor(); readFan(); readBattery();
  handleButtons();
  control();
  drawUI();
  static uint32_t t0 = 0;
  if (millis() - t0 >= LOG_PERIOD_MS) {
    t0 = millis();
    char line[96];
    snprintf(line, sizeof line, "%lu,%.2f,%.0f,%s,%s,%u,%u,%u,%d", (unsigned long)t0, waterC, targetC,
             MODE_TXT[mode], FAULT_TXT[fault][0] ? FAULT_TXT[fault] : "-", tecDuty, fanDuty, fanRpm, battPct);
    Serial.println(line);                       // same CSV on USB serial
    if (ENABLE_BT_LOGGING && SerialBT.hasClient()) SerialBT.println(line);
  }
}
