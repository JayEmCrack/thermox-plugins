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
    res("R6", "33k", "N15", "N20", "CHGS", "GND")
    t("3V3", (X, 24), "R24", "R12")
    t("GND", (X, 23), "Q23", "Q11")
    t("PWM", (X, 10), "O10", "O8")
    t("SCL", (X, 11), "P11", "P12")
    t("SDA", (X, 14), "O14", "O12")
    t("CHGS", (X, 15), "O15")
    t("GND", "N20", "N23")
    t("BTN1", (X, 16), "P16")
    # ---- insulated wires on the bottom (they may cross trails; keep them away from the antenna end)
    b.wire("W1", "GND", "A15", "F15", [], "button 2 GND")
    b.wire("W2", "FG", "B14", "Q8", [(2.4, 13.5), (X + 0.65, 13.5), (X + 0.65, 9.7), (17.0, 9.7)], "fan tach", 1)
    b.wire("W3", "DQ", "D19", "P20", [(4.0, 18.5), (X + 0.65, 18.5), (X + 0.65, 20.5), (16.0, 20.5)], "temp sensor data", 1)
    b.wire("W4", "CHG", "K4", "O19", [(11.0, 3.6), (X + 1.5, 3.6), (X + 1.5, 19.5), (15.0, 19.5)], "charger detect", 2)
    return b


# ------------------------------------------------------------------ checks
FW_PINS = {"PIN_BTN_DOWN": "BTN1", "PIN_BTN_UP": "BTN2", "PIN_SDA": "SDA", "PIN_SCL": "SCL", "PIN_LPWM": "LPWM",
           "PIN_RPWM": "RPWM", "PIN_LEN": "L_EN", "PIN_REN": "R_EN", "PIN_ONEWIRE": "DQ", "PIN_FAN_PWM": "PWM",
           "PIN_FAN_TACH": "FG", "PIN_CHG_DET": "CHGS", "PIN_BATT_ADC": "BATS"}
# what every part pin must be connected to (written from the schematic, not from the layout)
NETLIST = {
    "R1": ("FG", "3V3"), "R2": ("DQ", "3V3"), "R3": ("BAT+", "BATS"), "R4": ("BATS", "GND"), "C4": ("BATS", "GND"),
    "R5": ("CHG", "CHGS"), "R6": ("CHGS", "GND"), "D1": ("CHG", "BUS"), "D2": ("CHG", "BAT+"),
    "POWER": ("GND", "BUS"), "CHARGE": ("CHG", "GND"), "BAT": ("BAT+",), "LMI": ("BUS",), "LMO": ("GND", "5V"),
    "FAN": ("PWM", "BUS", "FG", "GND"), "OLED": ("SDA", "SCL", "GND", "3V3"), "TEMP": ("DQ", "GND", "3V3"),
    "BTN1": ("BTN1", "GND"), "BTN2": ("GND", "BTN2"), "BTSA": ("R_EN", "RPWM", "LPWM"), "BTSB": ("L_EN", "GND", "5V"),
}
GPIO = {"VP": 36, "VN": 39, "TX0": 1, "RX0": 3, "TX2": 17, "RX2": 16, "EN": None, "GND": None, "VIN": None, "3V3": None}


def check_firmware(b):
    """The ESP32 pins on the board must be the pins in ThermoX.ino, and every part must match the schematic."""
    import re
    err = []
    ino = os.path.join(OUT, "..", "ThermoX", "ThermoX.ino")
    src = open(ino).read()
    fw = {m.group(1): int(m.group(2)) for m in re.finditer(r"constexpr uint8_t (PIN_\w+)\s*=\s*(\d+);", src)}
    esp = next(p for p in b.parts if p["ref"] == "U1")
    by_net = {}
    for h, net, lab in esp["pins"]:
        g = GPIO.get(lab, int(lab[2:]) if lab.startswith("IO") else None)
        if net and g is not None:
            by_net[net] = g
    for const, net in FW_PINS.items():
        if const not in fw:
            err.append(f"{const} not found in ThermoX.ino")
        elif by_net.get(net) != fw[const]:
            err.append(f"{net}: board uses GPIO{by_net.get(net)}, ThermoX.ino {const} = {fw[const]}")
    for p in b.parts:
        if p["ref"] in NETLIST and tuple(n for _, n, _ in p["pins"]) != NETLIST[p["ref"]]:
            err.append(f"{p['ref']} pins {[n for _, n, _ in p['pins']]} do not match the schematic {NETLIST[p['ref']]}")
    missing = set(NETLIST) - {p["ref"] for p in b.parts}
    if missing:
        err.append(f"parts missing from the layout: {sorted(missing)}")
    return err


def check(b):
    err, owner = check_firmware(b), {}

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
    fig = plt.figure(figsize=(210 / 25.4, 297 / 25.4))
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
    fig, ax = page(pdf, f"ThermoX UNIVERSAL PCB - 2. PARTS SIDE, ZOOM (not to scale)  [{tag}]",
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
        "R5 and R6 lie flat side by side: R6 from N15 to N20, R5 from O15 to O19.",
        "FAN, OLED, TEMP and BTN1 headers lie ACROSS (left to right). Read the pin names under each pin.",
        "Nothing under the ESP32 antenna (hatched area): no parts and no trails.",
    ]
    for i, n in enumerate(notes):
        ax.text(12, ly - i * 4.6, n, fontsize=7, va="top")
    pdf.savefig(fig); plt.close(fig)


def bottom_page(pdf, b, tag):
    fig, ax = page(pdf, f"ThermoX UNIVERSAL PCB - 3. SOLDER SIDE, ZOOM (not to scale)  [{tag}]",
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


BOARD_W, BOARD_H = 50.0, 70.0      # mm, the 5 x 7 cm universal PCB
DRILL15 = ("D5", "J5", "K5", "P5")   # 1N5822 legs


def true_grid(left, top, mirror):
    """1:1 grid: hole A1 sits where it is on a real 5 x 7 cm board whose top-left corner is (left, top) mm."""
    s = 2.54
    mx = (BOARD_W - (NC - 1) * s) / 2
    my = (BOARD_H - (NR - 1) * s) / 2
    return Grid(left + mx - s, top - my + s, s, mirror)


def true_template(ax, b, left, top, side):
    g = true_grid(left, top, side == "bottom")
    s = g.s
    ax.add_patch(Rectangle((left, top - BOARD_H), BOARD_W, BOARD_H, fc="#fbf6e9" if side == "top" else "#f2f2f2",
                           ec="black", lw=0.6, ls=(0, (4, 2))))
    for c in range(1, NC + 1):
        x, _ = g(c, 0)
        ax.text(x, top - 0.9, COLS[c - 1], ha="center", va="center", fontsize=3.6, weight="bold", color="#444")
    for r in range(1, NR + 1):
        _, y = g(0, r)
        xr = left + BOARD_W - 0.9 if side == "top" else left + 0.9     # top copy: left margin holds header names
        ax.text(xr, y, str(r), ha="center", va="center", fontsize=3.0, weight="bold", color="#444")
    used = {}
    for p in b.parts:
        for h, net, lab in p["pins"]:
            used[h] = p
    for c in range(1, NC + 1):
        for r in range(1, NR + 1):
            x, y = g(c, r)
            if (c, r) in used:
                ax.add_patch(Circle((x, y), 0.55, fc="black", ec="none", zorder=6))
            else:
                ax.add_patch(Circle((x, y), 0.5, fc="none", ec="#999", lw=0.25, zorder=2))
    for k in b.keepout:
        xa, ya = g(k[0], k[3]); xb, yb = g(k[2], k[1])
        ax.add_patch(Rectangle((min(xa, xb), ya), abs(xb - xa), yb - ya, fc="none", ec="#c0392b", hatch="//////",
                               lw=0.3, zorder=1, alpha=0.5))
        mx_, my_ = g((k[0] + k[2]) / 2, (k[1] + k[3]) / 2)
        ax.text(mx_, my_, "ANTENNA: empty", fontsize=3.4, ha="center", va="center", color="#c0392b", weight="bold",
                zorder=7, bbox=dict(fc="white", ec="none", pad=0.2, alpha=0.8))
    for h in DRILL15:
        x, y = g(*H(h))
        ax.add_patch(Circle((x, y), 1.0, fc="none", ec="#1565c0", lw=0.6, zorder=7))
    if side == "top":
        esp = next(p for p in b.parts if p["ref"] == "U1")
        for col_ in (LX, b.rx):
            rect(ax, g, (col_ - 0.45, R0 - 0.5, col_ + 0.45, R0 + 14.5), fc="#999", ec="black", lw=0.3, alpha=0.35,
                 zorder=3)
        bx = esp["body"]
        rect(ax, g, (bx[0], bx[1], bx[2], min(bx[3], NR + 0.9)), fc="none", ec="#1565c0", lw=0.5, ls=(0, (3, 1.5)),
             zorder=8)
        cx, _ = g((bx[0] + bx[2]) / 2, 0)
        ax.text(cx, g(0, 17)[1], "ESP32\n(plug in last)\nUSB end down", fontsize=3.8, ha="center", va="center",
                color="#1565c0", weight="bold", zorder=9, bbox=dict(fc="white", ec="none", pad=0.3, alpha=0.75))
        for p in b.parts:
            k = p["kind"]
            if k in ("esp",):
                continue
            if p.get("body"):
                fc = {"term": "#a5d6a7", "hdr": "#cfcfcf", "res": "#f0d9b5", "dio": "#555", "cap": "#90caf9",
                      "resup": "#f0d9b5"}[k]
                cx, cy = rect(ax, g, p["body"], fc=fc, ec="black", lw=0.35, zorder=4, alpha=0.9)
            if k == "dio":
                (ha, _, _), (hk, _, _) = p["pins"]
                bx = p["body"]
                sx = bx[0] if hk[0] < ha[0] else bx[2] - 0.4
                rect(ax, g, (sx, bx[1], sx + 0.4, bx[3]), fc="white", ec="none", zorder=5)
                ax.text(cx, cy, p["ref"], fontsize=4.2, ha="center", va="center", color="white",
                        weight="bold", zorder=7)
            elif k in ("res", "cap"):
                (ha, _, _), (hc, _, _) = p["pins"]
                txt = "C4 104" if k == "cap" else f"{p['ref']} {p['label']}"
                ax.text(cx, cy, txt, fontsize=3.1, ha="center", va="center", weight="bold",
                        zorder=7, rotation=90 if ha[0] == hc[0] else 0)
            elif k == "resup":
                x, y = g(*p["pins"][0][0])
                ax.text(x - 0.9, y + 1.5, "R6 33k", fontsize=3.0, ha="center", weight="bold", zorder=7)
            elif k == "term":
                ax.text(cx, cy - 2.0, p["label"], fontsize=3.8, ha="center", va="center", weight="bold", zorder=7)
                for h, net, lab in p["pins"]:
                    x, y = g(*h)
                    ax.text(x, y + 1.3, lab, fontsize=3.2, ha="center", weight="bold", zorder=7)
            elif k == "hdr":
                vert = p["body"][2] - p["body"][0] < 1.5
                for h, net, lab in p["pins"]:
                    x, y = g(*h)
                    if vert and (h[0] + 1, h[1]) in used:
                        continue            # a wire pad sits there: the pin names are under the board
                    if vert:
                        ax.text(x + 1.0, y, lab, fontsize=2.7, ha="left", va="center", zorder=7, color="#1a237e",
                                weight="bold")
                    else:
                        ax.text(x, y - 1.0, lab, fontsize=2.7, ha="center", va="top", zorder=7, color="#1a237e",
                                weight="bold", rotation=90)
                bx = p["body"]
                if vert:
                    x, y = g(bx[0], (bx[1] + bx[3]) / 2)
                    ax.text(x - 0.15, y, p["label"], fontsize=3.2, ha="right", va="center", rotation=90,
                            weight="bold", color="#2e7d32", zorder=7)
                elif p["ref"] == "BTN1":
                    x, y = g(bx[2], (bx[1] + bx[3]) / 2)
                    ax.text(x + 0.3, y, p["label"], fontsize=3.4, ha="left", va="center", weight="bold",
                            color="#2e7d32", zorder=7)
                else:
                    x, y = g((bx[0] + bx[2]) / 2, bx[1])
                    ax.text(x, y + 0.3, p["label"], fontsize=3.4, ha="center", va="bottom", weight="bold",
                            color="#2e7d32", zorder=7)
            elif k == "pads":
                for h, net, lab in p["pins"]:
                    x, y = g(*h)
                    ax.add_patch(Circle((x, y), 1.0, fc="none", ec="#c0392b", lw=0.7, zorder=7))
                    txt = {"BAT": "BAT+", "LMI": "LM IN+"}.get(p["ref"], "LM " + lab)
                    if p["ref"] == "LMO":
                        pass
                    else:
                        ax.text(x, y + 1.2, txt, fontsize=3.0, ha="center", va="bottom", color="#c0392b",
                                weight="bold", zorder=8)
        ax.text(left + 1, top - BOARD_H - 1.5, "BTS B: A22 L_EN, A23 GND, A24 VCC.  Red rings: B23 = LM2596 OUT-, "
                "B24 = LM2596 OUT+", fontsize=3.6, va="top", color="#c0392b", weight="bold")
    else:
        for tr in b.trails:
            xs, ys = zip(*[g(*h) for h in tr["path"]])
            ax.plot(xs, ys, "-", lw=2.6 if tr["thick"] else 1.5, color=netcolor(tr["net"]), solid_capstyle="round",
                    zorder=4, alpha=0.9)
        for w in b.wires:
            pts = [w["a"]] + w["via"] + [w["b"]]
            xs, ys = zip(*[g(*q) for q in pts])
            ax.plot(xs, ys, "--", lw=0.9, color=netcolor(w["net"]), zorder=5, dashes=(2.5, 1.2))
            i = w["lab"]
            lx, ly = g((pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2)
            ax.text(lx, ly, w["name"], fontsize=3.4, ha="center", va="center", weight="bold", color="white", zorder=9,
                    bbox=dict(boxstyle="round,pad=0.15", fc=netcolor(w["net"]), ec="none"))


def truesize_page(pdf, b, tag):
    fig, ax = page(pdf, f"ThermoX UNIVERSAL PCB - TRUE SIZE (1:1)  [{tag}]",
                   "Print at 100 % / Actual size (NOT 'fit to page'). Check the 50 mm bar with a ruler before you cut.")
    top = 268
    true_template(ax, b, 22, top, "top")
    true_template(ax, b, 128, top, "bottom")
    ax.text(47, top + 2.5, "A. PARTS SIDE (paste this one)", ha="center", fontsize=8, weight="bold")
    ax.text(153, top + 2.5, "B. SOLDER SIDE (keep next to you)", ha="center", fontsize=8, weight="bold")
    ax.text(153, top - BOARD_H - 3, "Seen from the bottom: column A is on the RIGHT", ha="center", fontsize=6)
    # 50 mm scale bar
    y = top - BOARD_H - 12
    ax.plot([22, 72], [y, y], color="black", lw=1.2)
    for i in range(6):
        ax.plot([22 + 10 * i] * 2, [y - 1.2, y + 1.2], color="black", lw=0.8)
    ax.text(47, y - 4, "50 mm  (A1 to R1 = 43.18 mm, A1 to A24 = 58.42 mm)", ha="center", fontsize=6.5)
    legend = [
        ("black dot", "a part leg / pin goes in this hole"),
        ("red ring", "solder a wire here (no part)"),
        ("blue ring", "open this hole with a 1.5 mm drill (thick 1N5822 legs)"),
        ("white band", "diode stripe (cathode) side"),
        ("dashed blue", "ESP32 outline: it sits on the two grey female headers"),
    ]
    yy = y - 12
    ax.text(14, yy, "HOW TO USE THIS PAGE", fontsize=9, weight="bold"); yy -= 6
    steps = [
        "1. Print this page at 100 % (Actual size). Measure the 50 mm bar. If it is not 50 mm, fix the printer setting.",
        "2. Cut copy A along the dashed line. Lay it on the PARTS side of the 5 x 7 cm board, letters A-R at the top.",
        "3. Push a needle through the corner holes A1, R1, A24 and R24 into the board holes so every printed hole sits",
        "   on a real hole. Tape the paper down (thin double-sided tape at the edges).",
        "4. Push each part through the paper where it is drawn: low parts first (R1, R2, R4, C4 under the ESP32), then",
        "   R3, R5, R6, D1, D2 (white band = stripe), the 2 female headers, the male headers, the 2 screw terminals.",
        "5. Turn the board over. Copy B shows the same holes seen from the bottom: make every coloured line with bare",
        "   tinned wire / solder from hole to hole, and the dashed W1-W4 with thin insulated wire.",
        "6. Use pages 2-4 (big drawings and the hole-by-hole checklist) and tick each line when it is done.",
    ]
    for t in steps:
        ax.text(14, yy, t, fontsize=7, va="top"); yy -= 4.3
    yy -= 3
    for i, (k, d) in enumerate(legend):
        ax.text(14, yy - i * 4.2, f"{k}:", fontsize=7, weight="bold", va="top")
        ax.text(38, yy - i * 4.2, d, fontsize=7, va="top")
    yy -= 5 * 4.2 + 3
    ax.add_patch(Rectangle((12, yy - 13), 186, 15, fc="#fff3cd", ec="#b26a00", lw=0.8))
    ax.text(15, yy, "TWO CAPACITORS:", fontsize=7.5, weight="bold", va="top")
    ax.text(15, yy - 4.3, "C4 = 100 nF ceramic (marked 104), ON this board in D12 and F12 (blue, under the ESP32). "
            "No + or -, any direction.", fontsize=7, va="top")
    ax.text(15, yy - 8.6, "C1 = 2200 uF 25 V electrolytic, NOT on this board: screw it into the BTS7960 B+ and B- "
            "terminals, stripe (-) to B-. See the wiring diagram, page 6.", fontsize=7, va="top")
    yy -= 19
    items = [("GND", "ground"), ("BUS", "12 V"), ("BAT+", "battery +"), ("CHG", "charger +"), ("5V", "5 V"),
             ("3V3", "3.3 V"), ("SIG", "signals")]
    for i, (n, d) in enumerate(items):
        x = 14 + i * 27
        ax.add_patch(Rectangle((x, yy - 1.2), 6, 2.4, fc=netcolor(n) if n != "SIG" else SIG, ec="none"))
        ax.text(x + 7.5, yy, d, fontsize=6.5, va="center")
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
    ("7", "R6 33k", "N15 to N20", "flat, along column N"),
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
    fig, ax = page(pdf, f"ThermoX UNIVERSAL PCB - 4. BUILD CHECKLIST  [{tag}]")
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
    head("C. TRAILS ON THE BOTTOM (page 3). Follow each line hole by hole; '>' means a corner.")
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
    fig, ax = page(pdf, f"ThermoX UNIVERSAL PCB - 5. WIRES, CHECKS, FIRST POWER-UP  [{tag}]")
    y = 272

    def head(t):
        nonlocal y
        ax.text(10, y, t, fontsize=9, weight="bold", va="top"); y -= 5.5

    def line(t, fs=7.0, x=12, dy=4.1, **kw):
        nonlocal y
        ax.text(x, y, t, fontsize=fs, va="top", **kw); y -= dy
    head("D. INSULATED WIRES ON THE BOTTOM (dashed on page 3)")
    for w in b.wires:
        line(f"[ ] {w['name']}  {w['net']:<4} from {hn(w['a']):<4} to {hn(w['b']):<4}  ({w['note']})", family="monospace")
    line("Lay them flat along the path drawn on page 3, not across the ESP32 antenna end.", dy=5)
    head("E. CHECK WITH A METER (beep mode), ESP32 NOT plugged in, nothing connected")
    for t in [
        "[ ] Must NOT beep:  B2 (BAT+) to E2 (GND)   G2 (12V) to E2   K2 (CHG) to M2 (GND)   B24 (5V) to B23 (GND)",
        f"[ ] Must NOT beep:  R24 (3V3) to Q23 (GND)   B2 to G2   K2 to G2   each pin to its neighbours on the headers",
        "[ ] Must beep:      E2 to M2, E2 to Q12, E2 to R8 (all GND)   G2 to I2, G2 to P8 (12V)   B2 to D5 (BAT+)",
        f"[ ] Must beep:      B24 to A24 and C24 (5V)   {COLS[b.rx - 1]}24 to R20 and J14 (3V3)   K2 to O19 (CHG, via W4)",
    ]:
        line(t, family="monospace", fs=6.6)
    y -= 1.5
    head("F. WIRING DIAGRAMS (pages 6-8, fuses on page 9), then FIRST POWER-UP without the ESP32")
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


# ------------------------------------------------------------------ wiring diagrams (landscape)
RED, BLK, ORG, PNK, BRN = "#d62728", "#222222", "#ff7f0e", "#e377c2", "#8c564b"


def land(pdf, title, sub=None):
    fig = plt.figure(figsize=(297 / 25.4, 210 / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 297); ax.set_ylim(0, 210); ax.axis("off")
    ax.text(148.5, 202, title, ha="center", fontsize=13, weight="bold")
    if sub:
        ax.text(148.5, 196, sub, ha="center", fontsize=7.5, color="0.25")
    return fig, ax


class Draw:
    def __init__(self, ax):
        self.ax = ax

    def box(self, x0, y0, x1, y1, title, fc, fs=7.5, ty=None):
        self.ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle="round,pad=0.6", fc=fc, ec="0.25",
                                         lw=1.0, zorder=2))
        self.ax.text((x0 + x1) / 2, ty if ty is not None else (y0 + y1) / 2, title, ha="center", va="center",
                     fontsize=fs, weight="bold", zorder=3)

    def term(self, x, y, label, side, color="black"):
        """a terminal on a part: dot plus label inside the part"""
        self.ax.add_patch(Circle((x, y), 1.25, fc="#ffd54f", ec="black", lw=0.7, zorder=6))
        dx = {"l": 2.4, "r": -2.4, "t": 0, "b": 0}[side]
        dy = {"l": 0, "r": 0, "t": -2.6, "b": 2.6}[side]
        ha = {"l": "left", "r": "right", "t": "center", "b": "center"}[side]
        va = {"l": "center", "r": "center", "t": "top", "b": "bottom"}[side]
        self.ax.text(x + dx, y + dy, label, fontsize=6.3, ha=ha, va=va, weight="bold", color=color, zorder=7)

    def wire(self, pts, color, lw, num=None, at=None, dot=()):
        xs, ys = zip(*pts)
        self.ax.plot(xs, ys, color="white", lw=lw + 3.2, solid_capstyle="butt", zorder=4)
        self.ax.plot(xs, ys, color=color, lw=lw, solid_capstyle="round", zorder=5)
        for d in dot:
            self.ax.add_patch(Circle(d, 1.3, fc=color, ec="black", lw=0.5, zorder=8))
        if num is not None:
            if at is None:
                i = len(pts) // 2
                at = ((pts[i - 1][0] + pts[i][0]) / 2, (pts[i - 1][1] + pts[i][1]) / 2)
            self.ax.add_patch(Circle(at, 2.6, fc="white", ec=color, lw=1.4, zorder=9))
            self.ax.text(at[0], at[1], str(num), ha="center", va="center", fontsize=6.8, weight="bold", zorder=10)

    def fuse(self, x, y, name, amp):
        ax = self.ax
        ax.add_patch(FancyBboxPatch((x - 9, y - 2.6), 18, 5.2, boxstyle="round,pad=0.4", fc="#fde2e2", ec="0.2",
                                    lw=1.0, zorder=11))
        ax.add_patch(Rectangle((x - 5, y - 1.0), 10, 2.0, fc="white", ec="0.4", lw=0.5, zorder=12))
        ax.text(x, y + 4.6, f"{name} {amp}", ha="center", fontsize=7, weight="bold", color="#b71c1c", zorder=12)
        ax.text(x, y - 5.0, "inline fuse", ha="center", fontsize=5.3, color="0.3", zorder=12)


# power wires: number, from, to, size, colour, note
POWER_WIRES = [
    (1, "Battery P+ (BMS)", "SW1 BATT lug", "1.5 mm2", "red", ""),
    (2, "SW1 COM (middle lug)", "F1 10 A -> BTS7960 B+", "1.5 mm2", "red", "F1 inline in this wire"),
    (3, "Wire 2 after F1 (splice)", "Board POWER 12V (G2)", "0.75 mm2", "red", "solder + heat-shrink the splice"),
    (4, "Trigger board +", "SW1 USB lug", "1 mm2", "red", ""),
    (5, "Trigger board -", "Battery P- (BMS)", "1 mm2", "black", "Peltier current on USB-C"),
    (6, "Battery P- (BMS)", "BTS7960 B-", "1.5 mm2", "black", ""),
    (7, "Battery P- (BMS)", "Board POWER GND (E2)", "0.75 mm2", "black", ""),
    (8, "Battery P+ (BMS)", "F2 3 A -> Board BAT+ (B2)", "0.75 mm2", "orange", "F2 within 5 cm of P+"),
    (9, "BTS7960 M+ and M-", "Peltier red and black", "Peltier wires", "red/black",
     "swap them if it heats when it should cool"),
    (10, "C1 2200 uF + leg / stripe (-) leg", "BTS7960 B+ / B-", "C1 legs", "-", "in the screws with wires 2 and 6"),
    (11, "DC jack centre (+) / sleeve (-)", "Board CHARGE + (K2) / - (M2)", "0.5-0.75 mm2", "pink/black", ""),
    (12, "LM2596 IN+", "Board LM2596 IN+ (I2)", "0.5 mm2", "red", ""),
    (13, "LM2596 OUT-", "Board B23", "0.5 mm2", "black", "LM2596 IN- needs no wire (same as OUT-)"),
    (14, "LM2596 OUT+", "Board B24 (5 V)", "0.5 mm2", "brown", "set the LM2596 to 5.0 V first"),
]


def power_diagram_page(pdf, tag):
    fig, ax = land(pdf, f"ThermoX WIRING DIAGRAM 1 - POWER  [{tag}]",
                   "Thick lines = 1.5 mm2 (Peltier current). Dots = joined. Numbers = wire list on the next page. "
                   "Lines that cross without a dot are NOT joined.")
    d = Draw(ax)
    # parts
    d.box(15, 95, 60, 140, "", "#fff3cd")
    for i in range(3):
        for j in range(2):
            ax.add_patch(FancyBboxPatch((19 + i * 11, 101 + j * 14), 8, 11, boxstyle="round,pad=0.3", fc="#90caf9",
                                        ec="0.3", lw=0.6, zorder=3))
    ax.add_patch(Rectangle((52, 98), 6, 39, fc="#2e7d32", ec="black", lw=0.6, zorder=3))
    ax.text(33, 132.5, "BATTERY 3S2P", ha="center", fontsize=6.5, weight="bold", zorder=4)
    ax.text(55, 117.5, "BMS", rotation=90, ha="center", va="center", fontsize=6, color="white", weight="bold", zorder=4)
    d.term(55, 140, "P+", "b"); d.term(15, 108, "P-", "l")
    d.box(20, 165, 50, 182, "USB-C trigger\nboard (12 V)", "#e3f2fd", fs=6.6)
    d.term(50, 176, "+", "r"); d.term(20, 170, "-", "l")
    d.box(70, 150, 86, 186, "", "#e3f2fd")
    ax.text(78, 189.5, "SW1 ON-OFF-ON 10 A", ha="center", fontsize=6.8, weight="bold")
    ax.plot([78, 82], [180, 185], color="0.2", lw=2, zorder=3)
    d.term(70, 176, "USB", "l"); d.term(70, 158, "BATT", "l"); d.term(86, 168, "COM", "r")
    ax.text(78, 153, "COM =\nmiddle lug", ha="center", fontsize=4.8, zorder=4)
    d.box(190, 125, 240, 182, "BTS7960\n(IBT-2)", "#e8f5e9", ty=170)
    d.term(190, 168, "B+", "l"); d.term(190, 140, "B-", "l"); d.term(240, 168, "M+", "r"); d.term(240, 140, "M-", "r")
    ax.text(215, 129, "8-pin header:\nsee diagram 2", ha="center", fontsize=5.6, zorder=4)
    d.box(255, 138, 287, 172, "PELTIER\nTEC1-12706", "#b2dfdb")
    ax.text(271, 132, "swap the 2 wires if it\nheats when it should cool", ha="center", fontsize=5.5)
    d.box(115, 35, 175, 95, "THERMOX\nBOARD\n(universal PCB)", "#f6efd9", fs=8.5, ty=72)
    for x, y, lab, side in [(115, 88, "B2  BAT+", "l"), (115, 78, "E2  POWER GND", "l"), (115, 66, "I2  LM IN+", "l"),
                            (115, 52, "B23  LM OUT-", "l"), (115, 46, "B24  LM OUT+", "l"), (140, 95, "G2  POWER 12V", "t"),
                            (175, 70, "K2  CHARGE +", "r"), (175, 60, "M2  CHARGE -", "r")]:
        d.term(x, y, lab, side)
    d.box(62, 38, 96, 72, "LM2596S\n5.0 V", "#efebe9", ty=62)
    d.term(96, 66, "IN+", "r"); d.term(96, 59, "IN-", "r"); d.term(96, 52, "OUT-", "r"); d.term(96, 46, "OUT+", "r")
    ax.text(99, 57.2, "no wire", fontsize=4.8, color="0.4")
    d.box(200, 52, 226, 78, "DC jack\n5.5 x 2.1\n(on the case)", "#fce4ec", fs=6.3)
    d.term(200, 70, "centre +", "l"); d.term(200, 60, "sleeve -", "l")
    d.box(243, 52, 287, 78, "Li-ion charger\n12.6 V 2 A (3S)\nNOT 21 V", "#fce4ec", fs=6.5)
    ax.plot([226, 243], [65, 65], color="0.3", lw=2.4, zorder=1)
    ax.text(234.5, 67.5, "plug", fontsize=5.5, ha="center")
    # C1 on the BTS7960 B+ / B- screws
    ax.add_patch(FancyBboxPatch((172, 147), 9, 14, boxstyle="round,pad=0.3", fc="#37474f", ec="black", lw=0.6,
                                zorder=11))
    ax.add_patch(Rectangle((172.3, 147.2), 8.4, 3, fc="#cfd8dc", ec="none", zorder=12))
    ax.text(176.5, 155.5, "C1", color="white", fontsize=6, ha="center", va="center", weight="bold", zorder=12)
    ax.text(146, 152, "C1 2200 uF 25 V:\n+ leg to B+,\nstripe (-) leg to B-", fontsize=5.5, ha="right", va="center")
    # wires
    d.wire([(55, 140), (55, 158), (70, 158)], RED, 3.0, 1, (55, 150), dot=[(55, 140)])
    d.wire([(86, 168), (190, 168)], RED, 3.0, 2, (95, 168))
    d.fuse(112, 168, "F1", "10 A slow-blow")
    d.wire([(150, 168), (150, 102), (140, 102), (140, 95)], RED, 1.8, 3, (150, 120), dot=[(150, 168)])
    d.wire([(50, 176), (70, 176)], RED, 2.4, 4, (60, 176))
    d.wire([(20, 170), (9, 170), (9, 108)], BLK, 2.4, 5, (9, 150))
    d.wire([(15, 108), (9, 108), (9, 22), (183, 22), (183, 140), (190, 140)], BLK, 3.0, 6, (100, 22),
           dot=[(9, 108)])
    d.wire([(9, 78), (115, 78)], BLK, 1.8, 7, (35, 78), dot=[(9, 78)])
    d.wire([(55, 140), (100, 140), (100, 88), (115, 88)], ORG, 1.8, 8, (100, 115))
    d.fuse(78, 140, "F2", "3 A slow-blow")
    d.wire([(176.5, 161), (176.5, 168)], RED, 1.2, dot=[(176.5, 168)])
    d.wire([(176.5, 147), (176.5, 140), (183, 140)], BLK, 1.2, dot=[(183, 140)])
    d.wire([(240, 168), (248, 168), (248, 163), (255, 163)], RED, 2.0)
    d.wire([(240, 140), (248, 140), (248, 147), (255, 147)], BLK, 2.0, 9, (248, 155))
    d.wire([(175, 70), (200, 70)], PNK, 1.8, 11, (191, 70))
    d.wire([(175, 60), (200, 60)], BLK, 1.8)
    d.wire([(96, 66), (115, 66)], RED, 1.2, 12, (106, 66))
    d.wire([(96, 52), (115, 52)], BLK, 1.2, 13, (106, 52))
    d.wire([(96, 46), (115, 46)], BRN, 1.2, 14, (106, 45.5))
    ax.text(8, 12, "Before the battery goes on: SW1 in the middle (OFF), fuses in, LM2596 set to 5.0 V, trigger board "
            "set to 12 V. Never plug the USB-C charger and the DC charger in at the same time.", fontsize=7,
            weight="bold", color="#b71c1c")
    pdf.savefig(fig); plt.close(fig)


# signal wires: board pin (hole), name, goes to, note
SIGNAL_WIRES = [
    ("FAN", [("O8", "PWM", "fan BLUE wire"), ("P8", "12V", "fan RED wire"), ("Q8", "FG", "fan YELLOW wire"),
             ("R8", "GND", "fan BLACK wire")]),
    ("OLED", [("O12", "SDA", "OLED SDA"), ("P12", "SCL", "OLED SCL"), ("Q12", "GND", "OLED GND"),
              ("R12", "VCC", "OLED VCC (3.3 V)")]),
    ("BTN1", [("P16", "B1", "button 1 (DOWN), one leg"), ("Q16", "GND", "button 1, other leg")]),
    ("TEMP", [("P20", "DQ", "DS18B20 YELLOW (data)"), ("Q20", "GND", "DS18B20 BLACK"), ("R20", "VCC", "DS18B20 RED")]),
    ("BTN2", [("A15", "GND", "button 2, other leg"), ("A16", "B2", "button 2 (UP), one leg")]),
    ("BTS A", [("A17", "R_EN", "BTS7960 R_EN"), ("A18", "RPWM", "BTS7960 RPWM"), ("A19", "LPWM", "BTS7960 LPWM")]),
    ("BTS B", [("A22", "L_EN", "BTS7960 L_EN"), ("A23", "GND", "BTS7960 GND"), ("A24", "VCC", "BTS7960 VCC (5 V)")]),
]
DUP = ["#1f77b4", "#d62728", "#f1c40f", "#222222", "#2ca02c", "#9467bd", "#ff7f0e", "#8c564b", "#17becf"]


def signal_diagram_page(pdf, tag):
    fig, ax = land(pdf, f"ThermoX WIRING DIAGRAM 2 - HEADERS TO THE PARTS (Dupont wires)  [{tag}]",
                   "Each line is one female-female Dupont wire. Connect by NAME: the order of the pins on a module "
                   "can be different from the board.")
    d = Draw(ax)
    d.box(112, 28, 182, 186, "", "#f6efd9")
    ax.text(147, 180, "THERMOX BOARD (parts side)", ha="center", fontsize=8, weight="bold", zorder=4)
    ax.add_patch(Rectangle((126, 40), 42, 92, fc="none", ec="#1565c0", lw=1, ls="--", zorder=3))
    ax.text(147, 86, "ESP32", ha="center", fontsize=10, color="#1565c0", weight="bold", zorder=4)
    rows = {}
    right = [("FAN", 168), ("OLED", 136), ("BTN1", 106), ("TEMP", 80)]
    left = [("BTN2", 150), ("BTS A", 122), ("BTS B", 78)]
    pins = {}
    for name, y0 in right:
        grp = dict(SIGNAL_WIRES)[name]
        ax.text(178, y0 + 4, name, ha="right", fontsize=7, weight="bold", color="#2e7d32", zorder=4)
        for i, (hole, pin, to) in enumerate(grp):
            y = y0 - i * 5.2
            d.term(182, y, f"{hole} {pin}", "r")
            pins[(name, pin)] = (182, y)
    for name, y0 in left:
        grp = dict(SIGNAL_WIRES)[name]
        ax.text(116, y0 + 4, name, ha="left", fontsize=7, weight="bold", color="#2e7d32", zorder=4)
        for i, (hole, pin, to) in enumerate(grp):
            y = y0 - i * 5.2
            d.term(112, y, f"{hole} {pin}", "l")
            pins[(name, pin)] = (112, y)
    # modules on the right
    d.box(222, 156, 262, 176, "FAN 40 x 40\nSUNON 12 V", "#e0e0e0", fs=6.5)
    fan = {"PWM": (222, 171), "12V": (222, 167), "FG": (222, 163), "GND": (222, 159)}
    fcol = {"PWM": "#1f77b4", "12V": RED, "FG": "#f1c40f", "GND": BLK}
    for k, p in fan.items():
        d.wire([pins[("FAN", k)], (205, pins[("FAN", k)][1]), (212, p[1]), p], fcol[k], 1.6)
        ax.text(p[0] + 2, p[1], {"PWM": "blue", "12V": "red", "FG": "yellow", "GND": "black"}[k], fontsize=5.3,
                va="center", zorder=7)
    d.box(225, 116, 275, 146, "OLED 1.5 inch\nSH1107 I2C", "#263238", fs=6.5, ty=131)
    ax.texts[-1].set_color("white")
    oled = {"GND": (225, 141), "VCC": (225, 136), "SCL": (225, 131), "SDA": (225, 126)}
    ocol = {"GND": BLK, "VCC": RED, "SCL": "#2ca02c", "SDA": "#9467bd"}
    for k, p in oled.items():
        d.term(*p, k, "l", color="white")
        d.wire([pins[("OLED", k)], (200, pins[("OLED", k)][1]), (212, p[1]), p], ocol[k], 1.6)
    ax.text(250, 108, "OLED pin order: GND VCC SCL SDA.\nThe wires cross: match the names.", ha="center", fontsize=5.6)
    # button 1
    for name, y0, xb in (("BTN1", 106, 232),):
        ax.add_patch(Circle((xb, y0 - 2.6), 5, fc="#ef5350", ec="black", lw=0.8, zorder=3))
        ax.text(xb, y0 - 2.6, "BTN1\nDOWN", ha="center", va="center", fontsize=5.3, weight="bold", zorder=4)
        d.wire([pins[("BTN1", "B1")], (226, y0), (227.5, y0)], "#17becf", 1.6)
        d.wire([pins[("BTN1", "GND")], (226, y0 - 5.2), (227.5, y0 - 5.2)], BLK, 1.6)
    # DS18B20
    d.box(232, 64, 284, 84, "DS18B20 probe\n(in the water)", "#cfd8dc", fs=6.5)
    tcol = {"DQ": "#f1c40f", "GND": BLK, "VCC": RED}
    for i, k in enumerate(("DQ", "GND", "VCC")):
        p = pins[("TEMP", k)]
        d.wire([p, (232, p[1])], tcol[k], 1.6)
        ax.text(234, p[1], {"DQ": "yellow", "GND": "black", "VCC": "red"}[k], fontsize=5.3, va="center", zorder=7)
    # left: button 2 and the BTS7960 control header
    ax.add_patch(Circle((70, 147.4), 5, fc="#66bb6a", ec="black", lw=0.8, zorder=3))
    ax.text(70, 147.4, "BTN2\nUP", ha="center", va="center", fontsize=5.3, weight="bold", zorder=4)
    d.wire([pins[("BTN2", "GND")], (80, 150), (74.8, 150)], BLK, 1.6)
    d.wire([pins[("BTN2", "B2")], (80, 144.8), (74.8, 144.8)], "#ff7f0e", 1.6)
    d.box(14, 48, 58, 128, "BTS7960\nheader", "#e8f5e9", ty=122)
    hdr = ["RPWM", "LPWM", "R_EN", "L_EN", "R_IS", "L_IS", "VCC", "GND"]
    hp = {}
    for i, k in enumerate(hdr):
        y = 112 - i * 8
        d.term(58, y, k, "r")
        hp[k] = (58, y)
    ax.text(36, 52, "R_IS, L_IS:\nleave empty", ha="center", fontsize=5.6, zorder=4)
    bcol = {"R_EN": "#2ca02c", "RPWM": "#1f77b4", "LPWM": "#9467bd", "L_EN": "#17becf", "GND": BLK, "VCC": BRN}
    lanes = {"R_EN": 68, "RPWM": 100, "LPWM": 92, "L_EN": 78, "GND": 96, "VCC": 86}
    for grp in ("BTS A", "BTS B"):
        for hole, pin, to in dict(SIGNAL_WIRES)[grp]:
            k = pin
            a = pins[(grp, k)]
            bpt = hp[k]
            x = lanes[k]
            d.wire([a, (x, a[1]), (x, bpt[1]), bpt], bcol[k], 1.6)
    ax.text(8, 12, "The BTS7960 B+, B-, M+ and M- screw terminals are on diagram 1 (thick wires). "
            "Short Dupont wires are best: a loose plug can stop the fan or the driver.", fontsize=7)
    pdf.savefig(fig); plt.close(fig)


def wirelist_page(pdf, tag):
    fig, ax = land(pdf, f"ThermoX WIRE LIST  [{tag}]", "Tick each wire when it is done.")
    y = 188
    ax.text(10, y, "POWER WIRES (diagram 1)", fontsize=9, weight="bold"); y -= 6
    head = ["No.", "From", "To", "Wire", "Colour", "Note"]
    xs = [12, 22, 82, 152, 178, 200]
    for x, h in zip(xs, head):
        ax.text(x, y, h, fontsize=7, weight="bold")
    y -= 4.6
    for n, a, b2, size, col, note in POWER_WIRES:
        for x, t in zip(xs, [f"[ ] {n}", a, b2, size, col, note]):
            ax.text(x, y, t, fontsize=6.6, va="center")
        y -= 4.4
    y -= 4
    ax.text(10, y, "DUPONT WIRES (diagram 2)", fontsize=9, weight="bold"); y -= 6
    col_x = [12, 102, 192]
    items = [(g, h, p, t) for g, rows in SIGNAL_WIRES for h, p, t in rows]
    per = (len(items) + 2) // 3
    for i, (g, h, p, t) in enumerate(items):
        cx = col_x[i // per]
        yy = y - (i % per) * 4.4
        ax.text(cx, yy, f"[ ] {g:<6} {h:<4} {p:<5} -> {t}", fontsize=6.4, family="monospace", va="center")
    pdf.savefig(fig); plt.close(fig)


BOM = [
    ("ON THE UNIVERSAL PCB", [
        ("1", "Universal PCB 5 x 7 cm, single-sided, 18 x 24 holes, 2.54 mm", ""),
        ("1", "ESP32 DevKit V1, 30 pins (ESP-WROOM-32)", "U1"),
        ("2", "Female header 1 x 15, 2.54 mm", "socket for the ESP32"),
        ("1", "Male header strip 1 x 40, 2.54 mm (cut into 4+4+3+3+3+2+2 = 21 pins)", "FAN OLED TEMP BTS-A BTS-B BTN1 BTN2"),
        ("2", "Screw terminal 2-pin 5.08 mm (KF301-2P)", "POWER, CHARGE"),
        ("1", "Resistor 10 kOhm 1/4 W", "R1"),
        ("1", "Resistor 4.7 kOhm 1/4 W", "R2"),
        ("2", "Resistor 100 kOhm 1/4 W", "R3, R5"),
        ("1", "Resistor 22 kOhm 1/4 W", "R4"),
        ("1", "Resistor 33 kOhm 1/4 W", "R6"),
        ("1", "Ceramic capacitor 100 nF (104)", "C4"),
        ("2", "Schottky diode 1N5822 (3 A)", "D1, D2"),
        ("1 m", "Bare tinned copper wire 0.8-1 mm", "trails"),
        ("1 m", "Thin insulated wire (0.25-0.5 mm2)", "W1-W4"),
    ]),
    ("MODULES AND PARTS AROUND THE BOARD", [
        ("1", "OLED 1.5 inch 128 x 128, SH1107, I2C (GME128128-01-IIC)", "OLED header"),
        ("1", "DS18B20 waterproof temperature probe (3 wires)", "TEMP header"),
        ("1", "BTS7960 (IBT-2) 43 A motor driver module", "BTS A / BTS B headers"),
        ("1", "Peltier TEC1-12706 (12 V, about 6 A)", "BTS7960 M+ / M-"),
        ("1", "SUNON fan 40 x 40 x 28 mm, 12 V, 4-wire (PWM + FG)", "FAN header"),
        ("1", "LM2596S DC-DC step-down module (set to 5.0 V)", "I2, B23, B24"),
        ("1", "USB-C PD trigger board 100 W 5 A (ZY12PDN), set to 12 V", "SW1 USB"),
        ("2", "Push button, momentary, panel mount", "BTN1, BTN2"),
        ("1", "ON-OFF-ON toggle switch, 10 A or more (MTS-103 is only 6 A)", "SW1"),
        ("2", "Inline fuse holder 5 x 20 mm (with wire leads)", "F1, F2"),
        ("2+2", "Fuse 5 x 20 mm slow-blow: 10 A (F1) and 3 A (F2), plus 1 spare of each", "F1, F2"),
        ("1", "Electrolytic capacitor 2200 uF 25 V low ESR", "C1 at the BTS7960"),
        ("1", "DC jack 5.5 x 2.1 mm, female, panel mount", "charging input"),
    ]),
    ("BATTERY AND CHARGING", [
        ("6", "Li-ion 21700 cell 3.7 V 5000 mAh, 40 A (Enook)", "3S2P pack"),
        ("1", "3S BMS protection board, 20 A, with balance wires", ""),
        ("1", "3S2P 21700 holder, or nickel strip 0.15 x 8 mm (spot welded)", "builds the pack"),
        ("1", "Li-ion charger 12.6 V 2 A (3S, CC/CV), 5.5 x 2.1 mm plug. NOT 21 V", ""),
        ("1", "USB-C PD charger that gives 12 V (60 W or more) + 5 A USB-C cable", "optional, all-day use"),
    ]),
    ("WIRES AND SMALL PARTS", [
        ("1 m + 1 m", "Wire 1.5 mm2 (16 AWG), red and black", "battery, SW1, F1, BTS7960 B+/B-, Peltier"),
        ("1 m + 1 m", "Wire 0.75 mm2 (18 AWG), red and black", "G2, E2, B2, trigger board, charge jack"),
        ("1 m", "Wire 0.5 mm2 (20 AWG)", "LM2596"),
        ("1 pack", "Dupont jumper wires female-female, 20 cm (40 pcs)", "all headers"),
        ("1 set", "Heat-shrink tubing, assorted", ""),
        ("", "Solder 0.8 mm with flux, double-sided tape", ""),
    ]),
    ("THERMAL AND BODY", [
        ("1", "Copper heatsink for the Peltier hot side (fits the 40 mm fan)", ""),
        ("1", "Aluminium water cup (Peltier cold side on its floor)", ""),
        ("1", "Thermal paste (1 tube)", "Peltier, cup, heatsink"),
        ("4", "M3 screws + nuts or standoffs", "board, fan"),
        ("1", "Bottle body (3D printed, design from cad/)", ""),
    ]),
    ("TOOLS", [
        ("", "Soldering iron, multimeter (beep + volts), wire stripper, side cutter", ""),
        ("", "Drill bits 1.5 mm (diode holes) and 1.3 mm (only if the screw terminal pins do not fit)", ""),
    ]),
]


def fuse_fan_page(pdf, tag):
    fig, ax = page(pdf, f"ThermoX - 9. FUSES AND FAN WIRES  [{tag}]",
                   "The fuses are NOT on the board on purpose: the Peltier current (up to 7 A) must not go through a perfboard.")
    RED, BLK, ORG = "#d62728", "#222222", "#ff7f0e"

    def box(x, y, w, h, t, fc, fs=7, bold=True):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5", fc=fc, ec="0.3", lw=0.9))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs, weight="bold" if bold else None)

    def line(pts, c, lw, lab=None, at=None, fs=6):
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color=c, lw=lw, solid_capstyle="round", zorder=1)
        if lab:
            ax.text(at[0], at[1], lab, fontsize=fs, ha="center", va="center", color=c, weight="bold",
                    bbox=dict(fc="white", ec="none", pad=0.3))

    def fuse(x, y, name, amp, c):
        """inline 5 x 20 mm fuse holder drawn across a wire at (x, y)"""
        ax.add_patch(FancyBboxPatch((x - 11, y - 3.2), 22, 6.4, boxstyle="round,pad=0.4", fc="#fde2e2", ec="0.25",
                                    lw=1.0, zorder=3))
        ax.add_patch(Rectangle((x - 6, y - 1.3), 12, 2.6, fc="white", ec="0.4", lw=0.6, zorder=4))
        ax.plot([x - 6, x + 6], [y, y], color="0.4", lw=0.6, zorder=5)
        ax.text(x, y + 5.6, f"{name}  {amp} slow-blow", ha="center", fontsize=7.5, weight="bold", color="#b71c1c")
        ax.text(x, y - 6.0, "inline fuse holder 5 x 20", ha="center", fontsize=5.6, color="0.3")

    # ---------------- F1: main 12 V line
    ax.text(10, 268, "1. F1  10 A  - main 12 V line (Peltier, fan, board)", fontsize=9.5, weight="bold")
    box(8, 236, 30, 22, "BATTERY\n3S2P + BMS\nP+   P-", "#fff3cd")
    box(58, 238, 30, 18, "SW1\nON-OFF-ON 10 A\nBATT  COM  USB", "#e3f2fd", fs=6.6)
    box(58, 210, 30, 12, "USB-C trigger\nboard 12 V", "#e3f2fd", fs=6.6)
    box(150, 236, 34, 22, "BTS7960\nB+      B-\n(+ C1 2200 uF)", "#e8f5e9")
    box(150, 202, 34, 14, "BOARD  POWER\nG2 = 12V   E2 = GND", "#f6efd9", fs=6.6)
    line([(38, 252), (58, 252)], RED, 3, "P+ to BATT\n1.5 mm2", (48, 257))
    line([(73, 222), (73, 238)], RED, 2.2, "to USB lug", (84, 234.5))
    line([(88, 247), (106, 247)], RED, 3, "COM", (97, 250))
    fuse(117, 247, "F1", "10 A", RED)
    line([(128, 247), (150, 247)], RED, 3, "1.5 mm2", (140, 250))
    line([(138, 247), (138, 212), (150, 212)], RED, 1.8, "splice: 0.75 mm2\nto G2", (128, 224))
    ax.add_patch(Circle((138, 247), 1.3, fc=RED, ec="black", lw=0.5, zorder=6))
    line([(20, 236), (20, 196), (167, 196), (167, 202)], BLK, 1.8, "P- to E2  0.75 mm2", (100, 196))
    line([(30, 236), (30, 230), (192, 230), (192, 247), (184, 247)], BLK, 3, "P- to BTS7960 B-  1.5 mm2", (110, 230))
    line([(64, 210), (64, 196)], BLK, 1.4, "trigger -", (56, 203))
    ax.add_patch(Circle((64, 196), 1.0, fc=BLK, zorder=6))
    ax.add_patch(Circle((20, 196), 1.0, fc=BLK, zorder=6))
    # ---------------- F2: BAT+ wire to the board
    ax.text(10, 184, "2. F2  3 A  - BAT+ wire to the board (battery gauge and charging)", fontsize=9.5, weight="bold")
    box(8, 150, 30, 22, "BATTERY\n3S2P + BMS\nP+", "#fff3cd")
    box(150, 152, 34, 18, "BOARD\nB2 = BAT+ wire\n(red ring, top left)", "#f6efd9", fs=6.6)
    line([(38, 161), (66, 161)], ORG, 2.2, "short: 5 cm max", (52, 165))
    fuse(77, 161, "F2", "3 A", ORG)
    line([(88, 161), (150, 161)], ORG, 2.2, "0.75 mm2 to B2", (119, 165))
    # ---------------- how to fit an inline fuse holder
    y = 138
    ax.text(10, y, "HOW TO FIT EACH INLINE FUSE HOLDER", fontsize=9.5, weight="bold"); y -= 6
    for t in [
        "1. Battery disconnected (or BMS off) while you wire. SW1 in the middle (OFF).",
        "2. Cut the wire where the fuse goes. Strip 8 mm of each end and of both holder leads.",
        "3. Slide heat-shrink on first, then twist each end to one holder lead, solder, and shrink the tube over the joint.",
        "4. F1: the splice to G2 is on the BTS7960 side of F1 (after the fuse). Solder the 0.75 mm2 wire to the 1.5 mm2",
        "   wire and cover it with heat-shrink. Both the BTS7960 and the board are then protected by F1.",
        "5. F2: put it within 5 cm of the battery P+ so the whole thin wire to B2 is protected. Solder the F2 lead and",
        "   the 1.5 mm2 SW1 wire both on the BMS P+ pad.",
        "6. Put the fuses in: 10 A slow-blow in F1, 3 A slow-blow in F2. Never a bigger fuse, never a wire instead.",
        "7. Check with a meter (fuses in, battery off): SW1 COM to G2 beeps (through F1); battery P+ to B2 beeps (through F2).",
        "8. A fuse that blows means a short: find it before you put a new fuse in.",
    ]:
        ax.text(12, y, t, fontsize=7, va="top"); y -= 4.4
    # ---------------- fan wires
    y -= 4
    ax.text(10, y, "FAN: SUNON 40 x 40 x 28 mm, 12 V, 4 wires -> FAN header O8-R8 (row 8, lies across)", fontsize=9.5,
            weight="bold"); y -= 8
    cols = [("O8", "PWM", "BLUE", "#1f77b4", "speed control, GPIO23"), ("P8", "12V", "RED", RED, "+12 V (after F1)"),
            ("Q8", "FG", "YELLOW", "#f1c40f", "speed signal (rpm), GPIO35"), ("R8", "GND", "BLACK", BLK, "ground")]
    for i, (hole, pin, colr, cc, use) in enumerate(cols):
        x = 14 + i * 47
        ax.add_patch(Rectangle((x, y - 7), 42, 13, fc="white", ec="0.5", lw=0.6))
        ax.add_patch(Rectangle((x + 2, y - 1.6), 9, 3.2, fc=cc, ec="black", lw=0.4))
        ax.text(x + 13, y + 0.5, f"{colr} -> {hole}", fontsize=7.5, weight="bold", va="center")
        ax.text(x + 13, y - 4.2, f"{pin}: {use}", fontsize=5.8, va="center", color="0.25")
    y -= 13
    for t in [
        "These are the usual SUNON 4-wire colours. Check the sticker or datasheet of YOUR fan first: some fans use",
        "other colours. If the fan only has 3 wires (no blue), it has no PWM: leave O8 empty, it runs full speed whenever",
        "12 V is on. With only 2 wires there is no FG either: set FAN_MIN_RPM = 0 in ThermoX.ino (stall check off).",
        "The fan needs about 1 A at full speed. Use the Dupont cable only if it is short; a loose plug makes the fan stall.",
    ]:
        ax.text(12, y, t, fontsize=7, va="top"); y -= 4.4
    pdf.savefig(fig); plt.close(fig)


def bom_page(pdf, tag):
    fig, ax = page(pdf, f"ThermoX - 10. COMPLETE PARTS LIST (everything to buy)  [{tag}]")
    y = 272
    for head, rows in BOM:
        ax.text(10, y, head, fontsize=8.5, weight="bold", va="top"); y -= 5
        for qty, part, use in rows:
            ax.text(12, y, "[ ]", fontsize=6.8, va="top", family="monospace")
            ax.text(20, y, qty, fontsize=6.8, va="top", weight="bold")
            ax.text(36, y, part, fontsize=6.8, va="top")
            ax.text(150, y, use, fontsize=6.2, va="top", color="#555")
            y -= 3.9
        y -= 2.5
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
            truesize_page(pdf, b, tag)
            top_page(pdf, b, tag)
            bottom_page(pdf, b, tag)
            steps_page(pdf, b, tag)
            steps2_page(pdf, b, tag)
            power_diagram_page(pdf, tag)
            signal_diagram_page(pdf, tag)
            wirelist_page(pdf, tag)
            fuse_fan_page(pdf, tag)
            bom_page(pdf, tag)
        print(f"rows {spacing} OK -> {os.path.basename(name)}  ({len(b.trails)} trails, {len(b.wires)} wires)")
    with PdfPages(os.path.join(OUT, "thermox_wiring_diagram.pdf")) as pdf:     # the 3 wiring pages on their own
        power_diagram_page(pdf, "universal PCB")
        signal_diagram_page(pdf, "universal PCB")
        wirelist_page(pdf, "universal PCB")
        fuse_fan_page(pdf, "universal PCB")
    print("wiring diagram -> thermox_wiring_diagram.pdf")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
