#!/usr/bin/env python3
"""ThermoX: ten mock designs for where the DS18B20 thermowell can go in the round bottle.

Cross-sections use the round-bottle sizes from make_models.py: water cup 72 mm inside, 1 mm aluminium wall,
3 mm aluminium floor with the TEC1-12706 (40 x 40 mm) under it, 5.5 mm foam sleeve, about 68 mm of water (275 mL),
lid with the OLED on top. The thermowell is a closed-end stainless tube, 8 mm outside / 7 mm inside, so the
6 mm DS18B20 probe slides in with thermal paste. These are concepts to compare, not tested designs.

Run:  python3 make_thermowell_designs.py        (needs: pip install matplotlib)
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle

OUT = os.path.dirname(os.path.abspath(__file__))
R_IN, WALL, FOAM = 36.0, 1.0, 5.5          # cup inside radius, wall, foam sleeve (mm)
SHELL = R_IN + WALL + FOAM + 2.5           # outer shell
WATER, CUP_TOP, LID_TOP = 68.0, 71.0, 84.0  # heights above the cup floor (mm)
TUBE_OD = 8.0
CRIT = ["Accuracy", "No leak", "Cleaning / drinking", "Cable / lid", "Easy to build"]

# name, short, path (x, z points from the outside end to the closed tip), seal points, scores, text
DESIGNS = [
    ("1. Lid, centre, straight down", "Lid centre",
     [(0, 92), (0, 20)], [(0, LID_TOP - 6)], [5, 5, 2, 3, 2],
     "A straight tube hangs from the middle of the lid. The tip sits 20 mm above the floor, in the middle of the water.",
     ["Reads the bulk water in the centre", "No hole below the water line", "The OLED wires already go to the lid"],
     ["The OLED sits in the middle of the lid: it would have to move", "The tube is in the way when drinking and cleaning",
      "The lid needs a plug for the sensor cable"]),
    ("2. Lid, off-centre, straight down", "Lid off-centre",
     [(22, 92), (22, 20)], [(22, LID_TOP - 6)], [4, 5, 4, 3, 4],
     "Same as design 1, but 22 mm from the centre, so the middle of the cup stays free for drinking.",
     ["No hole below the water line", "Centre stays free", "Simple: one gland in the lid"],
     ["A little closer to the wall than design 1", "The lid needs a plug for the sensor cable"]),
    ("3. Lid, angled to the centre", "Lid angled",
     [(30, 92), (3, 20)], [(24.8, LID_TOP - 6)], [5, 5, 3, 3, 3],
     "A straight tube enters near the lid edge at an angle, so the tip ends at the centre of the water. "
     "The tube is straight because the steel probe cannot bend.",
     ["Tip in the centre, entry out of the way", "No hole below the water line"],
     ["The angled hole and gland are harder to make", "The lid needs a plug for the sensor cable"]),
    ("4. Side wall, mid-height", "Wall middle",
     [(SHELL + 10, 34), (4, 34)], [(R_IN + 0.5, 34)], [4, 2, 4, 5, 2],
     "A horizontal tube through the shell, foam and cup wall at half the water depth, tip near the centre.",
     ["Cable stays in the body, the lid is free", "Good height in the water"],
     ["Hole below the water line: must be sealed and food-safe", "Hard to seal through the 1 mm aluminium wall"]),
    ("5. Side wall, low", "Wall low",
     [(SHELL + 10, 8), (4, 8)], [(R_IN + 0.5, 8)], [2, 2, 4, 5, 2],
     "Like design 4, but 8 mm above the floor, close to the Peltier.",
     ["Cable stays in the body"],
     ["Reads the water next to the Peltier: the run stops too early", "Hole below the water line, high leak risk"]),
    ("6. Side wall, high", "Wall high",
     [(SHELL + 10, 60), (4, 60)], [(R_IN + 0.5, 60)], [1, 3, 4, 5, 2],
     "Like design 4, but 60 mm up, just under the water surface.",
     ["Cable stays in the body", "Less water pressure on the seal"],
     ["Reads air when the cup is not full", "The top of the water is not the average"]),
    ("7. Floor, beside the Peltier, straight up", "Floor up",
     [(28, -30), (28, 35)], [(28, -1.5)], [4, 1, 4, 2, 1],
     "Comes up through the cup floor beside the 40 mm Peltier, tip at half the water depth.",
     ["Lid is free, nothing hangs from it"],
     ["Hole in the floor right above the electronics: worst leak risk", "Must pass the heatsink and fan area"]),
    ("8. Floor edge, angled in", "Floor angled",
     [(40, -20), (6, 32)], [(27.9, -1.5)], [4, 1, 3, 2, 1],
     "A straight tube enters at the floor edge at an angle and ends at the centre of the water.",
     ["Tip in the centre", "Lid is free"],
     ["Hole in the floor above the electronics", "Angled seal in a 3 mm plate is hard to make"]),
    ("9. Lid, L-shape to the centre", "Lid L-shape",
     [(28, 92), (28, 22), (4, 22)], [(28, LID_TOP - 6)], [5, 5, 2, 3, 2],
     "Goes down near the wall, then turns to the centre. Only works with the BARE DS18B20 chip on thin wires: "
     "the 6 mm steel probe cannot go round the bend.",
     ["Tip in the centre at 1/3 height", "No hole below the water line"],
     ["The steel probe cannot be used: bare chip + wires, sealed in the tube", "Bent tube is in the way of cleaning"]),
    ("10. Straight tube on the inside wall, cable over the rim", "Inside wall",
     [(R_IN - 4, CUP_TOP - 1), (R_IN - 4, 20)], [], [4, 5, 4, 5, 4],
     "A STRAIGHT tube is clipped to the inside wall of the cup (not the lid). Its open top ends just under the rim; "
     "the tip is 20 mm above the floor. The steel probe slides straight in from the top. Only the CABLE bends, gently, "
     "over the rim and out through a groove in the foam under the lid seal.",
     ["No hole at all: nothing to seal", "Lid comes off freely, the cable stays in the body",
      "Easy to make: one straight tube and two clips", "The steel probe stays straight"],
     ["Tip is 4 mm from the wall, not in the centre", "The lid seal needs a small groove for the cable",
      "Bend the cable gently (round bend, not a kink)"],
     [(R_IN - 4, CUP_TOP - 1), (R_IN - 4, CUP_TOP + 3), (R_IN + 3, CUP_TOP + 3), (R_IN + 3, CUP_TOP - 6),
      (SHELL + 4, CUP_TOP - 6)]),
]
RECOMMEND = 9          # index of design 10


def section(ax, x0, y0, s, d, small=False):
    """Draw the bottle cross-section with design d. (x0, y0) = page position of the cup floor centre; s = page mm per mm."""
    P = lambda x, z: (x0 + x * s, y0 + z * s)

    def rect(xa, za, xb, zb, **kw):
        (a, b), (c, e) = P(xa, za), P(xb, zb)
        ax.add_patch(Rectangle((a, b), c - a, e - b, **kw))
    lw = 0.5 if small else 0.8
    rect(-SHELL, -70, SHELL, LID_TOP, fc="#eceff1", ec="0.4", lw=lw)                       # outer shell
    rect(-R_IN - WALL - FOAM, 0, R_IN + WALL + FOAM, CUP_TOP, fc="#e0c88a", ec="none")       # foam
    rect(-R_IN - WALL, -3, R_IN + WALL, CUP_TOP, fc="#b0bec5", ec="0.3", lw=lw)              # cup
    rect(-R_IN, 0, R_IN, CUP_TOP, fc="white", ec="none")
    rect(-R_IN, 0, R_IN, WATER, fc="#bbdefb", ec="none")                                    # water
    ax.plot(*zip(P(-R_IN, WATER), P(R_IN, WATER)), color="#1e88e5", lw=lw)
    rect(-SHELL, CUP_TOP, SHELL, LID_TOP, fc="#90a4ae", ec="0.3", lw=lw)                     # lid
    rect(-14, LID_TOP, 14, LID_TOP + 2.5, fc="#263238", ec="none")                           # OLED
    rect(-20, -7, 20, -3, fc="#eceff1", ec="0.2", lw=lw, hatch="////" if not small else None)  # Peltier
    rect(-30, -32, 30, -7, fc="#ffcc80", ec="0.3", lw=lw)                                    # heatsink
    rect(-20, -60, 20, -32, fc="#cfd8dc", ec="0.3", lw=lw)                                   # fan
    if not small:
        for x, z, t in [(0, 40, "water ~275 mL"), (0, -5, "Peltier"), (0, -20, "heatsink"), (0, -46, "fan"),
                        (0, LID_TOP - 6, "lid"), (-R_IN - 4, 35, "foam")]:
            ax.text(*P(x, z), t, ha="center", va="center", fontsize=6, color="0.25",
                    rotation=90 if t == "foam" else 0)
        ax.text(*P(0, LID_TOP + 5), "OLED", ha="center", fontsize=6, color="0.25")
    # thermowell
    pts = [P(*p) for p in d[2]]
    w = TUBE_OD * s / 0.3528                                   # tube width in points
    ax.plot(*zip(*pts), color="#455a64", lw=w, solid_capstyle="round", solid_joinstyle="round", zorder=5)
    ax.plot(*zip(*pts), color="#cfd8dc", lw=w * 0.72, solid_capstyle="round", solid_joinstyle="round", zorder=6)
    tip, prev = d[2][-1], d[2][-2]
    dx, dz = tip[0] - prev[0], tip[1] - prev[1]
    n = (dx * dx + dz * dz) ** 0.5
    sx, sz = tip[0] - dx / n * 10, tip[1] - dz / n * 10
    ax.plot(*zip(P(sx, sz), P(*tip)), color="#e53935", lw=w * 0.55, solid_capstyle="round", zorder=7)
    for sp in d[3]:
        x, y = P(*sp)
        ax.add_patch(Rectangle((x - 6.5 * s, y - 2.5 * s), 13 * s, 5 * s, fc="#43a047", ec="black", lw=0.4, zorder=8))
    start = P(*d[2][0])
    if len(d) > 8:                                   # cable path drawn for this design
        cp = [P(*q) for q in d[8]]
        ax.plot(*zip(*cp), color="#6a1b9a", lw=1.4 if not small else 0.8, ls="--", zorder=8)
        start = cp[-1]
    else:
        ax.plot([start[0], start[0] + (6 if not small else 3) * s * 2], [start[1], start[1] + 4 * s], color="#6a1b9a",
                lw=1.0 if not small else 0.6, ls="--", zorder=8)
    if not small:
        ax.annotate("sensor (last 10 mm\nof the probe)", xy=P(*tip), xytext=(P(*tip)[0] + 28, P(*tip)[1] - 14),
                    fontsize=6, color="#c62828", arrowprops=dict(arrowstyle="->", color="#c62828", lw=0.6), zorder=9)
        if d[3]:
            ax.annotate("seal: PG7 gland /\nfood-grade silicone", xy=P(*d[3][0]),
                        xytext=(P(*d[3][0])[0] + 22, P(*d[3][0])[1] + 10), fontsize=6, color="#2e7d32",
                        arrowprops=dict(arrowstyle="->", color="#2e7d32", lw=0.6), zorder=9)
        ax.text(start[0] + 14 * s, start[1] + 5 * s, "cable to\nthe board", fontsize=6, color="#6a1b9a")
        # tip height and immersion
        tz = tip[1]
        if tz < WATER:
            xa = P(-R_IN + 3, 0)[0]
            ax.annotate("", xy=(xa, P(0, tz)[1]), xytext=(xa, P(0, 0)[1]),
                        arrowprops=dict(arrowstyle="<->", lw=0.6, color="0.2"))
            ax.text(xa + 1.5, P(0, tz / 2)[1], f"tip {tz:.0f} mm\nabove floor", fontsize=5.8, va="center")


def stars(n):
    return "*" * n + "." * (5 - n)


def overview(pdf):
    fig = plt.figure(figsize=(297 / 25.4, 210 / 25.4))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 297); ax.set_ylim(0, 210); ax.axis("off")
    ax.text(148.5, 201, "ThermoX - 10 THERMOWELL POSITIONS (mock designs)", ha="center", fontsize=14, weight="bold")
    ax.text(148.5, 195, "Round bottle, cut through the middle. Grey tube = thermowell (8 mm stainless, closed end), red = "
            "sensor, green = seal, purple dashed = cable.", ha="center", fontsize=7.5, color="0.25")
    for i, d in enumerate(DESIGNS):
        cx = 30 + (i % 5) * 58
        cy = 141 if i < 5 else 55
        section(ax, cx, cy, 0.38, d, small=True)
        tot = sum(d[4])
        ax.text(cx, cy - 32, d[1], ha="center", fontsize=7.2, weight="bold")
        ax.text(cx, cy - 37, f"score {tot}/25", ha="center", fontsize=6.6,
                color="#2e7d32" if i == RECOMMEND else "0.3", weight="bold" if i == RECOMMEND else None)
        ax.text(cx - 24, cy + 40, str(i + 1), fontsize=10, weight="bold",
                bbox=dict(boxstyle="circle,pad=0.25", fc="#fff3cd" if i == RECOMMEND else "white", ec="0.3"))
    ax.text(10, 5, "Scores (1-5 each): " + ", ".join(CRIT) + ".  Recommended: design 10, then design 2.  "
            "Page 2: comparison. Pages 3-12: each design. Page 13: how to build the thermowell.", fontsize=7.5, weight="bold")
    pdf.savefig(fig); plt.close(fig)


def table(pdf):
    fig = plt.figure(figsize=(297 / 25.4, 210 / 25.4))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 297); ax.set_ylim(0, 210); ax.axis("off")
    ax.text(148.5, 199, "COMPARISON (5 = best)", ha="center", fontsize=14, weight="bold")
    xs = [12, 82] + [118 + i * 28 for i in range(5)] + [262]
    heads = ["Design", "Where"] + CRIT + ["Total"]
    y = 186
    for x, h in zip(xs, heads):
        ax.text(x, y, h, fontsize=7.5, weight="bold", va="center")
    for i, d in enumerate(DESIGNS):
        y -= 9
        if i == RECOMMEND:
            ax.add_patch(Rectangle((10, y - 4), 277, 8, fc="#e8f5e9", ec="none"))
        row = [d[0].split(". ", 1)[0], d[1]] + [stars(v) for v in d[4]] + [f"{sum(d[4])}/25"]
        for x, t in zip(xs, row):
            ax.text(x, y, t, fontsize=7.5, va="center", family="monospace" if "*" in t else None)
    y -= 14
    notes = [
        "How the scores were given (our judgement, to be checked with tests):",
        "  Accuracy: does the sensor sit in water that stands for the whole cup (not next to the Peltier, not at the surface)?",
        "  No leak: a hole below the water line has to be sealed and must stay food-safe; no hole scores 5.",
        "  Cleaning / drinking: is the tube in the way when you drink, pour or wash the cup?",
        "  Cable / lid: the OLED is already in the lid; a sensor in the lid needs a plug to take the lid off.",
        "  Easy to build: straight tube and one gland score high; holes in the 1-3 mm aluminium cup score low.",
        "",
        "Recommendation: design 10 (no hole, lid free, easy). Second choice: design 2 (in the lid, centre free).",
        "Whatever you choose, prove it with the validation test: compare with a reference thermometer at 10-50 C,",
        "measure the response time with and without thermal paste, and repeat each test 3-5 times.",
        "Rule of thumb for thermowells: immersion about 10 x the tube diameter (here ~80 mm). The cup is only 68 mm deep,",
        "so keep the tip low (about 20 mm above the floor), use thermal paste, and measure the lag instead of guessing it.",
    ]
    for t in notes:
        ax.text(12, y, t, fontsize=7.5, va="top", weight="bold" if t.startswith("Recommendation") else None)
        y -= 5.2
    pdf.savefig(fig); plt.close(fig)


def detail_page(pdf, i, d):
    fig = plt.figure(figsize=(297 / 25.4, 210 / 25.4))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 297); ax.set_ylim(0, 210); ax.axis("off")
    ax.text(10, 199, f"DESIGN {d[0]}" + ("   (RECOMMENDED)" if i == RECOMMEND else ""), fontsize=14, weight="bold",
            color="#2e7d32" if i == RECOMMEND else "black")
    section(ax, 85, 95, 1.05, d)
    x, y = 170, 185
    ax.text(x, y, "What it is", fontsize=9, weight="bold"); y -= 6
    import textwrap
    for line in textwrap.wrap(d[5], 62):
        ax.text(x, y, line, fontsize=7.5); y -= 4.6
    y -= 3
    ax.text(x, y, "Good", fontsize=9, weight="bold", color="#2e7d32"); y -= 6
    for t in d[6]:
        for k, line in enumerate(textwrap.wrap(t, 60)):
            ax.text(x, y, ("+ " if k == 0 else "  ") + line, fontsize=7.5); y -= 4.6
    y -= 3
    ax.text(x, y, "Not so good", fontsize=9, weight="bold", color="#c62828"); y -= 6
    for t in d[7]:
        for k, line in enumerate(textwrap.wrap(t, 60)):
            ax.text(x, y, ("- " if k == 0 else "  ") + line, fontsize=7.5); y -= 4.6
    y -= 3
    ax.text(x, y, "Score", fontsize=9, weight="bold"); y -= 6
    for c, v in zip(CRIT, d[4]):
        ax.text(x, y, f"{c:<22}", fontsize=7.5, family="monospace")
        ax.text(x + 52, y, stars(v), fontsize=7.5, family="monospace"); y -= 4.6
    ax.text(x, y, f"{'Total':<22}", fontsize=7.5, family="monospace", weight="bold")
    ax.text(x + 52, y, f"{sum(d[4])}/25", fontsize=7.5, family="monospace", weight="bold")
    ax.text(10, 10, "Mock design for comparison: sizes from the round bottle (cup 72 mm inside, water 68 mm deep). "
            "Not built or tested yet.", fontsize=7, color="0.35")
    pdf.savefig(fig); plt.close(fig)


def build_page(pdf):
    fig = plt.figure(figsize=(297 / 25.4, 210 / 25.4))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 297); ax.set_ylim(0, 210); ax.axis("off")
    ax.text(10, 199, "HOW TO MAKE THE THERMOWELL", fontsize=14, weight="bold")
    # drawing of the tube, scale 2:1
    s, x0, yc = 2.0, 20, 150
    L = 90
    ax.add_patch(FancyBboxPatch((x0, yc - 4 * s), L * s, 8 * s, boxstyle="round,pad=0,rounding_size=8",
                                fc="#cfd8dc", ec="#455a64", lw=1.2))
    ax.add_patch(Rectangle((x0, yc - 3.5 * s), (L - 1.5) * s, 7 * s, fc="white", ec="none"))
    ax.add_patch(Rectangle((x0, yc - 3 * s), (L - 3) * s, 6 * s, fc="#90a4ae", ec="0.3", lw=0.6))   # probe
    ax.add_patch(Rectangle((x0 + (L - 13) * s, yc - 3 * s), 10 * s, 6 * s, fc="#e53935", ec="none"))
    ax.add_patch(Rectangle((x0 + (L - 3) * s, yc - 3.5 * s), 1.5 * s, 7 * s, fc="#fff59d", ec="none"))
    ax.plot([x0 - 25, x0], [yc, yc], color="#6a1b9a", lw=2)
    for t, xy, xt in [("closed, sealed tip", (x0 + L * s, yc), (x0 + L * s + 8, yc + 22)),
                      ("thermal paste fills the gap", (x0 + (L - 2) * s, yc - 3 * s), (x0 + L * s + 6, yc - 18)),
                      ("DS18B20 sensor: last 10 mm of the probe", (x0 + (L - 8) * s, yc + 3 * s),
                       (x0 + 70, yc + 26)),
                      ("probe, 6 mm stainless", (x0 + 40 * s, yc), (x0 + 40, yc - 20)),
                      ("cable", (x0 - 12, yc), (x0 - 12, yc + 14))]:
        ax.annotate(t, xy=xy, xytext=xt, fontsize=7.5, arrowprops=dict(arrowstyle="->", lw=0.7))
    ax.annotate("", xy=(x0, yc - 18 * s), xytext=(x0 + L * s, yc - 18 * s), arrowprops=dict(arrowstyle="<->", lw=0.7))
    ax.text(x0 + L * s / 2, yc - 18 * s - 5, "about 90 mm (cut to your design)", ha="center", fontsize=7.5)
    ax.text(x0 + L * s + 30, yc - 2, "outside 8 mm\ninside 7 mm", fontsize=7.5)
    steps = [
        "Parts",
        "- Stainless steel tube 304 or 316, 8 mm outside, 7 mm inside (0.5 mm wall), closed at one end.",
        "  Easiest: buy a ready-made 'thermowell 8 mm' (sold for home brewing and smokers). A stainless drinking straw",
        "  of the right size also works if the end is sealed by a welder (TIG) or with lead-free silver solder.",
        "- Thermal paste (a small tube), food-grade silicone sealant, PG7 cable gland or silicone grommet (lid designs).",
        "",
        "Steps",
        "1. Close and check the tip: fill the tube with water and look for drops for 10 minutes. No drops = sealed.",
        "2. Put a little thermal paste in the tube, then push the probe in until it touches the tip.",
        "3. Fix the tube (gland in the lid, or clips over the cup rim for design 10).",
        "4. The tip must sit in the water: about 20 mm above the floor, away from the Peltier and the surface.",
        "5. Hold the cable so it cannot pull the probe out (cable tie or a drop of silicone at the top of the tube).",
        "6. Test: compare with a reference thermometer at 10, 20, 30, 40 and 50 C; measure the response time.",
        "",
        "Only stainless steel and food-grade silicone touch the drink. No hot glue, no tape, nothing inside the water but the tube.",
        "Never bend the 6 mm steel part of the probe (the sensor and its seal are inside). Keep the thermowell straight; only",
        "the cable may bend, in a smooth curve, with no sharp kink where it leaves the steel part.",
    ]
    y = 100
    for t in steps:
        ax.text(12, y, t, fontsize=7.6, va="top", weight="bold" if t in ("Parts", "Steps") else None)
        y -= 4.9
    pdf.savefig(fig); plt.close(fig)


def main():
    name = os.path.join(OUT, "thermowell_designs.pdf")
    with PdfPages(name) as pdf:
        overview(pdf)
        table(pdf)
        for i, d in enumerate(DESIGNS):
            detail_page(pdf, i, d)
        build_page(pdf)
    print("->", os.path.basename(name))


if __name__ == "__main__":
    main()
