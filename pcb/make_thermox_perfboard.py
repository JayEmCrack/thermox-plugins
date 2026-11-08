#!/usr/bin/env python3
"""ThermoX on a universal PCB (perfboard): a 5 x 7 cm board, 18 x 24 holes, 2.54 mm pitch.

Same circuit and pins as ThermoX.ino (Button 1 GPIO18, fan FG GPIO35, battery gauge GPIO36, charger detect GPIO19).
The holes are named like a chess board: columns A-R from the left (parts side up), rows 1-24 from the top.
Parts go on top. All connections are on the bottom: bare tinned wire trails along the holes, plus four
insulated wires (W1-W4) where a trail would cross another net.

The high-current Peltier loop does not touch this board: battery -> switch -> 10 A fuse -> BTS7960 B+, with C1 on
the BTS7960 terminals. The board takes 12 V after the fuse, the battery + for the gauge and the charger, and the
charger input.

The ESP32 pin rows are 25.4 mm or 22.86 mm apart depending on the board, so the layout is made for both.
Each run rebuilds both PDFs and checks them; it stops with an error if a check fails:
  - no hole is shared by two nets, every net is in one piece
  - no part body overlaps another or covers another part's pin (flat parts may sit under the ESP32)
  - nothing (parts or trails) under the ESP32 antenna
  - the battery + net (no fuse) has no ground hole next to it

Run:  python3 make_thermox_perfboard.py        (needs: pip install matplotlib)
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

OUT = os.path.dirname(os.path.abspath(__file__))
COLS = "ABCDEFGHIJKLMNOPQR"
NC, NR = 18, 24                 # holes across, holes down
LX, R0 = 3, 10                  # left ESP32 pin column (C), row of the first pin (EN)
LEFT = ["EN", "VP", "VN", "IO34", "IO35", "IO32", "IO33", "IO25", "IO26", "IO27", "IO14", "IO12", "IO13", "GND", "VIN"]
RIGHT = ["IO23", "IO22", "TX0", "RX0", "IO21", "IO19", "IO18", "IO5", "TX2", "RX2", "IO4", "IO2", "IO15", "GND", "3V3"]
USED = {"VP": "BATS", "IO35": "FG", "IO33": "BTN2", "IO25": "R_EN", "IO26": "RPWM", "IO27": "LPWM", "IO14": "DQ",
        "IO13": "L_EN", "GND": "GND", "VIN": "5V", "IO23": "PWM", "IO22": "SCL", "IO21": "SDA", "IO19": "CHGS",
        "IO18": "BTN1", "3V3": "3V3"}
THICK = ("BAT+", "BUS", "CHG")  # charge current and 12 V: bare 0.8-1 mm copper wire
NETC = {"GND": "#222222", "BUS": "#d62728", "BAT+": "#ff7f0e", "CHG": "#e377c2", "5V": "#8c564b", "3V3": "#9467bd"}
SIG = "#1f77b4"


def H(name):
    return (COLS.index(name[0]) + 1, int(name[1:]))


def hn(h):
    return f"{COLS[h[0] - 1]}{h[1]}"


def netcolor(net):
    return NETC.get(net, SIG)


class Board:
    def __init__(self, rx, rows):
        self.rx, self.rows = rx, rows
        self.parts, self.trails, self.wires, self.keepout = [], [], [], []

    def part(self, **k):
        k.setdefault("under", False)
        k.setdefault("low", False)
        k.setdefault("extra", {})
        k.setdefault("note", "")
        self.parts.append(k)

    def trail(self, net, *pts, thick=None):
        hs = [H(p) if isinstance(p, str) else p for p in pts]
        path = [hs[0]]
        for a, c in zip(hs, hs[1:]):
            assert a[0] == c[0] or a[1] == c[1], (net, pts)
            dc, dr = (c[0] > a[0]) - (c[0] < a[0]), (c[1] > a[1]) - (c[1] < a[1])
            x, y = a
            while (x, y) != c:
                x, y = x + dc, y + dr
                path.append((x, y))
        self.trails.append({"net": net, "path": path, "corners": hs,
                            "thick": net in THICK if thick is None else thick})

    def wire(self, name, net, a, c, via, note, lab=0):
        self.wires.append({"name": name, "net": net, "a": H(a), "b": H(c), "via": via, "note": note, "lab": lab})


def design(spacing):
    """spacing: ESP32 pin rows 25.4 or 22.86 mm apart."""
    X = LX + (10 if spacing == 25.4 else 9)          # right ESP32 pin column: M or L
    b = Board(X, spacing)
    pins = [((LX, R0 + i), USED.get(n), n) for i, n in enumerate(LEFT)] + \
           [((X, R0 + i), USED.get(n), n) for i, n in enumerate(RIGHT)]
    half, mid = (X - LX) / 2 + 0.57, (LX + X) / 2      # module = pin spacing + 2.9 mm wide
    b.part(ref="U1", kind="esp", label="ESP32", pins=pins, body=(mid - half, R0 - 3.14, mid + half, R0 + 17.14),
           extra={"tied": [[(LX, R0 + 13), (X, R0 + 13)]]})
    b.keepout.append((LX - 0.5, 6.6, X + 0.5, 9.6))

    def header(ref, label, holes, nets, labs):
        hs = [H(x) for x in holes]
        xs, ys = [h[0] for h in hs], [h[1] for h in hs]
        b.part(ref=ref, kind="hdr", label=label, pins=list(zip(hs, nets, labs)),
               body=(min(xs) - 0.5, min(ys) - 0.5, max(xs) + 0.5, max(ys) + 0.5))

    def term(ref, label, holes, nets, labs):
        hs = [H(x) for x in holes]
        b.part(ref=ref, kind="term", label=label, pins=list(zip(hs, nets, labs)),
               body=(hs[0][0] - 1.0, hs[0][1] - 1.8, hs[-1][0] + 1.0, hs[0][1] + 1.2))

    def pads(ref, label, holes, nets, labs):
        b.part(ref=ref, kind="pads", label=label, pins=[(H(x), n, l) for x, n, l in zip(holes, nets, labs)], body=None)

    def two(ref, kind, label, a, c, na, nc, la, lc, w, inset, under=False):
        ha, hc = H(a), H(c)
        if ha[1] == hc[1]:
            x0, x1 = sorted((ha[0], hc[0]))
            body = (x0 + inset, ha[1] - w, x1 - inset, ha[1] + w)
        else:
            y0, y1 = sorted((ha[1], hc[1]))
            body = (ha[0] - w, y0 + inset, ha[0] + w, y1 - inset)
        b.part(ref=ref, kind=kind, label=label, pins=[(ha, na, la), (hc, nc, lc)], body=body, under=under, low=True)

    def res(ref, val, a, c, na, nc, under=False):
        two(ref, "res", val, a, c, na, nc, "1", "2", 0.45, 0.6, under)

    def diode(ref, val, an, ca, na, nc):
        two(ref, "dio", val, an, ca, na, nc, "A", "K", 1.05, 1.1)

    t = b.trail
    # ---- top band: battery wire, terminals, charge diodes, 12 V lane
    pads("BAT", "BAT+ wire", ["B2"], ["BAT+"], ["BAT+"])
    term("POWER", "POWER", ["E2", "G2"], ["GND", "BUS"], ["GND", "12V"])
    pads("LMI", "LM2596 IN+", ["I2"], ["BUS"], ["IN+"])
    term("CHARGE", "CHARGE", ["K2", "M2"], ["CHG", "GND"], ["+", "-"])
    diode("D2", "1N5822", "J5", "D5", "CHG", "BAT+")
    diode("D1", "1N5822", "K5", "P5", "CHG", "BUS")
    res("R3", "100k", "B4", "B8", "BAT+", "BATS")
    header("FAN", "FAN", ["O8", "P8", "Q8", "R8"], ["PWM", "BUS", "FG", "GND"], ["PWM", "12V", "FG", "GND"])
    t("GND", "E2", "E1", "R1", "R11", "Q11", thick=True)
    t("GND", "M1", "M2", thick=True)
    t("BAT+", "B2", "B4"); t("BAT+", "B3", "D3", "D5")
    t("BATS", "B8", "B11", "D11", "D12")
    t("BUS", "G2", "G3", "I3", "I2"); t("BUS", "G3", "G6", "P6", "P5"); t("BUS", "P6", "P8")
    t("CHG", "K2", "K5"); t("CHG", "J5", "K5")
    # ---- left headers, straight into the ESP32 pins
    header("BTN2", "BTN2", ["A15", "A16"], ["GND", "BTN2"], ["GND", "B2"])
    header("BTSA", "BTS A", ["A17", "A18", "A19"], ["R_EN", "RPWM", "LPWM"], ["R_EN", "RPWM", "LPWM"])
    header("BTSB", "BTS B", ["A22", "A23", "A24"], ["L_EN", "GND", "5V"], ["L_EN", "GND", "VCC"])
    pads("LMO", "LM2596 OUT", ["B23", "B24"], ["GND", "5V"], ["OUT-", "OUT+"])
    for r, net in ((16, "BTN2"), (17, "R_EN"), (18, "RPWM"), (19, "LPWM"), (22, "L_EN"), (23, "GND"), (24, "5V")):
        t(net, (1, r), (LX, r))
    # ---- under the ESP32: flat parts only, between the two header rows
    res("R4", "22k", "D11", "H11", "BATS", "GND", under=True)
    two("C4", "cap", "100nF", "D12", "F12", "BATS", "GND", "1", "2", 0.5, 0.3, under=True)
    res("R1", "10k", "D14", "J14", "FG", "3V3", under=True)
    res("R2", "4.7k", "D20", "J20", "DQ", "3V3", under=True)
    t("GND", (LX, 23), "F23", "F11"); t("GND", "F11", "H11")
    t("FG", "B14", (LX, 14), "D14"); t("DQ", (LX, 20), "D20", "D19")
    t("3V3", (X, 24), "J24", "J14")
    # ---- right side: headers lie across, GND rail in column Q, 3V3 rail in column R
    header("OLED", "OLED", ["O12", "P12", "Q12", "R12"], ["SDA", "SCL", "GND", "3V3"], ["SDA", "SCL", "GND", "VCC"])
    header("BTN1", "BTN1", ["P16", "Q16"], ["BTN1", "GND"], ["B1", "GND"])
    header("TEMP", "TEMP", ["P20", "Q20", "R20"], ["DQ", "GND", "3V3"], ["DQ", "GND", "VCC"])
    res("R5", "100k", "O19", "O15", "CHG", "CHGS")
    b.part(ref="R6", kind="resup", label="33k", pins=[(H("P15"), "CHGS", "1"), (H("Q15"), "GND", "2")],
           body=(15.5, 14.5, 16.5, 15.5))
    t("3V3", (X, 24), "R24", "R12")
    t("GND", (X, 23), "Q23", "Q11")
    t("PWM", (X, 10), "O10", "O8")
    t("SCL", (X, 11), "P11", "P12")
    t("SDA", (X, 14), "O14", "O12")
    t("CHGS", (X, 15), "P15")
    t("BTN1", (X, 16), "P16")
    # ---- insulated wires on the bottom (they may cross trails; keep them away from the antenna end)
    b.wire("W1", "GND", "A15", "F15", [], "button 2 GND")
    b.wire("W2", "FG", "B14", "Q8", [(2.4, 13.5), (X + 0.65, 13.5), (X + 0.65, 9.7), (17.0, 9.7)], "fan tach", 1)
    b.wire("W3", "DQ", "D19", "P20", [(4.0, 18.5), (X + 0.65, 18.5), (X + 0.65, 20.5), (16.0, 20.5)], "temp sensor data", 1)
    b.wire("W4", "CHG", "K4", "O19", [(11.0, 3.6), (X + 1.35, 3.6), (X + 1.35, 19.5), (15.0, 19.5)], "charger detect", 2)
    return b


# ------------------------------------------------------------------ checks
def check(b):
    err, owner = [], {}

    def own(h, net, what):
        if not (1 <= h[0] <= NC and 1 <= h[1] <= NR):
            err.append(f"{what} off the board at {h}")
            return
        o = owner.get(h)
        if o and o[0] != net:
            err.append(f"hole {hn(h)}: {net} ({what}) and {o[0]} ({o[1]})")
        elif not o:
            owner[h] = (net, what)

    seen = {}
    for p in b.parts:
        for h, net, lab in p["pins"]:
            if h in seen:
                err.append(f"two pins in hole {hn(h)}: {p['ref']} and {seen[h]}")
            seen[h] = p["ref"]
            own(h, net or f"NC:{p['ref']}.{lab}", f"{p['ref']}.{lab}")
    for tr in b.trails:
        for h in tr["path"]:
            own(h, tr["net"], f"trail {tr['net']}")
    for w in b.wires:
        own(w["a"], w["net"], w["name"])
        own(w["b"], w["net"], w["name"])
    par = {}

    def f(x):
        while par.setdefault(x, x) != x:
            x = par[x]
        return x

    def u(x, y):
        par[f(x)] = f(y)
    for tr in b.trails:
        for x, y in zip(tr["path"], tr["path"][1:]):
            u(x, y)
    for w in b.wires:
        u(w["a"], w["b"])
    for p in b.parts:
        for grp in p["extra"].get("tied", []):
            for x, y in zip(grp, grp[1:]):
                u(x, y)
    nets = {}
    for p in b.parts:
        for h, net, lab in p["pins"]:
            if net:
                nets.setdefault(net, []).append((h, f"{p['ref']}.{lab}"))
    for net, pl in nets.items():
        groups = {}
        for h, w in pl:
            groups.setdefault(f(h), []).append(w)
        if len(groups) > 1:
            err.append(f"net {net} in {len(groups)} pieces: " + " | ".join(", ".join(g) for g in groups.values()))

    def ov(a, c):
        return a[0] < c[2] and c[0] < a[2] and a[1] < c[3] and c[1] < a[3]
    ps = [p for p in b.parts if p.get("body")]
    for i, p in enumerate(ps):
        for q in ps[i + 1:]:
            if "U1" in (p["ref"], q["ref"]) and (p["low"] or q["low"]):
                continue
            if ov(p["body"], q["body"]):
                err.append(f"bodies overlap: {p['ref']} and {q['ref']}")
        if p["ref"] != "U1":
            for k in b.keepout:
                if ov(p["body"], k):
                    err.append(f"{p['ref']} under the ESP32 antenna")
            x0, y0, x1, y1 = p["body"]
            for q in b.parts:
                if q is p or q["ref"] == "U1" and p["low"]:
                    continue
                for h, net, lab in q["pins"]:
                    if x0 < h[0] < x1 and y0 < h[1] < y1:
                        err.append(f"{p['ref']} covers pin {q['ref']}.{lab} at {hn(h)}")
    for k in b.keepout:
        for tr in b.trails:
            for h in tr["path"]:
                if k[0] < h[0] < k[2] and k[1] < h[1] < k[3]:
                    err.append(f"trail {tr['net']} under the antenna at {hn(h)}")
    for h, (n, _) in owner.items():
        if n == "BAT+":
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                m = owner.get((h[0] + d[0], h[1] + d[1]))
                if m and m[0] == "GND":
                    err.append(f"BAT+ at {hn(h)} next to GND")
    return err, owner


# ------------------------------------------------------------------ drawing
def page(pdf, title, sub=None):
    fig = plt.figure(figsize=(8.27, 11.69))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 210); ax.set_ylim(0, 297); ax.axis("off")
    ax.text(105, 286, title, ha="center", fontsize=13, weight="bold")
    if sub:
        ax.text(105, 279.5, sub, ha="center", fontsize=8, color="0.25")
    return fig, ax


class Grid:
    """Maps hole coordinates to page mm. mirror=True draws the solder side (board turned over left-right)."""
    def __init__(self, x0, ytop, s, mirror):
        self.x0, self.ytop, self.s, self.m = x0, ytop, s, mirror

    def __call__(self, c, r):
        cc = (NC + 1 - c) if self.m else c
        return self.x0 + cc * self.s, self.ytop - r * self.s


def draw_grid(ax, g, b, side):
    s = g.s
    x0, y0 = g(0.5 if not g.m else NC + 0.5, NR + 0.5)
    ax.add_patch(FancyBboxPatch((x0, y0), (NC) * s, (NR) * s, boxstyle="round,pad=0,rounding_size=1.5",
                                fc="#f6efd9" if side == "top" else "#f0f0f0", ec="0.35", lw=1.0, zorder=0))
    for c in range(1, NC + 1):
        for yy in (0.0, NR + 1.0):
            x, y = g(c, yy)
            ax.text(x, y, COLS[c - 1], ha="center", va="center", fontsize=7.5, weight="bold", color="#555")
    for r in range(1, NR + 1):
        for cc in (-0.35, NC + 1.0):
            x, y = g(cc, r)
            ax.text(x, y, str(r), ha="center", va="center", fontsize=7, weight="bold", color="#555")
    for c in range(1, NC + 1):
        for r in range(1, NR + 1):
            x, y = g(c, r)
            ax.add_patch(Circle((x, y), 0.30 * s, fc="#e2b46a" if side == "bottom" else "none", ec="#b08a48",
                                lw=0.4, zorder=1))
            ax.add_patch(Circle((x, y), 0.11 * s, fc="white", ec="none", zorder=1.1))
    for k in b.keepout:
        xa, ya = g(k[0], k[3])
        xb, yb = g(k[2], k[1])
        ax.add_patch(Rectangle((min(xa, xb), ya), abs(xb - xa), yb - ya, fc="none", ec="#c0392b", hatch="////",
                               lw=0.6, zorder=1.5, alpha=0.6))
        mx, my = g((k[0] + k[2]) / 2, (k[1] + k[3]) / 2)
        ax.text(mx, my, "ESP32 ANTENNA: leave empty", ha="center", va="center", fontsize=7, color="#c0392b",
                weight="bold", zorder=6, bbox=dict(fc="white", ec="none", alpha=0.85, pad=0.6))


def rect(ax, g, box, **kw):
    xa, ya = g(box[0], box[3])
    xb, yb = g(box[2], box[1])
    ax.add_patch(Rectangle((min(xa, xb), ya), abs(xb - xa), yb - ya, **kw))
    return (min(xa, xb) + max(xa, xb)) / 2, (ya + yb) / 2


def top_page(pdf, b, tag):
    fig, ax = page(pdf, f"ThermoX UNIVERSAL PCB - 1. PARTS SIDE (top)  [{tag}]",
                   "5 x 7 cm perfboard, 18 x 24 holes. Columns A-R, rows 1-24. Mark A, R, 1 and 24 on the board with a marker.")
    g = Grid(10, 270, 7.2, False)
    draw_grid(ax, g, b, "top")
    s = g.s
    esp = next(p for p in b.parts if p["ref"] == "U1")
    for p in b.parts:
        k = p["kind"]
        if k == "esp":
            continue
        if k == "term":
            cx, cy = rect(ax, g, p["body"], fc="#7fc97f", ec="#2e7d32", lw=1, zorder=3, alpha=0.9)
            ax.text(cx, cy - 1.0 * s, p["label"], ha="center", va="center", fontsize=8, weight="bold", zorder=7)
        elif k == "hdr":
            cx, cy = rect(ax, g, p["body"], fc="#333", ec="black", lw=0.8, zorder=3)
        elif k == "res" or k == "resup":
            pass
        if k in ("res", "dio") or k == "cap":
            (ha, _, _), (hc, _, _) = p["pins"]
            xa, ya = g(*ha); xc, yc = g(*hc)
            ax.plot([xa, xc], [ya, yc], color="#777", lw=1.2, zorder=3)
            fc = {"res": "#e8c99b", "dio": "#222", "cap": "#3b78c2"}[k]
            cx, cy = rect(ax, g, p["body"], fc=fc, ec="#555", lw=0.6, zorder=4)
            if k == "dio":       # stripe at the cathode
                hk = p["pins"][1][0]
                bx = p["body"]
                if ha[1] == hc[1]:
                    sx = bx[0] if hk[0] < ha[0] else bx[2] - 0.35
                    rect(ax, g, (sx, bx[1], sx + 0.35, bx[3]), fc="#ddd", ec="none", zorder=5)
                else:
                    sy = bx[1] if hk[1] < ha[1] else bx[3] - 0.35
                    rect(ax, g, (bx[0], sy, bx[2], sy + 0.35), fc="#ddd", ec="none", zorder=5)
            col = "white" if k in ("dio", "cap") else "black"
            vert = ha[0] == hc[0]
            ax.text(cx, cy, f"{p['ref']} {p['label']}", ha="center", va="center", fontsize=6.2 if not vert else 5.6,
                    color=col, rotation=90 if vert else 0, zorder=6, weight="bold")
        if k == "resup":
            (ha, _, _), (hc, _, _) = p["pins"]
            xa, ya = g(*ha); xc, yc = g(*hc)
            ax.add_patch(Circle((xa, ya), 0.42 * s, fc="#e8c99b", ec="#555", lw=0.6, zorder=4))
            ax.plot([xa, xc], [ya + 0.35 * s, ya + 0.35 * s], color="#777", lw=1.2, zorder=3)
            ax.plot([xc, xc], [ya + 0.35 * s, yc], color="#777", lw=1.2, zorder=3)
            ax.text(xa, ya + 0.85 * s, f"{p['ref']} {p['label']} standing", ha="center", fontsize=5.5, zorder=6,
                    weight="bold", bbox=dict(fc="white", ec="none", pad=0.3, alpha=0.8))
        if k == "pads":
            for h, net, lab in p["pins"]:
                x, y = g(*h)
                ax.add_patch(Circle((x, y), 0.38 * s, fc="none", ec="#c0392b", lw=1.6, zorder=5))
    # pins on top of everything, and header labels
    for p in b.parts:
        if p["kind"] == "esp":
            continue
        for h, net, lab in p["pins"]:
            x, y = g(*h)
            ax.add_patch(Circle((x, y), 0.17 * s, fc="#c9a227" if p["kind"] in ("hdr", "term") else "#555",
                                ec="black", lw=0.4, zorder=7))
    lab_pos = {"FAN": "above", "OLED": "above", "TEMP": "below", "BTN1": "above", "BTN2": "left", "BTSA": "left",
               "BTSB": "left"}
    for p in b.parts:
        if p["kind"] == "hdr":
            for h, net, lab in p["pins"]:
                x, y = g(*h)
                vert = p["body"][2] - p["body"][0] < 1.5
                if vert:
                    ax.text(x + 0.5 * s, y - 0.28 * s, lab, fontsize=5.2, va="center", ha="left", zorder=8, weight="bold",
                            color="#1a237e", bbox=dict(fc="white", ec="none", pad=0.2, alpha=0.85))
                else:
                    ax.text(x, y - 0.95 * s, lab, fontsize=5.0, va="center", ha="center", zorder=8, weight="bold",
                            color="#1a237e", rotation=90, bbox=dict(fc="white", ec="none", pad=0.2, alpha=0.85))
            bx = p["body"]
            if p["body"][2] - p["body"][0] < 1.5:
                x, y = g(bx[0], (bx[1] + bx[3]) / 2)
                ax.text(x - 0.12 * s, y, p["label"], fontsize=6.0, ha="right", va="center", weight="bold", zorder=8,
                        rotation=90, color="#2e7d32")
            elif p["ref"] == "BTN1":
                x, y = g(bx[2], (bx[1] + bx[3]) / 2)
                ax.text(x + 0.15 * s, y, p["label"], fontsize=7, ha="left", va="center", weight="bold", zorder=8,
                        color="#2e7d32", bbox=dict(fc="white", ec="none", pad=0.3, alpha=0.85))
            else:
                x, y = g((bx[0] + bx[2]) / 2, bx[1])
                ax.text(x, y + 0.25 * s, p["label"], fontsize=7, ha="center", va="bottom", weight="bold", zorder=8,
                        color="#2e7d32", bbox=dict(fc="white", ec="none", pad=0.3, alpha=0.85))
        if p["kind"] == "pads":
            for h, net, lab in p["pins"]:
                x, y = g(*h)
                txt = {"BAT": "BAT+ wire\n(battery +)", "LMI": "LM2596\nIN+"}.get(p["ref"], f"LM2596 {lab}")
                if p["ref"] == "LMO":
                    ax.text(x + 0.42 * s, y + 0.3 * s, lab, fontsize=4.6, ha="left", va="center", color="#c0392b",
                            weight="bold", zorder=8)
                else:
                    ax.text(x, y + 0.55 * s, txt, fontsize=5.5, ha="center", va="bottom", color="#c0392b",
                            weight="bold", zorder=8, bbox=dict(fc="white", ec="none", pad=0.2, alpha=0.85))
        if p["kind"] == "term":
            for h, net, lab in p["pins"]:
                x, y = g(*h)
                ax.text(x, y + 0.45 * s, lab, fontsize=6, ha="center", va="bottom", weight="bold", zorder=8)
    # ESP32: female header strips, pin names, module outline last (transparent)
    for col_ in (LX, b.rx):
        rect(ax, g, (col_ - 0.45, R0 - 0.5, col_ + 0.45, R0 + 14.5), fc="#222", ec="black", lw=0.6, zorder=2, alpha=0.25)
    for h, net, lab in esp["pins"]:
        x, y = g(*h)
        ax.add_patch(Circle((x, y), 0.17 * s, fc="#222" if net else "#bbb", ec="black", lw=0.4, zorder=7))
        left = h[0] == LX
        ax.text(x + (0.42 if left else -0.42) * s, y, lab, fontsize=4.8, ha="left" if left else "right", va="center",
                color="black" if net else "#999", zorder=8)
    rect(ax, g, esp["body"], fc="none", ec="#1565c0", lw=1.4, ls="--", zorder=9)
    mx, _ = g((esp["body"][0] + esp["body"][2]) / 2, 0)
    ax.text(mx, g(0, R0 + 7.5)[1], "U1  ESP32 DevKit 30-pin\non 2 x 1x15 female headers\n(plug it in LAST)",
            ha="center", va="center", fontsize=6.5, color="#1565c0", weight="bold", zorder=9,
            bbox=dict(fc="white", ec="none", pad=0.4, alpha=0.7))
    ax.text(mx, g(0, NR + 1.55)[1], "USB end of the ESP32 here (it sticks out past the board edge)", ha="center",
            fontsize=6.5, color="#1565c0", weight="bold")
    x, y = g(1, NR + 2.6)
    ax.text(x - 0.5 * s, y, "Red rings B23 / B24 = LM2596 OUT- / OUT+", fontsize=6, color="#c0392b", weight="bold",
            va="top")
    # legend
    ly = 52
    notes = [
        "Gold dots = header / terminal pins. Grey dots = part legs. Red rings = wire pads (no part, a wire is soldered here).",
        "R1, R2, R4, C4 lie FLAT under the ESP32 (between the two header rows): solder them before the female headers.",
        "D1, D2 (1N5822): the grey band (stripe) is the cathode. D2 stripe at D5, D1 stripe at P5. Their legs are thick:",
        "    open holes D5, J5, K5, P5 with a 1.5 mm drill bit.",
        "R6 stands up: body over P15, the other leg bent down into Q15.",
        "FAN, OLED, TEMP and BTN1 headers lie ACROSS (left to right). Read the pin names under each pin.",
        "Nothing under the ESP32 antenna (hatched area): no parts and no trails.",
    ]
    for i, n in enumerate(notes):
        ax.text(12, ly - i * 4.6, n, fontsize=7, va="top")
    pdf.savefig(fig); plt.close(fig)


def bottom_page(pdf, b, tag):
    fig, ax = page(pdf, f"ThermoX UNIVERSAL PCB - 2. SOLDER SIDE (bottom)  [{tag}]",
                   "Board turned over left to right: column A is now on the RIGHT, row 1 still at the top.")
    g = Grid(10, 270, 7.2, True)
    draw_grid(ax, g, b, "bottom")
    s = g.s
    for tr in b.trails:
        xs, ys = zip(*[g(*h) for h in tr["path"]])
        lw = 5.2 if tr["thick"] else 3.0
        ax.plot(xs, ys, "-", lw=lw + 1.2, color="white", solid_capstyle="round", zorder=3)
        ax.plot(xs, ys, "-", lw=lw, color=netcolor(tr["net"]), solid_capstyle="round", zorder=4, alpha=0.9)
    # net labels on the longest straight piece of each trail
    done = set()
    for tr in b.trails:
        cs = tr["corners"]
        segs = [(abs(a[0] - c[0]) + abs(a[1] - c[1]), a, c) for a, c in zip(cs, cs[1:])]
        if not segs:
            continue
        ln, a, c = max(segs, key=lambda z: z[0])
        key = (tr["net"], a, c)
        if ln < 2 or key in done:
            continue
        done.add(key)
        mx, my = g((a[0] + c[0]) / 2, (a[1] + c[1]) / 2)
        ax.text(mx, my, tr["net"], fontsize=5.4, ha="center", va="center", color="white", weight="bold", zorder=6,
                rotation=90 if a[0] == c[0] else 0,
                bbox=dict(fc=netcolor(tr["net"]), ec="none", pad=0.4, alpha=0.95))
    for w in b.wires:
        pts = [w["a"]] + w["via"] + [w["b"]]
        xs, ys = zip(*[g(*p) for p in pts])
        ax.plot(xs, ys, "-", lw=3.2, color="white", zorder=7)
        ax.plot(xs, ys, "--", lw=1.8, color=netcolor(w["net"]), zorder=8, dashes=(3, 1.5))
        i = w["lab"]
        lx, ly = g(*((pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2))
        ax.text(lx, ly, w["name"], fontsize=7, ha="center", va="center", weight="bold", zorder=9, color="white",
                bbox=dict(boxstyle="round,pad=0.25", fc=netcolor(w["net"]), ec="black", lw=0.5))
    for p in b.parts:
        for h, net, lab in p["pins"]:
            x, y = g(*h)
            if p["kind"] == "esp" and not net:
                ax.add_patch(Circle((x, y), 0.2 * s, fc="#bbb", ec="black", lw=0.4, zorder=10))
            else:
                ax.add_patch(Circle((x, y), 0.2 * s, fc="black", ec="white", lw=0.5, zorder=10))
    for w in b.wires:
        for h in (w["a"], w["b"]):
            x, y = g(*h)
            ax.add_patch(Circle((x, y), 0.26 * s, fc="none", ec=netcolor(w["net"]), lw=1.4, zorder=11))
    ly = 52
    items = [("GND", "ground"), ("BUS", "12 V after the fuse"), ("BAT+", "battery + (gauge, charging)"),
             ("CHG", "charger +"), ("5V", "5 V from the LM2596"), ("3V3", "3.3 V from the ESP32"), ("SIG", "signals")]
    for i, (n, d) in enumerate(items):
        x = 12 + (i % 4) * 48
        y = ly - (i // 4) * 5.5
        ax.add_patch(Rectangle((x, y - 1.2), 7, 2.4, fc=netcolor(n) if n != "SIG" else SIG, ec="none"))
        ax.text(x + 9, y, f"{n}: {d}", fontsize=6.6, va="center")
    notes = [
        "Thick lines: bare tinned copper wire 0.8-1 mm (12 V, battery +, charger, top ground). Thin lines: a solder bridge",
        "    or a bare wire from hole to hole. Black dots are part legs: the trail is soldered to them.",
        "Dashed W1-W4: insulated wire (0.5 mm2 or thinner). They may cross the bare trails. Lay them flat.",
        "Holes next to each other that belong to different colours must NOT touch. Check every joint with a meter.",
    ]
    for i, n in enumerate(notes):
        ax.text(12, ly - 13 - i * 4.4, n, fontsize=7, va="top")
    pdf.savefig(fig); plt.close(fig)


def seg_text(tr):
    cs = tr["corners"]
    return " > ".join(hn(h) for h in cs)


PLACE = [
    ("1", "R1 10k", "D14 to J14", "flat, under the ESP32"),
    ("2", "R2 4.7k", "D20 to J20", "flat, under the ESP32"),
    ("3", "R4 22k", "D11 to H11", "flat, under the ESP32"),
    ("4", "C4 100 nF", "D12 and F12", "under the ESP32, keep it low"),
    ("5", "R3 100k", "B4 to B8", "flat, along column B"),
    ("6", "R5 100k", "O15 to O19", "flat, along column O"),
    ("7", "R6 33k", "P15 (body) and Q15", "standing"),
    ("8", "D2 1N5822", "J5 to D5", "stripe at D5 (open the holes to 1.5 mm)"),
    ("9", "D1 1N5822", "K5 to P5", "stripe at P5 (open the holes to 1.5 mm)"),
    ("10", "ESP32 female headers 1x15", "C10-C24 and {R}10-{R}24", "plug the ESP32 in them to align, then solder"),
    ("11", "BTN2 2-pin header", "A15 (GND), A16 (B2)", ""),
    ("12", "BTS A 3-pin header", "A17 R_EN, A18 RPWM, A19 LPWM", ""),
    ("13", "BTS B 3-pin header", "A22 L_EN, A23 GND, A24 VCC (5 V)", ""),
    ("14", "FAN 4-pin header", "O8 PWM, P8 12V, Q8 FG, R8 GND", "lies across"),
    ("15", "OLED 4-pin header", "O12 SDA, P12 SCL, Q12 GND, R12 VCC", "lies across"),
    ("16", "BTN1 2-pin header", "P16 (B1), Q16 (GND)", "lies across"),
    ("17", "TEMP 3-pin header", "P20 DQ, Q20 GND, R20 VCC (3.3 V)", "lies across"),
    ("18", "POWER screw terminal 2-pin", "E2 GND, G2 12V", "wire openings toward the top edge"),
    ("19", "CHARGE screw terminal 2-pin", "K2 +, M2 -", "wire openings toward the top edge"),
]


def steps_page(pdf, b, tag):
    fig, ax = page(pdf, f"ThermoX UNIVERSAL PCB - 3. BUILD STEPS  [{tag}]")
    y = 272
    rc = COLS[b.rx - 1]

    def head(t):
        nonlocal y
        ax.text(10, y, t, fontsize=9, weight="bold", va="top"); y -= 5.5

    def line(t, fs=7.0, x=12, dy=4.1, **kw):
        nonlocal y
        ax.text(x, y, t, fontsize=fs, va="top", **kw); y -= dy
    head("A. PREPARE")
    line(f"[ ] Use a 5 x 7 cm board (18 x 24 holes). This PDF is for ESP32 pin rows {b.rows} mm apart: right header in column {rc}.")
    line("[ ] Write A ... R along the top edge and 1 ... 24 down the left edge, on BOTH sides (on the bottom A is on the right).")
    line("[ ] Open D5, J5, K5 and P5 with a 1.5 mm drill bit (the 1N5822 legs are thick).")
    y -= 1.5
    head("B. PARTS ON TOP (low parts first). Push each leg through, bend it a little, solder, cut.")
    ax.text(12, y, "Step   Part                          Holes                                   Note", fontsize=6.8,
            family="monospace", weight="bold", va="top"); y -= 4.2
    for n, part, holes, note in PLACE:
        holes = holes.replace("{R}", rc)
        ax.text(12, y, f"[ ] {n:<3} {part:<29} {holes:<39} {note}", fontsize=6.6, family="monospace", va="top")
        y -= 3.9
    y -= 1.5
    head("C. TRAILS ON THE BOTTOM (page 2). Follow each line hole by hole; '>' means a corner.")
    ax.text(12, y, "Net     From > corner > ... > to                            Wire", fontsize=6.8, family="monospace",
            weight="bold", va="top"); y -= 4.2
    order = ["GND", "BUS", "CHG", "BAT+", "5V", "3V3", "BATS", "FG", "DQ", "PWM", "SCL", "SDA", "CHGS", "BTN1", "BTN2",
             "R_EN", "RPWM", "LPWM", "L_EN"]
    trs = sorted(b.trails, key=lambda tr: (order.index(tr["net"]) if tr["net"] in order else 99))
    for tr in trs:
        kind = "bare 0.8-1 mm" if tr["thick"] else ("bridge" if len(tr["path"]) == 2 else "bare / solder")
        ax.text(12, y, f"[ ] {tr['net']:<6} {seg_text(tr):<52} {kind}", fontsize=6.4, family="monospace", va="top")
        y -= 3.55
    pdf.savefig(fig); plt.close(fig)


def steps2_page(pdf, b, tag):
    fig, ax = page(pdf, f"ThermoX UNIVERSAL PCB - 4. WIRES, CHECKS, FIRST POWER-UP  [{tag}]")
    y = 272

    def head(t):
        nonlocal y
        ax.text(10, y, t, fontsize=9, weight="bold", va="top"); y -= 5.5

    def line(t, fs=7.0, x=12, dy=4.1, **kw):
        nonlocal y
        ax.text(x, y, t, fontsize=fs, va="top", **kw); y -= dy
    head("D. INSULATED WIRES ON THE BOTTOM (dashed on page 2)")
    for w in b.wires:
        line(f"[ ] {w['name']}  {w['net']:<4} from {hn(w['a']):<4} to {hn(w['b']):<4}  ({w['note']})", family="monospace")
    line("Lay them flat along the path drawn on page 2, not across the ESP32 antenna end.", dy=5)
    head("E. CHECK WITH A METER (beep mode), ESP32 NOT plugged in, nothing connected")
    for t in [
        "[ ] Must NOT beep:  B2 (BAT+) to E2 (GND)   G2 (12V) to E2   K2 (CHG) to M2 (GND)   B24 (5V) to B23 (GND)",
        f"[ ] Must NOT beep:  R24 (3V3) to Q23 (GND)   B2 to G2   K2 to G2   each pin to its neighbours on the headers",
        "[ ] Must beep:      E2 to M2, E2 to Q12, E2 to R8 (all GND)   G2 to I2, G2 to P8 (12V)   B2 to D5 (BAT+)",
        f"[ ] Must beep:      B24 to A24 and C24 (5V)   {COLS[b.rx - 1]}24 to R20 and J14 (3V3)   K2 to O19 (CHG, via W4)",
    ]:
        line(t, family="monospace", fs=6.6)
    y -= 1.5
    head("F. OFF-BOARD WIRING (page 5), then FIRST POWER-UP without the ESP32")
    for t in [
        "[ ] Set the LM2596 to 5.0 V with a meter BEFORE wiring it. Set the USB-C trigger board to 12 V and measure it.",
        "[ ] Wire the LM2596: IN+ to I2, OUT+ to B24, OUT- to B23 (its IN- is the same as OUT-, no wire needed).",
        "[ ] Battery on, switch on BATT: G2 = battery voltage, B24 = 5.0 V, B2 = battery voltage. Switch to OFF: G2 = 0 V.",
        "[ ] Switch OFF, charger in the DC jack: K2 = about 12.6 V, G2 = about 12 V (D1 feeds the board), battery rises.",
        "[ ] Everything OK: switch off, plug in the ESP32 (USB end at the board edge), connect the headers.",
    ]:
        line(t, fs=6.8)
    y -= 1.5
    head("G. TEST AND USE")
    for t in [
        "[ ] Upload ThermoX_Bench/ThermoX_Bench.ino, Serial Monitor 115200: check TEMP, BATT, CHARGER, B1/B2, fan (f), Peltier (h, c).",
        "[ ] Upload ThermoX/ThermoX.ino. Set ENABLE_BATTERY_SENSE = true (the battery divider R3/R4 is on this board).",
        "    ENABLE_CHARGE_DETECT stays true (R5/R6 are on this board).",
        "[ ] Pins used: Button 1 GPIO18, Button 2 GPIO33, fan PWM GPIO23, fan FG GPIO35, battery GPIO36 (VP),",
        "    charger GPIO19, DS18B20 GPIO14, OLED SDA 21 / SCL 22, BTS7960 R_EN 25, RPWM 26, LPWM 27, L_EN 13.",
        "[ ] The DS18B20 runs from 3.3 V on this board (TEMP VCC = 3.3 V). That is fine for the DS18B20.",
    ]:
        line(t, fs=6.8)
    pdf.savefig(fig); plt.close(fig)


def wiring_page(pdf, b, tag):
    fig, ax = page(pdf, f"ThermoX UNIVERSAL PCB - 5. OFF-BOARD WIRING AND PARTS  [{tag}]")

    def box(x, y, w, h, t, fc="#f1f3f5", fs=6.6, bold=False):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6", fc=fc, ec="0.35", lw=0.8))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs, weight="bold" if bold else None)

    def wire(pts, color, lw=1.6, label=None, lpos=0.5, ls="-", at=None):
        xs, ys = zip(*pts)
        ax.plot(xs, ys, ls, color=color, lw=lw, solid_capstyle="round")
        if label:
            i = max(1, int(len(pts) * lpos))
            lx, ly = at or ((pts[i - 1][0] + pts[i][0]) / 2, (pts[i - 1][1] + pts[i][1]) / 2 + 1.4)
            ax.text(lx, ly, label, fontsize=5.4,
                    ha="center", color=color, weight="bold", bbox=dict(fc="white", ec="none", pad=0.2, alpha=0.9))
    R, K, O, P = "#d62728", "#222222", "#ff7f0e", "#e377c2"
    box(8, 236, 32, 24, "3S2P battery\n21700 x 6\n+ 3S BMS\n(P+  P-)", fc="#fff3cd", bold=True)
    box(66, 242, 30, 16, "SW1 toggle ON-OFF-ON\non the case\nBATT | OFF | USB", fc="#e3f2fd")
    box(108, 244, 28, 12, "F1 inline fuse\n10 A slow-blow", fc="#fde2e2")
    box(148, 236, 32, 26, "BTS7960\nB+  B-\n\nC1 2200 uF 25 V\nscrewed in with\nB+ (+) and B- (-)",
        fc="#e8f5e9")
    box(186, 243, 18, 14, "Peltier\nTEC1-12706", fc="#e8f5e9")
    box(66, 204, 30, 12, "USB-C trigger board\nset to 12 V", fc="#e3f2fd")
    box(100, 162, 52, 34, "THIS BOARD\nPOWER  E2 = GND, G2 = 12V\nB2 = BAT+ wire\nCHARGE  K2 = +, M2 = -\n"
        "LM2596  I2 = IN+, B24 = OUT+,\nB23 = OUT-", fc="#f6efd9", bold=True, fs=6.4)
    box(162, 170, 42, 16, "LM2596S module\nset to 5.0 V first", fc="#efebe9")
    box(52, 168, 30, 12, "DC jack 5.5x2.1\non the case", fc="#fce4ec")
    box(8, 168, 32, 12, "12.6 V 2 A Li-ion\ncharger (3S)", fc="#fce4ec")
    wire([(40, 254), (66, 254)], R, 2.8, "P+ to BATT  1.5 mm2")
    wire([(96, 250), (108, 250)], R, 2.8, "COM")
    wire([(136, 250), (148, 250)], R, 2.8, "1.5 mm2")
    wire([(142, 250), (142, 196)], R, 1.6, "12V to G2\n0.75 mm2", 0.5)
    wire([(81, 216), (81, 242)], R, 2.0, "12V to USB lug", at=(88, 236))
    wire([(24, 236), (24, 228), (164, 228), (164, 236)], K, 2.8, "P- to BTS7960 B-  1.5 mm2", 0.5, at=(106, 229.6))
    wire([(124, 228), (124, 196)], K, 1.6, "P- to E2\n0.75 mm2", 0.5)
    wire([(72, 216), (72, 228)], K, 1.6)
    ax.text(70.5, 220, "trigger -", fontsize=5.4, ha="right", color=K, weight="bold")
    wire([(40, 242), (48, 242), (48, 190), (100, 190)], O, 1.6, "BAT+ to B2  0.75 mm2", 0.8)
    wire([(40, 174), (52, 174)], P, 1.6, "+ / -")
    wire([(82, 174), (100, 174)], P, 1.6, "K2 / M2")
    wire([(152, 178), (162, 178)], "#8c564b", 1.6, "3 wires")
    wire([(180, 250), (186, 250)], "#555", 2.8)
    ax.text(183, 253, "M+ M-", fontsize=5.4, ha="center", color="#555", weight="bold")
    ax.text(10, 152, "Headers to the parts (Dupont wires):", fontsize=8, weight="bold")
    hdrs = [
        "FAN (O8-R8): PWM blue, 12V red, FG yellow, GND black (SUNON 4-wire fan).",
        "OLED (O12-R12): SDA, SCL, GND, VCC (3.3 V). Match the names printed on the OLED, not the order.",
        "TEMP (P20-R20): DQ yellow, GND black, VCC red (DS18B20 probe).",
        "BTN1 (P16-Q16) and BTN2 (A15-A16): one button leg to B1/B2, the other to GND.",
        "BTS A (A17-A19): R_EN, RPWM, LPWM.   BTS B (A22-A24): L_EN, GND, VCC (5 V). R_IS and L_IS stay open.",
    ]
    yy = 146
    for h in hdrs:
        ax.text(12, yy, h, fontsize=6.8, va="top"); yy -= 4.2
    yy -= 3
    ax.text(10, yy, "Parts for this board", fontsize=8, weight="bold"); yy -= 5
    bom = [
        "5 x 7 cm universal PCB (single-sided, 18 x 24 holes)      ESP32 DevKit 30-pin + 2 x 1x15 female headers",
        "R1 10k, R2 4.7k, R3 100k, R4 22k, R5 100k, R6 33k (1/4 W)   C4 100 nF ceramic      D1, D2: 1N5822",
        "2 x 2-pin screw terminal 5.08 mm (KF301-2P)                   Male headers 2.54 mm: 4+4+3+3+3+2+2 pins",
        "Bare tinned copper wire 0.8-1 mm, thin insulated wire (W1-W4), solder",
        "Off-board: SW1 ON-OFF-ON toggle, inline fuse holder + 10 A slow-blow fuse, C1 2200 uF 25 V, DC jack 5.5x2.1,",
        "    LM2596S module, USB-C PD trigger board, 12.6 V 2 A Li-ion charger (3S), wires 1.5 / 0.75 / 0.5 mm2",
    ]
    for t in bom:
        ax.text(12, yy, t, fontsize=6.7, va="top"); yy -= 4.1
    yy -= 3
    ax.text(10, yy, "Safety", fontsize=8, weight="bold"); yy -= 5
    safety = [
        "The Peltier current (up to about 7 A) goes battery -> SW1 -> fuse -> BTS7960 with thick wire. It does NOT go through this board.",
        "B2 (BAT+) is the battery + before the fuse: keep its wire short and check it never touches ground.",
        "Only one source at a time: never plug the USB-C charger and the DC charger in together.",
        "Charge with SW1 in the middle (OFF). Use a 12.6 V (3S) charger only, never 21 V.",
        "Trigger board at 12 V only. On USB-C keep the Peltier at 40-60 % (phone slider). On battery 80 % or less with the MTS-103.",
        "Not built and tested yet: lay the parts on the board before soldering and check every step with a meter.",
    ]
    for t in safety:
        ax.text(12, yy, t, fontsize=6.7, va="top"); yy -= 4.1
    pdf.savefig(fig); plt.close(fig)


def main():
    ok = True
    for spacing in (25.4, 22.86):
        b = design(spacing)
        err, _ = check(b)
        tag = f"ESP32 rows {spacing} mm"
        if err:
            ok = False
            print(f"rows {spacing}: {len(err)} problems")
            for e in err:
                print("   ", e)
            continue
        name = os.path.join(OUT, f"thermox_perfboard_5x7_rows{spacing}.pdf")
        with PdfPages(name) as pdf:
            top_page(pdf, b, tag)
            bottom_page(pdf, b, tag)
            steps_page(pdf, b, tag)
            steps2_page(pdf, b, tag)
            wiring_page(pdf, b, tag)
        print(f"rows {spacing} OK -> {os.path.basename(name)}  ({len(b.trails)} trails, {len(b.wires)} wires)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
