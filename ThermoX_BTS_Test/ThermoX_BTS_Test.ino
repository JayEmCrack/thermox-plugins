/*
  ThermoX BTS7960 simple test - starts by itself, no button to press
  Target board : ESP32 DevKit 30-pin (Arduino-ESP32 core 3.x), "ESP32 Dev Module"
  Libraries    : none. No buttons, no OLED, no temperature sensor and no fan signal are needed.

  What it does:
   - 3 s after power-up the BTS7960 switches ON by itself (plain HIGH levels, no PWM).
   - It stays ON for 60 s, rests 15 s, then switches ON again, and so on.
     The rest is there because this test has no temperature sensor to protect the Peltier.
   - The blue LED on the ESP32 is lit while the BTS7960 is ON.
   - The fan output is at 100 % all the time.
   - Serial Monitor (115200 baud): one line per second with what the ESP32 pins really are.

  While it is ON, measure on the BTS7960 with a meter on DC volts:
    B+ to B-   about 12 V
    VCC to GND about 5 V              (header pin 7 to pin 8)
    R_EN (pin 3) and L_EN (pin 4)     3.3 V each
    RPWM (pin 1)                      3.3 V   (LPWM pin 2 = 0 V)
    M+ to M-   about 12 V             (both probes on M+ and M-, not one on GND)

  Pins are the same as ThermoX.ino. Flash ThermoX.ino again when the BTS7960 works.
*/
#include <Arduino.h>

// ---------------- Pins (as in ThermoX.ino) ----------------
constexpr uint8_t PIN_RPWM    = 26;   // BTS7960 RPWM (header pin 1), board hole A18
constexpr uint8_t PIN_LPWM    = 27;   // BTS7960 LPWM (header pin 2), board hole A19
constexpr uint8_t PIN_REN     = 25;   // BTS7960 R_EN (header pin 3), board hole A17
constexpr uint8_t PIN_LEN     = 13;   // BTS7960 L_EN (header pin 4), board hole A22
constexpr uint8_t PIN_FAN_PWM = 23;
constexpr uint8_t PIN_LED     = 2;    // blue LED on the ESP32 DevKit

// ---------------- Settings ----------------
constexpr bool     USE_RPWM = true;   // true = RPWM side on, false = LPWM side on (the other direction)
constexpr uint32_t ON_MS  = 60000;    // ON time
constexpr uint32_t OFF_MS = 15000;    // rest time

bool     btsOn = false;
uint32_t since = 0;

void bts(bool run) {
  digitalWrite(PIN_RPWM, LOW); digitalWrite(PIN_LPWM, LOW);          // both inputs low first
  digitalWrite(PIN_REN, run ? HIGH : LOW);                            // both enables together
  digitalWrite(PIN_LEN, run ? HIGH : LOW);
  if (run) digitalWrite(USE_RPWM ? PIN_RPWM : PIN_LPWM, HIGH);
  digitalWrite(PIN_LED, run ? HIGH : LOW);
  btsOn = run; since = millis();
  Serial.println(run ? ">>> BTS7960 ON: M+ to M- must be about 12 V" : ">>> BTS7960 OFF (rest)");
}

void setup() {
  pinMode(PIN_RPWM, OUTPUT); pinMode(PIN_LPWM, OUTPUT);
  pinMode(PIN_REN, OUTPUT);  pinMode(PIN_LEN, OUTPUT);
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_RPWM, LOW); digitalWrite(PIN_LPWM, LOW);
  digitalWrite(PIN_REN, LOW);  digitalWrite(PIN_LEN, LOW);
  digitalWrite(PIN_LED, LOW);
  pinMode(PIN_FAN_PWM, OUTPUT); digitalWrite(PIN_FAN_PWM, HIGH);     // fan at 100 %
  Serial.begin(115200);
  delay(3000);
  Serial.println();
  Serial.println("ThermoX BTS7960 simple test: ON 60 s, rest 15 s, again and again. Nothing to press.");
  bts(true);
}

void loop() {
  uint32_t now = millis();
  if (now - since >= (btsOn ? ON_MS : OFF_MS)) bts(!btsOn);

  static uint32_t t0 = 0;
  if (now - t0 >= 1000) {
    t0 = now;
    Serial.printf("%s %2lu s | ESP32 pins: R_EN=%d L_EN=%d RPWM=%d LPWM=%d\n", btsOn ? "ON " : "OFF",
                  (unsigned long)((now - since) / 1000), digitalRead(PIN_REN), digitalRead(PIN_LEN),
                  digitalRead(PIN_RPWM), digitalRead(PIN_LPWM));
  }
}
