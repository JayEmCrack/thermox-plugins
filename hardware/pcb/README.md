# ThermoX ESP32 board v1 (single-sided, toner transfer)

Four board sizes, same circuit and pin map:

| PDF | Board | Notes |
|---|---|---|
| `ThermoX_PCB_60x60mm.pdf` | 60 x 60 mm | smallest, 2 holes; fan red +12V wire goes straight to the supply, J4 = GND/TACH/PWM, J8 = 2-pin 5V input |
| `ThermoX_PCB_70x70mm.pdf` | 70 x 70 mm | 2 mounting holes; gauge parts stand upright |
| `ThermoX_PCB_80x80mm.pdf` | 80 x 80 mm | same layout as 70 mm with a wider margin and 4 M3 holes |
| `ThermoX_PCB_toner_transfer.pdf` | 86 x 67 mm | original, gauge parts lie flat |

Each PDF is laid out the same way:

| Page | Content |
|---|---|
| 1 | Copper artwork, 1:1, 4 copies: ESP32 pin rows **25.4 mm** apart |
| 2 | Copper artwork, 1:1, 4 copies: ESP32 pin rows **22.86 mm** apart |
| 3 | Parts placement and drilling guide (top view, 2x) |
| 4 | Wiring from the board connectors to the fan, buttons, BTS7960, OLED, DS18B20 and power |
| 5 | Parts list, GPIO check, toner-transfer steps, first power-up checks |

Every board keeps footprints for the future battery gauge (GPIO35): R3 100k, R4 100k (1S Li-ion)
or 27k (3S 12 V), C1 100 nF and the J7 BAT+ header. They are marked "BATTERY GAUGE (future)" with
an orange box on the placement page and stay empty until `ENABLE_BATTERY_SENSE` is turned on.

Print only the copper page that matches your ESP32 (30-pin DevKit V1 clones come with either
row spacing). Use a laser printer at 100 % / "Actual size" with no mirroring. The copper text
reads backwards on paper and normally on the finished board.

The board keeps the current ThermoX pin map unchanged:

| Function | GPIO | Board connector |
|---|---|---|
| Button 1 / Button 2 | 32 / 33 | J5 / J6 |
| OLED SDA / SCL | 21 / 22 | J2 |
| BTS7960 LPWM / RPWM / LEN / REN | 27 / 26 / 13 / 25 | J1, J9 |
| DS18B20 | 14 | J3 (R1 4.7k pull-up) |
| SUNON fan PWM / tach | 23 / 34 | J4 (R2 10k tach pull-up) |
| Battery sense (future, not fitted) | 35 | R3/R4/C1, J7 |

The Peltier current goes only through the BTS7960 power terminals, never through this board.

## Regenerating

```
pip install reportlab shapely
python3 drc.py       # clearance + connectivity check of every variant, prints the netlist
python3 make_pdf.py  # writes the four PDFs
```

`layout.py` holds the pads and traces (2.54 mm grid, top view, copper on the bottom).
