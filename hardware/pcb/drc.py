"""Clearance and connectivity check for both layout variants (run: python3 drc.py)."""
import itertools
import sys

from reportlab.pdfbase.pdfmetrics import stringWidth
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

import layout as L

MIN_CLEAR = 0.5   # mm, copper to copper of different nets
EDGE_CLEAR = 1.0  # mm, copper to board edge
HOLE_CLEAR = 1.0  # mm, copper to mounting hole edge


def check(name, B):
    items = []  # (net, geom, desc)
    for p in B.pads:
        items.append((p["net"], Point(B.mm((p["x"], p["y"]))).buffer(p["d"] / 2, 32),
                      f'{p["ref"]}.{p["pin"]}'))
    for net, w, pts in B.traces:
        geom = LineString([B.mm(q) for q in pts]).buffer(w / 2, 16)
        items.append((net, geom, f"trace {net} {pts[0]}->{pts[-1]}"))
    for i, (s, tx, ty, size) in enumerate(B.copper_text):
        cx, cy = B.mm((tx, ty))
        w = stringWidth(s, "Helvetica-Bold", size)
        items.append((f"TEXT{i}", box(cx - w / 2, cy - 0.37 * size, cx + w / 2, cy + 0.35 * size),
                      f"text '{s}'"))

    errors = []
    worst = 99.0
    for (n1, g1, d1), (n2, g2, d2) in itertools.combinations(items, 2):
        if n1 == n2:
            continue
        dist = g1.distance(g2)
        worst = min(worst, dist)
        if dist < MIN_CLEAR:
            errors.append(f"CLEARANCE {dist:.2f} mm: {d1}  <->  {d2}")

    inner = box(0, 0, B.BOARD_W, B.BOARD_H).buffer(-EDGE_CLEAR)
    for net, g, d in items:
        if not inner.contains(g):
            errors.append(f"EDGE: {d} closer than {EDGE_CLEAR} mm to the board edge")
    for hx, hy in B.holes:
        hole = Point(B.mm((hx, hy))).buffer(L.HOLE_D / 2)
        for net, g, d in items:
            if g.distance(hole) < HOLE_CLEAR:
                errors.append(f"HOLE {hx},{hy}: {d} too close")

    # Connectivity: every pad of a net in one copper island (wire links join islands)
    nets = sorted({p["net"] for p in B.pads if not p["net"].startswith("NC:")})
    for net in nets:
        merged = unary_union([g for n, g, _ in items if n == net])
        islands = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
        for ref, jnet in B.JUMPERS:
            if jnet != net:
                continue
            ends = [Point(B.mm((p["x"], p["y"]))) for p in B.pads if p["ref"] == ref]
            hit = [i for i, isl in enumerate(islands) if any(isl.contains(e) for e in ends)]
            if len(hit) == 2:
                islands[hit[0]] = unary_union([islands[hit[0]], islands[hit[1]]])
                islands.pop(hit[1])
        pads_of_net = [p for p in B.pads if p["net"] == net]
        for p in pads_of_net:
            if not any(isl.contains(Point(B.mm((p["x"], p["y"])))) for isl in islands):
                errors.append(f"OPEN: pad {p['ref']}.{p['pin']} not on copper")
        if len(islands) != 1:
            errors.append(f"OPEN: net {net} is split into {len(islands)} islands")
        if len(pads_of_net) < 2:
            errors.append(f"NET {net} has only {len(pads_of_net)} pad(s)")

    print(f"[{name}] pads={len(B.pads)} traces={len(B.traces)} nets={len(nets)}  "
          f"board {B.BOARD_W:.1f} x {B.BOARD_H:.1f} mm, worst clearance {worst:.2f} mm")
    for e in errors:
        print("  " + e)
    print("  DRC OK" if not errors else f"  {len(errors)} problem(s)")
    return not errors


def netlist(B):
    out = {}
    for p in B.pads:
        if not p["net"].startswith("NC:"):
            out.setdefault(p["net"], []).append(f'{p["ref"]}.{p["pin"]}')
    return out


if __name__ == "__main__":
    boards = {f"86x67 {k}": B for k, B in L.VARIANTS.items()}
    boards.update({f"{s}x{s} {k}": B for (s, k), B in L.SMALL.items()})
    ok = all([check(k, B) for k, B in boards.items()])
    a = netlist(L.VARIANTS["25.4"])
    a_small = {n: m for n, m in a.items() if n not in ("BATT", "BATP")}
    a_small["GND"] = [m for m in a["GND"] if not m.startswith(("J7", "R4", "C1"))]
    for k, B in boards.items():
        ref = a if B.battery else a_small
        if netlist(B) != ref:
            print(f"netlist of {k} differs from the reference")
            ok = False
    for net, members in sorted(a.items()):
        print(f"  {net:5s} {' '.join(members)}")
    sys.exit(0 if ok else 1)
