"""Builds ThermoX_PCB_toner_transfer.pdf from layout.py (run: python3 make_pdf.py)."""
from reportlab.lib.colors import Color, black, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

import layout as L

OUT = "ThermoX_PCB_toner_transfer.pdf"
PW, PH = A4
GREY = Color(0.78, 0.78, 0.78)
DARK = Color(0.25, 0.25, 0.25)
BLUE = Color(0.05, 0.30, 0.65)
RED = Color(0.78, 0.10, 0.10)
GREEN = Color(0.05, 0.50, 0.20)
ORANGE = Color(0.85, 0.45, 0.0)


class View:
    """Maps layout units to page points for a board drawn at (ox, oy) mm from the page top-left."""

    def __init__(self, B, ox, oy, s=1.0):
        self.B, self.ox, self.oy, self.s = B, ox, oy, s

    def p(self, q):
        x, y = self.B.mm(q)
        return (self.ox + x * self.s) * mm, PH - (self.oy + y * self.s) * mm

    def d(self, v_mm):
        return v_mm * self.s * mm


def text(c, x, y, s, size=8, font="Helvetica", color=black, anchor="l"):
    c.setFont(font, size)
    c.setFillColor(color)
    if anchor == "c":
        c.drawCentredString(x, y, s)
    elif anchor == "r":
        c.drawRightString(x, y, s)
    else:
        c.drawString(x, y, s)


def paragraph(c, x, y, lines, size=8.5, lead=1.35, font="Helvetica", color=black):
    for ln in lines:
        f = font
        if ln.startswith("**"):
            ln, f = ln[2:], "Helvetica-Bold"
        text(c, x, y, ln, size, f, color)
        y -= size * lead
    return y


def board_outline(c, v, width=0.25, color=black):
    x0, y0 = v.p((v.B.BX0, v.B.BY0))
    x1, y1 = v.p((v.B.BX1, v.B.BY1))
    c.setStrokeColor(color)
    c.setLineWidth(width)
    c.rect(x0, y1, x1 - x0, y0 - y1, stroke=1, fill=0)


def draw_copper(c, B, v, color=black, drills=True, mirror_text=True, outline=True, labels=True):
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineCap(1)
    c.setLineJoin(1)
    for net, w, pts in B.traces:
        c.setLineWidth(v.d(w))
        path = c.beginPath()
        path.moveTo(*v.p(pts[0]))
        for q in pts[1:]:
            path.lineTo(*v.p(q))
        c.drawPath(path, stroke=1, fill=0)
    for p in B.pads:
        x, y = v.p((p["x"], p["y"]))
        c.circle(x, y, v.d(p["d"] / 2), stroke=0, fill=1)
    if drills:
        c.setFillColor(white)
        for p in B.pads:
            x, y = v.p((p["x"], p["y"]))
            c.circle(x, y, v.d(0.6 / 2), stroke=0, fill=1)
    # Mounting holes: thin ring + centre dot as a drill guide
    c.setStrokeColor(color)
    c.setLineWidth(v.d(0.25))
    for h in B.holes:
        x, y = v.p(h)
        c.circle(x, y, v.d(L.HOLE_D / 2), stroke=1, fill=0)
        c.setFillColor(color)
        c.circle(x, y, v.d(0.4), stroke=0, fill=1)
    for s, tx, ty, size in (B.copper_text if labels else []):
        x, y = v.p((tx, ty))
        c.saveState()
        c.translate(x, y)
        if mirror_text:
            c.scale(-1, 1)
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", v.d(size) / mm * 2.835)
        c.drawCentredString(0, -v.d(size) * 0.35, s)
        c.restoreState()
    if outline:
        board_outline(c, v, width=0.3, color=color)


# ---------------------------------------------------------------- page 1
def page_toner(c, B, other):
    rows = B.ROWS_MM
    text(c, 15 * mm, PH - 15 * mm,
         f"ThermoX board {B.name} mm - COPPER for toner transfer - ESP32 rows {rows:.2f} mm", 12,
         "Helvetica-Bold")
    c.setFillColor(Color(1, 0.95, 0.8))
    c.rect(14 * mm, PH - 29.5 * mm, 182 * mm, 10.5 * mm, stroke=0, fill=1)
    paragraph(c, 16 * mm, PH - 23 * mm, [
        f"**Use THIS page if the two pin rows of your ESP32 are {rows:.2f} mm ({rows / 25.4:.1f} in) apart, "
        "centre to centre.",
        f"If yours are {other:.2f} mm apart, use the other copper page. Easiest check: lay the ESP32 on "
        "the board drawing below.",
    ], 8.5)
    paragraph(c, 15 * mm, PH - 37 * mm, [
        "LASER printer, 100% / 'Actual size' (turn OFF 'Fit to page'), glossy or photo paper. Do NOT mirror: the",
        "small text reads BACKWARDS here and will read normally on the copper. 4 copies, pick the cleanest one.",
    ], 8.5)
    bw, bh = B.BOARD_W, B.BOARD_H
    gx, gy = 9.0, 8.0
    x0 = (PW / mm - (2 * bw + gx)) / 2
    y0 = 48.0
    for r in range(2):
        for k in range(2):
            v = View(B, x0 + k * (bw + gx), y0 + r * (bh + gy), 1.0)
            draw_copper(c, B, v)
    # Scale check
    yb = y0 + 2 * bh + gy + 17
    xb = 15.0
    c.setStrokeColor(black)
    c.setFillColor(black)
    c.setLineWidth(0.6)
    c.line(xb * mm, PH - yb * mm, (xb + 50) * mm, PH - yb * mm)
    for i in range(0, 51, 5):
        t = 3.0 if i % 10 == 0 else 1.6
        c.line((xb + i) * mm, PH - yb * mm, (xb + i) * mm, PH - (yb - t) * mm)
    text(c, xb * mm, PH - (yb + 5) * mm, "SCALE CHECK: this bar must measure exactly 50 mm.", 8.5,
         "Helvetica-Bold")
    c.rect((xb + 62) * mm, PH - yb * mm, 10 * mm, 10 * mm, stroke=1, fill=0)
    text(c, (xb + 75) * mm, PH - (yb - 6) * mm, "10 x 10 mm square", 8)
    paragraph(c, xb * mm, PH - (yb + 11) * mm, [
        f"Board {bw:.1f} x {bh:.1f} mm, cut on the outer line. White dots = drill centres "
        "(pins 0.8-1.0 mm, terminal 1.2 mm, holes 3.2 mm).",
    ], 8.5)


# ---------------------------------------------------------------- page 2
def label_bg(c, x, y, s, size, font="Helvetica-Bold", color=GREEN, anchor="l"):
    """Text with a white box behind it so it stays readable over grey copper."""
    w = stringWidth(s, font, size)
    x0 = {"l": x, "r": x - w, "c": x - w / 2}[anchor]
    c.setFillColor(white)
    c.rect(x0 - 1, y - 1.6, w + 2, size + 1.2, stroke=0, fill=1)
    text(c, x, y, s, size, font, color, anchor)


def rotated(c, x, y, s, size, font="Helvetica-Bold", color=black, angle=90, anchor="c"):
    c.saveState()
    c.translate(x, y)
    c.rotate(angle)
    text(c, 0, -size * 0.35, s, size, font, color, anchor)
    c.restoreState()


def page_placement(c, B):
    s = 2.0
    v = View(B, (PW / mm - B.BOARD_W * s) / 2, 33, s)
    text(c, 15 * mm, PH - 16 * mm,
         "Parts placement and drilling guide (TOP view, 2x size, not for transfer)", 12,
         "Helvetica-Bold")
    text(c, 15 * mm, PH - 22 * mm,
         "Parts go on the plain (non-copper) side. Grey = copper on the bottom, seen through the board.",
         8.5)
    text(c, 15 * mm, PH - 26.5 * mm,
         "Drawn for 25.4 mm ESP32 rows. On the 22.86 mm board the right socket row is one pin space "
         "(2.54 mm) closer; all other parts are the same.", 8.5)
    draw_copper(c, B, v, color=GREY, drills=False, outline=False, labels=False)
    board_outline(c, v, 0.6)
    for p in B.pads:
        x, y = v.p((p["x"], p["y"]))
        c.setStrokeColor(black)
        c.setLineWidth(0.4)
        c.setFillColor(white)
        c.circle(x, y, v.d(p["d"] / 2), stroke=1, fill=1)
        c.setFillColor(black)
        c.circle(x, y, v.d(p["drill"] / 2), stroke=0, fill=1)
    for h in B.holes:
        x, y = v.p(h)
        c.setStrokeColor(black)
        c.setLineWidth(0.6)
        c.circle(x, y, v.d(L.HOLE_D / 2), stroke=1, fill=0)
        r = v.d(L.HOLE_D / 2 + 0.5)
        c.line(x - r, y, x + r, y)
        c.line(x, y - r, x, y + r)

    # ESP32 outline and pin names
    mx0, my0, mx1, my1 = B.MODULE
    a, b = v.p((mx0, my0)), v.p((mx1, my1))
    c.setStrokeColor(BLUE)
    c.setLineWidth(0.9)
    c.setDash(4, 2)
    c.rect(a[0], b[1], b[0] - a[0], a[1] - b[1], stroke=1, fill=0)
    c.setDash()
    cx = (a[0] + b[0]) / 2
    text(c, cx, v.p((0, 3.75))[1], "ANTENNA END", 7, "Helvetica-Bold", BLUE, "c")
    text(c, cx, v.p((0, 5.0))[1], "U1  ESP32 DevKit V1, 30 pin", 7.5, "Helvetica-Bold", BLUE, "c")
    text(c, cx, v.p((0, 5.75))[1], "in two 15-pin female headers (drawn: 25.4 mm rows)", 6.5,
         "Helvetica", BLUE, "c")
    label_bg(c, cx, v.p((0, 23.75))[1], "USB END (faces this edge)", 7, "Helvetica-Bold", BLUE, "c")
    for p in B.pads:
        if p["ref"] not in ("U1L", "U1R"):
            continue
        x, y = v.p((p["x"], p["y"]))
        used = not p["net"].startswith("NC:")
        col = BLUE if used else Color(0.6, 0.65, 0.75)
        f = "Helvetica-Bold" if used else "Helvetica"
        if p["ref"] == "U1L":
            text(c, x + v.d(1.3), y - 2.2, p["label"], 6.5, f, col)
        else:
            text(c, x - v.d(1.3), y - 2.2, p["label"], 6.5, f, col, "r")

    # Pin headers: outline + pin names
    for comp in B.components:
        if comp["kind"] != "hdr":
            continue
        pins = comp["pins"]
        xs = [q[1] for q in pins]
        ys = [q[2] for q in pins]
        p0 = v.p((min(xs) - 0.5, min(ys) - 0.5))
        p1 = v.p((max(xs) + 0.5, max(ys) + 0.5))
        c.setStrokeColor(GREEN)
        c.setLineWidth(0.9)
        c.rect(p0[0], p1[1], p1[0] - p0[0], p0[1] - p1[1], stroke=1, fill=0)
        ref = comp["ref"]
        if ref == "J4":
            for name, x, y in pins:
                px, py = v.p((x, y - 0.45))
                c.saveState()
                c.translate(px, py)
                c.rotate(90)
                label_bg(c, 0, -2.1, name, 5.8, color=GREEN)
                c.restoreState()
        elif ref in ("J1", "J9"):
            for name, x, y in pins:
                px, py = v.p((x - 0.55, y))
                label_bg(c, px, py - 2.2, name, 6.5, color=GREEN, anchor="r")
        elif ref in ("J2", "J3"):
            for name, x, y in pins:
                px, py = v.p((x + 0.6, y))
                text(c, px, py - 2.2, name, 6.5, "Helvetica-Bold", GREEN)

    # Connector titles
    for (x, y), s, anchor in B.titles:
        px, py = v.p((x, y))
        label_bg(c, px, py, s, 7, color=GREEN, anchor=anchor)
    for (x, y, s) in B.tags:
        px, py = v.p((x, y))
        label_bg(c, px, py - 2.2, s, 6.2, color=GREEN, anchor="r")
    px, py = v.p((B.BX0, B.BY1))
    text(c, px, py - 4 * mm, "J4 fan: red 12V, black GND, yellow FG, blue PWM.   J3 DS18B20: red VCC, "
         "black GND, yellow DATA.", 7, "Helvetica", GREEN)
    text(c, px, py - 7.5 * mm, ("J7 (battery gauge) is for later: leave it open. " if B.battery else "")
         + "Power wires enter J8 from the bottom edge.", 7, "Helvetica", GREEN)

    # Screw terminal body
    p0, p1 = v.p((0.0, 22.6)), v.p((6.0, 25.7))
    c.setStrokeColor(GREEN)
    c.setLineWidth(0.9)
    c.rect(p0[0], p1[1], p1[0] - p0[0], p0[1] - p1[1], stroke=1, fill=0)
    for name, x, y in [("12V", 1, 24), ("GND", 3, 24), ("5V", 5, 24)]:
        px, py = v.p((x, y - 0.75))
        text(c, px, py, name, 6.5, "Helvetica-Bold", GREEN, "c")

    # Resistors / capacitor
    for comp in B.components:
        if comp["kind"] not in ("res", "cap"):
            continue
        (ax, ay), (bx, by) = comp["a"], comp["b"]
        pa, pb = v.p((ax, ay)), v.p((bx, by))
        col = black if comp["fit"] else Color(0.45, 0.45, 0.45)
        c.setStrokeColor(col)
        c.setFillColor(white)
        c.setLineWidth(0.8)
        if not comp["fit"]:
            c.setDash(2, 1.5)
        lab = f'{comp["ref"]} {comp["value"]}' if comp["fit"] else f'{comp["ref"]} empty'
        if ax == bx:
            w, h = v.d(2.6), abs(pa[1] - pb[1]) - v.d(3.0)
            c.rect(pa[0] - w / 2, min(pa[1], pb[1]) + v.d(1.5), w, h, stroke=1, fill=1)
            c.setDash()
            if comp["kind"] == "res":
                rotated(c, pa[0], (pa[1] + pb[1]) / 2, lab, 5.8, color=col)
        else:
            h, w = v.d(2.6), abs(pa[0] - pb[0]) - v.d(3.0)
            c.rect(min(pa[0], pb[0]) + v.d(1.5), pa[1] - h / 2, w, h, stroke=1, fill=1)
            c.setDash()
            text(c, (pa[0] + pb[0]) / 2, pa[1] - 2.0, lab, 5.8, "Helvetica-Bold", col, "c")
    if B.battery:
        px, py = v.p((6.95, 9.0))
        label_bg(c, px, py - 2.2, "C1 empty", 5.8, color=Color(0.45, 0.45, 0.45), anchor="r")

    # JP1 wire link
    jp = next(k for k in B.components if k["ref"] == "JP1")
    pa, pb = v.p(jp["a"]), v.p(jp["b"])
    c.setStrokeColor(RED)
    c.setLineWidth(1.8)
    c.line(pa[0], pa[1], pb[0], pb[1])
    label_bg(c, (pa[0] + pb[0]) / 2, pa[1] + 2.2 * mm, "JP1 wire link (GND)", 6.5, color=RED,
             anchor="c")

    y = v.p((0, B.BY1))[1] - 17 * mm
    paragraph(c, 15 * mm, y, [
        "**Order of assembly",
        "1. JP1 wire link first (a cut resistor leg). It sits under the ESP32.",
        "2. R1 4.7k and R2 10k." + (" Leave R3, R4 and C1 EMPTY (future battery gauge)." if B.battery else ""),
        "3. Male pin headers J1-J6" + (", J7" if B.battery else "") + " and J9 (2.54 mm), then the J8 screw terminal.",
        "4. The two 15-pin FEMALE headers last. Plug the ESP32 in with VIN/GND at the bottom-left,",
        "    3V3/GND at the bottom-right and the USB port toward the bottom edge.",
        "",
        "**Drill sizes",
        "Header and resistor pins 0.8-1.0 mm  |  screw terminal 1.2-1.3 mm  |  mounting holes 3.2 mm (M3)",
        "",
        "**Check before you solder the ESP32 headers",
        "No copper bridges between neighbouring pads (scrape with a blade, test with a multimeter).",
        "5V, 12V and 3V3 must NOT beep to GND on the continuity test.",
    ], 8.5)


# ---------------------------------------------------------------- page 3
WIRE_COLORS = {"red": RED, "black": black, "yellow": Color(0.85, 0.68, 0.0), "blue": BLUE,
               "orange": ORANGE, "pink": Color(0.85, 0.2, 0.55), "grey": Color(0.45, 0.45, 0.45),
               "green": GREEN}

HARNESS = [
    ("J4  FAN", "SUNON fan (4-wire)", [
        ("12V", "red +12V", "red"), ("GND", "black GND", "black"),
        ("TACH  D34", "yellow FG / tach", "yellow"), ("PWM  D23", "blue PWM", "blue")]),
    ("J5  BTN1", "Button 1 = DOWN", [("GND", "leg A", "black"), ("B1  D32", "leg B", "grey")]),
    ("J6  BTN2", "Button 2 = UP", [("GND", "leg A", "black"), ("B2  D33", "leg B", "grey")]),
    ("J1  BTS7960 A", "BTS7960 control pins", [
        ("R_EN  D25", "R_EN", "grey"), ("RPWM  D26", "RPWM", "grey"), ("LPWM  D27", "LPWM", "grey")]),
    ("J9  BTS7960 B", "BTS7960 control pins", [
        ("L_EN  D13", "L_EN", "grey"), ("GND", "GND", "black"), ("VCC  5V", "VCC", "orange")]),
    ("J2  OLED", "OLED SH1107 (I2C)", [
        ("VCC  3V3", "VCC", "pink"), ("GND", "GND", "black"), ("SCL  D22", "SCL", "grey"),
        ("SDA  D21", "SDA", "grey")]),
    ("J3  DS18B20", "DS18B20 probe", [
        ("VCC  3V3", "red", "red"), ("GND", "black", "black"), ("DATA  D14", "yellow", "yellow")]),
    ("J8  POWER IN", "Power (screw terminal)", [
        ("12V", "12V after switch + fuse", "red"), ("GND", "common GND", "black"),
        ("5V", "buck converter OUT+ (5.0 V)", "orange")]),
    ("J7  BATT", "Future battery gauge", [("GND", "leave open", "grey"), ("BAT+", "leave open", "grey")]),
]


def page_wiring(c, B):
    text(c, 15 * mm, PH - 16 * mm, "Wiring (line route): board connectors to ThermoX parts", 12,
         "Helvetica-Bold")
    text(c, 15 * mm, PH - 22 * mm,
         "Female-female dupont wires on the pin headers. Match the pin NAMES printed on each module.",
         8.5)
    xb0, xb1 = 15, 62        # board connector box
    xd0, xd1 = 120, 195      # device box
    pitch, gap = 4.5, 3.2
    y = 30.0
    for title, device, rows in [h for h in HARNESS if B.battery or not h[0].startswith("J7")]:
        h = len(rows) * pitch + 6
        # board side box
        c.setStrokeColor(GREEN)
        c.setFillColor(Color(0.93, 0.97, 0.93))
        c.setLineWidth(0.9)
        c.roundRect(xb0 * mm, PH - (y + h) * mm, (xb1 - xb0) * mm, h * mm, 1.5 * mm, stroke=1, fill=1)
        text(c, (xb0 + 2) * mm, PH - (y + 4) * mm, title, 7.5, "Helvetica-Bold", GREEN)
        # device box
        dashed = device.startswith("Future")
        c.setStrokeColor(DARK)
        c.setFillColor(white)
        if dashed:
            c.setDash(3, 2)
        c.roundRect(xd0 * mm, PH - (y + h) * mm, (xd1 - xd0) * mm, h * mm, 1.5 * mm, stroke=1, fill=1)
        c.setDash()
        text(c, (xd0 + 2) * mm, PH - (y + 4) * mm, device, 7.5, "Helvetica-Bold", DARK)
        for i, (pin, dev_pin, colname) in enumerate(rows):
            yy = y + 6 + i * pitch + pitch / 2
            col = WIRE_COLORS[colname]
            text(c, (xb1 - 2.5) * mm, PH - (yy + 1.1) * mm, pin, 6.8, "Helvetica-Bold", DARK, "r")
            text(c, (xd0 + 2.5) * mm, PH - (yy + 1.1) * mm, dev_pin, 6.8, "Helvetica", DARK)
            if dashed:
                c.setDash(2, 2)
            c.setStrokeColor(col)
            c.setLineWidth(1.6 if colname in ("red", "orange", "black") else 1.2)
            c.line(xb1 * mm, PH - yy * mm, xd0 * mm, PH - yy * mm)
            c.setDash()
            c.setFillColor(col)
            c.circle(xb1 * mm, PH - yy * mm, 0.8 * mm, stroke=0, fill=1)
            c.circle(xd0 * mm, PH - yy * mm, 0.8 * mm, stroke=0, fill=1)
        y += h + gap

    # Power path diagram
    y += 2
    text(c, 15 * mm, PH - (y + 3) * mm, "Power path (Peltier current never goes through the board)", 9,
         "Helvetica-Bold")
    top = y + 8

    def blk(x, yb, w, h, t1, t2="", col=DARK):
        c.setStrokeColor(col)
        c.setFillColor(white)
        c.setLineWidth(1.0)
        c.roundRect(x * mm, PH - (yb + h) * mm, w * mm, h * mm, 1.5 * mm, stroke=1, fill=1)
        text(c, (x + w / 2) * mm, PH - (yb + 4.3) * mm, t1, 7.3, "Helvetica-Bold", col, "c")
        if t2:
            text(c, (x + w / 2) * mm, PH - (yb + 8) * mm, t2, 6.5, "Helvetica", DARK, "c")

    def ln(pts, col, w=1.8):
        c.setStrokeColor(col)
        c.setLineWidth(w)
        c.setLineJoin(1)
        path = c.beginPath()
        path.moveTo(pts[0][0] * mm, PH - pts[0][1] * mm)
        for px, py in pts[1:]:
            path.lineTo(px * mm, PH - py * mm)
        c.drawPath(path, stroke=1, fill=0)

    bh = 10
    blk(15, top, 32, bh, "12V battery / PSU", "+ and -", RED)
    blk(55, top, 30, bh, "Switch + 10 A fuse", "on the + wire", RED)
    blk(105, top, 36, bh, "BTS7960 B+ / B-", "power screw terminals", DARK)
    blk(155, top, 40, bh, "Peltier (TEC)", "on BTS7960 M+ / M-", RED)
    blk(105, top + 14, 36, bh, "Buck 12V -> 5V", "set 5.0 V first", DARK)
    blk(155, top + 14, 40, bh, "Board J8: 5V", "", GREEN)
    blk(105, top + 28, 36, bh, "Board J8: 12V", "for the SUNON fan", GREEN)
    ym = top + bh / 2
    ln([(47, ym), (55, ym)], RED)
    ln([(85, ym), (105, ym)], RED)
    ln([(95, ym), (95, top + 28 + bh / 2), (105, top + 28 + bh / 2)], RED)
    ln([(95, top + 14 + bh / 2), (105, top + 14 + bh / 2)], RED)
    ln([(141, ym), (155, ym)], RED, 2.4)
    ln([(141, top + 14 + bh / 2), (155, top + 14 + bh / 2)], ORANGE)
    c.setFillColor(RED)
    c.circle(95 * mm, PH - ym * mm, 0.9 * mm, stroke=0, fill=1)
    c.circle(95 * mm, PH - (top + 14 + bh / 2) * mm, 0.9 * mm, stroke=0, fill=1)
    text(c, 15 * mm, PH - (top + 17) * mm, "GND: battery -, BTS7960 B-, buck IN-/OUT-", 7, "Helvetica",
         DARK)
    text(c, 15 * mm, PH - (top + 20.5) * mm, "and board J8 GND all go to ONE common point.", 7,
         "Helvetica", DARK)
    text(c, 15 * mm, PH - (top + 26) * mm, "Never put 12V on J8 5V or on any ESP32 pin.", 7,
         "Helvetica-Bold", RED)
    text(c, 15 * mm, PH - (top + 29.5) * mm, "Test: USB only -> fan -> dummy load -> Peltier.", 7,
         "Helvetica", DARK)


# ---------------------------------------------------------------- page 4
def table(c, x, y, cols, rows, size=8.0, lead=4.3, head=True):
    """cols: list of (title, width_mm). Returns the y (pt) under the table."""
    yy = y
    if head:
        xx = x
        for t, w in cols:
            text(c, xx * mm, yy, t, size, "Helvetica-Bold", DARK)
            xx += w
        yy -= 1.5 * mm
        c.setStrokeColor(GREY)
        c.setLineWidth(0.5)
        c.line(x * mm, yy, (x + sum(w for _, w in cols)) * mm, yy)
        yy -= lead * mm - 1.5 * mm
    for r in rows:
        xx = x
        for (t, w), cell in zip(cols, r):
            text(c, xx * mm, yy, cell, size, "Helvetica", black)
            xx += w
        yy -= lead * mm
    return yy


def page_bom(c, B):
    text(c, 15 * mm, PH - 16 * mm, "Parts list, GPIO check and how to make the board", 12,
         "Helvetica-Bold")
    y = PH - 26 * mm
    text(c, 15 * mm, y, "Parts", 9.5, "Helvetica-Bold")
    y = table(c, 15, y - 6 * mm, [("Ref", 18), ("Part", 70), ("Use", 90)], [
        ("U1", "ESP32 DevKit V1, 30 pin", "+ two 15-pin female headers, 2.54 mm"),
        ("J1, J9", "3-pin male header (x2)", "BTS7960: R_EN RPWM LPWM / L_EN GND VCC"),
        ("J2", "4-pin male header", "OLED: VCC(3V3) GND SCL SDA"),
        ("J3", "3-pin male header", "DS18B20: VCC(3V3) GND DATA"),
        ("J4", "4-pin male header", "SUNON fan: 12V GND TACH PWM"),
        ("J5, J6", "2-pin male header (x2)", "buttons: GND + signal"),
    ] + ([("J7", "2-pin male header", "battery sense, future (can be left off)")] if B.battery else []) + [
        ("J8", "3-way screw terminal, 5.08 mm", "power in: 12V GND 5V"),
        ("R1", "4.7 kohm, 1/4 W", "DS18B20 DATA pull-up to 3V3"),
        ("R2", "10 kohm, 1/4 W", "fan tach pull-up to 3V3 (GPIO34 has none)"),
    ] + ([("R3, R4, C1", "leave EMPTY", "future battery gauge, see notes")] if B.battery else []) + [
        ("JP1", "wire link (cut resistor leg)", "joins left and right GND"),
        ("PCB", "single-sided copper clad", f"at least {B.BOARD_W + 4:.0f} x {B.BOARD_H + 4:.0f} mm"),
    ])
    y -= 3 * mm
    text(c, 15 * mm, y, "GPIO check (current ThermoX pin map, nothing changed)", 9.5, "Helvetica-Bold")
    y = table(c, 15, y - 6 * mm, [("Function", 62), ("GPIO", 20), ("Board pin", 50)], [
        ("Button 1", "GPIO32", "J5 B1"),
        ("Button 2", "GPIO33", "J6 B2"),
        ("OLED SDA", "GPIO21", "J2 SDA"),
        ("OLED SCL", "GPIO22", "J2 SCL"),
        ("BTS7960 LPWM", "GPIO27", "J1 LPWM"),
        ("BTS7960 RPWM", "GPIO26", "J1 RPWM"),
        ("BTS7960 LEN", "GPIO13", "J9 L_EN"),
        ("BTS7960 REN", "GPIO25", "J1 R_EN"),
        ("Temperature sensor (DS18B20)", "GPIO14", "J3 DATA (+ R1 4.7k)"),
        ("SUNON fan PWM", "GPIO23", "J4 PWM"),
        ("SUNON fan tach / FG", "GPIO34", "J4 TACH (+ R2 10k)"),
        ("Battery sense (future, off)", "GPIO35",
         "R3/R4 divider -> J7" if B.battery else "not on this board (wire later)"),
    ])
    y -= 3 * mm
    y = paragraph(c, 15 * mm, y, [
        "**Toner transfer, step by step",
        "1. Print page 1 OR page 2 (the one that matches your ESP32 rows) on glossy/photo paper, laser, 100%.",
        "2. Measure the 50 mm scale bar. Put your ESP32 on the print and check that its pins land on the pads.",
        "3. Sand the copper lightly (fine sandpaper or steel wool), clean with alcohol/acetone, don't touch it.",
        "4. Toner side DOWN on the copper. Iron on the hottest (cotton) setting, no steam, 3-5 min, firm",
        "    pressure, go slowly over every edge and corner.",
        "5. Let it cool, soak in warm water 10-15 min, rub the paper off gently with your thumb.",
        "6. Touch up broken traces with a permanent marker. The text must read NORMALLY on the copper.",
        "7. Etch in ferric chloride (warm, keep it moving). Remove the toner with acetone.",
        "8. Drill at the dots, cut along the outline, solder in the order on page 3.",
    ], 8.3)
    y -= 2 * mm
    paragraph(c, 15 * mm, y, [
        "**Before first power-up",
        "* Continuity: 5V-GND, 12V-GND and 3V3-GND must be OPEN (no beep). No bridges between ESP32 pads.",
        "* First power: USB only (no 12V, no BTS7960). Check the OLED, both buttons and the temperature.",
        "* Then 12V + buck 5V, the fan, the BTS7960 with a dummy load, and only then the Peltier.",
        "",
        "**Notes",
        "* For the 30-pin DevKit V1 only. Page 1 = rows 25.4 mm apart, page 2 = rows 22.86 mm. 38-pin will NOT fit.",
        "* Battery gauge (later): " + ("R3 top, R4 bottom; " if B.battery else "divider from BAT+ to the GPIO35 "
        "socket pin; ") + "GPIO35 must stay under 3.1 V. 1S Li-ion: 100k/100k.",
        "   3S 12 V pack: 100k/27k and set BATT_DIVIDER = 4.7 in the firmware. Then ENABLE_BATTERY_SENSE.",
        "* Fan PWM is driven straight from GPIO23, as in the ThermoX firmware README.",
    ], 8.3)


def make(out, a, b):
    """a, b: the 25.4 mm and 22.86 mm row variants of one board size."""
    c = canvas.Canvas(out, pagesize=A4)
    c.setTitle(f"ThermoX ESP32 board {a.name} mm - toner transfer PCB")
    c.setAuthor("ThermoX")
    for page in (lambda: page_toner(c, a, b.ROWS_MM), lambda: page_toner(c, b, a.ROWS_MM),
                 lambda: page_placement(c, a), lambda: page_wiring(c, a), lambda: page_bom(c, a)):
        page()
        c.showPage()
    c.save()
    print("wrote", out)


def main():
    make(OUT, L.VARIANTS["25.4"], L.VARIANTS["22.86"])
    for size in (70, 80):
        make(f"ThermoX_PCB_{size}x{size}mm.pdf", L.SMALL[(size, "25.4")], L.SMALL[(size, "22.86")])


if __name__ == "__main__":
    main()
