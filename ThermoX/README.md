# ThermoX firmware

`ThermoX.ino` targets the **ESP32**, not an Arduino Uno. An Uno has no GPIO32/33/34,
runs at 5 V logic, and has no hardware I2C on pins 21/22, so the pin map cannot be
used on it. Use "ESP32 Dev Module" with Arduino-ESP32 core 3.x.
Libraries: OneWire, DallasTemperature, U8g2.

## Wiring notes
- DS18B20 DATA (GPIO14): 4.7 kΩ pull-up to 3.3 V.
- SUNON tach (GPIO34): input-only pin with no internal pull-up, so add 10 kΩ to 3.3 V
  (FG is open-collector).
- Common ground between ESP32, BTS7960, sensor, OLED, fan and battery.
- BTS7960 logic VCC from 5 V; its 3.3 V-level inputs are fine from ESP32 GPIOs.
- If heating/cooling is reversed, flip `HEAT_ON_RPWM` or swap the TEC leads.

## Suggested additions
1. **Battery gauge (FUTURE ADDITION, disabled for now)**: 100 kΩ/100 kΩ divider from the
   battery to GPIO35 plus 100 nF to GND, then set `ENABLE_BATTERY_SENSE = true`.
2. **Low-battery cutoff / undervoltage lockout**: stop the TEC below ~3.3 V/cell
   (use a protected Li-ion pack or BMS).
3. **Second DS18B20 on the heat sink** (same 1-Wire bus): cut the TEC if the hot side
   exceeds ~70 °C; this is a more reliable safeguard than fan RPM alone.
4. **Water-level or lid switch** to prevent running the TEC dry.
5. **Inline fuse (5–10 A)** on the TEC supply and a bulk capacitor (470–1000 µF) on the
   BTS7960 supply.
6. **Hardware watchdog** (`esp_task_wdt`) and a buzzer for fault/target-reached alerts.
8. **PID control** in place of the proportional taper once real heating/cooling curves
   are measured.

## Bluetooth logging (implemented)
Pair with the ESP32 named **ThermoX** (Classic Bluetooth SPP) and open it in any serial
terminal app (e.g. "Serial Bluetooth Terminal" on Android). One CSV line per second:
`ms,water_c,target_c,mode,fault,tec_duty,fan_duty,fan_rpm,batt_pct`
(`batt_pct` is -1 while the battery gauge is disabled.) The same lines go to USB serial at
115200 baud. Save the output as a `.csv` for the Chapter IV tests. Note: Classic Bluetooth
needs an ESP32 (not S2/C3/S3) and adds some power draw; set `ENABLE_BT_LOGGING = false` to
turn it off.
