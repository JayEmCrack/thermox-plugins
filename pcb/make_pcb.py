#!/usr/bin/env python3
"""ThermoX controller PCB: single-sided, through-hole, for home etching (toner transfer or UV film).

Makes print-ready PDFs (1:1 on A4) for a 60 x 60 mm square board and an 82 mm round board that fits the
85 mm battery bay of the round bottle designs. Both use the same copper. The ESP32 pin rows are 25.4 mm or
22.86 mm apart depending on the board, so each shape is made for both; measure your board and pick one.

Run:  python3 make_pcb.py            (needs: pip install shapely matplotlib)
Every run also checks the design: copper of different nets at least CLEAR mm apart, every net connected,
and every GND part reached by the ground fill. It stops with an error if a check fails.
"""
import math
import os
import sys

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

OUT = os.path.dirname(os.path.abspath(__file__))
CLEAR = 0.5          # mm, minimum copper gap between different nets (traces/pads)
POUR_CLEAR = 0.8     # mm, gap between the ground fill and other nets
EDGE_CLEAR = 0.6     # mm, copper kept away from the board edge
W_SIG, W_PWR = 0.7, 1.0
PAD, DRILL_HDR, DRILL_PART = 1.9, 1.0, 0.8


def rows(i):
    """ESP32 header row i (0 = antenna end, 14 = USB end), mm."""
    return 41.06 - 2.54 * i


LEFT_PINS = ["EN", "VP", "VN", "IO34", "IO35", "IO32", "IO33", "IO25", "IO26", "IO27", "IO14", "IO12", "IO13", "GND", "VIN"]
RIGHT_PINS = ["IO23", "IO22", "TX0", "RX0", "IO21", "IO19", "IO18", "IO5", "TX2", "RX2", "IO4", "IO2", "IO15", "GND", "3V3"]
# which ESP32 pins are used, and the net name on this board
USED = {"IO34": "FG", "IO35": "BATT", "IO32": "BTN1", "IO33": "BTN2", "IO25": "R_EN", "IO26": "RPWM", "IO27": "LPWM",
        "IO14": "DQ", "IO13": "L_EN", "GND": "GND", "VIN": "5V",
        "IO23": "PWM", "IO22": "SCL", "IO21": "SDA", "3V3": "3V3"}


def design(spacing):
    """Pads, traces and parts for one ESP32 row spacing. Coordinates: top view, mm, origin bottom-left."""
    LX = 17.3
    RX = LX + spacing
    pads, traces, parts, holes = [], [], [], []

    def pad(x, y, net, ref, pin, d=PAD, drill=DRILL_HDR, square=False):
        pads.append(dict(x=x, y=y, net=net, ref=ref, pin=pin, d=d, drill=drill, square=square))

    def tr(net, w, *pts):
        traces.append(dict(net=net, w=w, pts=list(pts)))

    # ---- ESP32 on two 1x15 female headers
    for i, nm in enumerate(LEFT_PINS):
        pad(LX, rows(i), USED.get(nm, "NC_L" + nm), "U1", nm, square=(i == 0))
    for i, nm in enumerate(RIGHT_PINS):
        pad(RX, rows(i), USED.get(nm, "NC_R" + nm), "U1", nm)
    parts.append(dict(ref="U1", kind="esp32", x0=LX - 5.3, x1=RX + 5.3, y0=1.5, y1=53.5, label="ESP32 DevKit 30-pin"))

    # ---- left strip: fan, divider, buttons, BTS7960, temperature sensor, power in
    fan = [("GND", "GND"), ("PWM", "PWM"), ("+12V", "VBAT"), ("FG", "FG")]
    for k, (pin, net) in enumerate(fan):
        pad(9.0, rows(k), net, "J1", pin, square=(k == 0))
    parts.append(dict(ref="J1", kind="hdr", pts=[(9.0, rows(k)) for k in range(4)], label="FAN", side="left"))
    pad(6.46, rows(5), "GND", "J2", "GND", square=True); pad(9.0, rows(5), "BTN1", "J2", "BTN1")
    parts.append(dict(ref="J2", kind="hdr", pts=[(6.46, rows(5)), (9.0, rows(5))], label="BTN1", side="left"))
    pad(6.46, rows(6), "GND", "J3", "GND", square=True); pad(9.0, rows(6), "BTN2", "J3", "BTN2")
    parts.append(dict(ref="J3", kind="hdr", pts=[(6.46, rows(6)), (9.0, rows(6))], label="BTN2", side="left"))
    for k, (pin, net) in enumerate([("R_EN", "R_EN"), ("RPWM", "RPWM"), ("LPWM", "LPWM")]):
        pad(9.0, rows(7 + k), net, "J4", pin, square=(k == 0))
    parts.append(dict(ref="J4", kind="hdr", pts=[(9.0, rows(7 + k)) for k in range(3)], label="BTS A", side="left"))
    for k, (pin, net) in enumerate([("L_EN", "L_EN"), ("GND", "GND"), ("VCC", "5V")]):
        pad(9.0, rows(12 + k), net, "J5", pin, square=(k == 0))
    parts.append(dict(ref="J5", kind="hdr", pts=[(9.0, rows(12 + k)) for k in range(3)], label="BTS B", side="left"))
    for k, (pin, net) in enumerate([("5V", "5V"), ("GND", "GND"), ("DQ", "DQ")]):
        pad(3.92 + 2.54 * k, rows(10), net, "J6", pin, square=(k == 0))
    parts.append(dict(ref="J6", kind="hdr", pts=[(3.92 + 2.54 * k, rows(10)) for k in range(3)], label="TEMP", side="below"))
    for k, (pin, net) in enumerate([("VBAT", "VBAT"), ("5V", "5V"), ("GND", "GND")]):
        pad(3.2 + 2.54 * k, 2.0, net, "J7", pin, square=(k == 0))
    parts.append(dict(ref="J7", kind="hdr", pts=[(3.2 + 2.54 * k, 2.0) for k in range(3)], label="POWER", side="above"))

    # battery divider (3S pack): R3 100k VBAT->GPIO35, R4 22k GPIO35->GND, C1 100nF GPIO35->GND
    pad(3.0, rows(4), "VBAT", "R3", "1", drill=DRILL_PART); pad(13.16, rows(4), "BATT", "R3", "2", drill=DRILL_PART)
    parts.append(dict(ref="R3", kind="res", a=(3.0, rows(4)), b=(13.16, rows(4)), label="100k"))
    pad(22.5, rows(4), "BATT", "R4", "1", drill=DRILL_PART); pad(22.5, rows(8), "GND", "R4", "2", drill=DRILL_PART)
    parts.append(dict(ref="R4", kind="res", a=(22.5, rows(4)), b=(22.5, rows(8)), label="22k"))
    pad(26.0, rows(4), "BATT", "C1", "1", drill=DRILL_PART); pad(26.0, rows(6), "GND", "C1", "2", drill=DRILL_PART)
    parts.append(dict(ref="C1", kind="cap", a=(26.0, rows(4)), b=(26.0, rows(6)), label="100nF"))
    # pull-ups to 3V3: R1 10k fan tach (GPIO34), R2 4.7k DS18B20 data (GPIO14)
    pad(19.9, rows(3), "FG", "R1", "1", drill=DRILL_PART); pad(30.06, rows(3), "3V3", "R1", "2", drill=DRILL_PART)
    parts.append(dict(ref="R1", kind="res", a=(19.9, rows(3)), b=(30.06, rows(3)), label="10k"))
    pad(19.9, rows(10), "DQ", "R2", "1", drill=DRILL_PART); pad(30.06, rows(10), "3V3", "R2", "2", drill=DRILL_PART)
    parts.append(dict(ref="R2", kind="res", a=(19.9, rows(10)), b=(30.06, rows(10)), label="4.7k"))

    # ---- right strip: OLED
    for k, (pin, net) in enumerate([("SCL", "SCL"), ("SDA", "SDA"), ("VCC", "3V3"), ("GND", "GND")]):
        pad(51.0, rows(1 + k), net, "J8", pin, square=(k == 0))
    parts.append(dict(ref="J8", kind="hdr", pts=[(51.0, rows(1 + k)) for k in range(4)], label="OLED", side="right"))

    # ---- traces (left)
    tr("FG", W_SIG, (9.0, rows(3)), (19.9, rows(3)))
    tr("BATT", W_SIG, (13.16, rows(4)), (26.0, rows(4)))
    tr("BTN1", W_SIG, (9.0, rows(5)), (LX, rows(5)))
    tr("BTN2", W_SIG, (9.0, rows(6)), (LX, rows(6)))
    for k, net in enumerate(["R_EN", "RPWM", "LPWM"]):
        tr(net, W_SIG, (9.0, rows(7 + k)), (LX, rows(7 + k)))
    tr("DQ", W_SIG, (9.0, rows(10)), (19.9, rows(10)))
    tr("L_EN", W_SIG, (9.0, rows(12)), (LX, rows(12)))
    tr("GND", W_PWR, (9.0, rows(13)), (LX, rows(13)))
    tr("5V", W_PWR, (9.0, rows(14)), (LX, rows(14)))
    tr("5V", W_PWR, (5.74, 2.0), (5.74, 4.3), (9.0, 4.3), (9.0, rows(14)))
    tr("5V", W_PWR, (5.74, 4.3), (3.92, 4.3), (3.92, rows(10)))
    tr("VBAT", W_PWR, (3.2, 2.0), (1.6, 3.6), (1.6, rows(2)), (9.0, rows(2)))
    tr("VBAT", W_PWR, (1.6, rows(4)), (3.0, rows(4)))
    # GPIO23 (fan PWM) runs round the edge of the board to the fan connector
    tr("PWM", W_SIG, (RX, rows(0)), (58.7, rows(0)), (58.7, 53.0), (53.0, 58.7), (7.1, 58.7), (1.4, 53.0),
       (1.4, rows(1)), (9.0, rows(1)))
    # ---- traces (channel under the ESP32)
    tr("3V3", W_PWR, (RX, rows(14)), (30.06, rows(14)), (30.06, rows(3)))
    # ---- traces (right)
    tr("SCL", W_SIG, (RX, rows(1)), (51.0, rows(1)))
    tr("SDA", W_SIG, (RX, rows(4)), (47.0, rows(4)), (47.0, rows(2)), (51.0, rows(2)))
    tr("3V3", W_PWR, (RX, rows(14)), (53.5, rows(14)), (53.5, rows(3)), (51.0, rows(3)))

    holes += [(6.5, 53.5), (53.5, 53.5), (57.0, 3.0)]
    return dict(pads=pads, traces=traces, parts=parts, holes=holes, spacing=spacing, LX=LX, RX=RX)


def pad_geom(p):
    if p["square"]:
        h = p["d"] / 2
        return box(p["x"] - h, p["y"] - h, p["x"] + h, p["y"] + h)
    return Point(p["x"], p["y"]).buffer(p["d"] / 2, 32)


def trace_geom(t):
    return LineString(t["pts"]).buffer(t["w"] / 2, 16)


def build(d, shape):
    """Copper geometry + checks for one design and board shape ('square' or 'round')."""
    if shape == "square":
        outline = box(0, 0, 60, 60)
        holes = list(d["holes"])
    else:
        outline = Point(30, 30).buffer(41, 128)
        holes = [(30, 66), (30, -6), (-6, 30), (66, 30)]
    nets = {}
    for p in d["pads"]:
        nets.setdefault(p["net"], []).append(pad_geom(p))
    for t in d["traces"]:
        nets.setdefault(t["net"], []).append(trace_geom(t))
    net_geom = {n: unary_union(g) for n, g in nets.items()}
    errors = []

    # clearance between different nets
    names = sorted(net_geom)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            dist = net_geom[a].distance(net_geom[b])
            if dist < CLEAR - 1e-6:
                errors.append("clearance %s-%s %.2f mm" % (a, b, dist))
    # copper inside the board, away from the edge and the mounting holes
    inner = outline.buffer(-EDGE_CLEAR)
    keep = unary_union([Point(x, y).buffer(1.6 + 0.8, 32) for x, y in holes])
    for n, g in net_geom.items():
        if not inner.contains(g):
            errors.append("net %s too close to the board edge" % n)
        if g.intersects(keep):
            errors.append("net %s hits a mounting hole" % n)
    # every net in one piece (traces + pads), GND checked together with the fill below
    for n, g in net_geom.items():
        if n.startswith("NC_") or n == "GND":
            continue
        if g.geom_type != "Polygon":
            errors.append("net %s is not connected (%d pieces)" % (n, len(g.geoms)))

    # ground fill: everything not near another net, the edge or a hole
    others = unary_union([g for n, g in net_geom.items() if n != "GND"]).buffer(POUR_CLEAR, 16)
    fill = inner.difference(others).difference(keep)
    fill = fill.buffer(-0.35, 8).buffer(0.35, 8)            # drop slivers a toner print cannot hold
    gnd = unary_union([fill, net_geom["GND"]])
    gnd_parts = list(gnd.geoms) if gnd.geom_type == "MultiPolygon" else [gnd]
    gnd_pads = [pad_geom(p) for p in d["pads"] if p["net"] == "GND"]
    main = [g for g in gnd_parts if any(g.intersects(pg) for pg in gnd_pads)]
    if len(main) != 1:
        errors.append("ground is in %d separate pieces that hold GND pads" % len(main))
    gnd_main = main[0] if main else gnd
    missing = [p for p in d["pads"] if p["net"] == "GND" and not gnd_main.intersects(pad_geom(p))]
    for p in missing:
        errors.append("GND pad %s.%s not reached by the ground" % (p["ref"], p["pin"]))
    dead = sum(g.area for g in gnd_parts if g is not gnd_main)
    copper = unary_union([gnd_main] + [g for n, g in net_geom.items() if n != "GND"])
    return dict(outline=outline, holes=holes, copper=copper, errors=errors, dead_area=dead, net_geom=net_geom)


# ================================================================ drawing
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import PathPatch, Circle, Rectangle
from matplotlib.path import Path
from matplotlib.textpath import TextPath
from matplotlib.transforms import Affine2D
from shapely.geometry.polygon import orient

A4 = (210.0, 297.0)
MM = 1 / 25.4


def poly_path(geom):
    verts, codes = [], []
    gs = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    for g in gs:
        if g.is_empty or g.geom_type != "Polygon":
            continue
        g = orient(g, 1.0)
        for ring in [g.exterior] + list(g.interiors):
            c = list(ring.coords)
            verts += c
            codes += [Path.MOVETO] + [Path.LINETO] * (len(c) - 2) + [Path.CLOSEPOLY]
    return Path(verts, codes) if verts else None


def page(pdf, title, lines=()):
    fig = plt.figure(figsize=(A4[0] * MM, A4[1] * MM))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, A4[0]); ax.set_ylim(0, A4[1]); ax.set_aspect("equal"); ax.axis("off")
    ax.text(15, 282, title, fontsize=13, weight="bold", va="top")
    for k, ln in enumerate(lines):
        ax.text(15, 274 - 5.2 * k, ln, fontsize=8.5, va="top")
    return fig, ax


def scale_bar(ax, x, y):
    ax.add_patch(Rectangle((x, y), 50, 1.2, color="black"))
    for k in range(0, 51, 10):
        ax.plot([x + k, x + k], [y, y + 3], color="black", lw=0.6)
    ax.text(x, y + 4, "50 mm: measure this after printing. It must be exactly 50 mm.", ha="left", fontsize=7.5)


def draw_outline(ax, r, ox, oy, lw=0.25, color="black"):
    xs, ys = r["outline"].exterior.xy
    ax.plot([ox + x for x in xs], [oy + y for y in ys], color=color, lw=lw)


def copper_page(pdf, d, r, shape):
    name = "%s, ESP32 rows %.2f mm apart" % ("60 x 60 mm square" if shape == "square" else "82 mm round", d["spacing"])
    fig, ax = page(pdf, "ThermoX PCB: COPPER (%s)" % name, [
        "Print at 100 % / Actual size (no 'fit to page'). Check the 50 mm bar with a ruler.",
        "Toner transfer or UV film: use this page as it is. Do NOT mirror it: it is the copper as seen through the board",
        "from the parts side, which is the right way round for copper on the bottom.",
        "Check: the small text 'THERMOX' looks mirrored on the paper and reads normally on the etched copper side.",
        "White dots in the pads mark the drill centres: 1.0 mm for headers, 0.8 mm for resistors/capacitor, 3.2 mm mounting holes.",
    ])
    for k, (cx, cy) in enumerate([(55 - 30, 120.0), (155 - 30, 120.0)]):
        path = poly_path(r["copper"])
        ax.add_patch(PathPatch(path.transformed(Affine2D().translate(cx, cy)), facecolor="black", edgecolor="none"))
        # mirrored marker text in copper: reads correctly from the copper side after transfer
        tp = TextPath((0, 0), "THERMOX", size=2.2)
        tx = Affine2D().scale(-1, 1).translate(cx + 37.5, cy + 46.0)
        ax.add_patch(PathPatch(tp.transformed(tx), facecolor="white", edgecolor="none"))
        for p in d["pads"]:
            ax.add_patch(Circle((cx + p["x"], cy + p["y"]), 0.3, color="white"))
        for hx, hy in r["holes"]:
            ax.add_patch(Circle((cx + hx, cy + hy), 1.6, facecolor="none", edgecolor="black", lw=0.3))
            ax.add_patch(Circle((cx + hx, cy + hy), 0.3, color="black"))
        draw_outline(ax, r, cx, cy)
        ax.text(cx + 30, cy - 4 if shape == "square" else cy - 15, "copy %d (spare)" % (k + 1) if k else "copy 1",
                fontsize=7, color="0.4", ha="center")
    scale_bar(ax, 15, 12)
    pdf.savefig(fig); plt.close(fig)


def parts_page(pdf, d, r, shape):
    S = 2.0 if shape == "square" else 1.6
    fig, ax = page(pdf, "ThermoX PCB: PARTS SIDE (top view, enlarged %g x)" % S, [
        "Parts go on this side; copper is underneath (grey = copper, for reference). Square pad = pin 1.",
        "R1 10k, R2 4.7k, R3 100k, R4 22k and C1 100 nF lie under the ESP32 or the fan header: fit them first, flat on the board.",
        "The ESP32 sits on two 1x15 female headers (USB end at the bottom edge). Fit headers last.",
    ])
    ox, oy = 105 - S * 30, 145 - S * 30
    T = Affine2D().scale(S).translate(ox, oy)
    xs, ys = r["outline"].exterior.xy
    ax.plot([ox + S * x for x in xs], [oy + S * y for y in ys], color="black", lw=0.8)
    ax.add_patch(PathPatch(poly_path(r["copper"]).transformed(T), facecolor="0.88", edgecolor="none"))
    for hx, hy in r["holes"]:
        ax.add_patch(Circle((ox + S * hx, oy + S * hy), S * 1.6, facecolor="white", edgecolor="black", lw=0.6))
    for pt in d["parts"]:
        if pt["kind"] == "esp32":
            ax.add_patch(Rectangle((ox + S * pt["x0"], oy + S * pt["y0"]), S * (pt["x1"] - pt["x0"]), S * (pt["y1"] - pt["y0"]),
                                   facecolor="none", edgecolor="#1f6feb", lw=1.0, ls="--"))
            cx = ox + S * (pt["x0"] + pt["x1"]) / 2
            ax.text(cx, oy + S * 47, "U1  ESP32 DevKit\n(antenna end)", ha="center", fontsize=8, color="#1f6feb")
            ax.add_patch(Rectangle((cx - S * 4, oy + S * 1.5), S * 8, S * 4, facecolor="none", edgecolor="#1f6feb", lw=0.8))
            ax.text(cx, oy + S * 6.5, "USB", ha="center", fontsize=7, color="#1f6feb")
        elif pt["kind"] in ("res", "cap"):
            (ax_, ay), (bx, by) = pt["a"], pt["b"]
            ax.plot([ox + S * ax_, ox + S * bx], [oy + S * ay, oy + S * by], color="#b35c00", lw=4 if pt["kind"] == "res" else 3,
                    alpha=0.55, solid_capstyle="butt")
            mx, my = (ax_ + bx) / 2, (ay + by) / 2
            if abs(bx - ax_) < 0.1:      # vertical part: label turned, R4 on its left, C1 on its right
                side = -1 if pt["ref"] == "R4" else 1
                ax.text(ox + S * (mx + 1.3 * side), oy + S * my, "%s %s" % (pt["ref"], pt["label"]), fontsize=6.5, color="#7a3e00",
                        rotation=90, ha="center", va="center")
            else:
                ax.text(ox + S * mx, oy + S * (my + 1.2), "%s %s" % (pt["ref"], pt["label"]), fontsize=6.5, color="#7a3e00",
                        ha="center", va="bottom")
        elif pt["kind"] == "hdr":
            xs_ = [x for x, _ in pt["pts"]]; ys_ = [y for _, y in pt["pts"]]
            ax.add_patch(Rectangle((ox + S * (min(xs_) - 1.27), oy + S * (min(ys_) - 1.27)), S * (max(xs_) - min(xs_) + 2.54),
                                   S * (max(ys_) - min(ys_) + 2.54), facecolor="none", edgecolor="#2b8a3e", lw=1.0))
    for p in d["pads"]:
        x, y = ox + S * p["x"], oy + S * p["y"]
        if p["square"]:
            ax.add_patch(Rectangle((x - S * 0.95, y - S * 0.95), S * 1.9, S * 1.9, facecolor="white", edgecolor="black", lw=0.6))
        else:
            ax.add_patch(Circle((x, y), S * 0.95, facecolor="white", edgecolor="black", lw=0.6))
        if p["ref"] == "U1":
            used = not p["net"].startswith("NC_")
            dx = -S * 1.4 if p["x"] < 30 else S * 1.4
            ax.text(x + dx, y, p["pin"], fontsize=4.6, ha="right" if dx < 0 else "left", va="center",
                    color="black" if used else "0.6")
        elif p["ref"].startswith("J"):
            ax.text(x, y - S * 1.55, p["pin"], fontsize=4.3, ha="center", va="top", color="#2b8a3e")
    # header labels
    lab = {"J1": (-3.5, 0), "J2": (-1.0, 0), "J3": (-1.0, 0), "J4": (-3.5, 0), "J5": (-3.5, 0), "J6": (-3.5, 0), "J7": (-3.5, 0),
           "J8": (3.0, 0)}
    for pt in d["parts"]:
        if pt["kind"] == "hdr":
            xs_ = [x for x, _ in pt["pts"]]; ys_ = [y for _, y in pt["pts"]]
            dx, dy = lab[pt["ref"]]
            ax.text(ox + S * (min(xs_) + dx), oy + S * ((min(ys_) + max(ys_)) / 2 + dy), "%s %s" % (pt["ref"], pt["label"]),
                    fontsize=7, color="#2b8a3e", weight="bold", ha="right" if dx < 0 else "left",
                    va="center")
    ax.text(15, 40, "This file: ESP32 pin rows %.2f mm apart. Measure your ESP32 from the centre of a left pin to the centre of\n"
            "the right pin in the same row: 25.4 mm (1.0\") or 22.86 mm (0.9\"), and print the matching file." % d["spacing"],
            fontsize=8, va="top")
    pdf.savefig(fig); plt.close(fig)


WIRING = [
    ("J7 POWER", "VBAT: battery + (after the BMS and fuse), also LM2596 IN+.  5V: LM2596 OUT+ (set to 5.0 V first!).  GND: battery -, LM2596 IN-/OUT-."),
    ("J1 FAN", "GND: fan black.  PWM: fan blue (control).  +12V: fan red.  FG: fan yellow/green (tach). Check your SUNON's colours."),
    ("J2 / J3 BTN1, BTN2", "Each push button: one wire to BTN, one to GND (BTN1 = GPIO32 down, BTN2 = GPIO33 up)."),
    ("J4 BTS A", "R_EN, RPWM, LPWM to the same pins on the BTS7960."),
    ("J5 BTS B", "L_EN to BTS7960 L_EN, GND to BTS7960 GND, VCC to BTS7960 VCC (5 V logic). R_IS / L_IS stay unconnected."),
    ("J6 TEMP", "DS18B20: 5V to red (VDD), GND to black, DQ to yellow (data). R2 4.7k pulls DQ up to 3.3 V on the board."),
    ("J8 OLED", "SCL, SDA, VCC (3.3 V) and GND to the same pins on the 1.5\" SH1107 module."),
]
NOTES = [
    "Heavy current does NOT go through this board: BTS7960 B+/B- straight from the pack with thick wire",
    "(1.5 mm2) and a 10 A fuse, and BTS7960 M+/M- straight to the Peltier.",
    "Battery gauge parts (R3 100k, R4 22k, C1 100 nF on GPIO35) are on the board but the firmware leaves it OFF for now",
    "(ENABLE_BATTERY_SENSE = false). After the board is built: BATT_CELLS = 3, BATT_DIVIDER = 5.545, then enable.",
    "Before fitting the ESP32: check with a meter that VBAT, 5V and 3V3 are not shorted to GND,",
    "then power J7 with the ESP32 out and check 5 V on J5 VCC and on J6 5V.",
]
BOM = [
    "U1  ESP32 DevKit 30-pin + 2 x 1x15 female header (2.54 mm)",
    "J1  1x4 male header, J2/J3 1x2, J4/J5/J6/J7 1x3, J8 1x4 (or JST-XH of the same pin count)",
    "R1 10 kOhm, R2 4.7 kOhm, R3 100 kOhm, R4 22 kOhm (1/4 W, 1 %), C1 100 nF ceramic",
    "3 x M3 screws/standoffs (square) or 4 (round)",
]


def wiring_page(pdf, d, shape, r):
    import textwrap
    wiring = []
    for k, v in WIRING:
        for j, ln in enumerate(textwrap.wrap(v, 88)):
            wiring.append("  %-20s %s" % (k if j == 0 else "", ln))
    lines = ["CONNECTORS"] + wiring + ["", "IMPORTANT"] + ["  " + n for n in NOTES] + \
            ["", "PARTS"] + ["  " + b for b in BOM] + ["", "DESIGN CHECK (run by make_pcb.py)",
            "  clearance >= %.1f mm between nets, ground fill %.1f mm from other nets," % (CLEAR, POUR_CLEAR),
            "  all nets connected, all GND pads on the ground: %s" % ("OK" if not r["errors"] else "FAILED")]
    fig, ax = page(pdf, "ThermoX PCB: WIRING, PARTS, NOTES", [])
    for k, ln in enumerate(lines):
        ax.text(12, 272 - 5.0 * k, ln, fontsize=7.2, va="top", family="monospace", weight="bold" if ln.isupper() and ln else "normal")
    pdf.savefig(fig); plt.close(fig)


def main():
    ok = True
    for shape in ("square", "round"):
        for spacing in (25.4, 22.86):
            d = design(spacing)
            r = build(d, shape)
            tag = "%s_rows%s" % ("60x60" if shape == "square" else "round82", "25.4" if spacing == 25.4 else "22.86")
            if r["errors"]:
                ok = False
                print(tag, "FAILED:", *r["errors"], sep="\n  ")
                continue
            path = os.path.join(OUT, "thermox_pcb_%s.pdf" % tag)
            with PdfPages(path) as pdf:
                copper_page(pdf, d, r, shape)
                parts_page(pdf, d, r, shape)
                wiring_page(pdf, d, shape, r)
            print(tag, "OK ->", os.path.basename(path))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
