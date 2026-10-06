/*
  ThermoX - Portable Dual-Temperature Smart Water Bottle
  Target board : ESP32 (Arduino-ESP32 core 3.x)  -- NOT an Arduino Uno (see README.md)
  Libraries    : OneWire, DallasTemperature, U8g2

  Behaviour (per Chapters I-III):
   - User sets target 20..50 C in 1 C steps with two buttons (B1 = down, B2 = up)
   - DS18B20 measures water temp; BTS7960 drives one TEC1-12706 in either direction
   - A button press starts ONE run toward the target: HEAT or COOL at full power until it is reached
   - At the target the Peltier and fan switch off (IDLE) and stay off, even if the water then
     drifts, until the next button press. Nothing starts by itself at power-up either.
   - Hot <-> cold reversal is blocked for REVERSE_COOLDOWN_MS (60 s) with the Peltier off
   - Fan: full duty in COOL, ~50 % in HEAT, off when idle (only the OLED stays on)
   - SH1107 128x128 OLED shows water temp, target, mode, fan RPM, battery
   - Phone control over Bluetooth Low Energy (page: dashboard/phone.html): live status, set the target,
     start/stop a run, fan AUTO or MANUAL % (see README.md)
*/
#include <Arduino.h>
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <U8g2lib.h>
#include <BluetoothSerial.h>   // ESP32 Classic Bluetooth (SPP)
#include <BLEDevice.h>         // ESP32 Bluetooth Low Energy (phone control)
#include <BLEServer.h>
#include <BLE2902.h>

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
constexpr float START_BAND_C = 0.5f;         // C, a press within this band of the target counts as already reached
constexpr float OVERTEMP_CUTOFF = 55.0f;     // C, hard stop
constexpr float UNDERTEMP_CUTOFF = 5.0f;     // C, hard stop (freezing)
constexpr uint8_t TEC_MAX_DUTY = 255;        // every run is at this duty; lower to limit current/battery draw
constexpr bool    HEAT_ON_RPWM = true;       // swap if your wiring heats on LPWM instead
constexpr uint32_t REVERSE_COOLDOWN_MS = 60000; // Peltier must rest this long (off) before the direction reverses
constexpr uint32_t FAN_RUNON_MS = 0;         // fan run-on after TEC stops; 0 = fan off immediately
constexpr uint32_t SENSOR_FAIL_MS = 5000;
constexpr uint32_t FAN_STALL_GRACE_MS = 5000;
constexpr uint16_t FAN_MIN_RPM = 500;        // below this while commanded => stall
constexpr uint8_t  FAN_PULSES_PER_REV = 2;   // SUNON 4-wire FG standard

constexpr uint32_t PWM_TEC_HZ = 20000, PWM_FAN_HZ = 25000;
constexpr uint8_t  PWM_BITS = 8;

constexpr bool    ENABLE_BT_LOGGING = true;
constexpr char    BT_NAME[] = "ThermoX";
constexpr uint32_t LOG_PERIOD_MS = 2000;   // 1-5 s is reasonable

// ---------------- Phone control (Bluetooth Low Energy) ----------------
// The phone page dashboard/phone.html connects with Web Bluetooth (Chrome on Android). It shows the
// status and can set the target, start or stop a run and set the fan. The Classic Bluetooth logging
// above keeps working at the same time.
constexpr bool     ENABLE_BLE_CONTROL = true;
constexpr uint8_t  FAN_MIN_PCT_COOL = 70;    // MANUAL fan never goes below this % while COOLING (hot side needs air)
constexpr uint8_t  FAN_MIN_PCT_HEAT = 40;    // ... or below this % while HEATING
constexpr uint32_t BLE_PING_MS = 1000;       // how often the phone is told to refresh
#define BLE_SERVICE_UUID "7a3c0000-63b5-4559-b515-2c37cc077186"
#define BLE_STATUS_UUID  "7a3c0001-63b5-4559-b515-2c37cc077186"   // read:   status (JSON)
#define BLE_CMD_UUID     "7a3c0002-63b5-4559-b515-2c37cc077186"   // write:  command (short text)
#define BLE_NOTIFY_UUID  "7a3c0003-63b5-4559-b515-2c37cc077186"   // notify: "refresh now"
#define BLE_LOG_UUID     "7a3c0004-63b5-4559-b515-2c37cc077186"   // read:   event log (JSON)

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
Mode lastDriven = IDLE;                      // last direction the Peltier was driven in
Mode runDir = IDLE;                          // direction of the run in progress (IDLE = no run)
bool newRun = false;                         // a button was pressed: pick the direction on the next pass
bool reached = false;                        // last run finished at the target (display only)
uint16_t waitLeftS = 0;                      // seconds left of the reversal cooldown (0 = none)
volatile uint32_t tachPulses = 0;
uint16_t fanRpm = 0;
int battPct = -1;
float battV = NAN;                           // stays NaN unless ENABLE_BATTERY_SENSE
enum FanCtl : uint8_t { FAN_AUTO, FAN_MANUAL };
FanCtl fanCtl = FAN_AUTO;                    // set from the phone; back to AUTO after every power-up
uint8_t fanManualPct = 50;                   // MANUAL fan speed from the phone, %
uint8_t fanFloorPct = 0;                     // safety minimum for the MANUAL fan right now, %

// Declared before the first function so the prototype Arduino generates for btnStep() compiles.
struct Btn { uint8_t pin; bool last; uint32_t since, rep; };

void IRAM_ATTR onTach() { tachPulses++; }

// ---------------- Outputs ----------------
void setFan(uint8_t d) {
  if (d > fanDuty) fanOnSince = 0;           // faster: give the fan time to spin up before the stall check
  fanDuty = d; ledcWrite(PIN_FAN_PWM, d);
}

// Fan duty for mode m. AUTO uses autoDuty (the normal behaviour). MANUAL uses the phone's %, but
// while the Peltier runs it never goes below FAN_MIN_PCT_COOL / FAN_MIN_PCT_HEAT.
uint8_t fanDutyFor(Mode m, uint8_t autoDuty) {
  fanFloorPct = (m == COOL) ? FAN_MIN_PCT_COOL : (m == HEAT) ? FAN_MIN_PCT_HEAT : 0;
  if (fanCtl == FAN_AUTO) return autoDuty;
  uint8_t pct = max(fanManualPct, fanFloorPct);
  return (uint8_t)((pct * 255U + 50) / 100);
}

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
  battV = v;
  battPct = constrain((int)((v - BATT_EMPTY_V) * 100 / (BATT_FULL_V - BATT_EMPTY_V)), 0, 100);
}

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
  if (btnStep(bDown)) { targetC = max(TARGET_MIN, targetC - 1.0f); newRun = true; }
  if (btnStep(bUp))   { targetC = min(TARGET_MAX, targetC + 1.0f); newRun = true; }
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

  // One run per button press. The direction is chosen when the press is handled; the run then
  // goes at full power until the water crosses the target. After that nothing restarts by itself,
  // however far the temperature drifts, until the next press.
  if (newRun && !isnan(waterC)) {
    newRun = false; reached = false;
    if (waterC < targetC - START_BAND_C)      runDir = HEAT;
    else if (waterC > targetC + START_BAND_C) runDir = COOL;
    else { runDir = IDLE; reached = true; }        // already at the target
  } else if ((runDir == HEAT && waterC >= targetC) || (runDir == COOL && waterC <= targetC)) {
    runDir = IDLE; reached = true;
  }
  Mode want = runDir;

  // Never flip hot <-> cold quickly: after driving one way the Peltier stays OFF until
  // REVERSE_COOLDOWN_MS has passed since it last ran, then it may start the other way.
  waitLeftS = 0;
  if ((want == HEAT || want == COOL) && lastDriven != IDLE && want != lastDriven &&
      now - lastTecActive < REVERSE_COOLDOWN_MS) {
    waitLeftS = (REVERSE_COOLDOWN_MS - (now - lastTecActive) + 999) / 1000;
    want = IDLE;
  }
  if (want != mode) { mode = want; modeSince = now; }

  if (mode == IDLE) {
    tecStop();
    setFan(fanDutyFor(IDLE, (now - lastTecActive < FAN_RUNON_MS) ? 128 : 0));
  } else {
    tecDrive(mode, TEC_MAX_DUTY);
    setFan(fanDutyFor(mode, mode == COOL ? 255 : 128));   // AUTO: full in cooling, ~50 % in heating
    lastTecActive = now; lastDriven = mode;
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
  if (mode == FAULT) oled.drawStr(8, 102, FAULT_TXT[fault]);
  else if (waitLeftS) { snprintf(b, sizeof b, "WAIT %us", waitLeftS); oled.drawStr(8, 102, b); }
  else if (mode == IDLE) oled.drawStr(8, 102, reached ? "REACHED" : "READY");
  else oled.drawStr(8, 102, MODE_TXT[mode]);

  oled.setFont(u8g2_font_6x12_tr);
  snprintf(b, sizeof b, "Fan %u rpm", fanRpm); oled.drawStr(2, 124, b);
  snprintf(b, sizeof b, "%u%%", tecDuty * 100 / 255); oled.drawStr(98, 124, b);
  oled.sendBuffer();
}

// ---------------- Logging ----------------
// One line per sample, read by receiver/receiver.py and stored via the PHP API:
//   TEMP=28.40,TARGET=18.0,MODE=COOLING,PELTIER=1,FAN=1[,BATTERY=12.10]
// MODE is HEATING, COOLING, IDLE (ready, or target reached and waiting for the next press) or FAULT.
// BATTERY is only sent when battery sensing is really enabled.
void logData() {
  static uint32_t t0 = 0;
  if (millis() - t0 < LOG_PERIOD_MS) return;
  t0 = millis();
  if (isnan(waterC)) return;                     // no valid reading yet
  char line[128];
  int n = snprintf(line, sizeof line, "TEMP=%.2f,TARGET=%.1f,MODE=%s,PELTIER=%d,FAN=%d",
                   waterC, targetC, MODE_TXT[mode], tecDuty > 0, fanDuty > 0);
  if (ENABLE_BATTERY_SENSE && !isnan(battV))
    snprintf(line + n, sizeof line - n, ",BATTERY=%.2f", battV);
  Serial.println(line);                          // same line on USB serial
  if (ENABLE_BT_LOGGING && SerialBT.hasClient()) SerialBT.println(line);
}

// ---------------- Phone control (BLE) ----------------
// Event log shown on the phone: the last EV_MAX events with their millis() time.
constexpr uint8_t EV_MAX = 10;
struct Ev { uint32_t ms; char txt[28]; };
Ev evBuf[EV_MAX];
uint8_t evNext = 0, evCount = 0;
volatile uint16_t evTotal = 0;               // events since power-up; the phone re-reads the log when it changes
portMUX_TYPE evMux = portMUX_INITIALIZER_UNLOCKED;   // the log is written from loop() and the Bluetooth task

void logEvent(const char* fmt, ...) {
  char t[sizeof(Ev::txt)];
  va_list ap; va_start(ap, fmt); vsnprintf(t, sizeof t, fmt, ap); va_end(ap);
  uint32_t now = millis();
  portENTER_CRITICAL(&evMux);
  evBuf[evNext].ms = now; memcpy(evBuf[evNext].txt, t, sizeof t);
  evNext = (evNext + 1) % EV_MAX;
  if (evCount < EV_MAX) evCount++;
  evTotal = evTotal + 1;
  portEXIT_CRITICAL(&evMux);
}

// Status JSON, e.g. {"t":28.44,"tg":25,...,"m":"COOLING","f":"","fc":"auto",...}. Built when the phone reads it.
void statusJson(char* b, size_t n) {
  char t[12] = "null", bv[12] = "null";
  float w = waterC;
  if (!isnan(w)) snprintf(t, sizeof t, "%.2f", w);
  if (!isnan(battV)) snprintf(bv, sizeof bv, "%.2f", battV);
  snprintf(b, n,
    "{\"t\":%s,\"tg\":%.0f,\"tmin\":%.0f,\"tmax\":%.0f,\"m\":\"%s\",\"f\":\"%s\",\"r\":%d,\"w\":%u,"
    "\"pel\":%u,\"fan\":%u,\"rpm\":%u,\"fc\":\"%s\",\"fp\":%u,\"fmin\":%u,\"bat\":%d,\"bv\":%s,\"up\":%lu,\"ev\":%u}",
    t, targetC, TARGET_MIN, TARGET_MAX, MODE_TXT[mode], FAULT_TXT[fault], reached ? 1 : 0, (unsigned)waitLeftS,
    tecDuty * 100U / 255, fanDuty * 100U / 255, (unsigned)fanRpm, fanCtl == FAN_AUTO ? "auto" : "manual",
    (unsigned)fanManualPct, (unsigned)fanFloorPct, battPct, bv, (unsigned long)millis(), (unsigned)evTotal);
}

// Event log JSON, oldest first: {"up":<millis now>,"e":[[<millis>,"text"],...]} (under 512 bytes).
void logJson(char* b, size_t n) {
  Ev copy[EV_MAX]; uint8_t cnt, next;
  portENTER_CRITICAL(&evMux);
  memcpy(copy, evBuf, sizeof copy); cnt = evCount; next = evNext;
  portEXIT_CRITICAL(&evMux);
  size_t len = snprintf(b, n, "{\"up\":%lu,\"e\":[", (unsigned long)millis());
  for (uint8_t i = 0; i < cnt && len < n; i++) {
    const Ev& e = copy[(next + EV_MAX - cnt + i) % EV_MAX];
    len += snprintf(b + len, n - len, "%s[%lu,\"%s\"]", i ? "," : "", (unsigned long)e.ms, e.txt);
  }
  if (len < n) snprintf(b + len, n - len, "]}");
}

struct PhoneCmd { char s[21]; };
QueueHandle_t phoneCmds = nullptr;           // written by the Bluetooth task, handled in loop()
BLECharacteristic* chNotify = nullptr;
volatile bool phoneConnected = false;
bool phonePing = false;                      // tell the phone to refresh now

class PhoneServerCb : public BLEServerCallbacks {
  void onConnect(BLEServer*) override { phoneConnected = true; logEvent("Phone connected"); }
  void onDisconnect(BLEServer*) override { phoneConnected = false; logEvent("Phone disconnected"); }
};
class StatusCb : public BLECharacteristicCallbacks {
  void onRead(BLECharacteristic* c) override {
    static char b[320]; statusJson(b, sizeof b); c->setValue((uint8_t*)b, strlen(b));
  }
};
class LogCb : public BLECharacteristicCallbacks {
  void onRead(BLECharacteristic* c) override {
    static char b[512]; logJson(b, sizeof b); c->setValue((uint8_t*)b, strlen(b));
  }
};
class CmdCb : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* c) override {
    String v = c->getValue();
    PhoneCmd m{};
    strncpy(m.s, v.c_str(), sizeof m.s - 1);
    if (phoneCmds) xQueueSend(phoneCmds, &m, 0);   // full queue (8 waiting): the command is dropped
  }
};

void bleBegin() {
  phoneCmds = xQueueCreate(8, sizeof(PhoneCmd));
  BLEDevice::init(BT_NAME);                  // same name as Classic Bluetooth
  BLEDevice::setMTU(185);                    // lets the phone use bigger packets if it asks
  BLEServer* server = BLEDevice::createServer();
  server->setCallbacks(new PhoneServerCb());
  server->advertiseOnDisconnect(true);       // visible again as soon as the phone leaves
  BLEService* svc = server->createService(BLE_SERVICE_UUID);
  svc->createCharacteristic(BLE_STATUS_UUID, BLECharacteristic::PROPERTY_READ)->setCallbacks(new StatusCb());
  svc->createCharacteristic(BLE_LOG_UUID, BLECharacteristic::PROPERTY_READ)->setCallbacks(new LogCb());
  svc->createCharacteristic(BLE_CMD_UUID, BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR)
     ->setCallbacks(new CmdCb());
  chNotify = svc->createCharacteristic(BLE_NOTIFY_UUID, BLECharacteristic::PROPERTY_NOTIFY);
  chNotify->addDescriptor(new BLE2902());
  svc->start();
  BLEAdvertising* adv = BLEDevice::getAdvertising();
  adv->addServiceUUID(BLE_SERVICE_UUID);
  adv->setScanResponse(true);
  BLEDevice::startAdvertising();
}

// Commands from the phone (one short text per write):
//   T<20-50>   set the target and start a run (same as a button press)
//   S          start a run toward the current target
//   X          stop the run (Peltier off)
//   FA         fan AUTO (the normal behaviour)
//   FM<0-100>  fan MANUAL at this %, never below FAN_MIN_PCT_* while the Peltier runs
// Fault cutoffs, the 60 s reversal rest and the fault latch work exactly as with the buttons.
void handlePhone() {
  if (!phoneCmds) return;
  PhoneCmd m;
  while (xQueueReceive(phoneCmds, &m, 0) == pdTRUE) {
    char* s = m.s;
    for (int i = (int)strlen(s) - 1; i >= 0 && isspace((unsigned char)s[i]); i--) s[i] = '\0';
    char* end = nullptr;
    long v = 0;
    char c0 = toupper((unsigned char)s[0]), c1 = c0 ? toupper((unsigned char)s[1]) : 0;
    if (c0 == 'T' && (v = strtol(s + 1, &end, 10), end != s + 1 && *end == '\0') &&
        v >= (long)TARGET_MIN && v <= (long)TARGET_MAX) {
      targetC = v; newRun = true;
    } else if (c0 == 'S' && c1 == '\0') {
      newRun = true; logEvent("Phone: start");
    } else if (c0 == 'X' && c1 == '\0') {
      runDir = IDLE; newRun = false; reached = false; logEvent("Phone: stop");
    } else if (c0 == 'F' && c1 == 'A' && s[2] == '\0') {
      fanCtl = FAN_AUTO; logEvent("Phone: fan AUTO");
    } else if (c0 == 'F' && c1 == 'M' && (v = strtol(s + 2, &end, 10), end != s + 2 && *end == '\0') &&
               v >= 0 && v <= 100) {
      fanCtl = FAN_MANUAL; fanManualPct = v; logEvent("Phone: fan %ld%%", v);
    } else {
      logEvent("Phone: bad command");
    }
    phonePing = true;
  }
}

// Adds an event when the run state changes, whoever caused it (buttons, phone or the control loop).
void trackEvents() {
  static Mode lastMode = IDLE;
  static bool lastReached = false, lastWait = false;
  static float lastTarget = TARGET_DEFAULT, loggedTarget = TARGET_DEFAULT;
  static uint32_t targetSince = 0;
  uint32_t now = millis();
  if (mode != lastMode) {
    if (mode == HEAT)       { logEvent("Heating to %.0f C", targetC); loggedTarget = targetC; }
    else if (mode == COOL)  { logEvent("Cooling to %.0f C", targetC); loggedTarget = targetC; }
    else if (mode == FAULT) logEvent("FAULT: %s", FAULT_TXT[fault]);
    lastMode = mode;
  }
  bool waiting = waitLeftS > 0;
  if (waiting && !lastWait) logEvent("Wait %us before reversing", (unsigned)waitLeftS);
  lastWait = waiting;
  if (reached && !lastReached) logEvent("Reached %.1f C", waterC);
  lastReached = reached;
  // A held button changes the target every 150 ms: log it once it has been steady for 1.5 s.
  if (targetC != lastTarget) { lastTarget = targetC; targetSince = now; }
  else if (targetC != loggedTarget && now - targetSince > 1500) { loggedTarget = targetC; logEvent("Target %.0f C", targetC); }
}

// Tells the phone to refresh: every BLE_PING_MS, and right after a phone command.
// Payload: 2 bytes counter + 2 bytes evTotal (little-endian).
void bleTick() {
  static uint32_t t0 = 0;
  static uint16_t seq = 0;
  if (!chNotify || !phoneConnected) return;
  uint32_t now = millis();
  if (!phonePing && now - t0 < BLE_PING_MS) return;
  t0 = now; phonePing = false;
  uint16_t ev = evTotal;
  uint8_t v[4] = {(uint8_t)seq, (uint8_t)(seq >> 8), (uint8_t)ev, (uint8_t)(ev >> 8)};
  seq++;
  chNotify->setValue(v, sizeof v);
  chNotify->notify();
}

// ---------------- Arduino ----------------
void setup() {
  Serial.begin(115200);
  logEvent("Power on");
  if (ENABLE_BT_LOGGING) SerialBT.begin(BT_NAME);
  pinMode(PIN_REN, OUTPUT); pinMode(PIN_LEN, OUTPUT);
  digitalWrite(PIN_REN, LOW); digitalWrite(PIN_LEN, LOW);
  ledcAttach(PIN_RPWM, PWM_TEC_HZ, PWM_BITS); ledcAttach(PIN_LPWM, PWM_TEC_HZ, PWM_BITS);
  ledcAttach(PIN_FAN_PWM, PWM_FAN_HZ, PWM_BITS);
  tecStop(); setFan(0);
  if (ENABLE_BLE_CONTROL) bleBegin();            // after the Peltier and fan outputs are safely off

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
  handlePhone();
  control();
  trackEvents();
  drawUI();
  logData();
  bleTick();
}
