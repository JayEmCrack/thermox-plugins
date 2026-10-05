"""ThermoX ESP32 carrier board: single-sided layout for toner transfer.

Coordinates are in grid units u = 2.54 mm, seen from the TOP (component side),
x to the right and y downward. Copper is on the BOTTOM layer only.

ESP32 board: DOIT ESP32 DEVKIT V1, 30 pins, plugged into two 15-pin female
headers with the USB end toward the bottom edge. 30-pin clones come with the
two pin rows either 25.4 mm (10 u) or 22.86 mm (9 u) apart, so build() makes
one variant for each.
"""
from types import SimpleNamespace

U = 2.54  # mm per grid unit

# Board outline (u)
BX0, BY0, BX1, BY1 = -0.5, -0.5, 33.5, 26.0
BOARD_W = (BX1 - BX0) * U
BOARD_H = (BY1 - BY0) * U

LX = 13   # left ESP32 header column
ROW0 = 6  # pin k (1..15) sits at y = ROW0 + k

LEFT_PINS = ["EN", "VP", "VN", "D34", "D35", "D32", "D33", "D25", "D26", "D27",
             "D14", "D12", "D13", "GND", "VIN"]
RIGHT_PINS = ["D23", "D22", "TX0", "RX0", "D21", "D19", "D18", "D5", "TX2", "RX2",
              "D4", "D2", "D15", "GND", "3V3"]
LEFT_NETS = [None, None, None, "TACH", "BATT", "BTN1", "BTN2", "REN", "RPWM", "LPWM",
             "DQ", None, "LEN", "GND", "5V"]
RIGHT_NETS = ["PWM", "SCL", None, None, "SDA", None, None, None, None, None,
              None, None, None, "GND", "3V3"]

# Pad diameters / drill (mm)
PAD_HDR, DRILL_HDR = 1.8, 0.8
PAD_RES, DRILL_RES = 2.0, 0.8
PAD_TB, DRILL_TB = 2.8, 1.2
HOLE_D = 3.2

# Trace widths (mm)
W_SIG, W_PWR, W_BUS = 0.8, 1.0, 1.2


def mm(p):
    return ((p[0] - BX0) * U, (p[1] - BY0) * U)


def build(rx=23):
    """Return the board for a right header column at x = rx (23: 25.4 mm rows, 22: 22.86 mm)."""
    RX = rx
    MID = (LX + RX) / 2
    pads, components, traces = [], [], []

    def pad(ref, pin, x, y, net, d=PAD_HDR, drill=DRILL_HDR, label=None):
        pads.append(dict(ref=ref, pin=pin, x=x, y=y, net=net or f"NC:{ref}.{pin}",
                         d=d, drill=drill, label=label))

    def header(ref, title, pins, horizontal=False, note=None):
        for pin, x, y, net in pins:
            pad(ref, pin, x, y, net)
        components.append(dict(ref=ref, kind="hdr", title=title, note=note,
                               pins=[(p[0], p[1], p[2]) for p in pins], horizontal=horizontal))

    def two_pin(ref, kind, value, a, b, fit=True):
        pad(ref, "1", a[0], a[1], a[2], d=PAD_RES, drill=DRILL_RES)
        pad(ref, "2", b[0], b[1], b[2], d=PAD_RES, drill=DRILL_RES)
        components.append(dict(ref=ref, kind=kind, value=value, a=a[:2], b=b[:2], fit=fit))

    def tr(net, w, *pts):
        traces.append((net, w, list(pts)))

    # ---------------- ESP32 sockets ----------------
    for k in range(15):
        y = ROW0 + 1 + k
        pad("U1L", LEFT_PINS[k], LX, y, LEFT_NETS[k], label=LEFT_PINS[k])
        pad("U1R", RIGHT_PINS[k], RX, y, RIGHT_NETS[k], label=RIGHT_PINS[k])
    components.append(dict(ref="U1", kind="esp32"))

    # ---------------- Connectors ----------------
    header("J4", "FAN (SUNON 4-wire)", [
        ("12V", 2, 3.5, "12V"), ("GND", 3, 3.5, "GND"),
        ("TACH", 4, 3.5, "TACH"), ("PWM", 5, 3.5, "PWM")], horizontal=True)
    header("J7", "BATT SENSE (optional)", [("GND", 3, 11, "GND"), ("BAT+", 4, 11, "BATP")],
           horizontal=True)
    header("J5", "BTN1 (GPIO32)", [("GND", 3, 12, "GND"), ("B1", 4, 12, "BTN1")], horizontal=True)
    header("J6", "BTN2 (GPIO33)", [("GND", 3, 13, "GND"), ("B2", 4, 13, "BTN2")], horizontal=True)
    header("J1", "BTS7960 A", [
        ("R_EN", 4, 14, "REN"), ("RPWM", 4, 15, "RPWM"), ("LPWM", 4, 16, "LPWM")])
    header("J9", "BTS7960 B", [
        ("L_EN", 4, 19, "LEN"), ("GND", 4, 20, "GND"), ("VCC", 4, 21, "5V")])
    header("J2", "OLED SH1107", [
        ("VCC", 25.5, 8, "3V3"), ("GND", 25.5, 9, "GND"),
        ("SCL", 25.5, 10, "SCL"), ("SDA", 25.5, 11, "SDA")])
    header("J3", "DS18B20", [
        ("VCC", 32, 21, "3V3"), ("GND", 32, 22, "GND"), ("DATA", 32, 23, "DQ")])

    # Power screw terminal, 5.08 mm pitch
    for pin, x, net in [("12V", 1, "12V"), ("GND", 3, "GND"), ("5V", 5, "5V")]:
        pad("J8", pin, x, 24, net, d=PAD_TB, drill=DRILL_TB)
    components.append(dict(ref="J8", kind="terminal", title="POWER IN"))

    # ---------------- Passives ----------------
    two_pin("R1", "res", "4.7k", (30.5, 19, "3V3"), (30.5, 23, "DQ"))
    two_pin("R2", "res", "10k", (9.5, 0.8, "3V3"), (9.5, 4.8, "TACH"))
    two_pin("R3", "res", "DNP", (5.5, 11, "BATP"), (9.5, 11, "BATT"), fit=False)
    two_pin("R4", "res", "DNP", (9.5, 10, "BATT"), (9.5, 6, "GND"), fit=False)
    two_pin("C1", "cap", "DNP", (7.5, 10, "BATT"), (7.5, 8, "GND"), fit=False)

    # Wire link on the top side joining the left and right GND under the module
    pad("JP1", "1", 14.5, 22, "GND")
    pad("JP1", "2", RX - 2.5, 22, "GND")
    components.append(dict(ref="JP1", kind="jumper", a=(14.5, 22), b=(RX - 2.5, 22)))

    # ---------------- Traces ----------------
    # Fan tach (GPIO34) and fan PWM (GPIO23)
    tr("TACH", W_SIG, (13, 10), (11.5, 10), (11.5, 4.8), (4, 4.8), (4, 3.5))
    tr("PWM", W_SIG, (RX, 7), (RX + 1.5, 7), (RX + 1.5, 2.0), (5, 2.0), (5, 3.5))

    # 3V3 from the ESP32 3V3 pin (right column, bottom)
    tr("3V3", W_PWR, (RX, 21), (32, 21))
    tr("3V3", W_PWR, (29, 21), (29, 0.8), (9.5, 0.8))
    tr("3V3", W_PWR, (29, 8), (25.5, 8))
    tr("3V3", W_PWR, (29, 19), (30.5, 19))

    # OLED I2C
    tr("SCL", W_SIG, (RX, 8), (RX + 1, 8), (RX + 1, 10), (25.5, 10))
    tr("SDA", W_SIG, (RX, 11), (25.5, 11))

    # GND right side (from the ESP32 GND pin, right column)
    tr("GND", W_PWR, (RX, 20), (27.5, 20), (27.5, 9), (25.5, 9))
    tr("GND", W_PWR, (RX, 20), (RX - 1, 20), (RX - 1, 22), (32, 22))
    tr("GND", W_PWR, (RX - 2.5, 22), (RX - 1, 22))

    # DS18B20 data (GPIO14) through the gap under the module
    tr("DQ", W_SIG, (13, 17), (16, 17), (16, 23), (32, 23))

    # GND left side: bus along x=3 from the fan header to the power terminal
    tr("GND", W_BUS, (3, 3.5), (3, 24))
    tr("GND", W_PWR, (3, 6), (9.5, 6))
    tr("GND", W_PWR, (7.5, 8), (7.5, 6))
    tr("GND", W_PWR, (13, 20), (3, 20))
    tr("GND", W_PWR, (13, 20), (14.5, 20), (14.5, 22))

    # 5V: terminal -> BTS7960 VCC and ESP32 VIN
    tr("5V", W_PWR, (13, 21), (4, 21))
    tr("5V", W_PWR, (5, 21), (5, 24))

    # 12V: terminal -> fan, along the left edge
    tr("12V", W_BUS, (1, 24), (1, 3.5), (2, 3.5))

    # Battery sense (optional parts)
    tr("BATP", W_SIG, (4, 11), (5.5, 11))
    tr("BATT", W_SIG, (9.5, 11), (13, 11))
    tr("BATT", W_SIG, (9.5, 11), (9.5, 10))
    tr("BATT", W_SIG, (7.5, 10), (9.5, 10))

    # Buttons and BTS7960 control: straight runs to the left
    tr("BTN1", W_SIG, (13, 12), (4, 12))
    tr("BTN2", W_SIG, (13, 13), (4, 13))
    tr("REN", W_SIG, (13, 14), (4, 14))
    tr("RPWM", W_SIG, (13, 15), (4, 15))
    tr("LPWM", W_SIG, (13, 16), (4, 16))
    tr("LEN", W_SIG, (13, 19), (4, 19))

    rows_mm = (RX - LX) * U
    return SimpleNamespace(
        RX=RX, MID=MID, ROWS_MM=rows_mm, pads=pads, components=components, traces=traces,
        holes=[(0.8, 0.8), (31.8, 1.0), (31.8, 24.8), (10, 24.8)],
        # Module body outline (u), approximate DevKit V1 size, for the placement page
        MODULE=(MID - 5.57, 2.7, MID + 5.57, 24.15),
        # Copper text, mirrored on the print so it reads correctly on the copper
        copper_text=[("THERMOX", MID + 0.5, 10.5, 3.2), (f"v1  {rows_mm:.2f}", MID + 0.5, 12.5, 2.2)],
        JUMPERS=[("JP1", "GND")],
    )


VARIANTS = {"25.4": build(23), "22.86": build(22)}
