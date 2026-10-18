#!/usr/bin/env python3
"""ThermoX power board: battery or USB-C PD (12 V) input, source switch, fuse, bulk capacitor and outputs.

Single-sided, through-hole, for home etching. Made as a 60 x 60 mm square and a 60 mm round board with the same
circuit. Each run rebuilds both PDFs and checks them; it stops with an error if a check fails:
  - copper of different nets at least CLEAR mm apart, ground fill POUR_CLEAR mm from other nets
  - every net in one piece, every GND pad on the one ground area
  - the ground path for the Peltier current (battery -, USB-C -, BTS7960 B-, C1 -) is at least GND_WIDE mm wide
  - part bodies do not overlap each other or the mounting holes, and stay on the board

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
W_HI, W_C, W_MID, W_LO, W_LED = 4.0, 2.0, 1.5, 1.2, 0.8     # trace widths, mm
TB = (3.0, 1.3)      # 5.08 mm screw terminal pad (diameter, drill)
FUSE = (3.4, 1.5)    # 5x20 mm PCB fuse holder (BLX-A type), pins 22.6 mm apart
HDR = (1.9, 1.0)     # 2.54 mm header
SMALL = (1.9, 0.8)   # resistor, LED
CAP = (2.2, 1.0)     # radial electrolytic
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
        xs = [p[0] for p in pins]; y = pins[0][1]
        parts.append(dict(ref=ref, kind="hdr", label=label, body=box(min(xs) - 1.27, y - 1.27, max(xs) + 1.27, y + 1.27),
                          pins=pins))

    def fuse(a, b):
        pad(a[0], a[1], "COM", "F1", "1", FUSE); pad(b[0], b[1], "BUS", "F1", "2", FUSE)
        cx, cy = (a[0] + b[0]) / 2, a[1]
        parts.append(dict(ref="F1", kind="fuse", label="10A", body=box(cx - 16.3, cy - 5.0, cx + 16.3, cy + 5.0), a=a, b=b))

    def cap(plus, minus):
        pad(plus[0], plus[1], "BUS", "C1", "+", CAP, square=True); pad(minus[0], minus[1], "GND", "C1", "-", CAP)
        cx, cy = (plus[0] + minus[0]) / 2, (plus[1] + minus[1]) / 2
        parts.append(dict(ref="C1", kind="cap", label="2200uF 25V", body=Point(cx, cy).buffer(6.5, 64), plus=plus, minus=minus))

    def led(anode, cathode):
        pad(anode[0], anode[1], "LEDA", "LED1", "A", SMALL, square=True); pad(cathode[0], cathode[1], "GND", "LED1", "K", SMALL)
        cx, cy = (anode[0] + cathode[0]) / 2, (anode[1] + cathode[1]) / 2
        parts.append(dict(ref="LED1", kind="led", label="ON", body=Point(cx, cy).buffer(2.9, 32), a=anode, k=cathode))

    def res(a, b):
        pad(a[0], a[1], "LEDA", "R1", "1", SMALL); pad(b[0], b[1], "BUS", "R1", "2", SMALL)
        cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        parts.append(dict(ref="R1", kind="res", label="2.2k", body=box(cx - 3.3, cy - 1.25, cx + 3.3, cy + 1.25), a=a, b=b))

    if shape == "square":
        outline = box(0, 0, 60, 60)
        terminal("J1", "BATTERY", [(7, 14.0, "BAT+", "BAT+"), (7, 8.92, "BAT-", "GND")], "left")
        terminal("J2", "USB-C 12V", [(7, 45.92, "+12V", "PD+"), (7, 51.0, "GND", "GND")], "left")
        terminal("J3", "SWITCH", [(7, 25.84, "BATT", "BAT+"), (7, 30.92, "COM", "COM"), (7, 36.0, "USB", "PD+")], "left")
        fuse((17.0, 30.92), (39.6, 30.92))
        terminal("J4", "BTS7960", [(53, 30.92, "B+", "BUS"), (53, 36.0, "B-", "GND")], "right")
        cap((44.0, 41.0), (44.0, 46.0))
        terminal("J5", "LM2596", [(36.0, 7.0, "OUT+", "5V"), (41.08, 7.0, "GND", "GND"), (46.16, 7.0, "IN+", "BUS")], "bottom")
        header("J7", "TO CONTROLLER J7", [(18.0, 6.0, "VBAT", "BUS"), (20.54, 6.0, "5V", "5V"), (23.08, 6.0, "GND", "GND")])
        res((28.0, 48.5), (38.16, 48.5))
        led((25.0, 48.5), (22.46, 48.5))
        tr("PD+", W_HI, (7, 45.92), (7, 36.0))
        tr("BAT+", W_HI, (7, 14.0), (7, 25.84))
        tr("COM", W_HI, (7, 30.92), (17.0, 30.92))
        tr("BUS", W_HI, (39.6, 30.92), (53, 30.92))
        tr("BUS", W_C, (44.0, 41.0), (44.0, 30.92))
        tr("BUS", W_MID, (48.0, 30.92), (48.0, 10.0), (46.16, 7.0))
        tr("BUS", W_LO, (48.0, 20.0), (18.0, 20.0), (18.0, 6.0))
        tr("5V", W_LO, (36.0, 7.0), (30.0, 10.0), (20.54, 10.0), (20.54, 6.0))
        tr("BUS", W_LED, (38.16, 48.5), (41.5, 45.0), (44.0, 41.0))
        tr("LEDA", W_LED, (25.0, 48.5), (28.0, 48.5))
        holes = [(3.5, 56.5), (56.5, 56.5), (54.5, 14.0), (3.0, 3.0)]
        marker = (30.0, 55.2)
    else:
        outline = Point(30, 30).buffer(30, 256)
        terminal("J1", "BATTERY", [(27.46, 7.0, "BAT+", "BAT+"), (32.54, 7.0, "BAT-", "GND")], "bottom")
        terminal("J2", "USB-C 12V", [(27.46, 53.0, "+12V", "PD+"), (32.54, 53.0, "GND", "GND")], "top")
        terminal("J3", "SWITCH", [(7, 24.92, "BATT", "BAT+"), (7, 30.0, "COM", "COM"), (7, 35.08, "USB", "PD+")], "left")
        fuse((18.7, 30.0), (41.3, 30.0))
        terminal("J4", "BTS7960", [(53, 30.0, "B+", "BUS"), (53, 35.08, "B-", "GND")], "right")
        cap((44.0, 39.5), (44.0, 44.5))
        terminal("J5", "LM2596", [(47, 12.0, "GND", "GND"), (47, 17.08, "OUT+", "5V"), (47, 22.16, "IN+", "BUS")], "right")
        header("J7", "TO CONTROLLER J7", [(25.5, 14.0, "VBAT", "BUS"), (28.04, 14.0, "5V", "5V"), (30.58, 14.0, "GND", "GND")])
        res((24.0, 40.0), (34.16, 40.0))
        led((21.0, 40.0), (18.46, 40.0))
        tr("BAT+", W_HI, (27.46, 7.0), (7, 24.92))
        tr("PD+", W_HI, (27.46, 53.0), (7, 35.08))
        tr("COM", W_HI, (7, 30.0), (18.7, 30.0))
        tr("BUS", W_HI, (41.3, 30.0), (53, 30.0))
        tr("BUS", W_C, (44.0, 39.5), (44.0, 30.0))
        tr("BUS", W_MID, (42.5, 30.0), (42.5, 22.16), (47, 22.16))
        tr("BUS", W_LO, (42.5, 22.16), (42.5, 20.2), (25.5, 20.2), (25.5, 14.0))
        tr("5V", W_LO, (47, 17.08), (28.04, 17.08), (28.04, 14.0))
        tr("BUS", W_LED, (34.16, 40.0), (44.0, 39.5))
        tr("LEDA", W_LED, (21.0, 40.0), (24.0, 40.0))
        holes = [(12.5, 47.5), (12.5, 12.5), (48.5, 49.5)]
        marker = (30.0, 26.5)
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
    # part bodies: no overlaps, on the board, clear of the holes
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
    # reaches battery -, USB-C -, BTS7960 B- and C1 -
    wide = gnd_main.buffer(-GND_WIDE / 2, 16).buffer(GND_WIDE / 2, 16)
    pieces = list(wide.geoms) if wide.geom_type == "MultiPolygon" else [wide]
    key = [p for p in gnd_pads if (p["ref"], p["pin"]) in (("J1", "BAT-"), ("J2", "GND"), ("J4", "B-"), ("C1", "-"))]
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
        "Drill: 1.3 mm screw terminals, 1.5 mm fuse holder, 1.0 mm capacitor and J7 header, 0.8 mm R1/LED, 3.2 mm mounting holes.",
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
    """Board-mm position for a part label that does not cover another body, a hole or an earlier label."""
    w, h = 0.36 * fs / 7 * 2.1 * len(text), 1.5 * fs / 7
    minx, miny, maxx, maxy = body.bounds
    cx = (minx + maxx) / 2
    cand = {"above": (cx - w / 2, maxy + 0.4), "below": (cx - w / 2, miny - 0.4 - h),
            "right": (maxx + 0.6, (miny + maxy) / 2 - h / 2), "left": (minx - 0.6 - w, (miny + maxy) / 2 - h / 2)}
    blockers = [pt["body"] for pt in d["parts"] if pt["body"] is not body] + \
               [Point(x, y).buffer(HOLE_R + 0.4, 16) for x, y in d["holes"]] + taken
    for side in order:
        x0, y0 = cand[side]
        rect = box(x0, y0, x0 + w, y0 + h)
        if not any(rect.intersects(b) for b in blockers):
            taken.append(rect)
            return x0, y0
    x0, y0 = cand[order[0]]
    taken.append(box(x0, y0, x0 + w, y0 + h))
    return x0, y0


def parts_page(pdf, d, r):
    S = 2.0
    fig, ax = base.page(pdf, "ThermoX POWER BOARD: PARTS SIDE (top view, enlarged %g x)" % S, [
        "Parts go on this side, copper is underneath (grey). Square pad = pin 1 (and + on C1, anode on LED1).",
        "Arrows show where the wires go into the screw terminals. C1: the stripe (-) of the capacitor towards the '-' pad.",
    ])
    ox, oy = 105 - S * 30, 140 - S * 30
    xs, ys = outline_xy(d, ox, oy, S)
    ax.plot(xs, ys, color="black", lw=0.8)
    ax.add_patch(PathPatch(base.poly_path(r["copper"]).transformed(Affine2D().scale(S).translate(ox, oy)),
                           facecolor="0.88", edgecolor="none"))
    for hx, hy in d["holes"]:
        ax.add_patch(Circle((ox + S * hx, oy + S * hy), S * HOLE_R, facecolor="white", edgecolor="black", lw=0.6))
    green, brown = "#2b8a3e", "#7a3e00"
    taken = []

    def label(pt, text, color, fs=7.0, bold=True, order=("above", "below", "right", "left")):
        x0, y0 = place_label(text, pt["body"], d, taken, order, fs)
        ax.text(ox + S * x0, oy + S * y0, text, fontsize=fs, color=color, weight="bold" if bold else "normal",
                ha="left", va="bottom")

    for pt in d["parts"]:
        geom = pt["body"]
        bx, by = geom.exterior.xy
        color = {"tb": green, "hdr": green, "fuse": "#1f6feb", "cap": brown, "led": "#c92a2a", "res": brown}[pt["kind"]]
        ax.add_patch(MplPolygon([(ox + S * x, oy + S * y) for x, y in zip(bx, by)], closed=True, facecolor="none",
                                edgecolor=color, lw=1.0))
        minx, miny, maxx, maxy = geom.bounds
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        if pt["kind"] == "tb":
            e = pt["entry"]
            ax_, ay = {"left": (minx, cy), "right": (maxx, cy), "bottom": (cx, miny), "top": (cx, maxy)}[e]
            dx, dy = {"left": (-4, 0), "right": (4, 0), "bottom": (0, -4), "top": (0, 4)}[e]
            ax.annotate("", xy=(ox + S * ax_, oy + S * ay), xytext=(ox + S * (ax_ + dx), oy + S * (ay + dy)),
                        arrowprops=dict(arrowstyle="->", color=green, lw=1.2))
            wire_side = {"left": "left", "right": "right", "bottom": "below", "top": "above"}[e]
            label(pt, "%s %s" % (pt["ref"], pt["label"]), green,
                  order=tuple(sd for sd in ("above", "below", "right", "left") if sd != wire_side) + (wire_side,))
        elif pt["kind"] == "hdr":
            label(pt, "%s %s" % (pt["ref"], pt["label"]), green, fs=6.5)
        elif pt["kind"] == "fuse":
            ax.text(ox + S * cx, oy + S * (cy + 2.0), "F1  fuse holder 5x20 mm", fontsize=7, color="#1f6feb", ha="center")
            ax.text(ox + S * cx, oy + S * (cy - 3.2), "fuse 10 A slow-blow", fontsize=6.5, color="#1f6feb", ha="center")
        elif pt["kind"] == "cap":
            label(pt, "C1 2200uF 25V", brown, fs=6.5, bold=False)
            px, py = pt["plus"]; mx_, my_ = pt["minus"]
            ax.text(ox + S * (px + 2.0), oy + S * py, "+", fontsize=9, color=brown, va="center", weight="bold")
            ax.text(ox + S * (mx_ + 2.0), oy + S * my_, "-", fontsize=9, color=brown, va="center", weight="bold")
        elif pt["kind"] == "led":
            label(pt, "LED1 ON", "#c92a2a", fs=6.5, bold=False)
        elif pt["kind"] == "res":
            label(pt, "R1 2.2k", brown, fs=6.5, bold=False)
    for p in d["pads"]:
        x, y = ox + S * p["x"], oy + S * p["y"]
        rr = S * p["d"] / 2
        if p["square"]:
            ax.add_patch(Rectangle((x - rr, y - rr), 2 * rr, 2 * rr, facecolor="white", edgecolor="black", lw=0.6))
        else:
            ax.add_patch(Circle((x, y), rr, facecolor="white", edgecolor="black", lw=0.6))
        if p["ref"].startswith("J"):
            ax.text(x, y, p["pin"], fontsize=4.6 if p["ref"] == "J7" else 5.2, ha="center", va="center", color="black")
    pdf.savefig(fig); plt.close(fig)


WIRING = [
    ("J1 BATTERY", "BAT+: battery + after the BMS (P+). BAT-: battery - (BMS P-)."),
    ("J2 USB-C 12V", "+12V and GND from the PD trigger board output. Set the trigger board to 12 V and measure it first."),
    ("J3 SWITCH", "ON-OFF-ON toggle switch, 10 A DC or more. Middle lug to COM, one outer lug to BATT, the other to USB. "
                  "Middle position = everything off."),
    ("J4 BTS7960", "B+ and B- to the BTS7960 power terminals (thick wire, 1.5 mm2). M+/M- of the BTS7960 go to the Peltier."),
    ("J5 LM2596", "IN+ to LM2596 IN+, GND to LM2596 IN- (IN- and OUT- are the same on the module), OUT+ from LM2596 OUT+. "
                  "Set the LM2596 to 5.0 V before connecting it."),
    ("J7 TO CONTROLLER", "VBAT, 5V, GND to J7 VBAT, 5V, GND on the controller board (pin 1 = VBAT on both, square pad)."),
]
NOTES = [
    "Only ONE source at a time: the switch picks battery or USB-C. Never connect the trigger board straight to the battery.",
    "The trigger board does not charge the battery; on USB-C the battery is just not used.",
    "Peltier power on USB-C (phone page slider): 12V 5A charger and 5A cable -> 60 % max; 12V 3A -> 40 % max.",
    "Never set the trigger board to 15 V or 20 V: the 12 V fan and the TEC1-12706 would be damaged.",
    "Fuse F1 (10 A slow-blow, 5x20 mm) protects both sources. C1 smooths the Peltier PWM so the charger does not cut out.",
    "Before the first power-up: check with a meter that BAT+, +12V, COM and BUS are not shorted to GND. Then, with the",
    "switch on BATT, LED1 lights and J7 VBAT reads the battery voltage. Switch to the middle (off) before changing source.",
    "Cover the wide copper tracks with solder after etching (they carry up to 7 A).",
]
BOM = [
    "J1, J2, J4: 2-pin screw terminal 5.08 mm (KF301-2P)    J3, J5: 3-pin screw terminal 5.08 mm (KF301-3P)",
    "J7: 1x3 male header 2.54 mm + 3 dupont wires to the controller J7",
    "F1: 5x20 mm PCB fuse holder (BLX-A, pins 22.6 mm apart) + 10 A slow-blow fuse",
    "C1: 2200 uF 25 V electrolytic, up to 13 mm diameter, 5 mm lead spacing",
    "LED1: 3 or 5 mm LED,  R1: 2.2 kOhm 1/4 W,  SW: ON-OFF-ON toggle 10 A (on the case, wired to J3)",
    "M3 screws/standoffs: 4 (square) or 3 (round)",
]


def wiring_page(pdf, d, r):
    import textwrap
    lines = ["CONNECTORS"]
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
        ax.text(12, 272 - 5.0 * k, ln, fontsize=7.0, va="top", family="monospace", weight="bold" if ln.isupper() and ln else "normal")
    # block diagram
    y0 = 62
    ax.text(12, y0 + 28, "HOW IT CONNECTS", fontsize=7.5, weight="bold", family="monospace")
    boxes = [(12, y0 + 12, "3S battery\n+ BMS", "J1"), (12, y0, "USB-C charger\n-> PD trigger 12V", "J2"),
             (62, y0 + 6, "switch\nON-OFF-ON", "J3"), (100, y0 + 6, "F1 10A\n+ C1", ""),
             (140, y0 + 16, "BTS7960 power\n-> Peltier", "J4"), (140, y0 + 6, "LM2596 -> 5V", "J5"),
             (140, y0 - 4, "controller PCB J7", "J7")]
    for x, y, t, j in boxes:
        ax.add_patch(Rectangle((x, y), 34, 8, facecolor="#f1f3f5", edgecolor="0.4", lw=0.6))
        ax.text(x + 17, y + 4, t, fontsize=6.3, ha="center", va="center")
        if j:
            ax.text(x + 17, y + 8.8, j, fontsize=6, ha="center", color="#2b8a3e", weight="bold")
    for (x0, y0_, x1, y1) in [(46, y0 + 16, 62, y0 + 10), (46, y0 + 4, 62, y0 + 10), (96, y0 + 10, 100, y0 + 10),
                              (134, y0 + 10, 140, y0 + 20), (134, y0 + 10, 140, y0 + 10), (134, y0 + 10, 140, y0)]:
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
