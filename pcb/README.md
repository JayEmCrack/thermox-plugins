# ThermoX controller PCB (home-etch, single-sided)

A carrier board for the 30-pin ESP32 DevKit with every ThermoX connection. Through-hole only, one copper layer
(bottom), ground fill, made for toner transfer or UV film. The GPIO assignments are the same as the firmware.

| File | Board | ESP32 pin rows |
|---|---|---|
| `thermox_pcb_60x60_rows25.4.pdf` | 60 x 60 mm square | 25.4 mm (1.0") apart |
| `thermox_pcb_60x60_rows22.86.pdf` | 60 x 60 mm square | 22.86 mm (0.9") apart |
| `thermox_pcb_round82_rows25.4.pdf` | 82 mm round | 25.4 mm |
| `thermox_pcb_round82_rows22.86.pdf` | 82 mm round | 22.86 mm |

**Measure your ESP32 first**: centre of a left pin to centre of the right pin in the same row. 30-pin boards
come in both widths. The round board is the same circuit on an 82 mm disc. It fits the 85 mm inside of the battery
bay of the round bottle designs in `cad/` (Classic, Modern, Trail, Pebble, Deco), with 4 mounting holes outside the
copper area.

Each PDF has three pages:
1. **Copper**, two copies at actual size. Print at 100 % and check the 50 mm bar. Use it as it is for toner transfer
   or UV film (do not mirror). The small mirrored "THERMOX" text reads correctly on the finished copper side.
2. **Parts side**, enlarged, with every part, connector pin and ESP32 pin named.
3. **Wiring, parts list and notes.**

## Connectors

| Ref | Pins | Goes to |
|---|---|---|
| J7 POWER | VBAT, 5V, GND | Battery + (after BMS/fuse) and LM2596 IN+; LM2596 OUT+ (set to 5.0 V); battery - |
| J1 FAN | GND, PWM, +12V, FG | SUNON fan (PWM = GPIO23, FG = GPIO34 with R1 10k pull-up) |
| J2 / J3 | BTN, GND | Button 1 (GPIO32) / Button 2 (GPIO33) |
| J4 BTS A | R_EN, RPWM, LPWM | BTS7960 (GPIO25, GPIO26, GPIO27) |
| J5 BTS B | L_EN, GND, VCC | BTS7960 (GPIO13, GND, 5 V logic) |
| J6 TEMP | 5V, GND, DQ | DS18B20 (DQ = GPIO14 with R2 4.7k pull-up to 3.3 V) |
| J8 OLED | SCL, SDA, VCC, GND | 1.5" SH1107 OLED (GPIO22, GPIO21, 3.3 V) |

The Peltier current does **not** go through this board. Connect BTS7960 B+/B- straight to the pack with thick wire
and a 10 A fuse, and M+/M- straight to the Peltier.

## Battery gauge (set aside for now)
R3 100k, R4 22k and C1 100 nF divide the 3S pack (12.6 V max) to about 2.3 V on GPIO35. The firmware keeps battery
sensing **off** (`ENABLE_BATTERY_SENSE = false`) until the board is built. Then set `BATT_CELLS = 3`,
`BATT_DIVIDER = 5.545` and `ENABLE_BATTERY_SENSE = true`. That also turns on the low-battery cutoff.

## Checks
`python3 make_pcb.py` (needs `pip install shapely matplotlib`) rebuilds the PDFs and checks the design. It confirms:
- every copper gap between different nets is at least 0.5 mm, and the ground fill is 0.8 mm from other nets;
- every net is connected, and every GND pad is on the one ground area;
- copper stays 0.6 mm from the board edge and clear of the mounting holes.

The board has not been made yet. Print page 1, place the ESP32 and the headers on the paper and check that the pins
line up before etching.
