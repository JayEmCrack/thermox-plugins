/*
  ThermoX - Portable Dual-Temperature Smart Water Bottle
  Target board : ESP32 (Arduino-ESP32 core 3.x)  -- NOT an Arduino Uno (see README.md)
  Libraries    : OneWire, DallasTemperature, U8g2

  Behaviour:
   - Two buttons, two programs: COLD (blue button) holds the water at 22 C, HOT holds it at 50 C.
     Press the same button again for OFF. Pressing the other button switches program (after the 60 s rest).
   - DS18B20 measures water temp; BTS7960 drives one TEC1-12706 in either direction
   - Thermostat: the Peltier first pulls the water to the target at full power (the phone's power limit).
     Then it holds it: when the water drifts HOLD_BAND_C (0.5 C) away it runs again at HOLD_POWER_PCT (50 %)
     until the water is back at the target. This goes on until OFF. Nothing starts by itself at power-up.
   - Hot <-> cold reversal is blocked for REVERSE_COOLDOWN_MS (60 s) with the Peltier off
   - Fan: only while the Peltier COOLS, at 60 % (AUTO) or the phone's MANUAL % (50-100 %). Off while it heats
     (FAN_HEAT_PCT = 0) and while the Peltier is off. A fault runs it at FAN_FAULT_PCT.
   - SH1107 128x128 OLED, mounted in LANDSCAPE (on its side). It shows water temp, program, state, fan and the
     battery %. While the Peltier runs the battery % and bar are replaced by RUNNING (the pack voltage drops
     under load); the battery % is the last one read with the Peltier off.
     The phone can switch it on/off and set its brightness, orientation and title (saved on the device).
   - Phone control over Bluetooth Low Energy (page: dashboard/phone.html): live status, COLD / HOT / STOP,
     the COLD and HOT targets, fan AUTO or MANUAL %, Peltier power limit (see README.md)
   - The two targets, the power limit and the OLED settings are saved; ThermoX starts OFF after power-up
   - Low-battery cutoff: OFF (ENABLE_LOW_BATT_CUTOFF = false). The battery % is still shown; the BMS still cuts
     the power when the cells are empty. With it on (needs ENABLE_BATTERY_SENSE) it stops the Peltier and blocks new runs until the
     battery recovers
   - Charging (needs ENABLE_CHARGE_DETECT): while a charger is plugged into J10 the OLED shows CHARGING,
     the Peltier stays off and no run can start, from the buttons or the phone
   - A fault (SENSOR, OVER TEMP, TOO COLD, FAN STALL) stops the Peltier. A lost sensor clears by itself when
     it reads again; the others clear on the next button press once the water is back inside the limits
   - USB Serial Monitor (115200): a "# ..." status line every 2 s and a "PRESS: ..." line for every button
     press that says what the press did, or what blocked it
   - Button 1 / Button 2 roles: COLD_IS_BUTTON1 (true = Button 1 on GPIO18 is COLD)
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
constexpr uint8_t PIN_BTN_DOWN = 18;   // Button 1 (moved from GPIO32)
constexpr uint8_t PIN_BTN_UP   = 33;   // Button 2
constexpr uint8_t PIN_SDA      = 21;
constexpr uint8_t PIN_SCL      = 22;
constexpr uint8_t PIN_LPWM     = 27;   // BTS7960 LPWM
constexpr uint8_t PIN_RPWM     = 26;   // BTS7960 RPWM
constexpr uint8_t PIN_LEN      = 13;   // BTS7960 L_EN
constexpr uint8_t PIN_REN      = 25;   // BTS7960 R_EN
constexpr uint8_t PIN_ONEWIRE  = 14;   // DS18B20 data (4.7k pull-up to 3.3V)
constexpr uint8_t PIN_FAN_PWM  = 23;   // SUNON control (blue/PWM wire)
constexpr uint8_t PIN_FAN_TACH = 35;   // SUNON FG (input-only pin: needs external pull-up; GPIO34 no longer used)
constexpr uint8_t PIN_CHG_DET  = 19;   // HIGH while a charger is plugged into J10 (R5 100k / R6 33k divider)

// Charge detection: true for the ThermoX one-board PCB (J10 CHARGE). Set false on a board without
// the R5/R6 divider, or GPIO19 floats and may read as charging.
constexpr bool    ENABLE_CHARGE_DETECT = true;
constexpr uint32_t CHARGE_DEBOUNCE_MS = 500;  // the pin must stay the same this long before it counts
// Charging screen (needs ENABLE_BATTERY_SENSE): 4 bars of 25 %, FULL once the pack reaches what the
// 12.6 V charger gives through D2 (about 12.1 V) and stays there. Check the real value with a meter.
constexpr float   CHARGE_FULL_V  = 4.04f;     // per cell
constexpr uint32_t CHARGE_FULL_MS = 60000;    // must stay at CHARGE_FULL_V this long before FULL

// Battery gauge on GPIO36 (VP): battery % on the OLED and the phone, the low-battery cutoff and the charging bars.
// The universal PCB has the divider (R3 100k / R4 22k from the 3S pack). Set false on a board without it.
constexpr bool    ENABLE_BATTERY_SENSE = true;
constexpr uint8_t PIN_BATT_ADC = 36;   // VP pin, ADC1 (moved from GPIO35)
constexpr float   BATT_DIVIDER = 5.545f;    // (100k + 22k) / 22k
constexpr float   BATT_EMPTY_V = 3.3f;      // per cell, Li-ion
constexpr float   BATT_FULL_V  = 4.15f;
constexpr uint8_t BATT_CELLS = 3;           // Li-ion cells in series (3S pack); keep GPIO36 below ~3.1 V
// Low-battery cutoff. false = removed: ThermoX keeps running on a low battery until the BMS cuts the power
// (about 3.0 V per cell). The battery % on the OLED and the phone still works. true = Peltier stops below 3.30 V per cell.
constexpr bool    ENABLE_LOW_BATT_CUTOFF = false;
constexpr float   LOW_BATT_CUTOFF_V = 3.30f;  // per cell: Peltier stops below this...
constexpr uint32_t LOW_BATT_DELAY_MS = 5000;  // ...for this long (ignores short dips under load)
constexpr float   LOW_BATT_RESUME_V = 3.60f;  // per cell: new runs allowed again above this
constexpr float   BATT_PRESENT_V = 6.0f;      // pack: below this no battery is connected (bench test on USB-C):
                                              // no battery %, no low-battery cutoff

// ---------------- Tunables ----------------
// Two programs, one per button. The phone can change both targets (saved).
constexpr bool  COLD_IS_BUTTON1 = true;      // true: Button 1 (GPIO18) = COLD (blue), Button 2 (GPIO33) = HOT
constexpr float COLD_TARGET_DEFAULT = 22.0f, HOT_TARGET_DEFAULT = 50.0f;
constexpr float COLD_TARGET_MIN = 10.0f, COLD_TARGET_MAX = 30.0f;   // what the phone may set for COLD
constexpr float HOT_TARGET_MIN = 35.0f,  HOT_TARGET_MAX = 52.0f;    // what the phone may set for HOT (cutoff 55 C)
constexpr float HOLD_BAND_C = 0.5f;          // thermostat: the Peltier runs again when the water is this far off
constexpr uint8_t HOLD_POWER_PCT = 50;       // Peltier power while holding the target, %
constexpr uint32_t BATT_REST_MS = 3000;      // battery % uses only samples taken 3 s or more after the Peltier stops
constexpr float OVERTEMP_CUTOFF = 55.0f;     // C, hard stop
constexpr float UNDERTEMP_CUTOFF = 5.0f;     // C, hard stop (freezing)
constexpr uint8_t TEC_MAX_DUTY = 255;        // full power; each run uses TEC_MAX_DUTY x tecPowerPct
constexpr uint8_t POWER_MIN_PCT = 30;        // lowest Peltier power the phone can set, %
constexpr bool    HEAT_ON_RPWM = true;       // swap if your wiring heats on LPWM instead
constexpr uint32_t REVERSE_COOLDOWN_MS = 60000; // Peltier must rest this long (off) before the direction reverses
constexpr uint32_t FAN_RUNON_MS = 0;         // fan run-on after cooling stops; 0 = fan off immediately
constexpr uint32_t SENSOR_FAIL_MS = 5000;
constexpr uint32_t FAN_STALL_GRACE_MS = 5000;
// Fan speed sensor (FG, yellow wire). false = the yellow wire is NOT connected (tape it off): the fan is still
// controlled by PWM, but there is no rpm reading and no FAN STALL check. Check by eye that the fan spins.
// true only after measuring the yellow wire alone (fan on 12 V, ESP32 out): it must read about 0 V.
constexpr bool     ENABLE_FAN_TACH = false;
constexpr uint16_t FAN_MIN_RPM = 500;        // below this while commanded => stall (only with ENABLE_FAN_TACH)
constexpr uint8_t  FAN_PULSES_PER_REV = 2;   // SUNON 4-wire FG standard

// Fan speeds. COOLING: AUTO (the default) 60 %, MANUAL from the phone 50-100 %. HEATING: off.
constexpr uint8_t  FAN_MAX_PCT       = 100;  // highest speed the phone (MANUAL) can set, %
constexpr uint8_t  FAN_AUTO_COOL_PCT = 60;   // AUTO speed while COOLING, %
constexpr uint8_t  FAN_HEAT_PCT      = 0;    // speed while HEATING, % (0 = off; try 60 if heating is slow)
constexpr uint8_t  FAN_FAULT_PCT     = 60;   // speed during a fault (Peltier off), %
constexpr uint8_t  FAN_RUNON_PCT     = 35;   // speed during the run-on after a run (FAN_RUNON_MS), %
#define FAN_PCT_TO_DUTY(pct) ((uint8_t)(((pct) * 255U + 50) / 100))   // fan % -> PWM duty 0..255
constexpr uint8_t  FAN_MAX_DUTY = FAN_PCT_TO_DUTY(FAN_MAX_PCT);
// Fan PWM wiring. false = GPIO23 -> R7 1k -> fan PWM wire (resistor only, as on the universal PCB).
// true  = only if an NPN transistor sits between GPIO23 and the fan (it turns the signal upside down).
constexpr bool     FAN_PWM_INVERTED = false;
// Tach glitch filter (instead of a capacitor): FG pulses closer together than this are noise and are
// not counted. 300 us still counts a fan up to 50,000 rpm (2 pulses per turn).
constexpr uint32_t FAN_TACH_MIN_US = 300;
// Tach plausibility: a reading above this is noise, not a real speed. It then counts as 0 rpm, so a fan
// that has really stopped is still caught by the stall check. Set it a little above your fan's 100 % speed.
constexpr uint16_t FAN_RPM_MAX_VALID = 25000;

constexpr uint32_t PWM_TEC_HZ = 20000, PWM_FAN_HZ = 25000;
constexpr uint8_t  PWM_BITS = 8;

constexpr bool    ENABLE_BT_LOGGING = true;
constexpr char    BT_NAME[] = "ThermoX";
constexpr uint32_t LOG_PERIOD_MS = 2000;   // 1-5 s is reasonable

// ---------------- Phone control (Bluetooth Low Energy) ----------------
// The phone page dashboard/phone.html connects with Web Bluetooth (Chrome on Android). It shows the
// status and can start COLD or HOT, stop, set both targets, the fan, the power limit and the OLED. The Classic Bluetooth logging
// above keeps working at the same time.
constexpr bool     ENABLE_BLE_CONTROL = true;
constexpr uint8_t  FAN_MIN_PCT_COOL = 50;    // MANUAL fan never goes below this % while COOLING (hot side needs air)
static_assert(FAN_MAX_PCT <= 100 && FAN_AUTO_COOL_PCT <= FAN_MAX_PCT && FAN_HEAT_PCT <= FAN_MAX_PCT &&
              FAN_FAULT_PCT <= FAN_MAX_PCT && FAN_RUNON_PCT <= FAN_MAX_PCT && FAN_MIN_PCT_COOL <= FAN_MAX_PCT,
              "fan speeds must not be above FAN_MAX_PCT");
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
// GME128128-01 (1.5" SH1107 128x128) needs x offset 0: the PIMORONI variant. The plain
// U8G2_SH1107_128X128 driver adds a 96-pixel offset, which shifts and wraps the picture.
// The OLED sits in LANDSCAPE in the case (module on its side), so the picture is turned 90 degrees.
// The phone can change the orientation, brightness and title; they are saved. These are the first-time values.
// Orientation: 0 = portrait (old upright mount), 1 = landscape, 2 = portrait upside down, 3 = landscape the other way.
constexpr uint8_t OLED_ROT_DEFAULT = 1;
constexpr uint8_t OLED_BRIGHT_DEFAULT = 100;   // %
constexpr char    OLED_TITLE_DEFAULT[] = "ThermoX";
constexpr uint8_t OLED_TITLE_MAX = 10;         // characters (fits next to the battery % at the top)
U8G2_SH1107_PIMORONI_128X128_F_HW_I2C oled(U8G2_R1, U8X8_PIN_NONE);

float waterC = NAN;
float coldTargetC = COLD_TARGET_DEFAULT, hotTargetC = HOT_TARGET_DEFAULT;   // saved
enum Prog : uint8_t { P_OFF, P_COLD, P_HOT };
const char* PROG_TXT[] = {"off", "cold", "hot"};
Prog prog = P_OFF;                           // program chosen with the buttons or the phone
int8_t progReq = -1;                         // a button or the phone asked for this program (-1 = nothing)
bool approach = false;                       // first pull to the target at full power; then the thermostat holds it
bool holdOn = false;                         // thermostat: the Peltier is running to bring the water back
Mode mode = IDLE; Fault fault = F_NONE;
uint8_t tecDuty = 0, fanDuty = 0;
uint32_t lastGoodRead = 0, lastTecActive = 0, modeSince = 0, fanOnSince = 0;
Mode lastDriven = IDLE;                      // last direction the Peltier was driven in
bool reached = false;                        // the target has been reached once: the thermostat is holding it
uint16_t waitLeftS = 0;                      // seconds left of the reversal cooldown (0 = none)
volatile uint32_t tachPulses = 0;
uint16_t fanRpm = 0;
int battPct = -1;
float battV = NAN;                           // stays NaN unless ENABLE_BATTERY_SENSE
int battRestPct = -1;                        // battery % read with the Peltier off (shown on the OLED and the phone)
float battRestV = NAN;
uint32_t tecOffSince = 0;                    // when the Peltier last stopped
enum FanCtl : uint8_t { FAN_AUTO, FAN_MANUAL };
FanCtl fanCtl = FAN_AUTO;                    // set from the phone; back to AUTO after every power-up
uint8_t fanManualPct = 60;                   // MANUAL fan speed from the phone, % (used while cooling)
uint8_t fanFloorPct = 0;                     // safety minimum for the MANUAL fan right now, %
uint8_t tecPowerPct = 100;                   // Peltier power limit from the phone, % (saved)
bool lowBatt = false;                        // low-battery cutoff active
uint8_t oledRot = OLED_ROT_DEFAULT;          // OLED orientation 0-3 (saved)
uint8_t oledBright = OLED_BRIGHT_DEFAULT;    // OLED brightness % (saved)
bool oledOn = true;                          // screen on/off from the phone (back on after every power-up)
char oledTitle[OLED_TITLE_MAX + 1] = "ThermoX";   // top-left text on the OLED (saved)
bool charging = false;                       // charger plugged in: ThermoX locked
bool chargeFull = false;                     // charging and the pack is full for this charger
int chgPct = -1;                             // charge level on the CHARGING screen (-1 = not measured)
uint32_t lowBattSince = 0;
Preferences prefs;

// Declared before the first function so the prototype Arduino generates for btnStep() compiles.
struct Btn { uint8_t pin; bool last; uint32_t since, rep; };
void logEvent(const char* fmt, ...);         // defined further down; declared here so every compiler finds it

void IRAM_ATTR onTach() {
  static uint32_t lastUs = 0;
  uint32_t now = micros();
  if (now - lastUs < FAN_TACH_MIN_US) return;   // too soon after the last pulse: noise
  lastUs = now;
  tachPulses = tachPulses + 1;
}

// ---------------- Outputs ----------------
void setFan(uint8_t d) {
  if (d > FAN_MAX_DUTY) d = FAN_MAX_DUTY;    // speed limit: never faster than FAN_MAX_PCT
  if (d > fanDuty) fanOnSince = 0;           // faster: give the fan time to spin up before the stall check
  fanDuty = d; ledcWrite(PIN_FAN_PWM, FAN_PWM_INVERTED ? 255 - d : d);
}

// Fan duty for mode m. COOL: AUTO uses autoDuty, MANUAL the phone's % (never below FAN_MIN_PCT_COOL).
// HEAT and IDLE: autoDuty (FAN_HEAT_PCT = off while heating; off or the run-on when idle).
uint8_t fanDutyFor(Mode m, uint8_t autoDuty) {
  fanFloorPct = (m == COOL) ? FAN_MIN_PCT_COOL : 0;
  if (m != COOL || fanCtl == FAN_AUTO) return autoDuty;
  uint8_t pct = min(max(fanManualPct, fanFloorPct), FAN_MAX_PCT);
  return FAN_PCT_TO_DUTY(pct);
}

// Applies the phone's OLED settings: orientation, brightness, on/off.
void oledApply() {
  switch (oledRot & 3) {
    case 0: oled.setDisplayRotation(U8G2_R0); break;
    case 2: oled.setDisplayRotation(U8G2_R2); break;
    case 3: oled.setDisplayRotation(U8G2_R3); break;
    default: oled.setDisplayRotation(U8G2_R1); break;
  }
  oled.setContrast((uint8_t)(1 + oledBright * 254U / 100));   // 0 % is dim, not black
  oled.setPowerSave(oledOn ? 0 : 1);
}

// A title from the phone: 1-OLED_TITLE_MAX characters, letters, digits, space and . - _ # ! ( ) +
// (nothing that would break the status JSON).
bool titleOk(const char* t) {
  size_t n = strlen(t);
  if (n == 0 || n > OLED_TITLE_MAX) return false;
  for (size_t i = 0; i < n; i++) {
    char c = t[i];
    if (!(isalnum((unsigned char)c) || strchr(" .-_#!()+", c))) return false;
  }
  return true;
}

void tecStop() {
  if (tecDuty > 0) tecOffSince = millis();
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

void enterFault(Fault f) { tecStop(); setFan(FAN_PCT_TO_DUTY(FAN_FAULT_PCT)); mode = FAULT; fault = f; modeSince = millis(); }

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
  uint32_t rpm = (uint32_t)p * 60000UL / (now - t0) / FAN_PULSES_PER_REV;
  fanRpm = rpm > FAN_RPM_MAX_VALID ? 0 : (uint16_t)rpm;   // noise is not a speed: count it as stopped
  t0 = now;
}

void readBattery() {
  if (!ENABLE_BATTERY_SENSE) return;
  static uint32_t t0 = 0; uint32_t now = millis();
  if (now - t0 < 2000) return; t0 = now;
  float v = analogReadMilliVolts(PIN_BATT_ADC) / 1000.0f * BATT_DIVIDER;
  battV = isnan(battV) ? v : battV * 0.7f + v * 0.3f;   // smoothed pack voltage
  if (battV < BATT_PRESENT_V) battPct = -1;
  else battPct = constrain((int)((battV / BATT_CELLS - BATT_EMPTY_V) * 100 / (BATT_FULL_V - BATT_EMPTY_V)), 0, 100);
  // The Peltier pulls about 6 A, so the pack voltage drops while it runs. The % shown on the OLED and the
  // phone comes from its own average of samples taken with the Peltier off for BATT_REST_MS (resting voltage).
  if ((tecDuty == 0 && now - tecOffSince > BATT_REST_MS) || isnan(battRestV)) {
    battRestV = isnan(battRestV) ? v : battRestV * 0.6f + v * 0.4f;
    battRestPct = battRestV < BATT_PRESENT_V ? -1
      : constrain((int)((battRestV / BATT_CELLS - BATT_EMPTY_V) * 100 / (BATT_FULL_V - BATT_EMPTY_V)), 0, 100);
  }
}

// Charger on J10: GPIO19 reads HIGH through R5/R6. Debounced so plugging the jack in does not flicker.
void readCharger() {
  if (!ENABLE_CHARGE_DETECT) return;
  static bool last = false; static uint32_t since = 0;
  bool now = digitalRead(PIN_CHG_DET) == HIGH;
  if (now != last) { last = now; since = millis(); }
  else if (now != charging && millis() - since > CHARGE_DEBOUNCE_MS) charging = now;

  // Charge level: 0-100 % up to what this charger reaches, 100 % only once it is really full.
  static uint32_t fullSince = 0;
  if (!charging || isnan(battV) || battV < BATT_PRESENT_V) { chgPct = -1; chargeFull = false; fullSince = 0; return; }
  float cell = battV / BATT_CELLS;
  chgPct = constrain((int)((cell - BATT_EMPTY_V) * 100 / (CHARGE_FULL_V - BATT_EMPTY_V)), 0, 100);
  if (cell >= CHARGE_FULL_V) {
    if (fullSince == 0) fullSince = millis();
    if (millis() - fullSince > CHARGE_FULL_MS) chargeFull = true;
  } else {
    fullSince = 0;
    if (cell < CHARGE_FULL_V - 0.05f) chargeFull = false;
  }
  if (!chargeFull && chgPct > 99) chgPct = 99;
}

Btn bCold{COLD_IS_BUTTON1 ? PIN_BTN_DOWN : PIN_BTN_UP, HIGH, 0, 0};
Btn bHot{COLD_IS_BUTTON1 ? PIN_BTN_UP : PIN_BTN_DOWN, HIGH, 0, 0};

bool btnStep(Btn& b) {           // true once per press (30 ms debounce, no auto-repeat)
  bool s = digitalRead(b.pin); uint32_t now = millis(); bool fire = false;
  if (s != b.last && now - b.since > 30) {
    b.since = now; b.last = s;
    if (s == LOW) fire = true;
  }
  return fire;
}

// COLD button: COLD, or OFF if COLD is already on. HOT button: the same for HOT.
void handleButtons() {
  if (btnStep(bCold)) progReq = (prog == P_COLD) ? P_OFF : P_COLD;
  if (btnStep(bHot))  progReq = (prog == P_HOT)  ? P_OFF : P_HOT;
}

// Target of the program that is on (COLD target when OFF, for display only).
float progTarget() { return prog == P_HOT ? hotTargetC : coldTargetC; }

// Starts a program (or OFF). Every start first pulls to the target at full power.
void setProg(Prog p) {
  prog = p; approach = (p != P_OFF); holdOn = false; reached = false;
}

// ---------------- Serial Monitor help (USB only, 115200 baud) ----------------
// One line per button press / phone start: what it did, or what blocked it.
void pressInfo(const char* what) {
  char t[10] = "--";
  if (!isnan(waterC)) snprintf(t, sizeof t, "%.1f", waterC);
  Serial.printf("PRESS: water %s C -> %s\n", t, what);
}

// Status line every 2 s. It starts with '#', so receiver.py ignores it.
void debugLine() {
  static uint32_t t0 = 0;
  if (millis() - t0 < 2000) return;
  t0 = millis();
  char t[10] = "--", bv[10] = "--";
  if (!isnan(waterC)) snprintf(t, sizeof t, "%.1f", waterC);
  if (!isnan(battV)) snprintf(bv, sizeof bv, "%.1f", battV);
  const char* st = mode == FAULT ? FAULT_TXT[fault] : charging ? "CHARGING (locked)" : lowBatt ? "LOW BATT (locked)"
                   : waitLeftS ? "WAIT" : prog == P_OFF ? "OFF" : mode != IDLE ? MODE_TXT[mode] : reached ? "HOLD" : "READY";
  Serial.printf("# %s | %s %.0f C | water %s C | Peltier %u%% | fan %u%% %u rpm | batt %s V | charger pin %s | BTN1 %s BTN2 %s\n",
                st, PROG_TXT[prog], progTarget(), t, tecDuty * 100U / 255, fanDuty * 100U / 255, (unsigned)fanRpm, bv,
                digitalRead(PIN_CHG_DET) == HIGH ? "HIGH" : "low",
                digitalRead(PIN_BTN_DOWN) == LOW ? "DOWN" : "up", digitalRead(PIN_BTN_UP) == LOW ? "DOWN" : "up");
}

// ---------------- Control ----------------
void control() {
  uint32_t now = millis();
  int req = progReq; progReq = -1;             // a button or phone request waiting since the last pass

  // A fault keeps the Peltier off and the fan at FAN_FAULT_PCT. A lost sensor clears by itself as soon as it
  // reads again (ThermoX then stays OFF). The other faults clear on the next button press (or phone COLD/HOT),
  // once the water is back inside the limits; that press then starts its program as usual.
  if (mode == FAULT) {
    bool sensorOk = !isnan(waterC) && now - lastGoodRead <= SENSOR_FAIL_MS;
    bool tempOk = sensorOk && waterC < OVERTEMP_CUTOFF && waterC > UNDERTEMP_CUTOFF;
    bool clear = tempOk && (fault == F_SENSOR || req >= 0);
    if (!clear) {
      if (req >= 0) pressInfo(fault == F_SENSOR || !sensorOk ? "blocked: no temperature sensor reading (check the TEMP plug and R2)"
                              : fault == F_FAN ? "blocked: FAN STALL" : "blocked: water temperature outside 5..55 C");
      tecStop(); setFan(FAN_PCT_TO_DUTY(FAN_FAULT_PCT)); return;
    }
    logEvent("Fault cleared");
    fault = F_NONE; mode = IDLE; modeSince = now; reached = false;
    fanOnSince = 0;                              // a new 5 s spin-up time before the stall check
  }
  if (now - lastGoodRead > SENSOR_FAIL_MS) { setProg(P_OFF); enterFault(F_SENSOR); return; }
  if (waterC >= OVERTEMP_CUTOFF)  { setProg(P_OFF); enterFault(F_OVERTEMP);  return; }
  if (waterC <= UNDERTEMP_CUTOFF) { setProg(P_OFF); enterFault(F_UNDERTEMP); return; }

  // Low battery: stop and refuse COLD/HOT until the battery recovers (not latched). Off unless ENABLE_LOW_BATT_CUTOFF.
  if (!ENABLE_LOW_BATT_CUTOFF) { lowBatt = false; lowBattSince = 0; }
  else if (ENABLE_BATTERY_SENSE && !isnan(battV) && battV < BATT_PRESENT_V) { lowBatt = false; lowBattSince = 0; }
  else if (ENABLE_BATTERY_SENSE && !isnan(battV)) {
    float cell = battV / BATT_CELLS;
    if (cell < LOW_BATT_CUTOFF_V) {
      if (lowBattSince == 0) lowBattSince = now;
      if (now - lowBattSince > LOW_BATT_DELAY_MS) lowBatt = true;
    } else {
      lowBattSince = 0;
      if (cell > LOW_BATT_RESUME_V) lowBatt = false;
    }
  }
  if (lowBatt) {
    if (req > P_OFF) pressInfo("blocked: LOW BATT (battery below 9.9 V, charge it)");
    if (prog != P_OFF) setProg(P_OFF);
    req = -1;
  }
  // Charging: ThermoX must not be used. Stop and refuse COLD/HOT until the charger is unplugged.
  if (charging) {
    if (req > P_OFF) pressInfo("blocked: CHARGING (charger detect pin GPIO19 reads HIGH)");
    if (prog != P_OFF) setProg(P_OFF);
    req = -1;
  }
  if (req >= 0) {
    setProg((Prog)req);
    pressInfo(req == P_COLD ? "COLD program" : req == P_HOT ? "HOT program" : "OFF");
  }

  // Thermostat. First pull to the target (approach), then hold it: the Peltier runs again at HOLD_POWER_PCT
  // when the water drifts HOLD_BAND_C away from the target, and stops when it is back at the target.
  Mode want = IDLE;
  float tg = progTarget();
  if (prog == P_COLD && !isnan(waterC)) {
    if (approach) { if (waterC <= tg) { approach = false; reached = true; } }
    else if (holdOn) { if (waterC <= tg) holdOn = false; }
    else if (waterC >= tg + HOLD_BAND_C) holdOn = true;
    if (approach || holdOn) want = COOL;
  } else if (prog == P_HOT && !isnan(waterC)) {
    if (approach) { if (waterC >= tg) { approach = false; reached = true; } }
    else if (holdOn) { if (waterC >= tg) holdOn = false; }
    else if (waterC <= tg - HOLD_BAND_C) holdOn = true;
    if (approach || holdOn) want = HEAT;
  }

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
    bool runOn = lastDriven == COOL && now - lastTecActive < FAN_RUNON_MS;
    setFan(fanDutyFor(IDLE, runOn ? FAN_PCT_TO_DUTY(FAN_RUNON_PCT) : 0));
  } else {
    uint8_t pct = approach ? tecPowerPct : min(HOLD_POWER_PCT, tecPowerPct);
    tecDrive(mode, (uint8_t)((TEC_MAX_DUTY * pct + 50) / 100));
    setFan(fanDutyFor(mode, FAN_PCT_TO_DUTY(mode == COOL ? FAN_AUTO_COOL_PCT : FAN_HEAT_PCT)));
    lastTecActive = now; lastDriven = mode;
  }

  // Fan stall protection (only with the FG wire): TEC without airflow overheats its heat sink
  if (fanDuty > 0) {
    if (fanOnSince == 0) fanOnSince = now;
    if (ENABLE_FAN_TACH && now - fanOnSince > FAN_STALL_GRACE_MS && fanRpm < FAN_MIN_RPM && mode != IDLE)
      enterFault(F_FAN);
  } else fanOnSince = 0;
}

// ---------------- Display ----------------
void drawBattery(int x, int y) {
  oled.drawFrame(x, y, 22, 10); oled.drawBox(x + 22, y + 3, 2, 4);
  if (battRestPct >= 0) oled.drawBox(x + 2, y + 2, (18 * battRestPct) / 100, 6);
  else { oled.setFont(u8g2_font_5x7_tr); oled.drawStr(x + 8, y + 8, "?"); }
}

// Full screen shown while a charger is plugged in.
void drawCharging(char* b, size_t n) {
  oled.setFont(u8g2_font_6x12_tr);
  oled.drawStr(2, 12, oledTitle);
  if (!isnan(waterC)) { snprintf(b, n, "%.1fC", waterC); oled.drawStr(92, 12, b); }
  oled.drawHLine(0, 17, 128);
  oled.drawFrame(24, 26, 74, 30); oled.drawBox(98, 34, 5, 14);
  bool blink = (millis() / 500) % 2 == 0;
  if (chgPct < 0) {
    oled.drawBox(28, 30, ((millis() / 500) % 5) * 16 + 2, 22);   // no battery sensing: a moving bar only
  } else {
    // 4 bars of 25 %: the charged bars stay on, the bar being charged blinks, all 4 on when full
    int on = chargeFull ? 4 : min(chgPct / 25, 3);
    for (int i = 0; i < 4; i++)
      if (i < on || (i == on && blink)) oled.drawBox(28 + i * 17, 30, 15, 22);
  }
  oled.setFont(u8g2_font_9x15_tr);
  if (chargeFull) snprintf(b, n, "FULL 100%%");
  else if (chgPct >= 0) snprintf(b, n, "CHARGING %d%%", chgPct);
  else snprintf(b, n, "CHARGING");
  oled.drawStr(64 - (int)strlen(b) * 9 / 2, 76, b);
  oled.setFont(u8g2_font_6x12_tr);
  if (chargeFull) {
    oled.drawStr(4, 94, "Battery is full.");
    oled.drawStr(4, 106, "Unplug the charger");
    oled.drawStr(4, 118, "to use ThermoX.");
  } else {
    oled.drawStr(4, 94, "Do not use while");
    oled.drawStr(4, 106, "charging. Unplug the");
    oled.drawStr(4, 118, "charger to use it.");
  }
}

void drawUI() {
  static uint32_t t0 = 0; if (millis() - t0 < 250) return; t0 = millis();
  char b[24];
  oled.clearBuffer();
  if (charging) { drawCharging(b, sizeof b); oled.sendBuffer(); return; }
  oled.setFont(u8g2_font_6x12_tr);
  oled.drawStr(2, 12, oledTitle);
  if (tecDuty > 0) oled.drawStr(84, 12, "RUNNING");   // battery % hidden while the Peltier pulls the pack down
  else {
    if (battRestPct >= 0) { snprintf(b, sizeof b, "%d%%", battRestPct); oled.drawStr(97 - (int)strlen(b) * 6, 12, b); }
    drawBattery(100, 3);
  }
  oled.drawHLine(0, 17, 128);

  oled.setFont(u8g2_font_logisoso32_tn);
  if (isnan(waterC)) snprintf(b, sizeof b, "--.-"); else snprintf(b, sizeof b, "%.1f", waterC);
  oled.drawStr(8, 62, b);
  oled.setFont(u8g2_font_9x15_tr); oled.drawStr(100, 62, "C");

  oled.setFont(u8g2_font_9x15_tr);
  if (prog == P_OFF) snprintf(b, sizeof b, "OFF");
  else snprintf(b, sizeof b, "%s %.0f C", prog == P_COLD ? "COLD" : "HOT", progTarget());
  oled.drawStr(8, 84, b);
  if (mode == FAULT) {
    oled.drawStr(8, 102, FAULT_TXT[fault]);
    oled.setFont(u8g2_font_5x7_tr);
    oled.drawStr(8, 111, fault == F_SENSOR ? "check the TEMP plug" : fault == F_FAN ? "check fan, then press"
                          : "press a button to retry");
    oled.setFont(u8g2_font_9x15_tr);
  }
  else if (lowBatt) oled.drawStr(8, 102, "LOW BATT");
  else if (waitLeftS) { snprintf(b, sizeof b, "WAIT %us", waitLeftS); oled.drawStr(8, 102, b); }
  else if (prog == P_OFF) oled.drawStr(8, 102, "PRESS COLD/HOT");
  else if (mode != IDLE) oled.drawStr(8, 102, approach ? MODE_TXT[mode] : "HOLDING");
  else oled.drawStr(8, 102, reached ? "AT TARGET" : "READY");

  oled.setFont(u8g2_font_6x12_tr);
  if (ENABLE_FAN_TACH) snprintf(b, sizeof b, "Fan %u rpm", fanRpm);
  else snprintf(b, sizeof b, "Fan %u%%", fanDuty * 100U / 255);     // no FG wire: show the speed setting
  oled.drawStr(2, 124, b);
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
                   waterC, progTarget(), MODE_TXT[mode], tecDuty > 0, fanDuty > 0);
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
  if (!isnan(battRestV)) snprintf(bv, sizeof bv, "%.2f", battRestV);
  snprintf(b, n,
    "{\"t\":%s,\"tg\":%.0f,\"p\":\"%s\",\"ap\":%d,\"tc\":%.0f,\"th\":%.0f,\"m\":\"%s\",\"f\":\"%s\",\"r\":%d,\"w\":%u,"
    "\"pel\":%u,\"fan\":%u,\"rpm\":%u,\"fc\":\"%s\",\"fp\":%u,\"fmin\":%u,\"bat\":%d,\"bv\":%s,\"lb\":%d,\"chg\":%d,\"cp\":%d,\"chf\":%d,\"pw\":%u,\"up\":%lu,\"ev\":%u,"
    "\"fmax\":%u,\"fauto\":%u,\"ob\":%u,\"or\":%u,\"os\":%d,\"ot\":\"%s\"}",
    t, progTarget(), PROG_TXT[prog], approach ? 1 : 0, coldTargetC, hotTargetC, MODE_TXT[mode], FAULT_TXT[fault], reached ? 1 : 0, (unsigned)waitLeftS,
    tecDuty * 100U / 255, fanDuty * 100U / 255, (unsigned)fanRpm, fanCtl == FAN_AUTO ? "auto" : "manual",
    (unsigned)fanManualPct, (unsigned)fanFloorPct, battRestPct, bv, lowBatt ? 1 : 0, charging ? 1 : 0, chgPct, chargeFull ? 1 : 0, (unsigned)tecPowerPct, (unsigned long)millis(), (unsigned)evTotal,
    (unsigned)FAN_MAX_PCT, (unsigned)FAN_AUTO_COOL_PCT, (unsigned)oledBright, (unsigned)oledRot, oledOn ? 1 : 0, oledTitle);
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
    static char b[448]; statusJson(b, sizeof b); c->setValue((uint8_t*)b, strlen(b));
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
//   C          COLD program (same as the blue button when OFF)
//   H          HOT program
//   X          OFF (Peltier and fan off)
//   TC<10-30>  COLD target, C (saved)        TH<35-52>  HOT target, C (saved)
//   FA         fan AUTO (the normal behaviour)
//   FM<0-100>  fan MANUAL at this % while cooling, never below FAN_MIN_PCT_COOL (the fan is off while heating)
//   P<30-100>  Peltier power limit, % (saved)
//   OB<0-100>  OLED brightness, % (saved)
//   OR<0-3>    OLED orientation: 0 portrait, 1 landscape, 2 portrait upside down, 3 landscape the other way (saved)
//   OS1 / OS0  OLED screen on / off (comes back on after a power-up)
//   OT<text>   OLED title, 1-10 characters: letters, digits, space . - _ # ! ( ) + (saved)
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
    if (c0 == 'C' && c1 == '\0') {
      progReq = P_COLD; logEvent(charging ? "Charging: unplug first" : "Phone: COLD");
    } else if (c0 == 'H' && c1 == '\0') {
      progReq = P_HOT; logEvent(charging ? "Charging: unplug first" : "Phone: HOT");
    } else if (c0 == 'X' && c1 == '\0') {
      progReq = P_OFF; logEvent("Phone: OFF");
    } else if (c0 == 'T' && c1 == 'C' && (v = strtol(s + 2, &end, 10), end != s + 2 && *end == '\0') &&
               v >= (long)COLD_TARGET_MIN && v <= (long)COLD_TARGET_MAX) {
      coldTargetC = v; prefs.putFloat("tcold", coldTargetC); logEvent("Phone: COLD target %ld C", v);
      if (prog == P_COLD) setProg(P_COLD);       // new target: pull to it again
    } else if (c0 == 'T' && c1 == 'H' && (v = strtol(s + 2, &end, 10), end != s + 2 && *end == '\0') &&
               v >= (long)HOT_TARGET_MIN && v <= (long)HOT_TARGET_MAX) {
      hotTargetC = v; prefs.putFloat("thot", hotTargetC); logEvent("Phone: HOT target %ld C", v);
      if (prog == P_HOT) setProg(P_HOT);
    } else if (c0 == 'F' && c1 == 'A' && s[2] == '\0') {
      fanCtl = FAN_AUTO; logEvent("Phone: fan AUTO");
    } else if (c0 == 'F' && c1 == 'M' && (v = strtol(s + 2, &end, 10), end != s + 2 && *end == '\0') &&
               v >= 0 && v <= 100) {
      fanCtl = FAN_MANUAL; fanManualPct = max((long)FAN_MIN_PCT_COOL, v); logEvent("Phone: fan %u%%", (unsigned)fanManualPct);
    } else if (c0 == 'O' && c1 == 'B' && (v = strtol(s + 2, &end, 10), end != s + 2 && *end == '\0') &&
               v >= 0 && v <= 100) {
      oledBright = v; prefs.putUChar("obr", oledBright); oledApply(); logEvent("Phone: OLED %ld%%", v);
    } else if (c0 == 'O' && c1 == 'R' && (v = strtol(s + 2, &end, 10), end != s + 2 && *end == '\0') &&
               v >= 0 && v <= 3) {
      oledRot = v; prefs.putUChar("orot", oledRot); oledApply(); logEvent("Phone: OLED turned (%ld)", v);
    } else if (c0 == 'O' && c1 == 'S' && (s[2] == '0' || s[2] == '1') && s[3] == '\0') {
      oledOn = s[2] == '1'; oledApply(); logEvent(oledOn ? "Phone: OLED on" : "Phone: OLED off");
    } else if (c0 == 'O' && c1 == 'T' && titleOk(s + 2)) {
      strncpy(oledTitle, s + 2, OLED_TITLE_MAX); oledTitle[OLED_TITLE_MAX] = '\0';
      prefs.putString("otitle", oledTitle); logEvent("Phone: OLED title");
    } else if (c0 == 'P' && (v = strtol(s + 1, &end, 10), end != s + 1 && *end == '\0') &&
               v >= POWER_MIN_PCT && v <= 100) {
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
  static Prog lastProg = P_OFF;
  static bool lastReached = false, lastWait = false;
  if (prog != lastProg) {
    if (prog == P_COLD)     logEvent("COLD to %.0f C", coldTargetC);
    else if (prog == P_HOT) logEvent("HOT to %.0f C", hotTargetC);
    else                    logEvent("OFF");
    lastProg = prog;
  }
  if (mode != lastMode) {
    if (mode == FAULT) logEvent("FAULT: %s", FAULT_TXT[fault]);
    lastMode = mode;
  }
  bool waiting = waitLeftS > 0;
  if (waiting && !lastWait) logEvent("Wait %us before reversing", (unsigned)waitLeftS);
  lastWait = waiting;
  if (reached && !lastReached) logEvent("Reached %.1f C, holding", waterC);
  lastReached = reached;
  static bool lastLow = false;
  if (lowBatt != lastLow) { logEvent(lowBatt ? "LOW BATTERY: Peltier off" : "Battery OK again"); lastLow = lowBatt; }
  static bool lastChg = false;
  if (charging != lastChg) { logEvent(charging ? "Charger in: locked" : "Charger out"); lastChg = charging; }
  static bool lastFull = false;
  if (chargeFull && !lastFull) logEvent("Battery full");
  lastFull = chargeFull;
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
  // Peltier and fan off first: the BTS7960 enable pins float until they are driven.
  pinMode(PIN_REN, OUTPUT); pinMode(PIN_LEN, OUTPUT);
  digitalWrite(PIN_REN, LOW); digitalWrite(PIN_LEN, LOW);
  ledcAttach(PIN_RPWM, PWM_TEC_HZ, PWM_BITS); ledcAttach(PIN_LPWM, PWM_TEC_HZ, PWM_BITS);
  ledcAttach(PIN_FAN_PWM, PWM_FAN_HZ, PWM_BITS);
  tecStop(); setFan(0);
  Serial.begin(115200);
  logEvent("Power on");
  prefs.begin("thermox", false);                 // saved targets, power limit and OLED settings (starts OFF)
  coldTargetC = constrain(prefs.getFloat("tcold", COLD_TARGET_DEFAULT), COLD_TARGET_MIN, COLD_TARGET_MAX);
  hotTargetC = constrain(prefs.getFloat("thot", HOT_TARGET_DEFAULT), HOT_TARGET_MIN, HOT_TARGET_MAX);
  tecPowerPct = constrain(prefs.getUChar("power", 100), POWER_MIN_PCT, (uint8_t)100);
  oledRot = prefs.getUChar("orot", OLED_ROT_DEFAULT) & 3;
  oledBright = min(prefs.getUChar("obr", OLED_BRIGHT_DEFAULT), (uint8_t)100);
  String t = prefs.getString("otitle", OLED_TITLE_DEFAULT);
  if (!titleOk(t.c_str())) t = OLED_TITLE_DEFAULT;
  strncpy(oledTitle, t.c_str(), OLED_TITLE_MAX); oledTitle[OLED_TITLE_MAX] = '\0';
  if (ENABLE_BT_LOGGING) SerialBT.begin(BT_NAME);
  if (ENABLE_BLE_CONTROL) bleBegin();            // after the Peltier and fan outputs are safely off

  pinMode(PIN_BTN_DOWN, INPUT_PULLUP); pinMode(PIN_BTN_UP, INPUT_PULLUP);
  pinMode(PIN_FAN_TACH, INPUT);                  // GPIO35: R8 1k from the fan FG wire, R1 10k pull-up to 3.3V (never 5 V or 12 V)
  if (ENABLE_FAN_TACH) attachInterrupt(digitalPinToInterrupt(PIN_FAN_TACH), onTach, FALLING);
  if (ENABLE_BATTERY_SENSE) analogSetPinAttenuation(PIN_BATT_ADC, ADC_11db);
  if (ENABLE_CHARGE_DETECT) pinMode(PIN_CHG_DET, INPUT);   // R6 33k pulls it down when no charger

  Wire.begin(PIN_SDA, PIN_SCL);
  oled.setI2CAddress(0x3C << 1);
  oled.begin();
  oledApply();                                   // saved orientation and brightness

  ds.begin(); ds.setWaitForConversion(false); ds.setResolution(12);
  Serial.printf("\nThermoX ready. DS18B20 sensors found: %d. Fan limit %u %%\n", ds.getDeviceCount(), (unsigned)FAN_MAX_PCT);
  lastGoodRead = millis();
}

void loop() {
  readSensor(); readFan(); readBattery(); readCharger();
  handleButtons();
  handlePhone();
  control();
  trackEvents();
  drawUI();
  logData();
  debugLine();
  bleTick();
}
