#!/usr/bin/env python3
"""ThermoX power board: battery or USB-C PD (12 V) input, source switch, fuse, bulk capacitor and 5 V regulator.

The USB-C trigger board, the switch and the 5 V regulator all sit on this board. Only the battery, the BTS7960 and
the controller board are wired to it. Single-sided, through-hole, for home etching. Made as a 60 x 60 mm square and
a 60 mm round board with the same circuit. Each run rebuilds both PDFs and checks them; it stops with an error if a
check fails:
  - copper of different nets at least CLEAR mm apart, ground fill POUR_CLEAR mm from other nets
  - every net in one piece, every GND pad on the one ground area
  - the ground path for the Peltier current (battery -, trigger board -, BTS7960 B-, C1 -) is at least GND_WIDE mm wide
  - part bodies do not overlap each other or the mounting holes, stay on the board and cover no other part's pads

Run:  python3 make_power_pcb.py        (needs: pip install shapely matplotlib)
"""
import os
import sys

from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

import make_pcb as base     # drawing helpers shared with the controller board

OUT = os.path.dirname(os.path.abspath(__file__))
CLEAR = 0.6          # mm, copper gap between different nets
POUR_CLEAR = 1.0     # mm, gap between the ground fill and other nets
EDGE_CLEAR = 0.6     # mm, copper kept away from the board edge
GND_WIDE = 3.2       # mm, narrowest ground path allowed for the Peltier return current
W_HI, W_C, W_LO, W_LED = 4.0, 2.0, 1.2, 0.8     # trace widths, mm
TB = (3.0, 1.3)      # 5.08 mm screw terminal pad (diameter, drill)
FUSE = (3.4, 1.5)    # 5x20 mm PCB fuse holder (BLX-A type), pins 22.6 mm apart
WIRE = (3.4, 1.5)    # trigger board output wire (1 mm2)
SWP = (4.0, 2.2)     # mini toggle switch lug (MTS-103 type), lugs 4.7 mm apart
HDR = (1.9, 1.0)     # 2.54 mm header, regulator pins
SMALL = (1.9, 0.8)   # resistor, LED, C2, C3
CAP = (2.2, 1.0)     # C1 radial electrolytic
HOLE_R = 1.6         # M3 mounting hole
MARKER = "THERMOX PWR"   # mirrored text cut into the ground fill, reads correctly on the etched board


def design(shape):
    """Pads, traces, part bodies and holes. Coordinates: top (parts) side view, mm, origin bottom-left."""
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
        if len(set(xs)) == 1:                       # vertical row of pins
            body = box(xs[0] - 3.8, min(ys) - 2.46, xs[0] + 3.8, max(ys) + 2.46)
        else:
            body = box(min(xs) - 2.46, ys[0] - 3.8, max(xs) + 2.46, ys[0] + 3.8)
        parts.append(dict(ref=ref, kind="tb", label=label, body=body, entry=entry, pins=pins))

    def header(ref, label, pins):
        for k, (x, y, name, net) in enumerate(pins):
            pad(x, y, net, ref, name, HDR, square=(k == 0))
        xs = [p[0] for p in pins]; ys = [p[1] for p in pins]
        parts.append(dict(ref=ref, kind="hdr", label=label, pins=pins,
                          body=box(min(xs) - 1.27, min(ys) - 1.27, max(xs) + 1.27, max(ys) + 1.27)))

    def module(rect, usb, plus, minus):
        """M1, the USB-C PD trigger board: stuck on the area rect (x0, y0, x1, y1) with its USB-C end on side usb,
        its output wired to the pads plus and minus."""
        pad(plus[0], plus[1], "PD+", "M1", "+", WIRE, square=True); pad(minus[0], minus[1], "GND", "M1", "-", WIRE)
        parts.append(dict(ref="M1", kind="mod", label="USB-C PD TRIGGER", body=box(*rect), usb=usb, plus=plus,
                          minus=minus))

    def switch(pins):
        """SW1, ON-OFF-ON mini toggle switch (MTS-103 type): 3 lugs 4.7 mm apart, body 13 x 8 mm."""
        for x, y, name, net in pins:
            pad(x, y, net, "SW1", name, SWP)
        xs = [p[0] for p in pins]; ys = [p[1] for p in pins]
        cx, cy = xs[1], ys[1]
        body = box(cx - 4.0, cy - 6.5, cx + 4.0, cy + 6.5) if len(set(xs)) == 1 else box(cx - 6.5, cy - 4.0, cx + 6.5, cy + 4.0)
        parts.append(dict(ref="SW1", kind="sw", label="ON-OFF-ON", body=body, pins=pins))

    def regulator(pins):
        """U1, 3-pin 5 V switching regulator (K7805-1000R3 / R-78E5.0-1.0, same pins as a 7805): pins = IN, GND, 5V,
        2.54 mm apart. Body 11.6 x 8.5 mm, the pin row 2.0 mm from one face; the area kept free is 6.5 mm on both
        sides of the pins, so any of these modules fits."""
        for k, (x, y, name, net) in enumerate(pins):
            pad(x, y, net, "U1", name, HDR, square=(k == 0))
        cx, cy = pins[1][0], pins[1][1]
        body = box(cx - 5.8, cy - 6.5, cx + 5.8, cy + 6.5) if pins[0][1] == pins[2][1] else box(cx - 6.5, cy - 5.8, cx + 6.5, cy + 5.8)
        parts.append(dict(ref="U1", kind="reg", label="5V 1A", body=body, pins=pins))

    def fuse(a, b):
        """F1 fuse holder, COM at a and BUS at b."""
        assert abs(Point(a).distance(Point(b)) - 22.6) < 1e-6
        pad(a[0], a[1], "COM", "F1", "1", FUSE); pad(b[0], b[1], "BUS", "F1", "2", FUSE)
        cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        body = box(cx - 16.3, cy - 5.0, cx + 16.3, cy + 5.0) if a[1] == b[1] else box(cx - 5.0, cy - 16.3, cx + 5.0, cy + 16.3)
        parts.append(dict(ref="F1", kind="fuse", label="10A", body=body, a=a, b=b))

    def cap(ref, label, plus, minus, net, r, size):
        pad(plus[0], plus[1], net, ref, "+", size, square=True); pad(minus[0], minus[1], "GND", ref, "-", size)
        cx, cy = (plus[0] + minus[0]) / 2, (plus[1] + minus[1]) / 2
        parts.append(dict(ref=ref, kind="cap", label=label, body=Point(cx, cy).buffer(r, 64), plus=plus, minus=minus))

    def led(anode, cathode):
        pad(anode[0], anode[1], "LEDA", "LED1", "A", SMALL, square=True); pad(cathode[0], cathode[1], "GND", "LED1", "K", SMALL)
        cx, cy = (anode[0] + cathode[0]) / 2, (anode[1] + cathode[1]) / 2
        parts.append(dict(ref="LED1", kind="led", label="ON", body=Point(cx, cy).buffer(2.9, 32), a=anode, k=cathode))

    def res(a, b):
        """R1 lying flat, a = LED side, b = BUS side, 10.16 mm apart."""
        pad(a[0], a[1], "LEDA", "R1", "1", SMALL); pad(b[0], b[1], "BUS", "R1", "2", SMALL)
        cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        body = box(cx - 3.3, cy - 1.25, cx + 3.3, cy + 1.25) if a[1] == b[1] else box(cx - 1.25, cy - 3.3, cx + 1.25, cy + 3.3)
        parts.append(dict(ref="R1", kind="res", label="2.2k", body=body, a=a, b=b))

    if shape == "square":
        outline = box(0, 0, 60, 60)
        module((0.5, 43.0, 32.5, 59.0), "left", (35.0, 47.0), (35.0, 52.0))
        switch([(7, 25.0, "BATT", "BAT+"), (7, 29.7, "COM", "COM"), (7, 34.4, "USB", "PD+")])
        terminal("J1", "BATTERY", [(7, 15.0, "BAT+", "BAT+"), (7, 9.92, "BAT-", "GND")], "left")
        fuse((17.5, 29.7), (40.1, 29.7))
        terminal("J4", "BTS7960", [(53, 29.7, "B+", "BUS"), (53, 34.78, "B-", "GND")], "right")
        cap("C1", "2200uF 25V", (45.0, 41.5), (45.0, 46.5), "BUS", 6.5, CAP)
        regulator([(40.1, 14.0, "IN", "BUS"), (37.56, 14.0, "GND", "GND"), (35.02, 14.0, "5V", "5V")])
        cap("C2", "10uF", (47.0, 14.0), (47.0, 11.46), "BUS", 2.75, SMALL)
        cap("C3", "22uF", (28.5, 14.0), (28.5, 11.46), "5V", 2.75, SMALL)
        header("J7", "TO CONTROLLER J7", [(50.0, 5.5, "VBAT", "BUS"), (47.46, 5.5, "5V", "5V"), (44.92, 5.5, "GND", "GND")])
        res((50.26, 22.0), (40.1, 22.0))
        led((53.5, 22.0), (56.04, 22.0))
        tr("BAT+", W_HI, (7, 15.0), (7, 25.0))
        tr("COM", W_HI, (7, 29.7), (17.5, 29.7))
        tr("PD+", W_HI, (35.0, 47.0), (14.0, 47.0), (9.5, 42.5), (9.5, 38.5), (7, 36.0), (7, 34.4))
        tr("BUS", W_HI, (40.1, 29.7), (53, 29.7))
        tr("BUS", W_C, (45.0, 41.5), (45.0, 29.7))
        tr("BUS", W_LO, (40.1, 29.7), (40.1, 14.0), (47.0, 14.0), (50.0, 14.0), (50.0, 5.5))
        tr("5V", W_LO, (35.02, 14.0), (28.5, 14.0))
        tr("5V", W_LO, (35.02, 14.0), (35.02, 8.5), (47.46, 8.5), (47.46, 5.5))
        tr("LEDA", W_LED, (50.26, 22.0), (53.5, 22.0))
        holes = [(3.5, 3.5), (56.5, 3.5), (56.5, 56.5), (3.5, 40.0)]
        marker = (17.0, 55.0)
    else:
        outline = Point(30, 30).buffer(30, 256)
        module((2.0, 22.0, 34.0, 38.0), "left", (32.0, 41.0), (26.0, 41.0))
        switch([(39.5, 34.7, "USB", "PD+"), (39.5, 30.0, "COM", "COM"), (39.5, 25.3, "BATT", "BAT+")])
        fuse((49.5, 18.7), (49.5, 41.3))
        terminal("J1", "BATTERY", [(39.5, 10.0, "BAT+", "BAT+"), (34.42, 10.0, "BAT-", "GND")], "bottom")
        cap("C1", "2200uF 25V", (38.5, 51.5), (38.5, 46.5), "BUS", 6.5, CAP)
        terminal("J4", "BTS7960", [(28.54, 50.5, "B+", "BUS"), (23.46, 50.5, "B-", "GND")], "top")
        regulator([(14.0, 15.0, "IN", "BUS"), (16.54, 15.0, "GND", "GND"), (19.08, 15.0, "5V", "5V")])
        cap("C2", "10uF", (7.5, 17.5), (7.5, 14.96), "BUS", 2.75, SMALL)
        cap("C3", "22uF", (25.2, 15.0), (25.2, 12.46), "5V", 2.75, SMALL)
        header("J7", "TO CONTROLLER J7", [(20.0, 6.5, "VBAT", "BUS"), (22.54, 6.5, "5V", "5V"), (25.08, 6.5, "GND", "GND")])
        res((20.16, 41.0), (10.0, 41.0))
        led((17.5, 46.0), (14.96, 46.0))
        tr("PD+", W_HI, (32.0, 41.0), (35.5, 41.0), (39.5, 37.0), (39.5, 34.7))
        tr("COM", W_HI, (39.5, 30.0), (45.0, 30.0), (49.5, 25.5), (49.5, 18.7))
        tr("BAT+", W_HI, (39.5, 10.0), (39.5, 25.3))
        tr("BUS", W_HI, (49.5, 41.3), (49.5, 44.5), (44.0, 50.0), (40.0, 51.5), (38.5, 51.5))
        tr("BUS", W_HI, (38.5, 51.5), (28.54, 50.5))
        tr("BUS", W_LO, (28.54, 50.5), (25.8, 53.5), (17.0, 53.5), (10.0, 46.5), (10.0, 19.0), (14.0, 15.0))
        tr("BUS", W_LO, (10.0, 19.0), (7.5, 17.5))
        tr("BUS", W_LO, (14.0, 15.0), (14.0, 9.5), (17.0, 6.5), (20.0, 6.5))
        tr("5V", W_LO, (19.08, 15.0), (25.2, 15.0))
        tr("5V", W_LO, (19.08, 15.0), (19.08, 12.0), (22.54, 8.5), (22.54, 6.5))
        tr("LEDA", W_LED, (20.16, 41.0), (20.16, 43.5), (17.5, 46.0))
        holes = [(30.0, 57.0), (47.0, 8.0), (6.0, 44.0)]
        marker = (21.0, 30.0)
    return dict(shape=shape, outline=outline, pads=pads, traces=traces, parts=parts, holes=holes, marker=marker)


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
        if n != "GND" and g.geom_type != "Polygon":
            errors.append("net %s is not connected (%d pieces)" % (n, len(g.geoms)))
    # part bodies: no overlaps, on the board, clear of the holes and of other parts' pads
    holes = [Point(x, y).buffer(HOLE_R + 0.3, 32) for x, y in d["holes"]]
    for i, a in enumerate(d["parts"]):
        if not d["outline"].buffer(0.01).contains(a["body"]):
            errors.append("%s body sticks out of the board" % a["ref"])
        for h in holes:
            if a["body"].intersects(h):
                errors.append("%s body hits a mounting hole" % a["ref"])
        for b in d["parts"][i + 1:]:
            if a["body"].intersection(b["body"]).area > 0.01:
                errors.append("%s and %s bodies overlap" % (a["ref"], b["ref"]))
        for p in d["pads"]:
            if p["ref"] != a["ref"] and a["body"].intersects(base.pad_geom(p)):
                errors.append("%s pad %s is under the %s body" % (p["ref"], p["pin"], a["ref"]))
    # ground fill
    others = unary_union([g for n, g in net_geom.items() if n != "GND"]).buffer(POUR_CLEAR, 16)
    fill = inner.difference(others).difference(keep)
    fill = fill.buffer(-0.35, 8).buffer(0.35, 8)
    gnd = unary_union([fill, net_geom["GND"]])
    parts_ = list(gnd.geoms) if gnd.geom_type == "MultiPolygon" else [gnd]
    gnd_pads = [p for p in d["pads"] if p["net"] == "GND"]
    main = [g for g in parts_ if any(g.intersects(base.pad_geom(p)) for p in gnd_pads)]
    if len(main) != 1:
        errors.append("ground is in %d separate pieces that hold GND pads" % len(main))
    gnd_main = main[0] if main else gnd
    for p in gnd_pads:
        if not gnd_main.intersects(base.pad_geom(p)):
            errors.append("GND pad %s.%s not reached by the ground" % (p["ref"], p["pin"]))
    # wide ground path for the Peltier current: open the ground by GND_WIDE and see that one piece still
    # reaches battery -, trigger board -, BTS7960 B- and C1 -
    wide = gnd_main.buffer(-GND_WIDE / 2, 16).buffer(GND_WIDE / 2, 16)
    pieces = list(wide.geoms) if wide.geom_type == "MultiPolygon" else [wide]
    key = [p for p in gnd_pads if (p["ref"], p["pin"]) in (("J1", "BAT-"), ("M1", "-"), ("J4", "B-"), ("C1", "-"))]
    shared = None
    for p in key:
        near = {i for i, g in enumerate(pieces) if g.distance(base.pad_geom(p)) < 0.6}
        shared = near if shared is None else shared & near
    if not shared:
        errors.append("ground path for the Peltier current is narrower than %.1f mm somewhere" % GND_WIDE)
    from matplotlib.textpath import TextPath
    from matplotlib.transforms import Affine2D as _A
    from shapely.geometry import MultiPoint
    mx, my = d["marker"]
    tv = TextPath((0, 0), MARKER, size=2.0).transformed(_A().scale(-1, 1).translate(mx + 8.5, my - 0.7)).vertices
    if not gnd_main.buffer(-0.3).contains(MultiPoint([tuple(v) for v in tv])):
        errors.append("marker text is not fully on the ground fill")
    copper = unary_union([gnd_main] + [g for n, g in net_geom.items() if n != "GND"])
    return dict(copper=copper, errors=errors, net_geom=net_geom)


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
    name = "60 x 60 mm square" if d["shape"] == "square" else "60 mm round"
    fig, ax = base.page(pdf, "ThermoX POWER BOARD: COPPER (%s)" % name, [
        "Print at 100 % / Actual size (no 'fit to page'). Check the 50 mm bar with a ruler.",
        "Toner transfer or UV film: use this page as it is (do not mirror). Copper is on the bottom of the board.",
        "Check: the small text 'THERMOX PWR' looks mirrored on the paper and reads normally on the etched copper side.",
        "Drill: 2.2 mm SW1, 1.5 mm F1 and M1 wire pads, 1.3 mm screw terminals, 1.0 mm C1, U1 and J7,",
        "0.8 mm R1, LED1, C2 and C3, 3.2 mm mounting holes.",
        "The wide tracks carry up to 7 A: cover them with a layer of solder after etching.",
    ])
    for k, cx in enumerate((25.0, 125.0)):
        cy = 120.0
        ax.add_patch(PathPatch(base.poly_path(r["copper"]).transformed(Affine2D().translate(cx, cy)), facecolor="black",
                               edgecolor="none"))
        mx, my = d["marker"]
        tp = TextPath((0, 0), MARKER, size=2.0)
        ax.add_patch(PathPatch(tp.transformed(Affine2D().scale(-1, 1).translate(cx + mx + 8.5, cy + my - 0.7)),
                               facecolor="white", edgecolor="none"))
        for p in d["pads"]:
            ax.add_patch(Circle((cx + p["x"], cy + p["y"]), 0.3, color="white"))
        for hx, hy in d["holes"]:
            ax.add_patch(Circle((cx + hx, cy + hy), HOLE_R, facecolor="none", edgecolor="black", lw=0.3))
            ax.add_patch(Circle((cx + hx, cy + hy), 0.3, color="black"))
        xs, ys = outline_xy(d, cx, cy)
        ax.plot(xs, ys, color="black", lw=0.25)
        ax.text(cx + 30, cy - 4, "copy %d%s" % (k + 1, " (spare)" if k else ""), fontsize=7, color="0.4", ha="center")
    base.scale_bar(ax, 15, 12)
    pdf.savefig(fig); plt.close(fig)


def place_label(text, body, d, taken, order, fs=7.0):
    """Board-mm position for a part label that does not cover another body, a pad, a hole or an earlier label.
    Each side in order is tried centred on the body first, then lined up with either end of it."""
    w, h = 0.36 * fs / 7 * 2.1 * len(text), 1.5 * fs / 7
    minx, miny, maxx, maxy = body.bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    cand = {"above": [(x, maxy + 0.4) for x in (cx - w / 2, minx, maxx - w)],
            "below": [(x, miny - 0.4 - h) for x in (cx - w / 2, minx, maxx - w)],
            "right": [(maxx + 0.6, y) for y in (cy - h / 2, miny, maxy - h)],
            "left": [(minx - 0.6 - w, y) for y in (cy - h / 2, miny, maxy - h)]}
    blockers = [pt["body"] for pt in d["parts"] if pt["body"] is not body] + \
               [base.pad_geom(p).buffer(0.2) for p in d["pads"]] + \
               [Point(x, y).buffer(HOLE_R + 0.4, 16) for x, y in d["holes"]] + taken
    for side in order:
        for x0, y0 in cand[side]:
            rect = box(x0, y0, x0 + w, y0 + h)
            if not any(rect.intersects(b) for b in blockers):
                taken.append(rect)
                return x0, y0
    x0, y0 = cand[order[0]][0]
    taken.append(box(x0, y0, x0 + w, y0 + h))
    return x0, y0


COLORS = {"tb": "#2b8a3e", "hdr": "#2b8a3e", "fuse": "#1f6feb", "cap": "#7a3e00", "led": "#c92a2a", "res": "#7a3e00",
          "mod": "#6741d9", "sw": "#1f6feb", "reg": "#e8590c"}


def parts_page(pdf, d, r):
    S = 2.0
    fig, ax = base.page(pdf, "ThermoX POWER BOARD: PARTS SIDE (top view, enlarged %g x)" % S, [
        "Parts go on this side, copper is underneath (grey). Square pad = pin 1 (+ on C1-C3, anode on LED1, IN on U1).",
        "M1: stick the trigger board on the dashed area with thick double-sided foam tape, USB-C at the board edge. Set it",
        "to 12 V and measure it first, then solder 2 short 1 mm2 wires from its output + and - to the M1 + and - pads.",
        "SW1: the 3 lugs go through the big holes (or 3 wires to a switch on the case). U1: pin 1 (IN) in the square pad.",
        "Arrows show where the wires go into the screw terminals. C1: the stripe (-) of the capacitor towards the '-' pad.",
    ])
    ox, oy = 105 - S * 30, 145 - S * 30
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

    for pt in d["parts"]:
        geom = pt["body"]
        bx, by = geom.exterior.xy
        color = COLORS[pt["kind"]]
        ax.add_patch(MplPolygon([(ox + S * x, oy + S * y) for x, y in zip(bx, by)], closed=True, facecolor="none",
                                edgecolor=color, lw=1.0, ls="--" if pt["kind"] in ("mod", "reg") else "-"))
        minx, miny, maxx, maxy = geom.bounds
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        if pt["kind"] == "tb":
            e = pt["entry"]
            ax_, ay = {"left": (minx, cy), "right": (maxx, cy), "bottom": (cx, miny), "top": (cx, maxy)}[e]
            dx, dy = {"left": (-4, 0), "right": (4, 0), "bottom": (0, -4), "top": (0, 4)}[e]
            ax.annotate("", xy=(ox + S * ax_, oy + S * ay), xytext=(ox + S * (ax_ + dx), oy + S * (ay + dy)),
                        arrowprops=dict(arrowstyle="->", color=color, lw=1.2))
            wire_side = {"left": "left", "right": "right", "bottom": "below", "top": "above"}[e]
            label(pt, "%s %s" % (pt["ref"], pt["label"]), color,
                  order=tuple(sd for sd in ("above", "below", "right", "left") if sd != wire_side) + (wire_side,))
        elif pt["kind"] == "hdr":
            label(pt, "%s %s" % (pt["ref"], pt["label"]), color, fs=6.5)
        elif pt["kind"] == "fuse":
            rot = 90 if maxy - miny > maxx - minx else 0
            ax.text(ox + S * cx, oy + S * cy, "F1  fuse holder 5x20 mm\nfuse 10 A slow-blow", fontsize=6.5, color=color,
                    ha="center", va="center", rotation=rot, linespacing=1.6)
        elif pt["kind"] == "mod":
            ax.add_patch(Rectangle((ox + S * minx, oy + S * miny), S * (maxx - minx), S * (maxy - miny),
                                   facecolor=color, alpha=0.06, edgecolor="none"))
            ax.text(ox + S * cx, oy + S * cy, "M1  USB-C PD TRIGGER BOARD\nset to 12 V, foam tape under it",
                    fontsize=6.8, color=color, ha="center", va="center", weight="bold", linespacing=1.5)
            # the USB-C socket of the trigger board (about 9 x 7 mm) at the board edge
            w, dep = 9.0, 7.0
            x0, y0, rw, rh = {"left": (minx, cy - w / 2, dep, w), "right": (maxx - dep, cy - w / 2, dep, w),
                              "bottom": (cx - w / 2, miny, w, dep), "top": (cx - w / 2, maxy - dep, w, dep)}[pt["usb"]]
            ax.add_patch(Rectangle((ox + S * x0, oy + S * y0), S * rw, S * rh, facecolor="white", edgecolor=color, lw=0.8))
            ax.text(ox + S * (x0 + rw / 2), oy + S * (y0 + rh / 2), "USB-C", fontsize=6, color=color, ha="center",
                    va="center", rotation=90 if pt["usb"] in ("left", "right") else 0)
            (px, py), (qx, qy) = pt["plus"], pt["minus"]
            out = box(min(px, qx) - 1.7, min(py, qy) - 1.7, max(px, qx) + 1.7, max(py, qy) + 1.7)
            label(dict(body=out), "M1 OUT", color, fs=6.0)
        elif pt["kind"] == "sw":
            label(pt, "SW1 ON-OFF-ON", color, fs=6.5)
        elif pt["kind"] == "reg":
            label(pt, "U1 5V 1A", color, fs=6.5)
        elif pt["kind"] == "cap":
            label(pt, "%s %s" % (pt["ref"], pt["label"]), color, fs=6.5 if pt["ref"] == "C1" else 6.0, bold=False)
            for (x, y), s in ((pt["plus"], "+"), (pt["minus"], "-")):
                if pt["ref"] == "C1":
                    ax.text(ox + S * (x + 2.0), oy + S * y, s, fontsize=9, color=color, va="center", weight="bold")
        elif pt["kind"] == "led":
            label(pt, "LED1 ON", color, fs=6.5, bold=False)
        elif pt["kind"] == "res":
            label(pt, "R1 2.2k", color, fs=6.5, bold=False)
    for p in d["pads"]:
        x, y = ox + S * p["x"], oy + S * p["y"]
        rr = S * p["d"] / 2
        if p["square"]:
            ax.add_patch(Rectangle((x - rr, y - rr), 2 * rr, 2 * rr, facecolor="white", edgecolor="black", lw=0.6))
        else:
            ax.add_patch(Circle((x, y), rr, facecolor="white", edgecolor="black", lw=0.6))
        if p["ref"].startswith("J") or p["ref"] in ("SW1", "U1", "M1"):
            fs = {"J7": 4.4, "U1": 4.2, "M1": 7.0}.get(p["ref"], 5.2)
            ax.text(x, y, p["pin"], fontsize=fs, ha="center", va="center", color="black",
                    weight="bold" if p["ref"] == "M1" else "normal")
    pdf.savefig(fig); plt.close(fig)


WIRING = [
    ("J1 BATTERY", "BAT+: battery + after the BMS (P+). BAT-: battery - (BMS P-)."),
    ("J4 BTS7960", "B+ and B- to the BTS7960 power terminals (thick wire, 1.5 mm2). M+/M- of the BTS7960 go to the Peltier."),
    ("J7 TO CONTROLLER", "VBAT, 5V, GND to J7 VBAT, 5V, GND on the controller board (pin 1 = VBAT on both, square pad)."),
    ("M1 (on board)", "USB-C PD trigger board. Output + to the M1 + pad, output - to the M1 - pad, short 1 mm2 wires. "
                      "Its USB-C end at the board edge; the charger plugs in there."),
    ("SW1 (on board)", "ON-OFF-ON toggle: BATT = battery, middle (off), USB = trigger board. COM is the middle lug."),
    ("U1 (on board)", "5 V for the ESP32 and the controller board. Replaces the LM2596 module."),
]
NOTES = [
    "Only ONE source at a time: SW1 picks battery or USB-C. Never connect the trigger board straight to the battery.",
    "The trigger board does not charge the battery; on USB-C the battery is just not used.",
    "Set the trigger board to 12 V and measure it with a meter BEFORE soldering its wires. Never 15 V or 20 V: the 12 V fan",
    "and the TEC1-12706 would be damaged. Peltier power on USB-C (phone page slider): 12V 5A charger -> 60 % max, 12V 3A -> 40 %.",
    "SW1 (MTS-103) is rated 6 A at 125 V AC: on battery keep the Peltier power at 80 % or less, or use a 10 A toggle on",
    "3 wires. Move the switch only when the Peltier is off (phone page: Stop) and wait in the middle position for 2 s.",
    "Fuse F1 (10 A slow-blow, 5x20 mm) protects both sources. C1 smooths the Peltier PWM so the charger does not cut out.",
    "U1 must be a switching type (K7805-1000R3, R-78E5.0-1.0). A plain LM7805 gets too hot here.",
    "Before the first power-up: check with a meter that BAT+, PD+, COM, BUS and 5V are not shorted to GND. Then, with SW1",
    "on BATT, LED1 lights, J7 VBAT reads the battery voltage and J7 5V reads 5.0 V. Only then plug in the controller.",
    "Cover the wide copper tracks with solder after etching (they carry up to 7 A).",
]
BOM = [
    "M1: USB-C PD/QC trigger board (100W 5A type, up to 32 x 16 mm) + double-sided foam tape + 2 x 3 cm of 1 mm2 wire",
    "SW1: ON-OFF-ON mini toggle switch, 3 lugs (MTS-103, 6 A), or a bigger 10 A ON-OFF-ON toggle on 3 wires",
    "U1: 5 V 1 A 3-pin switching regulator: K7805-1000R3 or R-78E5.0-1.0 (same pins as a 7805)",
    "C1: 2200 uF 25 V electrolytic, low ESR, up to 13 mm diameter, 5 mm lead spacing",
    "C2: 10 uF 50 V (ceramic or electrolytic, 5 mm)    C3: 22 uF 16 V (ceramic or low-ESR electrolytic, 5 mm)",
    "F1: 5x20 mm PCB fuse holder (BLX-A, pins 22.6 mm apart) + 10 A slow-blow fuse",
    "J1, J4: 2-pin screw terminal 5.08 mm (KF301-2P)    J7: 1x3 male header 2.54 mm + 3 dupont wires to the controller J7",
    "LED1: 3 or 5 mm LED,  R1: 2.2 kOhm 1/4 W,  M3 screws/standoffs: 4 (square) or 3 (round)",
]


def wiring_page(pdf, d, r):
    import textwrap
    lines = ["CONNECTIONS"]
    for k, v in WIRING:
        for j, ln in enumerate(textwrap.wrap(v, 84)):
            lines.append("  %-18s %s" % (k if j == 0 else "", ln))
    lines += ["", "IMPORTANT"] + ["  " + n for n in NOTES] + ["", "PARTS"] + ["  " + b for b in BOM] + [
        "", "DESIGN CHECK (run by make_power_pcb.py)",
        "  clearance >= %.1f mm between nets, ground fill %.1f mm from other nets, all nets connected," % (CLEAR, POUR_CLEAR),
        "  ground path for the Peltier current >= %.1f mm wide, no part bodies overlapping: %s"
        % (GND_WIDE, "OK" if not r["errors"] else "FAILED")]
    fig, ax = base.page(pdf, "ThermoX POWER BOARD: WIRING, PARTS, NOTES", [])
    for k, ln in enumerate(lines):
        ax.text(12, 272 - 4.6 * k, ln, fontsize=6.8, va="top", family="monospace", weight="bold" if ln.isupper() and ln else "normal")
    # block diagram: the dashed box is the power board
    y0 = 40
    ax.text(12, y0 + 30, "HOW IT CONNECTS (dashed = on this board)", fontsize=7.5, weight="bold", family="monospace")
    ax.add_patch(Rectangle((48, y0 - 7), 90, 31, facecolor="none", edgecolor="0.5", lw=0.7, ls="--"))
    boxes = [(12, y0 + 12, "3S battery\n+ BMS", "J1"), (12, y0, "USB-C charger\n(PD 12 V)", ""),
             (52, y0, "M1 trigger\nboard 12 V", ""), (52, y0 + 12, "J1", ""), (90, y0 + 6, "SW1 -> F1 10A\n+ C1", ""),
             (90, y0 - 5, "U1 5 V", ""), (150, y0 + 14, "BTS7960 power\n-> Peltier", "J4"),
             (150, y0 - 5, "controller PCB J7", "J7")]
    for x, y, t, j in boxes:
        if t == "J1":
            continue
        ax.add_patch(Rectangle((x, y), 34, 8, facecolor="#f1f3f5", edgecolor="0.4", lw=0.6))
        ax.text(x + 17, y + 4, t, fontsize=6.3, ha="center", va="center")
        if j:
            ax.text(x + 17, y + 8.8, j, fontsize=6, ha="center", color="#2b8a3e", weight="bold")
    for (x0, y0_, x1, y1) in [(46, y0 + 16, 90, y0 + 10), (46, y0 + 4, 52, y0 + 4), (86, y0 + 4, 90, y0 + 10),
                              (124, y0 + 10, 150, y0 + 18), (107, y0 + 6, 107, y0 + 3), (124, y0 - 1, 150, y0 - 1)]:
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0_), arrowprops=dict(arrowstyle="->", color="0.3", lw=0.8))
    pdf.savefig(fig); plt.close(fig)


def main():
    ok = True
    for shape in ("square", "round"):
        d = design(shape)
        r = check(d)
        tag = "60x60" if shape == "square" else "round60"
        if r["errors"]:
            ok = False
            print(tag, "FAILED:", *r["errors"], sep="\n  ")
            continue
        path = os.path.join(OUT, "thermox_power_%s.pdf" % tag)
        with PdfPages(path) as pdf:
            copper_page(pdf, d, r)
            parts_page(pdf, d, r)
            wiring_page(pdf, d, r)
        print(tag, "OK ->", os.path.basename(path))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
