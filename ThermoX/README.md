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

## Bluetooth logging to MySQL (experiments)

```
ThermoX ESP32 --Bluetooth--> receiver/receiver.py (PC) --HTTP--> dashboard/api/log.php --> MySQL "thermox" --> dashboard/index.html
```

Folders: `ThermoX/` firmware, `database/schema.sql`, `dashboard/` (PHP API + HTML page), `receiver/` (Bluetooth-to-HTTP bridge).
The ESP32 pin assignments are unchanged.

### 1. Firmware output
Every 2 s (`LOG_PERIOD_MS`) the ESP32 sends one line over Bluetooth (device name **ThermoX**) and USB serial:

```
TEMP=28.40,TARGET=22.0,MODE=COOLING,PELTIER=1,FAN=1
```

| Field | Meaning |
|---|---|
| `TEMP` | DS18B20 water temperature, °C |
| `TARGET` | Target currently set with the buttons, °C |
| `MODE` | `HEATING`, `COOLING`, `IDLE` (inside the 0.5 °C hysteresis band) or `FAULT` |
| `PELTIER` | 1 when the BTS7960 is driving the Peltier, else 0 |
| `FAN` | 1 when the SUNON fan is commanded on, else 0 |
| `BATTERY` | Volts. **Only sent when `ENABLE_BATTERY_SENSE = true`** (not implemented yet, so it is omitted) |

Nothing is sent until the DS18B20 gives a valid reading. If the sketch reports "too big", choose
Tools → Partition Scheme → **Huge APP** (Classic Bluetooth uses a lot of flash).

### 2. Database setup (MySQL / MariaDB)
Easiest on a Windows PC: install **XAMPP**, start *Apache* and *MySQL*, then:
1. Open http://localhost/phpmyadmin → **Import** → choose `database/schema.sql` → Go. This creates the `thermox` database and tables.
2. In phpMyAdmin → **SQL**, create a limited user (pick your own password):
   ```sql
   CREATE USER 'thermox_user'@'localhost' IDENTIFIED BY 'your-own-password';
   GRANT SELECT, INSERT, UPDATE ON thermox.* TO 'thermox_user'@'localhost';
   ```
   (`root` with no password also works on a private XAMPP machine, but the limited user is safer.)

Tables (`database/schema.sql`):

**experiments**: `id`, `experiment_name`, `mode` (HEATING/COOLING), `target_temperature`, `start_time`, `end_time` (NULL while running)

**temperature_logs**: `id`, `experiment_id` (foreign key → `experiments.id`, cascade delete), `timestamp`, `temperature`, `target_temperature`, `peltier_status`, `fan_status`, `battery_voltage` (NULL when not measured)

### 3. PHP API / dashboard setup
1. Copy the `dashboard/` folder to `C:\xampp\htdocs\thermox\`.
2. Copy `config.sample.php` to `config.php` and set `db_user`, `db_pass` and a long random `api_key`. `config.php` is git-ignored; never commit it.
3. Open http://localhost/thermox/.

| Endpoint | Purpose |
|---|---|
| `POST api/start_experiment.php` | JSON `{experiment_name, mode, target_temperature}`; ends any running experiment first |
| `POST api/stop_experiment.php` | Ends the running experiment |
| `POST api/log.php` | Raw ThermoX line + `X-API-Key` header; stores it in the running experiment |
| `GET api/status.php[?experiment_id=N]` | Latest sample and history |
| `GET api/experiments.php` | Experiment list |
| `GET api/export.php?experiment_id=N` | CSV download |

All SQL uses prepared statements. `log.php` only accepts the six known fields, checks ranges (e.g. `TEMP` −55 to 125 °C, `PELTIER`/`FAN` 0 or 1) and needs the API key. The writing endpoints reject non-JSON requests. This is built for a local prototype: do not expose it to the internet.

### 4. Receiver (PC)
1. Pair the ESP32 **ThermoX** in the PC's Bluetooth settings. On Windows, open *More Bluetooth settings → COM Ports* and note the **outgoing** COM port.
2. ```
   pip install -r receiver/requirements.txt
   python receiver/receiver.py --list-ports
   python receiver/receiver.py --port COM5 --url http://localhost/thermox/api/log.php --key YOUR_API_KEY
   ```
   (Linux: `sudo rfcomm bind 0 <ESP32 MAC>` then `--port /dev/rfcomm0`.) The receiver reconnects automatically and prints `stored` or the API error for each line.

### 5. Running an experiment
1. Open the dashboard, enter a name, pick HEATING or COOLING, enter the target (20–50 °C, like the firmware), press **Start experiment**.
2. Set the same target on the ThermoX with its buttons. The dashboard value only labels the experiment; each sample stores the target the device reports.
3. Run `receiver.py`. The badge turns to "Receiving data" and the cards, graph and history update every 2 s. Samples are only stored while an experiment is running.
4. Press **Stop** when finished. Old runs are listed under *Previous experiments* (**View** to graph, **CSV** to download for Chapter IV).

Quick test without the ESP32 (needs a running experiment):
```
curl -X POST http://localhost/thermox/api/log.php -H "X-API-Key: YOUR_API_KEY" -d "TEMP=28.4,TARGET=22.0,MODE=COOLING,PELTIER=1,FAN=1"
```

### Limitations
- Classic Bluetooth needs the original ESP32 (not S2/S3/C3) and adds some power draw; set `ENABLE_BT_LOGGING = false` to disable.
- The receiver is a PC script. A phone cannot forward data to the API without a custom app (a phone terminal app can only save the lines to a file).
- Data flows one way: the dashboard cannot change the device target or mode.
- Battery voltage is not measured yet (future addition on GPIO35), so no battery value is logged or shown.
- Timestamps come from the PC when each line arrives, not from the ESP32.
