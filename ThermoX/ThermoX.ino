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
   - Hot <-> cold reversal is blocked for 60 s (setting "cd") with the Peltier off
   - Fan: full duty in COOL, ~50 % in HEAT, off when idle (only the OLED stays on)
   - SH1107 128x128 OLED shows water temp, target, mode, fan RPM, battery
   - Phone control over Bluetooth Low Energy (page: dashboard/phone.html): live status, set the target,
     start/stop a run, fan AUTO or MANUAL %, Peltier power limit (see README.md)
   - The last target and the power limit are saved and come back after power-up (no run starts by itself)
   - Low-battery cutoff (needs battery sensing switched on, setting "be"): stops the Peltier and blocks
     new runs until the battery recovers
   - Admin tab on the phone (PIN): safety limits, Peltier, fan, sensor, battery, OLED and system settings
     are changed over BLE and saved in flash, so nothing has to be re-uploaded (see README.md)
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
#include <Preferences.h>       // saved settings (flash)

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

constexpr uint8_t PIN_BATT_ADC = 35;       // battery divider input (FUTURE ADDITION, see README.md)

// ---------------- Settings (adjustable from the phone, saved in flash) ----------------
// Everything that used to be a compile-time constant lives in cfg[]. The numbers below are the factory
// defaults; the phone's Admin tab changes them over BLE (PIN needed) and each change is saved in flash,
// so nothing has to be re-uploaded. The lo/hi limits are enforced here, whatever the phone sends.
// Not adjustable on purpose: the GPIO pin assignments above.
enum Param : uint8_t {
  P_OT, P_UT, P_TMIN, P_TMAX, P_SB,                          // group 0: safety and range
  P_PMIN, P_MD, P_CD, P_HR, P_RO, P_RP,                      // group 1: Peltier / BTS7960
  P_FMC, P_FMH, P_FAC, P_FAH, P_FR, P_FG, P_FPP,             // group 2: fan
  P_OFF, P_SF,                                               // group 3: temperature sensor
  P_BE, P_BC, P_BD, P_BM, P_BF, P_LC, P_LD, P_LR,            // group 4: battery
  P_OB, P_OR, P_OI, P_OU, P_OS,                              // group 5: OLED display
  P_LP,                                                      // group 6: system
  P_COUNT };
struct ParamDef { const char* key; uint8_t group; float lo, hi, def; };
const ParamDef PARAMS[P_COUNT] = {
  {"ot",   0, 40,   60,   55},      // over-temperature hard stop, C
  {"ut",   0, 1,    15,   5},       // under-temperature (freezing) hard stop, C
  {"tmin", 0, 5,    40,   20},      // lowest target, C
  {"tmax", 0, 25,   60,   50},      // highest target, C
  {"sb",   0, 0.1f, 3,    0.5f},    // start band: a press this close to the target counts as reached, C
  {"pmin", 1, 10,   100,  30},      // lowest Peltier power the phone can set, %
  {"md",   1, 50,   255,  255},     // Peltier PWM duty at 100 % power (255 = full)
  {"cd",   1, 10,   600,  60},      // rest before hot <-> cold reversal, s
  {"hr",   1, 0,    1,    1},       // 1 = heat on RPWM, 0 = heat on LPWM (swap if wired the other way)
  {"ro",   1, 0,    300,  0},       // fan run-on after the Peltier stops, s (0 = off at once)
  {"rp",   1, 0,    30,   0},       // soft start: seconds to ramp the Peltier from 0 to full (0 = off)
  {"fmc",  2, 30,   100,  70},      // MANUAL fan floor while COOLING, %
  {"fmh",  2, 20,   100,  40},      // MANUAL fan floor while HEATING, %
  {"fac",  2, 40,   100,  100},     // AUTO fan speed while cooling, %
  {"fah",  2, 20,   100,  50},      // AUTO fan speed while heating, %
  {"fr",   2, 100,  3000, 500},     // below this RPM while commanded => fan stall fault
  {"fg",   2, 2,    30,   5},       // stall check grace time after the fan speeds up, s
  {"fpp",  2, 1,    4,    2},       // tach pulses per revolution (SUNON 4-wire FG = 2)
  {"off",  3, -5,   5,    0},       // temperature calibration offset, C
  {"sf",   3, 2,    60,   5},       // sensor lost for this long => SENSOR fault, s
  {"be",   4, 0,    1,    0},       // battery sensing on (needs the GPIO35 divider)
  {"bc",   4, 1,    6,    1},       // Li-ion cells in series (3S pack = 3)
  {"bd",   4, 1,    20,   2.0f},    // divider ratio: pack volts / GPIO35 volts (keep GPIO35 below ~3.1 V)
  {"bm",   4, 2.5f, 4.0f, 3.3f},    // empty voltage per cell (0 % on the gauge)
  {"bf",   4, 3.8f, 4.4f, 4.15f},   // full voltage per cell (100 %)
  {"lc",   4, 2.5f, 4.0f, 3.30f},   // low-battery cutoff per cell: Peltier stops below this...
  {"ld",   4, 1,    60,   5},       // ...for this long, s (ignores short dips under load)
  {"lr",   4, 3.0f, 4.2f, 3.60f},   // per cell: new runs allowed again above this
  {"ob",   5, 5,    100,  100},     // OLED brightness, %
  {"or",   5, 0,    1,    0},       // 1 = rotate the OLED 180 degrees
  {"oi",   5, 0,    1,    0},       // 1 = inverted (light on dark) OLED
  {"ou",   5, 0,    1,    0},       // 1 = show Fahrenheit on the OLED (phone and logs stay in C)
  {"os",   5, 0,    3600, 0},       // OLED goes dark after this many seconds without activity (0 = never)
  {"lp",   6, 1,    60,   2},       // logging period, s
};
float cfg[P_COUNT];
inline bool cfgOn(Param p) { return cfg[p] >= 0.5f; }
inline uint32_t cfgMs(Param p) { return (uint32_t)(cfg[p] * 1000.0f + 0.5f); }
inline uint8_t pctToDuty(float pct) { return (uint8_t)(pct * 255.0f / 100.0f + 0.5f); }

constexpr float    TARGET_DEFAULT = 25.0f;
constexpr char    DEFAULT_PIN[] = "1234";    // admin PIN until changed on the phone
constexpr char    FW_VERSION[] = "1.1";
constexpr uint32_t ADMIN_TIMEOUT_MS = 300000; // admin unlock lasts 5 min after the last admin command

constexpr uint32_t PWM_TEC_HZ = 20000, PWM_FAN_HZ = 25000;
constexpr uint8_t  PWM_BITS = 8;

constexpr bool    ENABLE_BT_LOGGING = true;
constexpr char    BT_NAME[] = "ThermoX";   // default name; the phone can rename the device (applies after a reboot)

// ---------------- Phone control (Bluetooth Low Energy) ----------------
// The phone page dashboard/phone.html connects with Web Bluetooth (Chrome on Android). It shows the
// status and can set the target, start or stop a run and set the fan. The Classic Bluetooth logging
// above keeps working at the same time.
constexpr bool     ENABLE_BLE_CONTROL = true;
constexpr uint32_t BLE_PING_MS = 1000;       // how often the phone is told to refresh
#define BLE_SERVICE_UUID "7a3c0000-63b5-4559-b515-2c37cc077186"
#define BLE_STATUS_UUID  "7a3c0001-63b5-4559-b515-2c37cc077186"   // read:   status (JSON)
#define BLE_CMD_UUID     "7a3c0002-63b5-4559-b515-2c37cc077186"   // write:  command (short text)
#define BLE_NOTIFY_UUID  "7a3c0003-63b5-4559-b515-2c37cc077186"   // notify: "refresh now"
#define BLE_LOG_UUID     "7a3c0004-63b5-4559-b515-2c37cc077186"   // read:   event log (JSON)
#define BLE_CFG_UUID     "7a3c0005-63b5-4559-b515-2c37cc077186"   // read:   settings group chosen by the "G<n>" command (JSON)

// ---------------- Globals ----------------
BluetoothSerial SerialBT;
enum Mode : uint8_t { IDLE, HEAT, COOL, FAULT };
enum Fault : uint8_t { F_NONE, F_SENSOR, F_OVERTEMP, F_UNDERTEMP, F_FAN };
const char* MODE_TXT[]  = {"IDLE", "HEATING", "COOLING", "FAULT"};
const char* FAULT_TXT[] = {"", "SENSOR", "OVER TEMP", "TOO COLD", "FAN STALL"};

OneWire oneWire(PIN_ONEWIRE);
DallasTemperature ds(&oneWire);
// GME128128-01 (1.5" SH1107 128x128) needs x offset 0: the PIMORONI variant. The plain
// U8G2_SH1107_128X128 driver adds a 96-pixel offset, which shifts and wraps the picture.
U8G2_SH1107_PIMORONI_128X128_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);

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
float battV = NAN;                           // stays NaN unless battery sensing is on (cfg "be")
float battRawV = NAN;                        // smoothed voltage at GPIO35, before the divider ratio
enum FanCtl : uint8_t { FAN_AUTO, FAN_MANUAL };
FanCtl fanCtl = FAN_AUTO;                    // set from the phone; back to AUTO after every power-up
uint8_t fanManualPct = 50;                   // MANUAL fan speed from the phone, %
uint8_t fanFloorPct = 0;                     // safety minimum for the MANUAL fan right now, %
uint8_t tecPowerPct = 100;                   // Peltier power limit from the phone, % (saved)
bool lowBatt = false;                        // low-battery cutoff active
uint32_t lowBattSince = 0;
Preferences prefs;
char btName[16] = "ThermoX";                 // BLE / Classic Bluetooth name (saved; applies after a reboot)
char pinStr[9] = "1234";                     // admin PIN (4-8 digits, saved)
volatile bool adminOn = false;               // admin unlocked from the phone (this connection only)
volatile uint32_t adminUntil = 0;
uint8_t pinFails = 0; bool pinLocked = false; uint32_t pinLockUntil = 0;
uint16_t faultCnt[5] = {0};                  // faults since the history was last cleared (saved), by Fault
uint8_t lastFault = 0;                       // last fault seen (saved)
bool fanTest = false; uint32_t fanTestEnd = 0;   // admin fan test while idle
bool rebootPending = false; uint32_t rebootAt = 0;
uint32_t lastActivity = 0;                   // last button press, phone command or run (for the OLED sleep)
bool oledSleeping = false;
float tecRamp = 0;                           // soft-start ramp, PWM duty counts

// Declared before the first function so the prototype Arduino generates for btnStep() compiles.
struct Btn { uint8_t pin; bool last; uint32_t since, rep; };

void IRAM_ATTR onTach() { tachPulses++; }

// ---------------- Outputs ----------------
void setFan(uint8_t d) {
  if (d > fanDuty) fanOnSince = 0;           // faster: give the fan time to spin up before the stall check
  fanDuty = d; ledcWrite(PIN_FAN_PWM, d);
}

// Fan duty for mode m. AUTO uses autoDuty (the normal behaviour). MANUAL uses the phone's %, but
// while the Peltier runs it never goes below the "fmc" (cooling) / "fmh" (heating) floors.
uint8_t fanDutyFor(Mode m, uint8_t autoDuty) {
  fanFloorPct = (m == COOL) ? (uint8_t)cfg[P_FMC] : (m == HEAT) ? (uint8_t)cfg[P_FMH] : 0;
  if (m == IDLE && fanTest) {                  // admin fan test (only while idle)
    if ((int32_t)(fanTestEnd - millis()) > 0) return 255;
    fanTest = false;
  }
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
  bool useR = (m == HEAT) == cfgOn(P_HR);
  digitalWrite(PIN_REN, HIGH); digitalWrite(PIN_LEN, HIGH);
  ledcWrite(useR ? PIN_LPWM : PIN_RPWM, 0);   // opposite side off first
  ledcWrite(useR ? PIN_RPWM : PIN_LPWM, duty);
  tecDuty = duty;
}

void enterFault(Fault f) {
  tecStop(); setFan(255); mode = FAULT; fault = f; modeSince = millis();
  char k[8]; snprintf(k, sizeof k, "fc%u", (unsigned)f);     // fault history, kept across power cycles
  faultCnt[f]++; lastFault = f;
  prefs.putUShort(k, faultCnt[f]); prefs.putUChar("lastf", lastFault);
}

// ---------------- Inputs ----------------
void readSensor() {
  static bool requested = false; static uint32_t t0 = 0;
  uint32_t now = millis();
  if (!requested) { ds.requestTemperatures(); t0 = now; requested = true; return; }
  if (now - t0 < 800) return;                  // 12-bit conversion ~750 ms
  float t = ds.getTempCByIndex(0);
  requested = false;
  if (t != DEVICE_DISCONNECTED_C && t > -40 && t < 120) { waterC = t + cfg[P_OFF]; lastGoodRead = now; }
}

void readFan() {
  static uint32_t t0 = 0; uint32_t now = millis();
  if (now - t0 < 1000) return;
  noInterrupts(); uint32_t p = tachPulses; tachPulses = 0; interrupts();
  fanRpm = (uint32_t)p * 60000UL / (now - t0) / (uint32_t)cfg[P_FPP];
  t0 = now;
}

void readBattery() {
  if (!cfgOn(P_BE)) {                            // sensing off: no gauge, no low-battery cutoff
    if (!isnan(battV) || !isnan(battRawV)) { battV = battRawV = NAN; battPct = -1; lowBatt = false; lowBattSince = 0; }
    return;
  }
  static uint32_t t0 = 0; uint32_t now = millis();
  if (now - t0 < 2000) return; t0 = now;
  float raw = analogReadMilliVolts(PIN_BATT_ADC) / 1000.0f;
  battRawV = isnan(battRawV) ? raw : battRawV * 0.7f + raw * 0.3f;   // smoothed
  battV = battRawV * cfg[P_BD];                  // pack voltage
  float cell = battV / cfg[P_BC];
  battPct = constrain((int)((cell - cfg[P_BM]) * 100 / (cfg[P_BF] - cfg[P_BM])), 0, 100);
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

void oledPower();                                // below, with the display code

void handleButtons() {
  bool dn = btnStep(bDown), up = btnStep(bUp);
  if (dn || up) {
    bool wasAsleep = oledSleeping;
    lastActivity = millis();
    if (wasAsleep) { oledPower(); return; }      // a press on a dark display only wakes it (no run starts unseen)
  }
  if (dn) { targetC = max(cfg[P_TMIN], targetC - 1.0f); newRun = true; }
  if (up) { targetC = min(cfg[P_TMAX], targetC + 1.0f); newRun = true; }
}

// ---------------- Control ----------------
void control() {
  uint32_t now = millis();
  static uint32_t lastCtl = 0;
  uint32_t dtMs = now - lastCtl; lastCtl = now;

  if (fault == F_FAN || mode == FAULT) {         // latched; clears on power cycle
    tecStop(); setFan(255); return;
  }
  if (now - lastGoodRead > cfgMs(P_SF)) { enterFault(F_SENSOR); return; }
  if (waterC >= cfg[P_OT])  { enterFault(F_OVERTEMP);  return; }
  if (waterC <= cfg[P_UT]) { enterFault(F_UNDERTEMP); return; }

  // Low battery: stop the run and refuse new ones until the battery recovers (not latched).
  if (cfgOn(P_BE) && !isnan(battV)) {
    float cell = battV / cfg[P_BC];
    if (cell < cfg[P_LC]) {
      if (lowBattSince == 0) lowBattSince = now;
      if (now - lowBattSince > cfgMs(P_LD)) lowBatt = true;
    } else {
      lowBattSince = 0;
      if (cell > cfg[P_LR]) lowBatt = false;
    }
  }
  if (lowBatt) { runDir = IDLE; newRun = false; reached = false; }

  // One run per button press. The direction is chosen when the press is handled; the run then
  // goes at full power until the water crosses the target. After that nothing restarts by itself,
  // however far the temperature drifts, until the next press.
  if (newRun && !isnan(waterC)) {
    newRun = false; reached = false;
    if (waterC < targetC - cfg[P_SB])      runDir = HEAT;
    else if (waterC > targetC + cfg[P_SB]) runDir = COOL;
    else { runDir = IDLE; reached = true; }        // already at the target
  } else if ((runDir == HEAT && waterC >= targetC) || (runDir == COOL && waterC <= targetC)) {
    runDir = IDLE; reached = true;
  }
  Mode want = runDir;

  // Never flip hot <-> cold quickly: after driving one way the Peltier stays OFF until
  // the reversal rest ("cd", 60 s by default) has passed since it last ran, then it may start the other way.
  waitLeftS = 0;
  if ((want == HEAT || want == COOL) && lastDriven != IDLE && want != lastDriven &&
      now - lastTecActive < cfgMs(P_CD)) {
    waitLeftS = (cfgMs(P_CD) - (now - lastTecActive) + 999) / 1000;
    want = IDLE;
  }
  if (want != mode) { mode = want; modeSince = now; }

  if (mode == IDLE) {
    tecStop(); tecRamp = 0;
    setFan(fanDutyFor(IDLE, (now - lastTecActive < cfgMs(P_RO)) ? 128 : 0));
  } else {
    uint8_t wantDuty = (uint8_t)((cfg[P_MD] * tecPowerPct + 50) / 100);
    uint8_t duty = wantDuty;
    if (cfg[P_RP] > 0.0f) {                      // soft start: ramp up over "rp" seconds, drop at once
      tecRamp = min(255.0f, tecRamp + dtMs * 255.0f / (cfg[P_RP] * 1000.0f));
      duty = (tecRamp >= wantDuty) ? wantDuty : (uint8_t)tecRamp;
    }
    tecDrive(mode, duty);
    setFan(fanDutyFor(mode, pctToDuty(mode == COOL ? cfg[P_FAC] : cfg[P_FAH])));   // AUTO: "fac" % cooling, "fah" % heating
    lastTecActive = now; lastDriven = mode;
  }

  // Fan stall protection: TEC without airflow overheats its heat sink
  if (fanDuty > 0) {
    if (fanOnSince == 0) fanOnSince = now;
    if (now - fanOnSince > cfgMs(P_FG) && fanRpm < cfg[P_FR] && mode != IDLE) enterFault(F_FAN);
  } else fanOnSince = 0;
}

// ---------------- Display ----------------
void drawBattery(int x, int y) {
  oled.drawFrame(x, y, 22, 10); oled.drawBox(x + 22, y + 3, 2, 4);
  if (battPct >= 0) oled.drawBox(x + 2, y + 2, (18 * battPct) / 100, 6);
  else { oled.setFont(u8g2_font_5x7_tr); oled.drawStr(x + 8, y + 8, "?"); }
}

// Applies the OLED settings (brightness, rotation, inverse). Called at start-up and after a change.
void applyOled() {
  oled.setContrast(pctToDuty(cfg[P_OB]));
  oled.setDisplayRotation(cfgOn(P_OR) ? U8G2_R2 : U8G2_R0);
  oled.sendF("c", cfgOn(P_OI) ? 0xA7 : 0xA6);    // SH1107: A7 = inverse display, A6 = normal
  lastActivity = millis();
}

// Auto-sleep: the OLED goes dark after "os" seconds without a button press, phone command or run.
// A fault, a run, the reversal wait and low battery keep it lit.
void oledPower() {
  uint32_t now = millis();
  if (mode != IDLE || waitLeftS || lowBatt) lastActivity = now;
  bool wantSleep = cfg[P_OS] > 0.0f && now - lastActivity > cfgMs(P_OS);
  if (wantSleep != oledSleeping) { oledSleeping = wantSleep; oled.setPowerSave(wantSleep ? 1 : 0); }
}

void drawUI() {
  oledPower();
  if (oledSleeping) return;
  static uint32_t t0 = 0; if (millis() - t0 < 250) return; t0 = millis();
  char b[24];
  bool useF = cfgOn(P_OU);                       // Fahrenheit on the OLED only
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x12_tr);
  oled.drawStr(2, 12, "ThermoX");
  drawBattery(100, 3);
  oled.drawHLine(0, 17, 128);

  oled.setFont(u8g2_font_logisoso32_tn);
  float shown = useF ? waterC * 1.8f + 32.0f : waterC;
  if (isnan(waterC)) snprintf(b, sizeof b, "--.-");
  else snprintf(b, sizeof b, shown >= 100.0f ? "%.0f" : "%.1f", shown);
  oled.drawStr(8, 62, b);
  oled.setFont(u8g2_font_9x15_tr); oled.drawStr(100, 62, useF ? "F" : "C");

  oled.setFont(u8g2_font_9x15_tr);
  snprintf(b, sizeof b, "Set: %.0f %c", useF ? targetC * 1.8f + 32.0f : targetC, useF ? 'F' : 'C'); oled.drawStr(8, 84, b);
  if (mode == FAULT) oled.drawStr(8, 102, FAULT_TXT[fault]);
  else if (lowBatt) oled.drawStr(8, 102, "LOW BATT");
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
// BATTERY is only sent when battery sensing is switched on in the settings.
void logData() {
  static uint32_t t0 = 0;
  if (millis() - t0 < cfgMs(P_LP)) return;
  t0 = millis();
  if (isnan(waterC)) return;                     // no valid reading yet
  char line[128];
  int n = snprintf(line, sizeof line, "TEMP=%.2f,TARGET=%.1f,MODE=%s,PELTIER=%d,FAN=%d",
                   waterC, targetC, MODE_TXT[mode], tecDuty > 0, fanDuty > 0);
  if (!isnan(battV))
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
// "ad" = seconds of admin unlock left (0 = locked), "al" = seconds of PIN lock-out left, "dp" = 1 when the
// default PIN is still in use (only sent while unlocked).
void statusJson(char* b, size_t n) {
  char t[12] = "null", bv[12] = "null";
  float w = waterC;
  if (!isnan(w)) snprintf(t, sizeof t, "%.2f", w);
  if (!isnan(battV)) snprintf(bv, sizeof bv, "%.2f", battV);
  uint32_t now = millis();
  bool adm = adminOn && (int32_t)(adminUntil - now) > 0;
  unsigned ad = adm ? (adminUntil - now) / 1000 + 1 : 0;
  unsigned al = (pinLocked && (int32_t)(pinLockUntil - now) > 0) ? (pinLockUntil - now) / 1000 + 1 : 0;
  snprintf(b, n,
    "{\"t\":%s,\"tg\":%.0f,\"tmin\":%.0f,\"tmax\":%.0f,\"m\":\"%s\",\"f\":\"%s\",\"r\":%d,\"w\":%u,"
    "\"pel\":%u,\"fan\":%u,\"rpm\":%u,\"fc\":\"%s\",\"fp\":%u,\"fmin\":%u,\"bat\":%d,\"bv\":%s,\"lb\":%d,\"pw\":%u,"
    "\"pmin\":%.0f,\"ad\":%u,\"al\":%u,\"dp\":%d,\"up\":%lu,\"ev\":%u}",
    t, targetC, cfg[P_TMIN], cfg[P_TMAX], MODE_TXT[mode], FAULT_TXT[fault], reached ? 1 : 0, (unsigned)waitLeftS,
    tecDuty * 100U / 255, fanDuty * 100U / 255, (unsigned)fanRpm, fanCtl == FAN_AUTO ? "auto" : "manual",
    (unsigned)fanManualPct, (unsigned)fanFloorPct, battPct, bv, lowBatt ? 1 : 0, (unsigned)tecPowerPct,
    cfg[P_PMIN], ad, al, (adm && !strcmp(pinStr, DEFAULT_PIN)) ? 1 : 0, (unsigned long)millis(), (unsigned)evTotal);
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

// Number for JSON: up to 3 decimals, trailing zeros removed.
void fmtNum(char* b, size_t n, float v) {
  int len = snprintf(b, n, "%.3f", v);
  while (len > 1 && b[len - 1] == '0') b[--len] = '\0';
  if (len > 1 && b[len - 1] == '.') b[--len] = '\0';
  if (!strcmp(b, "-0")) strcpy(b, "0");
}

const char* resetReasonTxt() {
  switch (esp_reset_reason()) {
    case ESP_RST_POWERON:  return "POWER ON";
    case ESP_RST_SW:       return "SOFTWARE";
    case ESP_RST_PANIC:    return "CRASH";
    case ESP_RST_BROWNOUT: return "BROWNOUT";
    case ESP_RST_INT_WDT: case ESP_RST_TASK_WDT: case ESP_RST_WDT: return "WATCHDOG";
    case ESP_RST_DEEPSLEEP: return "SLEEP";
    default: return "OTHER";
  }
}

// One settings group as JSON (under 512 bytes): {"g":4,"p":[["be",0,0,1],...]} = [key, value, lowest, highest].
// Group 6 also carries the device name "nm"; group 7 is read-only diagnostics.
void cfgJson(uint8_t g, char* b, size_t n) {
  if (g == 7) {
    uint32_t now = millis();
    char br[16]; fmtNum(br, sizeof br, isnan(battRawV) ? 0.0f : battRawV);
    snprintf(b, n, "{\"g\":7,\"fw\":\"%s\",\"rr\":\"%s\",\"h\":%lu,\"fc\":[%u,%u,%u,%u],\"lf\":%u,\"sa\":%lu,\"br\":%s}",
      FW_VERSION, resetReasonTxt(), (unsigned long)ESP.getFreeHeap(), faultCnt[F_SENSOR], faultCnt[F_OVERTEMP],
      faultCnt[F_UNDERTEMP], faultCnt[F_FAN], lastFault, (unsigned long)(now - lastGoodRead), br);
    return;
  }
  size_t len = snprintf(b, n, "{\"g\":%u,\"p\":[", g);
  bool first = true;
  for (uint8_t i = 0; i < P_COUNT && len < n; i++) {
    if (PARAMS[i].group != g) continue;
    char v[16], lo[16], hi[16];
    fmtNum(v, sizeof v, cfg[i]); fmtNum(lo, sizeof lo, PARAMS[i].lo); fmtNum(hi, sizeof hi, PARAMS[i].hi);
    len += snprintf(b + len, n - len, "%s[\"%s\",%s,%s,%s]", first ? "" : ",", PARAMS[i].key, v, lo, hi);
    first = false;
  }
  if (len < n) len += snprintf(b + len, n - len, "]");
  if (g == 6 && len < n) len += snprintf(b + len, n - len, ",\"nm\":\"%s\"", btName);
  if (len < n) snprintf(b + len, n - len, "}");
}

struct PhoneCmd { char s[40]; };
QueueHandle_t phoneCmds = nullptr;           // written by the Bluetooth task, handled in loop()
BLECharacteristic* chNotify = nullptr;
volatile bool phoneConnected = false;
volatile uint8_t cfgSel = 0;                 // settings group the phone reads next (set by "G<n>")
bool phonePing = false;                      // tell the phone to refresh now

class PhoneServerCb : public BLEServerCallbacks {
  void onConnect(BLEServer*) override { phoneConnected = true; logEvent("Phone connected"); }
  void onDisconnect(BLEServer*) override { phoneConnected = false; adminOn = false; logEvent("Phone disconnected"); }
};
class StatusCb : public BLECharacteristicCallbacks {
  void onRead(BLECharacteristic* c) override {
    static char b[420]; statusJson(b, sizeof b); c->setValue((uint8_t*)b, strlen(b));
  }
};
class CfgCb : public BLECharacteristicCallbacks {
  void onRead(BLECharacteristic* c) override {
    static char b[512]; cfgJson(cfgSel, b, sizeof b); c->setValue((uint8_t*)b, strlen(b));
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
    if (v.length() == 2 && (v[0] == 'G' || v[0] == 'g') && v[1] >= '0' && v[1] <= '7') {   // pick the group to read: done here, so the next read sees it
      cfgSel = v[1] - '0';
      return;
    }
    PhoneCmd m{};
    strncpy(m.s, v.c_str(), sizeof m.s - 1);
    if (phoneCmds) xQueueSend(phoneCmds, &m, 0);   // full queue (8 waiting): the command is dropped
  }
};

void bleBegin() {
  phoneCmds = xQueueCreate(8, sizeof(PhoneCmd));
  BLEDevice::init(btName);                   // same name as Classic Bluetooth
  BLEDevice::setMTU(185);                    // lets the phone use bigger packets if it asks
  BLEServer* server = BLEDevice::createServer();
  server->setCallbacks(new PhoneServerCb());
  server->advertiseOnDisconnect(true);       // visible again as soon as the phone leaves
  BLEService* svc = server->createService(BLE_SERVICE_UUID);
  svc->createCharacteristic(BLE_STATUS_UUID, BLECharacteristic::PROPERTY_READ)->setCallbacks(new StatusCb());
  svc->createCharacteristic(BLE_LOG_UUID, BLECharacteristic::PROPERTY_READ)->setCallbacks(new LogCb());
  svc->createCharacteristic(BLE_CFG_UUID, BLECharacteristic::PROPERTY_READ)->setCallbacks(new CfgCb());
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

// ---- Settings changes (admin) ----
// Checks a complete set of values: every value inside its lo/hi, and the values that belong together.
bool cfgValid(const float* c) {
  for (uint8_t i = 0; i < P_COUNT; i++)
    if (!(c[i] >= PARAMS[i].lo && c[i] <= PARAMS[i].hi)) return false;   // also rejects NaN
  return c[P_TMAX] >= c[P_TMIN] + 5.0f      // a usable target range
      && c[P_TMAX] + 3.0f <= c[P_OT]        // the highest target stays below the over-temperature stop
      && c[P_UT] + 3.0f <= c[P_TMIN]        // the lowest target stays above the freezing stop
      && c[P_BM] + 0.3f <= c[P_BF]          // empty below full
      && c[P_LC] + 0.1f <= c[P_LR]          // the cutoff stays below the resume level
      && c[P_LR] <= c[P_BF];
}

void saveParam(uint8_t i) {
  char k[8]; snprintf(k, sizeof k, "c_%s", PARAMS[i].key);
  if (cfg[i] == PARAMS[i].def) prefs.remove(k); else prefs.putFloat(k, cfg[i]);
}

void loadCfg() {
  for (uint8_t i = 0; i < P_COUNT; i++) {
    char k[8]; snprintf(k, sizeof k, "c_%s", PARAMS[i].key);
    cfg[i] = prefs.getFloat(k, PARAMS[i].def);
  }
  if (!cfgValid(cfg)) for (uint8_t i = 0; i < P_COUNT; i++) cfg[i] = PARAMS[i].def;   // damaged or conflicting: factory values
}

// Things that depend on the settings: keep the target and power limit inside their ranges, redo the OLED.
void applyCfg() {
  targetC = constrain(targetC, cfg[P_TMIN], cfg[P_TMAX]);
  if (tecPowerPct < (uint8_t)cfg[P_PMIN]) { tecPowerPct = (uint8_t)cfg[P_PMIN]; prefs.putUChar("power", tecPowerPct); }
  applyOled();
}

// Sets one value if the whole new set stays valid. The heat/cool wiring swap is refused while the Peltier is driven.
bool setParam(uint8_t i, float v) {
  float c[P_COUNT]; memcpy(c, cfg, sizeof c); c[i] = v;
  if (!cfgValid(c)) return false;
  if (i == P_HR && v != cfg[i]) {
    if (tecDuty > 0) return false;
    lastDriven = lastDriven == HEAT ? COOL : lastDriven == COOL ? HEAT : IDLE;   // same physical side, new name: keeps the reversal rest honest
  }
  cfg[i] = v; saveParam(i); applyCfg();
  return true;
}

void resetDefaults() {
  for (uint8_t i = 0; i < P_COUNT; i++) {
    if (i == P_HR && cfg[i] != PARAMS[i].def) lastDriven = lastDriven == HEAT ? COOL : lastDriven == COOL ? HEAT : IDLE;
    cfg[i] = PARAMS[i].def; saveParam(i);
  }
  strlcpy(btName, BT_NAME, sizeof btName); prefs.remove("name");
  applyCfg();
}

// Battery calibration: the phone sends the pack voltage measured with a multimeter and the divider ratio is
// worked out from the voltage at GPIO35.
bool calibrateBatt(float measured) {
  if (!cfgOn(P_BE) || isnan(battRawV) || battRawV < 0.2f) return false;
  return setParam(P_BD, roundf(measured / battRawV * 1000.0f) / 1000.0f);
}

bool nameOk(const char* n) {
  size_t len = strlen(n);
  if (len < 1 || len > 15) return false;
  for (size_t i = 0; i < len; i++) if (!isalnum((unsigned char)n[i]) && n[i] != ' ' && n[i] != '-' && n[i] != '_') return false;
  return true;
}

bool pinOk(const char* p) {
  size_t len = strlen(p);
  if (len < 4 || len > 8) return false;
  for (size_t i = 0; i < len; i++) if (!isdigit((unsigned char)p[i])) return false;
  return true;
}

// Admin commands (all but U and L need the unlock):
//   U<pin>        unlock (5 wrong PINs lock the unlock for 60 s); L locks again; the unlock also ends
//                 5 min after the last admin command and when the phone disconnects
//   C<key>=<val>  change a setting, e.g. Cot=55 (see PARAMS); Cnm=<name> device name (needs a reboot);
//                 Cpin=<4-8 digits> new PIN; Ccal=<volts> battery calibration with a multimeter reading
//   TF<1-30>      spin the fan at full speed for this many seconds (only while idle)
//   RD            all settings back to factory values (not the PIN, only while the Peltier is off)
//   RF            clear the fault history; RB reboot
// G<0-7> (select the settings group the phone reads next) is handled in CmdCb.
// Returns true when the text was an admin command (done or refused).
bool handleAdmin(char* s) {
  uint32_t now = millis();
  char c0 = toupper((unsigned char)s[0]), c1 = c0 ? toupper((unsigned char)s[1]) : 0;
  if (c0 == 'U') {
    if (pinLocked && (int32_t)(pinLockUntil - now) > 0) { logEvent("Admin: PIN locked out"); return true; }
    pinLocked = false;
    if (strcmp(s + 1, pinStr) == 0) { adminOn = true; adminUntil = now + ADMIN_TIMEOUT_MS; pinFails = 0; logEvent("Admin unlocked"); }
    else if (++pinFails >= 5) { pinFails = 0; pinLocked = true; pinLockUntil = now + 60000; logEvent("Wrong PIN: locked 60 s"); }
    else logEvent("Admin: wrong PIN");
    return true;
  }
  if (c0 == 'L' && c1 == '\0') { adminOn = false; logEvent("Admin locked"); return true; }
  bool admin = c0 == 'C' || (c0 == 'T' && c1 == 'F') || (c0 == 'R' && (c1 == 'D' || c1 == 'F' || c1 == 'B') && s[2] == '\0');
  if (!admin) return false;
  if (!adminOn || (int32_t)(adminUntil - now) <= 0) { adminOn = false; logEvent("Admin: locked, enter PIN"); return true; }
  adminUntil = now + ADMIN_TIMEOUT_MS;

  if (c0 == 'R' && c1 == 'B') { runDir = IDLE; newRun = false; tecStop(); logEvent("Rebooting"); rebootPending = true; rebootAt = now + 700; }
  else if (c0 == 'R' && c1 == 'F') {
    memset(faultCnt, 0, sizeof faultCnt); lastFault = 0;
    for (uint8_t f = 1; f < 5; f++) { char k[8]; snprintf(k, sizeof k, "fc%u", f); prefs.remove(k); }
    prefs.remove("lastf"); logEvent("Fault history cleared");
  } else if (c0 == 'R' && c1 == 'D') {
    if (tecDuty > 0) logEvent("Reset: stop the run first");
    else { resetDefaults(); logEvent("Settings reset"); }
  } else if (c0 == 'T') {
    char* end = nullptr; long v = strtol(s + 2, &end, 10);
    if (end != s + 2 && *end == '\0' && v >= 1 && v <= 30 && mode == IDLE) { fanTest = true; fanTestEnd = now + v * 1000UL; logEvent("Fan test %lds", v); }
    else logEvent("Fan test refused");
  } else {                                       // C<key>=<value>
    char* eq = strchr(s + 1, '=');
    if (!eq) { logEvent("Phone: bad command"); return true; }
    *eq = '\0'; const char* key = s + 1; const char* val = eq + 1;
    if (!strcmp(key, "pin")) {
      if (pinOk(val)) { strlcpy(pinStr, val, sizeof pinStr); prefs.putString("pin", pinStr); logEvent("PIN changed"); }
      else logEvent("PIN needs 4-8 digits");
    } else if (!strcmp(key, "nm")) {
      if (nameOk(val)) { strlcpy(btName, val, sizeof btName); prefs.putString("name", btName); logEvent("Name saved, reboot"); }
      else logEvent("Name refused");
    } else if (!strcmp(key, "cal")) {
      char* end = nullptr; float v = strtof(val, &end);
      if (end != val && *end == '\0' && calibrateBatt(v)) logEvent("Battery calibrated");
      else logEvent("Calibration refused");
    } else {
      int idx = -1;
      for (uint8_t i = 0; i < P_COUNT; i++) if (!strcmp(key, PARAMS[i].key)) idx = i;
      char* end = nullptr; float v = idx >= 0 ? strtof(val, &end) : 0;
      if (idx >= 0 && end != val && *end == '\0' && setParam(idx, v)) logEvent("Set %s=%.8s", key, val);
      else logEvent("Refused %.8s=%.8s", key, val);
    }
  }
  return true;
}

// Commands from the phone (one short text per write):
//   T<tmin-tmax>  set the target and start a run (same as a button press)
//   S             start a run toward the current target
//   X             stop the run (Peltier off)
//   FA            fan AUTO (the normal behaviour)
//   FM<0-100>     fan MANUAL at this %, never below the fan floors ("fmc"/"fmh") while the Peltier runs
//   P<pmin-100>   Peltier power limit, % (saved)
// plus the admin commands above. Fault cutoffs, the reversal rest and the fault latch work exactly as with the buttons.
void handlePhone() {
  uint32_t now = millis();
  if (adminOn && (int32_t)(adminUntil - now) <= 0) { adminOn = false; logEvent("Admin locked (timeout)"); }
  if (rebootPending && (int32_t)(now - rebootAt) >= 0) { tecStop(); ESP.restart(); }
  if (!phoneCmds) return;
  PhoneCmd m;
  while (xQueueReceive(phoneCmds, &m, 0) == pdTRUE) {
    char* s = m.s;
    for (int i = (int)strlen(s) - 1; i >= 0 && isspace((unsigned char)s[i]); i--) s[i] = '\0';
    lastActivity = now;
    if (handleAdmin(s)) { phonePing = true; continue; }
    char* end = nullptr;
    long v = 0;
    char c0 = toupper((unsigned char)s[0]), c1 = c0 ? toupper((unsigned char)s[1]) : 0;
    if (c0 == 'T' && (v = strtol(s + 1, &end, 10), end != s + 1 && *end == '\0') &&
        v >= (long)cfg[P_TMIN] && v <= (long)cfg[P_TMAX]) {
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
    } else if (c0 == 'P' && (v = strtol(s + 1, &end, 10), end != s + 1 && *end == '\0') &&
               v >= (long)cfg[P_PMIN] && v <= 100) {
      tecPowerPct = v; prefs.putUChar("power", tecPowerPct); logEvent("Phone: power %ld%%", v);
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
  static bool lastLow = false;
  if (lowBatt != lastLow) { logEvent(lowBatt ? "LOW BATTERY: Peltier off" : "Battery OK again"); lastLow = lowBatt; }
  // A held button changes the target every 150 ms: log it once it has been steady for 1.5 s.
  if (targetC != lastTarget) { lastTarget = targetC; targetSince = now; }
  else if (targetC != loggedTarget && now - targetSince > 1500) { loggedTarget = targetC; logEvent("Target %.0f C", targetC); }
}

// Saves the target once it has been steady for 3 s (a held button would otherwise write flash often).
void saveTarget() {
  static float saved = NAN, last = NAN;
  static uint32_t since = 0;
  if (isnan(saved)) saved = last = targetC;
  if (targetC != last) { last = targetC; since = millis(); }
  else if (targetC != saved && millis() - since > 3000) { prefs.putFloat("target", targetC); saved = targetC; }
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
  prefs.begin("thermox", false);                 // saved settings, target and power limit (no run starts)
  loadCfg();
  targetC = constrain(prefs.getFloat("target", TARGET_DEFAULT), cfg[P_TMIN], cfg[P_TMAX]);
  tecPowerPct = constrain(prefs.getUChar("power", 100), (uint8_t)cfg[P_PMIN], (uint8_t)100);
  String nm = prefs.getString("name", BT_NAME);
  if (nameOk(nm.c_str())) strlcpy(btName, nm.c_str(), sizeof btName);
  String pn = prefs.getString("pin", DEFAULT_PIN);
  strlcpy(pinStr, pinOk(pn.c_str()) ? pn.c_str() : DEFAULT_PIN, sizeof pinStr);
  for (uint8_t f = 1; f < 5; f++) { char k[8]; snprintf(k, sizeof k, "fc%u", f); faultCnt[f] = prefs.getUShort(k, 0); }
  lastFault = prefs.getUChar("lastf", 0);
  if (ENABLE_BT_LOGGING) SerialBT.begin(btName);
  pinMode(PIN_REN, OUTPUT); pinMode(PIN_LEN, OUTPUT);
  digitalWrite(PIN_REN, LOW); digitalWrite(PIN_LEN, LOW);
  ledcAttach(PIN_RPWM, PWM_TEC_HZ, PWM_BITS); ledcAttach(PIN_LPWM, PWM_TEC_HZ, PWM_BITS);
  ledcAttach(PIN_FAN_PWM, PWM_FAN_HZ, PWM_BITS);
  tecStop(); setFan(0);
  if (ENABLE_BLE_CONTROL) bleBegin();            // after the Peltier and fan outputs are safely off

  pinMode(PIN_BTN_DOWN, INPUT_PULLUP); pinMode(PIN_BTN_UP, INPUT_PULLUP);
  pinMode(PIN_FAN_TACH, INPUT);                  // GPIO34: external 10k pull-up to 3.3V
  attachInterrupt(digitalPinToInterrupt(PIN_FAN_TACH), onTach, FALLING);
  analogSetPinAttenuation(PIN_BATT_ADC, ADC_11db);   // only read when battery sensing is on

  // PIN recovery: holding both buttons while powering on for 3 s puts the admin PIN back to the default.
  if (digitalRead(PIN_BTN_DOWN) == LOW && digitalRead(PIN_BTN_UP) == LOW) {
    uint32_t t0 = millis();
    while (millis() - t0 < 3000 && digitalRead(PIN_BTN_DOWN) == LOW && digitalRead(PIN_BTN_UP) == LOW) delay(20);
    if (millis() - t0 >= 3000) { strlcpy(pinStr, DEFAULT_PIN, sizeof pinStr); prefs.putString("pin", pinStr); logEvent("PIN reset to default"); }
  }

  Wire.begin(PIN_SDA, PIN_SCL);
  oled.setI2CAddress(0x3C << 1);
  oled.begin();
  applyOled();

  ds.begin(); ds.setWaitForConversion(false); ds.setResolution(12);
  lastGoodRead = millis();
}

void loop() {
  readSensor(); readFan(); readBattery();
  handleButtons();
  handlePhone();
  control();
  trackEvents();
  saveTarget();
  drawUI();
  logData();
  bleTick();
}
