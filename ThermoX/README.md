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
ThermoX ESP32 --Bluetooth--> dashboard page in Chrome/Edge (Web Serial) --HTTPS--> api/log.php --> cloud MySQL --> same page
```

Everything runs on a free PHP + MySQL web host, so **nothing has to be installed** on the PC. The files only need to be
uploaded to the host. The Bluetooth bridge is built into the dashboard page (Chrome or Edge on a computer).

Folders: `ThermoX/` firmware, `database/schema.sql`, `dashboard/` (PHP API + HTML page),
`receiver/` (optional Python bridge, only for computers without Chrome/Edge).
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

### 2. Cloud hosting and database (one-time, about 15 minutes)
Use any free host that gives **PHP + MySQL + phpMyAdmin + free HTTPS** (for example InfinityFree; hosts change
their free plans, so check). HTTPS is required because the browser only allows Bluetooth/serial access on secure pages.
1. Create a free hosting account and a website (a free subdomain is fine).
2. In the hosting panel open **MySQL Databases** and create a database. Note the **host name** (like `sql123.example.com`),
   **database name**, **user** and **password**. Free hosts add a prefix to these names; use exactly what the panel shows.
3. Open **phpMyAdmin** for that database, choose **Import**, select `database/schema.sql`, and press Go.

Tables (`database/schema.sql`):

**experiments**: `id`, `experiment_name`, `mode` (HEATING/COOLING), `target_temperature`, `start_time`, `end_time` (NULL while running)

**temperature_logs**: `id`, `experiment_id` (foreign key to `experiments.id`, cascade delete), `timestamp`, `temperature`, `target_temperature`, `peltier_status`, `fan_status`, `battery_voltage` (NULL when not measured)

(The spec calls the database `thermox`. Use that name if your host allows it.)

### 3. Upload the dashboard (PHP API)
1. Copy `dashboard/config.sample.php` to `config.php` and fill in the host, database name, user and password from step 2,
   plus a long random `api_key` (this is the **access key** you type into the dashboard). `config.php` is git-ignored; never commit it.
2. Upload everything in the `dashboard/` folder (keeping the `api/` subfolder) plus your `config.php` into the website's
   web folder (usually `htdocs`) using the host's online File Manager or FTP.
3. Open `https://your-site/` in Chrome or Edge.

| Endpoint | Purpose |
|---|---|
| `POST api/start_experiment.php` | JSON `{experiment_name, mode, target_temperature}`; ends any running experiment first |
| `POST api/stop_experiment.php` | Ends the running experiment |
| `POST api/log.php` | Raw ThermoX line; stores it in the running experiment |
| `GET api/status.php[?experiment_id=N]` | Latest sample and history |
| `GET api/experiments.php` | Experiment list |
| `GET api/export.php?experiment_id=N` | CSV download |

Security: all SQL uses prepared statements. `log.php` only accepts the six known fields and checks their ranges
(e.g. `TEMP` -55 to 125 C, `PELTIER`/`FAN` 0 or 1). The three POST endpoints need the access key, and only accept JSON
(or the plain ThermoX line for `log.php`). Because the site is public, the **read** endpoints (status, list, CSV) are open to
anyone who knows the address; keep the URL private and do not put personal data in experiment names.

### 4. Running an experiment
1. Pair the ESP32 **ThermoX** in the PC's Bluetooth settings (Windows: *Add device, Bluetooth*).
2. Open the dashboard, type the **access key**, and press **Connect ThermoX (Bluetooth)**. Choose the port named
   *Standard Serial over Bluetooth link (COMx)* (the **outgoing** one). The page then forwards every `TEMP=...` line to the API.
3. Enter a name, pick HEATING or COOLING, enter the target (20-50 C, same as the firmware), and press **Start experiment**.
4. Set the same target on the ThermoX with its buttons. The dashboard value only labels the experiment; each sample stores
   the target the device reports.
5. The cards, graph and history update every 2 s and the badge shows "Receiving data". Keep the tab open while logging.
   Samples are only stored while an experiment is running.
6. Press **Stop** when finished. Old runs are listed under *Previous experiments* (**View** to graph, **CSV** to download for Chapter IV).

Quick test without the ESP32 (needs a running experiment):
```
curl -X POST https://your-site/api/log.php -H "X-API-Key: YOUR_KEY" -d "TEMP=28.4,TARGET=22.0,MODE=COOLING,PELTIER=1,FAN=1"
```
Some free hosts show a bot-check page to command-line tools like curl; the dashboard itself is not affected.

### Optional: Python receiver
`receiver/receiver.py` does the same job as the page's Connect button, for computers without Chrome/Edge
(`pip install -r receiver/requirements.txt`, then `python receiver/receiver.py --port COM5 --url https://your-site/api/log.php --key YOUR_KEY`).

### Limitations
- Needs a computer with Chrome or Edge (Web Serial). Phones cannot forward Classic Bluetooth data this way.
- Classic Bluetooth needs the original ESP32 (not S2/S3/C3) and adds some power draw; set `ENABLE_BT_LOGGING = false` to disable.
- Logging stops if the browser tab is closed or the Bluetooth link drops (press Connect again).
- Data flows one way: the dashboard cannot change the device target or mode.
- Battery voltage is not measured yet (future addition on GPIO35), so no battery value is logged or shown.
- Timestamps come from the server when each line arrives, not from the ESP32.
- Free hosts can be slow, limit traffic, or change their terms; export your CSVs after each test.
