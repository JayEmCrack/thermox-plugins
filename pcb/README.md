# ThermoX one-board PCB (recommended): everything on one 82 mm round board

`thermox_onepcb_round82_rows25.4.pdf` and `thermox_onepcb_round82_rows22.86.pdf` put the controller and the power
circuit on one single-sided board. It fits the 85 mm battery bay of the round bottles and replaces the controller
board and the power board. The LM2596S 5 V buck module is wired to U2. Pick the PDF that matches your ESP32: centre of a left pin to centre
of the right pin in the same row, 25.4 mm or 22.86 mm.

| Ref | Part | Notes |
|---|---|---|
| U1 | ESP32 DevKit 30-pin on two 1x15 female headers (8.5 mm) | USB end at the board edge. Plugged in last |
| M1 | USB-C PD/QC trigger board, max 32 x 16 x 7 mm | Lies under the ESP32 on thin foam tape, USB-C at the board edge next to the ESP32 USB. Set it to 12 V and measure first; its 2 output wires (1 mm2) run out under the antenna end to the M1 + and - pads |
| SW1 | ON-OFF-ON mini toggle (MTS-103) | BATT = battery, middle = off, USB = trigger board. The holes also take 3 wires to a switch on the case |
| F1, C1 | 5x20 fuse holder + 10 A slow-blow, 2200 uF 25 V | As on the power board |
| U2 | Wire pads (or a KF301-3P) to the LM2596S 5 V buck module | IN+ to module IN+, GND to IN- (= OUT-), OUT+ to module OUT+. 5 V for the ESP32, the BTS7960 logic and the DS18B20. Set and measure 5.0 V before wiring it |
| R1, R2 | 10k fan tach pull-up, 4.7k DS18B20 pull-up | Lie flat under the ESP32 |
| R3, R4, C4 | 100k, 22k, 100 nF | Battery gauge on GPIO35, under the ESP32 |
| JP1 | Wire link | Carries 3.3 V to the OLED header (bare wire on the parts side) |
| J1 BATTERY / J2 BTS7960 | Screw terminals | Battery after the BMS / BTS7960 B+ and B- |
| J3 FAN, J4 OLED, J5/J6 buttons, J7/J8 BTS7960 control, J9 TEMP | 2.54 mm headers | Same pins as the firmware (GPIO assignments unchanged) |
| J10 CHARGE | 2-pin screw terminal (KF301) | To a 5.5 x 2.1 mm DC jack on the case: centre pin (+) to J10 +, sleeve to J10 - |
| D1, D2 | 1N5822 (3 A Schottky) | D2: charger to the battery. D1: charger to the board, so the OLED works with SW1 in the middle. Stripe as drawn |
| R5, R6 | 100k, 33k | Charger detect on GPIO19: about 3.1 V when a 12.6 V charger is plugged in |

- No copper sits under the ESP32 antenna, for better Bluetooth range.
- The battery gauge is on the board. `ThermoX.ino` already has `BATT_CELLS = 3` and `BATT_DIVIDER = 5.545`; set
  `ENABLE_BATTERY_SENSE = true` to show battery % on the OLED and the phone. On USB-C power it shows the USB
  voltage, not the battery.
- Charging: SW1 in the middle, plug a **12.6 V (3S) CC/CV Li-ion charger** (2 A) into the DC jack. Never a 21 V (5S)
  charger. The battery charges through D2 to about 90 % (the diode drops a little voltage). The OLED shows CHARGING
  and ThermoX will not run (buttons and phone) until the charger is unplugged. Never plug the USB-C charger and the
  DC charger in at the same time.
- All the power-board notes below apply: one source at a time, trigger board at 12 V only, the USB-C power limit,
  the MTS-103 rating and the switching regulator.

`python3 make_thermox_pcb.py` rebuilds both PDFs and checks them: the copper rules of the power board, all nets
connected (the wire link counts), no copper under the antenna, a ground path of at least 3.2 mm for the Peltier
current, and no part bodies overlapping (the low parts under the ESP32 are allowed there). The board has not been
made yet: print page 1 and check the ESP32, the trigger board, the fuse holder and the switch on the paper first.
Each PDF has four pages: copper at actual size, parts side, wiring/parts/notes, and a step-by-step tutorial (make,
solder, first power-up, bench test with `ThermoX_Bench`, charging).

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
| J7 POWER | VBAT, 5V, GND | Power board J7 (same names, see below) |
| J1 FAN | GND, PWM, +12V, FG | SUNON fan (PWM = GPIO23, FG = GPIO34 with R1 10k pull-up) |
| J2 / J3 | BTN, GND | Button 1 (GPIO32) / Button 2 (GPIO33) |
| J4 BTS A | R_EN, RPWM, LPWM | BTS7960 (GPIO25, GPIO26, GPIO27) |
| J5 BTS B | L_EN, GND, VCC | BTS7960 (GPIO13, GND, 5 V logic) |
| J6 TEMP | 5V, GND, DQ | DS18B20 (DQ = GPIO14 with R2 4.7k pull-up to 3.3 V) |
| J8 OLED | SCL, SDA, VCC, GND | 1.5" SH1107 OLED (GPIO22, GPIO21, 3.3 V) |

The Peltier current does **not** go through this board. BTS7960 B+/B- go to the power board J4 with thick wire, and
M+/M- straight to the Peltier.

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

# Power board (all parts on the board, plug and play)

`thermox_power_60x60.pdf` (60 x 60 mm square) and `thermox_power_round60.pdf` (60 mm round) are the same circuit. The
USB-C trigger board, the source switch and the 5 V regulator sit on the board itself. Only the battery, the BTS7960
and the controller board are wired to it. The pages are the same as for the controller board: copper at actual size,
parts side and wiring.

| Ref | Part | Notes |
|---|---|---|
| M1 | USB-C PD/QC trigger board (100W 5A type) | Stuck on the dashed 32 x 16 mm area with foam tape, USB-C at the board edge. Set it to 12 V and measure it first, then solder 2 short 1 mm2 wires from its output to the M1 + and - pads |
| SW1 | ON-OFF-ON mini toggle (MTS-103), lugs 4.7 mm apart | BATT = battery, middle = off, USB = trigger board. The holes also take 3 wires to a switch on the case |
| F1 | 5x20 mm fuse holder (BLX-A, pins 22.6 mm apart) + 10 A slow-blow fuse | Protects both sources |
| C1 | 2200 uF 25 V, low ESR | Smooths the Peltier PWM so the charger does not cut out |
| U1 | K7805-1000R3 or R-78E5.0-1.0 (5 V 1 A switching, 7805 pins) | Replaces the LM2596 module. Pin 1 (IN) in the square pad. C2 10 uF on its input, C3 22 uF on its output |
| LED1, R1 | LED + 2.2 k | Lights when there is power after the fuse |
| J1 BATTERY | BAT+, BAT- | Battery after the BMS (P+, P-) |
| J4 BTS7960 | B+, B- | BTS7960 power terminals (thick wire) |
| J7 TO CONTROLLER | VBAT, 5V, GND | Controller board J7, same names (pin 1 = VBAT) |

- Only one source at a time: never connect the trigger board straight to the battery. The trigger board does not
  charge the battery.
- Set the trigger board to 12 V and check it with a meter before you solder its wires. Never 15 V or 20 V.
- On USB-C, limit the Peltier power with the phone page slider: 60 % with a 12 V 5 A charger and 5 A cable, 40 % with
  12 V 3 A.
- SW1 (MTS-103) is rated 6 A at 125 V AC. On battery, keep the Peltier power at 80 % or less, or wire a 10 A toggle
  into the SW1 holes. Move the switch only while the Peltier is stopped.
- U1 must be a switching regulator; a plain LM7805 would get too hot. The old LM2596 module still works: wire its IN+,
  IN- (= OUT-) and OUT+ to the U1 IN, GND and 5V holes.
- Trigger board sizes differ between makers. The area fits the ZY12PDN type (about 31.5 x 15 mm). Lay your board on
  the printed parts page before etching.
- The wide tracks carry up to 7 A: cover them with solder after etching.

`python3 make_power_pcb.py` rebuilds both PDFs. It checks:
- the same copper rules as the controller board;
- that the ground path for the Peltier current (battery -, trigger board -, BTS7960 B-, C1 -) is at least 3.2 mm wide;
- that no part bodies overlap each other or the mounting holes, all bodies stay on the board, and no body covers
  another part's pads.

Part sizes used: R-78E5.0-1.0 is an 11.6 x 8.5 mm SIP-3 with 2.54 mm pin pitch, pin 1 +Vin, 2 GND, 3 +Vout (RECOM;
KiCad footprint `Converter_DCDC_RECOM_R-78E-0.5_THT`). The board keeps 6.5 mm free on both sides of the U1 pins, so
the K7805-1000R3 fits as well. MTS-103 lugs are 0.185" (4.7 mm) apart, body about 13 x 8 mm. ZY12PDN is about
30-31.5 x 15 mm.
