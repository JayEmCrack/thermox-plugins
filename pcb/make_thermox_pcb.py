#!/usr/bin/env python3
"""ThermoX one-board PCB: controller and power on a single 82 mm round board.

The ESP32, the USB-C trigger board, the source switch, the fuse, the bulk capacitor, the battery gauge and every
connector sit on one single-sided, through-hole board for home etching. It fits the 85 mm battery bay of the round
bottles and replaces the controller board and the power board. The LM2596S 5 V buck module is wired to U2.

To keep it this small, the trigger board (M1) lies flat under the ESP32, between its two female headers, with its
USB-C at the board edge. The ESP32 is plugged in last.

The ESP32 pin rows are 25.4 mm or 22.86 mm apart depending on the board, so the board is made for both.
Each run rebuilds both PDFs and checks them; it stops with an error if a check fails:
  - copper of different nets at least CLEAR mm apart, ground fill POUR_CLEAR / POUR_CLEAR_HI mm from other nets
  - every net in one piece, every GND pad on the one ground area, no copper under the ESP32 antenna
  - the ground path for the Peltier current (battery -, trigger board -, BTS7960 B-, C1 -) is at least GND_WIDE mm wide
  - part bodies do not overlap each other or the mounting holes, stay on the board and cover no other part's pads
    (low parts under the ESP32 excepted)

Run:  python3 make_thermox_pcb.py        (needs: pip install shapely matplotlib)
"""
import os
import sys

from shapely.geometry import LineString, MultiPoint, Point, box
from shapely.ops import unary_union

import make_pcb as base     # drawing helpers shared with the other boards

OUT = os.path.dirname(os.path.abspath(__file__))
R_BOARD = 41.0       # mm, board radius (82 mm round)
CLEAR = 0.6          # mm, copper gap between different nets
POUR_CLEAR = 0.8     # mm, gap between the ground fill and signal nets
POUR_CLEAR_HI = 1.0  # mm, gap between the ground fill and the power nets
EDGE_CLEAR = 0.6     # mm, copper kept away from the board edge
GND_WIDE = 3.2       # mm, narrowest ground path allowed for the Peltier return current
HI_NETS = ("BAT+", "PD+", "COM", "BUS")
W_HI, W_C, W_PWR, W_SIG = 4.0, 2.0, 1.2, 0.7     # trace widths, mm
TB = (3.0, 1.3)      # 5.08 mm screw terminal pad (diameter, drill)
FUSE = (3.4, 1.5)    # 5x20 mm PCB fuse holder (BLX-A type), pins 22.6 mm apart
WIRE = (3.4, 1.5)    # trigger board output wire (1 mm2)
SWP = (4.0, 2.2)     # mini toggle switch lug (MTS-103 type), lugs 4.7 mm apart
HDR = (1.9, 1.0)     # 2.54 mm header, ESP32 socket
SMALL = (1.9, 0.8)   # resistors, small capacitors
CAP = (2.2, 1.0)     # C1 radial electrolytic
HOLE_R = 1.6         # M3 mounting hole
MARKER = "THERMOX"   # mirrored text cut into the ground fill, reads correctly on the etched board

LEFT_PINS = ["EN", "VP", "VN", "IO34", "IO35", "IO32", "IO33", "IO25", "IO26", "IO27", "IO14", "IO12", "IO13", "GND", "VIN"]
RIGHT_PINS = ["IO23", "IO22", "TX0", "RX0", "IO21", "IO19", "IO18", "IO5", "TX2", "RX2", "IO4", "IO2", "IO15", "GND", "3V3"]
USED = {"IO34": "FG", "IO35": "BATT", "IO32": "BTN1", "IO33": "BTN2", "IO25": "R_EN", "IO26": "RPWM", "IO27": "LPWM",
        "IO14": "DQ", "IO13": "L_EN", "GND": "GND", "VIN": "5V",
        "IO23": "PWM", "IO22": "SCL", "IO21": "SDA", "3V3": "3V3"}
LX = 23.15           # left ESP32 pin row, mm


def row(i):
    """y of ESP32 pin i (0 = antenna end, 14 = USB end), mm."""
    return 45.06 - 2.54 * i


def design(spacing):
    """Pads, traces, part bodies and holes. Coordinates: top (parts) side view, mm, origin bottom-left."""
    RX = LX + spacing
    pads, traces, parts = [], [], []

    def pad(x, y, net, ref, pin, size, square=False):
        pads.append(dict(x=x, y=y, net=net, ref=ref, pin=pin, d=size[0], drill=size[1], square=square))

    def tr(net, w, *pts):
        traces.append(dict(net=net, w=w, pts=list(pts)))

    def terminal(ref, label, pins, entry):
        """5.08 mm screw terminal. pins = [(x, y, name, net), ...] in a line; entry = side the wires go in."""
        for k, (x, y, name, net) in enumerate(pins):
            pad(x, y, net, ref, name, TB, square=(k == 0))
        xs = [p[0] for p in pins]; ys = [p[1] for p in pins]
        if len(set(xs)) == 1:
            body = box(xs[0] - 3.8, min(ys) - 2.46, xs[0] + 3.8, max(ys) + 2.46)
        else:
            body = box(min(xs) - 2.46, ys[0] - 3.8, max(xs) + 2.46, ys[0] + 3.8)
        parts.append(dict(ref=ref, kind="tb", label=label, body=body, entry=entry, pins=pins))

    def header(ref, label, pins):
        """2.54 mm male header (straight or L-shaped)."""
        for k, (x, y, name, net) in enumerate(pins):
            pad(x, y, net, ref, name, HDR, square=(k == 0))
        body = unary_union([box(x - 1.28, y - 1.28, x + 1.28, y + 1.28) for x, y, _, _ in pins]).buffer(-0.01, join_style=2)
        parts.append(dict(ref=ref, kind="hdr", label=label, body=body, pins=pins))

    def module(rect, usb, plus, minus):
        """M1, the USB-C PD trigger board, lying on the area rect with its USB-C end on side usb. Its output is wired
        to the pads plus and minus."""
        pad(plus[0], plus[1], "PD+", "M1", "+", WIRE, square=True); pad(minus[0], minus[1], "GND", "M1", "-", WIRE)
        parts.append(dict(ref="M1", kind="mod", label="USB-C PD TRIGGER", body=box(*rect), usb=usb, plus=plus,
                          minus=minus, under=True))

    def switch(pins):
        """SW1, ON-OFF-ON mini toggle switch (MTS-103 type): 3 lugs 4.7 mm apart, body 13 x 8 mm."""
        for x, y, name, net in pins:
            pad(x, y, net, "SW1", name, SWP)
        xs = [p[0] for p in pins]; ys = [p[1] for p in pins]
        cx, cy = xs[1], ys[1]
        body = box(cx - 4.0, cy - 6.5, cx + 4.0, cy + 6.5) if len(set(xs)) == 1 else box(cx - 6.5, cy - 4.0, cx + 6.5, cy + 4.0)
        parts.append(dict(ref="SW1", kind="sw", label="ON-OFF-ON", body=body, pins=pins))

    def fuse(a, b):
        """F1 fuse holder, COM at a and BUS at b."""
        assert abs(Point(a).distance(Point(b)) - 22.6) < 1e-6
        pad(a[0], a[1], "COM", "F1", "1", FUSE); pad(b[0], b[1], "BUS", "F1", "2", FUSE)
        cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        body = box(cx - 16.3, cy - 5.0, cx + 16.3, cy + 5.0) if a[1] == b[1] else box(cx - 5.0, cy - 16.3, cx + 5.0, cy + 16.3)
        parts.append(dict(ref="F1", kind="fuse", label="10A", body=body, a=a, b=b))

    def cap(ref, label, plus, minus, net, r, size, minus_net="GND"):
        pad(plus[0], plus[1], net, ref, "+", size, square=True); pad(minus[0], minus[1], minus_net, ref, "-", size)
        cx, cy = (plus[0] + minus[0]) / 2, (plus[1] + minus[1]) / 2
        parts.append(dict(ref=ref, kind="cap", label=label, body=Point(cx, cy).buffer(r, 64), plus=plus, minus=minus))

    def ceramic(ref, label, a, b, net_a, net_b, under=False):
        """Small ceramic capacitor, leads 2.54 mm apart."""
        pad(a[0], a[1], net_a, ref, "1", SMALL); pad(b[0], b[1], net_b, ref, "2", SMALL)
        line = LineString([a, b])
        parts.append(dict(ref=ref, kind="cer", label=label, body=line.buffer(1.3, 8), a=a, b=b, under=under))

    def jumper(ref, a, b, net):
        """Wire link on the parts side (bare wire or a cut resistor lead) between pads a and b."""
        pad(a[0], a[1], net, ref, "1", SMALL); pad(b[0], b[1], net, ref, "2", SMALL)
        parts.append(dict(ref=ref, kind="jp", label="wire link", body=LineString([a, b]).buffer(0.5, 8), a=a, b=b,
                          link=True))

    def res(ref, label, a, b, net_a, net_b, under=False):
        """Resistor lying flat, leads 10.16 mm apart."""
        pad(a[0], a[1], net_a, ref, "1", SMALL); pad(b[0], b[1], net_b, ref, "2", SMALL)
        cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        body = box(cx - 3.3, cy - 1.25, cx + 3.3, cy + 1.25) if a[1] == b[1] else box(cx - 1.25, cy - 3.3, cx + 1.25, cy + 3.3)
        parts.append(dict(ref=ref, kind="res", label=label, body=body, a=a, b=b, under=under))

    outline = Point(R_BOARD, R_BOARD).buffer(R_BOARD, 256)

    # ---- U1 ESP32 DevKit on two 1x15 female headers, USB end at the bottom edge
    for i, nm in enumerate(LEFT_PINS):
        pad(LX, row(i), USED.get(nm, "NC_L" + nm), "U1", nm, HDR, square=(i == 0))
    for i, nm in enumerate(RIGHT_PINS):
        pad(RX, row(i), USED.get(nm, "NC_R" + nm), "U1", nm, HDR)
    esp = box(LX - 1.45, row(14) - 4.0, RX + 1.45, row(0) + 12.44)
    antenna = box(LX - 1.45, row(0) + 5.44, RX + 1.45, row(0) + 12.44)
    parts.append(dict(ref="U1", kind="esp32", label="ESP32 DevKit", body=esp, antenna=antenna))

    # ---- M1 trigger board under the ESP32; its output wires come out under the antenna end
    module((27.85, 3.0, 43.85, 35.0), "bottom", (62.0, 46.0), (67.5, 46.0))

    # ---- power: battery and USB-C -> SW1 -> F1 -> BUS
    terminal("J1", "BATTERY", [(70.5, 61.4, "BAT+", "BAT+"), (70.5, 56.32, "BAT-", "GND")], "right")
    switch([(62.0, 52.0, "USB", "PD+"), (62.0, 56.7, "COM", "COM"), (62.0, 61.4, "BATT", "BAT+")])
    fuse((51.6, 67.0), (29.0, 67.0))
    terminal("J2", "BTS7960", [(19.48, 66.0, "B+", "BUS"), (14.4, 66.0, "B-", "GND")], "top")
    cap("C1", "2200uF 25V", (12.0, 56.5), (12.0, 51.5), "BUS", 6.5, CAP)
    tr("PD+", W_HI, (62.0, 46.0), (62.0, 52.0))
    tr("BAT+", W_HI, (70.5, 61.4), (62.0, 61.4))
    tr("COM", W_HI, (62.0, 56.7), (57.0, 56.7), (54.0, 62.5), (51.6, 67.0))
    tr("BUS", W_HI, (29.0, 67.0), (19.48, 66.0))
    tr("BUS", W_C, (19.48, 66.0), (12.0, 56.5))
    # BUS on to the fan, the 5 V module and, through the gap above the ESP32 pins, to the battery gauge
    tr("BUS", W_PWR, (19.48, 66.0), (16.0, 61.0), (16.0, 42.52), (LX - 4.25, 42.52))
    tr("BUS", W_PWR, (16.0, 49.1), (40.0, 49.1))

    # ---- U2: wires to the LM2596S buck module (5 V), left of the ESP32. Solder the wires, or fit a KF301-3P.
    terminal("U2", "LM2596 5V", [(8.0, 43.08, "IN+", "BUS"), (8.0, 38.0, "GND", "GND"), (8.0, 32.92, "OUT+", "5V")], "left")
    tr("BUS", W_PWR, (16.0, 46.0), (10.0, 46.0), (8.0, 44.5), (8.0, 43.08))
    tr("5V", W_PWR, (8.0, 32.92), (11.0, 29.5), (11.0, 21.0), (13.82, row(10)))

    # ---- left side: buttons, BTS7960 control, temperature, fan (signal column x = LX - 4.25)
    SX, GX = LX - 4.25, LX - 6.79
    header("J3", "FAN", [(SX, row(0), "PWM", "PWM"), (SX, row(1), "+12V", "BUS"), (SX, row(2), "GND", "GND"),
                         (SX, row(3), "FG", "FG")])
    header("J5", "BTN1", [(GX, row(5), "GND", "GND"), (SX, row(5), "B1", "BTN1")])
    header("J6", "BTN2", [(GX, row(6), "GND", "GND"), (SX, row(6), "B2", "BTN2")])
    header("J7", "BTS A", [(SX, row(7), "R_EN", "R_EN"), (SX, row(8), "RPWM", "RPWM"), (SX, row(9), "LPWM", "LPWM")])
    header("J9", "TEMP", [(SX, row(10), "DQ", "DQ"), (GX, row(10), "GND", "GND"), (GX - 2.54, row(10), "5V", "5V")])
    header("J8", "BTS B", [(SX, row(12), "L_EN", "L_EN"), (SX, row(13), "GND", "GND"), (SX, row(14), "VCC", "5V")])
    for i, net in ((3, "FG"), (5, "BTN1"), (6, "BTN2"), (7, "R_EN"), (8, "RPWM"), (9, "LPWM"), (10, "DQ"), (12, "L_EN")):
        tr(net, W_SIG, (SX, row(i)), (LX, row(i)))
    tr("GND", W_PWR, (SX, row(13)), (LX, row(13)))
    tr("5V", W_PWR, (SX, row(14)), (LX, row(14)))
    tr("5V", W_PWR, (GX - 2.54, row(10)), (13.82, 12.2), (17.0, row(14)), (SX, row(14)))
    # fan PWM from GPIO23 through the gap above the ESP32 pins
    tr("PWM", W_SIG, (RX, row(0)), (RX, 47.0), (SX, 47.0), (SX, row(0)))

    # ---- pull-ups under the ESP32 (left lane) and the battery gauge
    res("R2", "4.7k", (25.7, row(10)), (25.7, row(14)), "DQ", "3V3", under=True)
    res("R1", "10k", (25.7, row(3)), (25.7, row(7)), "FG", "3V3", under=True)
    tr("DQ", W_SIG, (LX, row(10)), (25.7, row(10)))
    tr("FG", W_SIG, (LX, row(3)), (25.7, row(3)))
    tr("3V3", W_SIG, (RX, row(14)), (RX, 7.6), (25.7, 7.6), (25.7, row(14)))
    tr("3V3", W_SIG, (25.7, row(14)), (29.0, 12.0), (29.0, 25.5), (25.7, row(7)))
    # battery gauge: R3 100k BUS -> GPIO35, R4 22k and C4 100 nF GPIO35 -> GND
    res("R3", "100k", (40.0, 49.1), (40.0, 38.94), "BUS", "BATT", under=True)
    res("R4", "22k", (37.4, 41.6), (27.24, 41.6), "BATT", "GND", under=True)
    ceramic("C4", "100nF", (33.5, 38.94), (30.96, 38.94), "BATT", "GND", under=True)
    tr("BATT", W_SIG, (LX, row(4)), (33.5, row(4)), (33.5, 38.94), (40.0, 38.94))
    tr("BATT", W_SIG, (37.4, 38.94), (37.4, 41.6))

    # ---- right side: OLED
    OX = 53.5
    header("J4", "OLED", [(OX, row(1), "SCL", "SCL"), (OX, row(2), "GND", "GND"), (OX, row(3), "SDA", "SDA"),
                          (OX, row(4), "VCC", "3V3")])
    tr("SCL", W_SIG, (RX, row(1)), (OX, row(1)))
    tr("SDA", W_SIG, (RX, row(4)), (50.9, row(4)), (50.9, row(3)), (OX, row(3)))
    jumper("JP1", (56.0, row(14)), (56.0, row(4)), "3V3")
    tr("3V3", W_SIG, (RX, row(14)), (56.0, row(14)))
    tr("3V3", W_SIG, (56.0, row(4)), (OX, row(4)))

    holes = [(41.0, 77.0), (7.5, 22.5), (74.0, 33.0)]
    marker = (36.0, 59.8)
    return dict(spacing=spacing, RX=RX, outline=outline, pads=pads, traces=traces, parts=parts, holes=holes,
                marker=marker, keepout=antenna)


def pour_clear(net):
    return POUR_CLEAR_HI if net in HI_NETS else POUR_CLEAR


def check(d):
    """Copper geometry and all design checks. Returns dict with copper and a list of errors."""
    nets = {}
    for p in d["pads"]:
        nets.setdefault(p["net"], []).append(base.pad_geom(p))
    for t in d["traces"]:
        nets.setdefault(t["net"], []).append(base.trace_geom(t))
    net_geom = {n: unary_union(g) for n, g in nets.items()}
    errors = []
    names = sorted(net_geom)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            dist = net_geom[a].distance(net_geom[b])
            if dist < CLEAR - 1e-6:
                errors.append("clearance %s-%s %.2f mm" % (a, b, dist))
    inner = d["outline"].buffer(-EDGE_CLEAR)
    keep = unary_union([Point(x, y).buffer(HOLE_R + 0.8, 32) for x, y in d["holes"]])
    for n, g in net_geom.items():
        if not inner.contains(g):
            errors.append("net %s too close to the board edge" % n)
        if g.intersects(keep):
            errors.append("net %s hits a mounting hole" % n)
        if g.intersects(d["keepout"]):
            errors.append("net %s is under the ESP32 antenna" % n)
        links = [LineString([pt["a"], pt["b"]]).buffer(0.1) for pt in d["parts"] if pt.get("link")
                 and any(p["ref"] == pt["ref"] and p["net"] == n for p in d["pads"])]
        joined = unary_union([g] + links)
        if n != "GND" and joined.geom_type != "Polygon":
            errors.append("net %s is not connected (%d pieces)" % (n, len(joined.geoms)))
    # part bodies: no overlaps, on the board, clear of the holes and of other parts' pads.
    # Low parts (flagged under) may sit under the ESP32.
    holes = [Point(x, y).buffer(HOLE_R + 0.3, 32) for x, y in d["holes"]]
    for i, a in enumerate(d["parts"]):
        if not d["outline"].buffer(0.01).contains(a["body"]):
            errors.append("%s body sticks out of the board" % a["ref"])
        for h in holes:
            if a["body"].intersects(h):
                errors.append("%s body hits a mounting hole" % a["ref"])
        for b in d["parts"][i + 1:]:
            if "U1" in (a["ref"], b["ref"]) and (a.get("under") or b.get("under")) or a.get("link") or b.get("link"):
                continue
            if a["body"].intersection(b["body"]).area > 0.01:
                errors.append("%s and %s bodies overlap" % (a["ref"], b["ref"]))
        for p in d["pads"]:
            if p["ref"] == a["ref"] or not a["body"].intersects(base.pad_geom(p)):
                continue
            under = next(pt for pt in d["parts"] if pt["ref"] == p["ref"]).get("under")
            if a["ref"] == "U1" and under:
                continue
            errors.append("%s pad %s is under the %s body" % (p["ref"], p["pin"], a["ref"]))
    # ground fill
    others = unary_union([g.buffer(pour_clear(n), 16) for n, g in net_geom.items() if n != "GND"])
    fill = inner.difference(others).difference(keep).difference(d["keepout"])
    fill = fill.buffer(-0.35, 8).buffer(0.35, 8)
    gnd = unary_union([fill, net_geom["GND"]])
    parts_ = list(gnd.geoms) if gnd.geom_type == "MultiPolygon" else [gnd]
    gnd_pads = [p for p in d["pads"] if p["net"] == "GND"]
    main = [g for g in parts_ if any(g.intersects(base.pad_geom(p)) for p in gnd_pads)]
    if len(main) != 1:
        errors.append("ground is in %d separate pieces that hold GND pads" % len(main))
    gnd_main = max(main, key=lambda g: g.area) if main else gnd
    for p in gnd_pads:
        if not gnd_main.intersects(base.pad_geom(p)):
            errors.append("GND pad %s.%s not reached by the ground" % (p["ref"], p["pin"]))
    wide = gnd_main.buffer(-GND_WIDE / 2, 16).buffer(GND_WIDE / 2, 16)
    pieces = list(wide.geoms) if wide.geom_type == "MultiPolygon" else [wide]
    key = [p for p in gnd_pads if (p["ref"], p["pin"]) in (("J1", "BAT-"), ("M1", "-"), ("J2", "B-"), ("C1", "-"))]
    shared = None
    for p in key:
        near = {i for i, g in enumerate(pieces) if g.distance(base.pad_geom(p)) < 0.6}
        shared = near if shared is None else shared & near
    if not shared:
        errors.append("ground path for the Peltier current is narrower than %.1f mm somewhere" % GND_WIDE)
    from matplotlib.textpath import TextPath
    from matplotlib.transforms import Affine2D as _A
    mx, my = d["marker"]
    tv = TextPath((0, 0), MARKER, size=2.0).transformed(_A().scale(-1, 1).translate(mx + 5.5, my - 0.7)).vertices
    if not gnd_main.buffer(-0.3).contains(MultiPoint([tuple(v) for v in tv])):
        errors.append("marker text is not fully on the ground fill")
    copper = unary_union([gnd_main] + [g for n, g in net_geom.items() if n != "GND"])
    return dict(copper=copper, errors=errors, net_geom=net_geom, fill=gnd_main)


# ================================================================ drawing
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import PathPatch, Circle, Rectangle, Polygon as MplPolygon
from matplotlib.textpath import TextPath
from matplotlib.transforms import Affine2D

A4 = base.A4


def outline_xy(d, ox, oy, S=1.0):
    xs, ys = d["outline"].exterior.xy
    return [ox + S * x for x in xs], [oy + S * y for y in ys]


def copper_page(pdf, d, r):
    fig, ax = base.page(pdf, "ThermoX ONE BOARD: COPPER (82 mm round, ESP32 rows %.2f mm)" % d["spacing"], [
        "Print at 100 % / Actual size (no 'fit to page'). Check the 50 mm bar with a ruler.",
        "Use THIS page only if your ESP32 pin rows are %.2f mm apart (centre to centre). Otherwise use the other PDF."
        % d["spacing"],
        "Toner transfer or UV film: use this page as it is (do not mirror). Copper is on the bottom of the board.",
        "Check: the small text 'THERMOX' looks mirrored on the paper and reads normally on the etched copper side.",
        "Drill: 2.2 mm SW1, 1.5 mm F1 and M1 wire pads, 1.3 mm screw terminals and U2, 1.0 mm C1, ESP32 socket and",
        "headers, 0.8 mm resistors and C4, 3.2 mm mounting holes. Cover the wide tracks with solder.",
    ])
    for k, cx in enumerate((15.0, 112.0)):
        cy = 110.0
        ax.add_patch(PathPatch(base.poly_path(r["copper"]).transformed(Affine2D().translate(cx, cy)), facecolor="black",
                               edgecolor="none"))
        mx, my = d["marker"]
        ax.add_patch(PathPatch(TextPath((0, 0), MARKER, size=2.0).transformed(
            Affine2D().scale(-1, 1).translate(cx + mx + 5.5, cy + my - 0.7)), facecolor="white", edgecolor="none"))
        for p in d["pads"]:
            ax.add_patch(Circle((cx + p["x"], cy + p["y"]), 0.3, color="white"))
        for hx, hy in d["holes"]:
            ax.add_patch(Circle((cx + hx, cy + hy), HOLE_R, facecolor="none", edgecolor="black", lw=0.3))
            ax.add_patch(Circle((cx + hx, cy + hy), 0.3, color="black"))
        xs, ys = outline_xy(d, cx, cy)
        ax.plot(xs, ys, color="black", lw=0.25)
        ax.text(cx + R_BOARD, cy - 4, "copy %d%s" % (k + 1, " (spare)" if k else ""), fontsize=7, color="0.4", ha="center")
    base.scale_bar(ax, 15, 12)
    pdf.savefig(fig); plt.close(fig)


def place_label(text, body, d, taken, order, fs=7.0):
    """Board-mm position for a part label that does not cover another body, a pad, a hole or an earlier label."""
    w, h = 0.36 * fs / 7 * 2.45 * len(text), 1.5 * fs / 7
    minx, miny, maxx, maxy = body.bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    cand = {"above": [(x, maxy + 0.4) for x in (cx - w / 2, minx, maxx - w)],
            "below": [(x, miny - 0.4 - h) for x in (cx - w / 2, minx, maxx - w)],
            "right": [(maxx + 0.6, y) for y in (cy - h / 2, miny, maxy - h)],
            "left": [(minx - 0.6 - w, y) for y in (cy - h / 2, miny, maxy - h)]}
    blockers = [pt["body"] for pt in d["parts"] if pt["body"] is not body and pt["kind"] != "esp32"] + \
               [base.pad_geom(p).buffer(0.2) for p in d["pads"]] + \
               [Point(x, y).buffer(HOLE_R + 0.4, 16) for x, y in d["holes"]] + taken
    inside = d["outline"].buffer(-0.5)
    for side in order:
        for x0, y0 in cand[side]:
            rect = box(x0, y0, x0 + w, y0 + h)
            if inside.contains(rect) and not any(rect.intersects(b) for b in blockers):
                taken.append(rect)
                return x0, y0
    # no free spot: take the one that covers the least of the other labels and parts
    best = min((c for side in order for c in cand[side]),
               key=lambda c: sum(box(c[0], c[1], c[0] + w, c[1] + h).intersection(b).area for b in blockers))
    taken.append(box(best[0], best[1], best[0] + w, best[1] + h))
    return best


COLORS = {"tb": "#2b8a3e", "hdr": "#2b8a3e", "fuse": "#1f6feb", "cap": "#7a3e00", "cer": "#7a3e00", "res": "#7a3e00",
          "mod": "#6741d9", "sw": "#1f6feb", "reg": "#e8590c", "esp32": "#0b7285", "jp": "#c92a2a"}


def parts_page(pdf, d, r):
    S = 2.0
    fig, ax = base.page(pdf, "ThermoX ONE BOARD: PARTS SIDE (top view, enlarged %g x)" % S, [
        "Parts go on this side, copper is underneath (grey). Square pad = pin 1 (+ on C1, IN+ on U2).",
        "Order: R1-R4 and C4 (they lie flat under the ESP32), M1 (dashed purple, under the ESP32), then the rest,",
        "the two 1x15 female headers for the ESP32 last. Plug the ESP32 in with its USB end at the board edge.",
        "M1: set it to 12 V and measure first. Stick it down with thin foam tape, USB-C at the edge, and run its 2 output",
        "wires (1 mm2) out under the ESP32 antenna end to the M1 + and - pads. M1 must be 7 mm tall or less.",
        "Arrows show where the wires go into the screw terminals.",
    ])
    ox, oy = 105 - S * R_BOARD, 128 - S * R_BOARD
    xs, ys = outline_xy(d, ox, oy, S)
    ax.plot(xs, ys, color="black", lw=0.8)
    ax.add_patch(PathPatch(base.poly_path(r["copper"]).transformed(Affine2D().scale(S).translate(ox, oy)),
                           facecolor="0.88", edgecolor="none"))
    for hx, hy in d["holes"]:
        ax.add_patch(Circle((ox + S * hx, oy + S * hy), S * HOLE_R, facecolor="white", edgecolor="black", lw=0.6))
    taken = []

    def label(pt, text, color, fs=7.0, bold=True, order=("above", "below", "right", "left")):
        x0, y0 = place_label(text, pt["body"], d, taken, order, fs)
        ax.text(ox + S * x0, oy + S * y0, text, fontsize=fs, color=color, weight="bold" if bold else "normal",
                ha="left", va="bottom")

    def poly(geom, color, lw=1.0, ls="-", fc="none", alpha=1.0):
        for g in getattr(geom, "geoms", [geom]):
            bx, by = g.exterior.xy
            ax.add_patch(MplPolygon([(ox + S * x, oy + S * y) for x, y in zip(bx, by)], closed=True, facecolor=fc,
                                    edgecolor=color, lw=lw, ls=ls, alpha=alpha))

    order = sorted(d["parts"], key=lambda pt: {"mod": 0, "esp32": 1}.get(pt["kind"], 2))
    for pt in order:
        geom = pt["body"]
        color = COLORS[pt["kind"]]
        minx, miny, maxx, maxy = geom.bounds
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        if pt["kind"] == "esp32":
            poly(geom, color, lw=1.2, ls="--")
            poly(pt["antenna"], color, lw=0.6, fc=color, alpha=0.12)
            ax.text(ox + S * cx, oy + S * (pt["antenna"].bounds[1] + 3.5), "U1 ESP32 antenna end: no copper here",
                    ha="center", fontsize=6.5, color=color)
            continue
        if pt["kind"] == "jp":
            (x0, y0), (x1, y1) = pt["a"], pt["b"]
            ax.plot([ox + S * x0, ox + S * x1], [oy + S * y0, oy + S * y1], color=color, lw=1.6)
            ax.text(ox + S * (x0 + x1) / 2 + 2, oy + S * (y0 + y1) / 2, "%s wire link (3.3 V)" % pt["ref"], fontsize=6,
                    color=color, rotation=90, va="center")
            continue
        poly(geom, color, ls="--" if pt["kind"] in ("mod", "reg") else "-",
             fc=color if pt["kind"] == "mod" else "none", alpha=0.08 if pt["kind"] == "mod" else 1.0)
        if pt["kind"] == "mod":
            poly(geom, color, ls="--")
            ax.text(ox + S * cx, oy + S * (cy + 4), "M1 USB-C PD\nTRIGGER BOARD\n(under the ESP32;\nboth USB ports\nat this edge)", fontsize=6.5,
                    color=color, ha="center", va="center", weight="bold", linespacing=1.4)
            w, dep = 9.0, 7.0
            x0, y0 = cx - w / 2, miny
            ax.add_patch(Rectangle((ox + S * x0, oy + S * y0), S * w, S * dep, facecolor="white", edgecolor=color, lw=0.8))
            ax.text(ox + S * cx, oy + S * (y0 + dep / 2), "USB-C", fontsize=6, color=color, ha="center", va="center")
            (px, py), (qx, qy) = pt["plus"], pt["minus"]
            out = box(min(px, qx) - 1.7, min(py, qy) - 1.7, max(px, qx) + 1.7, max(py, qy) + 1.7)
            label(dict(body=out), "M1 OUT", color, fs=6.0, order=("below", "above", "right", "left"))
        elif pt["kind"] == "tb":
            e = pt["entry"]
            ax_, ay = {"left": (minx, cy), "right": (maxx, cy), "bottom": (cx, miny), "top": (cx, maxy)}[e]
            dx, dy = {"left": (-4, 0), "right": (4, 0), "bottom": (0, -4), "top": (0, 4)}[e]
            ax.annotate("", xy=(ox + S * ax_, oy + S * ay), xytext=(ox + S * (ax_ + dx), oy + S * (ay + dy)),
                        arrowprops=dict(arrowstyle="->", color=color, lw=1.2))
            wire_side = {"left": "left", "right": "right", "bottom": "below", "top": "above"}[e]
            if pt["ref"] == "U2":       # no room around it: name inside the body, along its left side
                ax.text(ox + S * (minx + 1.2), oy + S * cy, "U2  LM2596 5V", fontsize=6.5, color=color, weight="bold",
                        rotation=90, ha="center", va="center")
                continue
            label(pt, "%s %s" % (pt["ref"], pt["label"]), color,
                  order=tuple(sd for sd in ("above", "below", "right", "left") if sd != wire_side) + (wire_side,))
        elif pt["kind"] == "hdr":
            label(pt, "%s %s" % (pt["ref"], pt["label"]), color, fs=6.0, order=("left", "right", "above", "below"))
        elif pt["kind"] == "fuse":
            rot = 90 if maxy - miny > maxx - minx else 0
            ax.text(ox + S * cx, oy + S * cy, "F1  fuse holder 5x20 mm\nfuse 10 A slow-blow", fontsize=6.5, color=color,
                    ha="center", va="center", rotation=rot, linespacing=1.5)
        elif pt["kind"] == "sw":
            label(pt, "SW1 ON-OFF-ON", color, fs=6.5)
        elif pt["kind"] in ("cap", "cer", "res"):
            label(pt, "%s %s" % (pt["ref"], pt["label"]), color, fs=6.0 if pt["ref"] != "C1" else 6.5, bold=False)
            if pt["ref"] == "C1":
                for (x, y), s in ((pt["plus"], "+"), (pt["minus"], "-")):
                    ax.text(ox + S * (x + 2.0), oy + S * y, s, fontsize=9, color=color, va="center", weight="bold")
    for p in d["pads"]:
        x, y = ox + S * p["x"], oy + S * p["y"]
        rr = S * p["d"] / 2
        if p["square"]:
            ax.add_patch(Rectangle((x - rr, y - rr), 2 * rr, 2 * rr, facecolor="white", edgecolor="black", lw=0.6))
        else:
            ax.add_patch(Circle((x, y), rr, facecolor="white", edgecolor="black", lw=0.6))
        if p["ref"].startswith("J") or p["ref"] in ("SW1", "U2", "M1"):
            fs = {"SW1": 5.0, "M1": 7.0}.get(p["ref"], 4.0 if p["ref"].startswith("J") and p["d"] < 2 else 4.6)
            ax.text(x, y, p["pin"], fontsize=fs, ha="center", va="center", color="black",
                    weight="bold" if p["ref"] == "M1" else "normal")
        elif p["ref"] == "U1" and not p["net"].startswith("NC"):
            left = abs(p["x"] - LX) < 0.01
            ax.text(x + (-S * 1.3 if left else S * 1.3), y, p["pin"].replace("IO", ""), fontsize=3.8, color="#0b7285",
                    ha="right" if left else "left", va="center")
    pdf.savefig(fig); plt.close(fig)


WIRING = [
    ("J1 BATTERY", "BAT+: battery + after the BMS (P+). BAT-: battery - (BMS P-)."),
    ("J2 BTS7960", "B+ and B- to the BTS7960 power terminals (1.5 mm2 wire). M+/M- of the BTS7960 go to the Peltier."),
    ("J3 FAN", "SUNON fan: PWM blue, +12V red, GND black, FG yellow (tach)."),
    ("J4 OLED", "1.5\" SH1107 OLED: SCL, GND, SDA, VCC (3.3 V). Match the names on the OLED."),
    ("J5 / J6", "Button 1 (DOWN) / Button 2 (UP): one leg to B1/B2, the other to GND."),
    ("J7 BTS A", "BTS7960 control: R_EN, RPWM, LPWM."),
    ("J8 BTS B", "BTS7960 control: L_EN, GND, VCC (5 V logic). R_IS and L_IS stay open."),
    ("J9 TEMP", "DS18B20: DQ yellow, GND black, 5V red (R2 4.7k pulls DQ up to 3.3 V)."),
    ("U2 LM2596 5V", "LM2596S buck module (24V/12V to 5V): IN+ to module IN+, GND to IN- (and OUT-), OUT+ to module OUT+. "
                     "The module goes beside the board (foam tape); use 0.5 mm2 wires, 10-15 cm max."),
    ("M1 (on board)", "USB-C PD trigger board under the ESP32, USB-C at the board edge. Output + / - to the M1 pads."),
    ("SW1 (on board)", "ON-OFF-ON: BATT = battery, middle = off, USB = trigger board. Holes also take 3 wires to a case switch."),
]
NOTES = [
    "Only ONE source at a time: SW1 picks battery or USB-C. Never connect the trigger board straight to the battery.",
    "Set the trigger board to 12 V and measure it BEFORE fitting it. Never 15 V or 20 V. On USB-C keep the Peltier at",
    "60 % (12V 5A charger) or 40 % (12V 3A) with the phone page slider.",
    "SW1 (MTS-103) is rated 6 A: on battery keep the Peltier at 80 % or less, or use a 10 A toggle on wires.",
    "Battery gauge: R3 100k / R4 22k on GPIO35. ThermoX.ino already has BATT_CELLS = 3 and BATT_DIVIDER = 5.545; to show",
    "battery % set ENABLE_BATTERY_SENSE = true. On USB-C power it shows the USB voltage, not the battery.",
    "Fan tach (FG) is on GPIO34 as before. All other pins are the same as the firmware.",
    "LM2596S module: if it has a trimmer, set it to 5.0 V with a meter BEFORE wiring it to U2. Never more than 5.2 V.",
    "Before the ESP32 goes in: check that BAT+, PD+, COM, BUS, 5V and 3V3 are not shorted to GND. Switch on BATT and",
    "measure 5.0 V between the ESP32 socket VIN and GND pins. Only then plug in the ESP32.",
]
BOM = [
    "U1: ESP32 DevKit 30-pin + two 1x15 female headers (8.5 mm tall)    M1: USB-C PD/QC trigger board, max 32 x 16 x 7 mm",
    "U2: LM2596S 5 V buck module (you have it) + 3 wires 0.5 mm2, or a 3-pin screw terminal 5.08 mm (KF301-3P)",
    "SW1: MTS-103 ON-OFF-ON    F1: BLX-A 5x20 holder + 10 A slow-blow fuse    C1: 2200 uF 25 V low ESR, max 13 mm",
    "R1 10k, R2 4.7k, R3 100k, R4 22k (1/4 W)    C4: 100 nF ceramic    J1, J2: 2-pin screw terminal 5.08 mm (KF301)",
    "J3 4-pin, J4 4-pin, J5/J6 2-pin, J7 3-pin, J8 3-pin, J9 3-pin male headers 2.54 mm    M3 screws: 3",
]


def wiring_page(pdf, d, r):
    import textwrap
    lines = ["CONNECTIONS"]
    for k, v in WIRING:
        for j, ln in enumerate(textwrap.wrap(v, 86)):
            lines.append("  %-16s %s" % (k if j == 0 else "", ln))
    lines += ["", "IMPORTANT"] + ["  " + n for n in NOTES] + ["", "PARTS"] + ["  " + b for b in BOM] + [
        "", "DESIGN CHECK (run by make_thermox_pcb.py)",
        "  clearance >= %.1f mm between nets, all nets connected, no copper under the ESP32 antenna, ground path for" % CLEAR,
        "  the Peltier current >= %.1f mm wide, no part bodies overlapping: %s" % (GND_WIDE, "OK" if not r["errors"] else "FAILED")]
    fig, ax = base.page(pdf, "ThermoX ONE BOARD: WIRING, PARTS, NOTES", [])
    for k, ln in enumerate(lines):
        ax.text(10, 272 - 4.5 * k, ln, fontsize=6.4, va="top", family="monospace", weight="bold" if ln.isupper() and ln else "normal")
    pdf.savefig(fig); plt.close(fig)


def main():
    ok = True
    for spacing in (25.4, 22.86):
        d = design(spacing)
        r = check(d)
        tag = "%.2f" % spacing if spacing != 25.4 else "25.4"
        if r["errors"]:
            ok = False
            print("rows", tag, "FAILED:", *r["errors"], sep="\n  ")
            continue
        path = os.path.join(OUT, "thermox_onepcb_round82_rows%s.pdf" % tag)
        with PdfPages(path) as pdf:
            copper_page(pdf, d, r)
            parts_page(pdf, d, r)
            wiring_page(pdf, d, r)
        print("rows", tag, "OK ->", os.path.basename(path))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
