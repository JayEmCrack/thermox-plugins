#!/usr/bin/env python3
"""ThermoX design drafts: one parts list per design -> STEP, OBJ/MTL, (STL, Blender script) and the 3D viewer data.

Units: millimetres, Z up. Round designs are centred on the Z axis. The "retro" box has X = depth (0 = front), Y = width, Z = up.
Every design uses the same inside parts: 3S2P 21700 pack, LM2596 buck module, BTS7960, ESP32, SUNON fan, copper heatsink,
TEC1-12706 and a water cup. Only the outside, the handle and the slots differ.

  python3 make_models.py OUTDIR            STEP + OBJ/MTL for every design (push fan)
  python3 make_models.py OUTDIR --extras   also STL and a Blender script
  python3 make_models.py OUTDIR --pull     export the pull-fan version of the round designs

STEP needs `pip install cadquery`; everything else needs only the standard library.
"""
import json, math, os, sys

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
FLAGS = [a for a in sys.argv[1:] if a.startswith("--")]
OUT = ARGS[0] if ARGS else "."
SEG = 48                      # segments on round parts
P = []                        # the parts of the design being built


def box(name, grp, x0, x1, y0, y1, z0, z1, color, label=None, alpha=1.0, rotz=0.0, edges=False, rotx=0.0, roty=0.0, skin=False, metal=None, flow=None):
    """Axis-aligned box; rotx/roty/rotz (degrees) turn it about its own centre, applied in that order about the global axes."""
    P.append(dict(kind="box", name=name, grp=grp, x0=x0, x1=x1, y0=y0, y1=y1, z0=z0, z1=z1, color=color,
                  alpha=alpha, rotz=rotz, rotx=rotx, roty=roty, edges=edges, skin=skin, metal=metal, flow=flow, label=label or name))


def cyl(name, grp, cx, cy, r, z0, z1, color, label=None, alpha=1.0, skin=False, metal=None, flow=None):
    P.append(dict(kind="cyl", name=name, grp=grp, cx=cx, cy=cy, r=r, z0=z0, z1=z1, color=color, alpha=alpha,
                  rotz=0.0, rotx=0.0, roty=0.0, edges=False, skin=skin, metal=metal, flow=flow, label=label or name))


def ring(name, grp, cx, cy, r_in, r_out, z0, z1, color, label=None, alpha=1.0, skin=False, metal=None, flow=None):
    P.append(dict(kind="ring", name=name, grp=grp, cx=cx, cy=cy, r_in=r_in, r_out=r_out, z0=z0, z1=z1, color=color,
                  alpha=alpha, rotz=0.0, rotx=0.0, roty=0.0, edges=False, skin=skin, metal=metal, flow=flow, label=label or name))


def lathe(name, grp, pts, color, label=None, alpha=1.0, skin=False, metal=None, flow=None):
    """Solid of revolution about the Z axis. pts = closed outline of (radius, z), counter-clockwise (radius to the right, z up)."""
    P.append(dict(kind="lathe", name=name, grp=grp, pts=[list(q) for q in pts], cx=0.0, cy=0.0, color=color, alpha=alpha,
                  rotz=0.0, rotx=0.0, roty=0.0, edges=False, skin=skin, metal=metal, flow=flow, label=label or name))


def stad(name, grp, cx, cy, a, r, z0, z1, color, label=None, t=None, alpha=1.0, skin=False, metal=None, flow=None):
    """Stadium (rounded-end) prism: straight length a along X, end radius r. Hollow when the wall thickness t is given."""
    P.append(dict(kind="stad", name=name, grp=grp, cx=cx, cy=cy, a=a, r=r, t=t, z0=z0, z1=z1, color=color, alpha=alpha,
                  rotz=0.0, rotx=0.0, roty=0.0, edges=False, skin=skin, metal=metal, flow=flow, label=label or name))


def stad_outline(cx, cy, a, r, n=24):
    """Counter-clockwise outline of a stadium: right half circle, then left half circle."""
    pts = []
    for i in range(n + 1):
        ang = -math.pi / 2 + math.pi * i / n
        pts.append((cx + a / 2 + r * math.cos(ang), cy + r * math.sin(ang)))
    for i in range(n + 1):
        ang = math.pi / 2 + math.pi * i / n
        pts.append((cx - a / 2 + r * math.cos(ang), cy + r * math.sin(ang)))
    return pts


def shell_pts(outer, t=1.5):
    """Hollow wall of thickness t from the outer profile (bottom to top)."""
    return [tuple(q) for q in outer] + [(r - t, z) for r, z in reversed(outer)]


def waist(r_end, depth, z0, z1, step=4):
    """Outer profile that narrows by `depth` in the middle between z0 and z1."""
    pts = [(r_end, z0)]
    z = z0 + step
    while z < z1:
        pts.append((r_end - depth * math.sin(math.pi * (z - z0) / (z1 - z0)), z))
        z += step
    pts.append((r_end, z1))
    return pts


def r_at(profile, z):
    """Outer radius of a profile (list of (r, z), z rising) at height z."""
    for (ra, za), (rb, zb) in zip(profile, profile[1:]):
        if za <= z <= zb and zb > za:
            return ra + (rb - ra) * (z - za) / (zb - za)
    return profile[-1][0]


# ================================================================ parts every design shares
DZ = 14                       # the buck module sits under the battery, which lifts everything above the bay by 14 mm
TOP = 263                     # top face of the lid on the round designs
LID0 = 250                    # base of the lid = top of the cup


def lm2596(cx, cy, z0, long_axis="x"):
    """LM2596 buck module lying flat: 43 x 21 x 14 mm. Output must be set to 5.0 V before the ESP32 is connected."""
    def m(dx, dy):                                   # module frame -> design frame
        return (cx + dx, cy + dy) if long_axis == "x" else (cx + dy, cy + dx)
    def bx(name, x0, x1, y0, y1, za, zb, color, label):
        (ax, ay), (bx_, by) = m(x0, y0), m(x1, y1)
        box(name, "elec", min(ax, bx_), max(ax, bx_), min(ay, by), max(ay, by), za, zb, color, label)
    desc = "LM2596 buck module (24/12 V in, 5 V out), about 43 x 21 x 14 mm"
    bx("lm2596_pcb", -21.5, 21.5, -10.5, 10.5, z0, z0 + 1.6, "#1b57b8", desc)
    bx("lm2596_ic", -19, -11, -3.5, 3.5, z0 + 1.6, z0 + 5.6, "#1d1f22", "LM2596 regulator chip")
    bx("lm2596_trimmer", 14, 20, -3.5, 3.5, z0 + 1.6, z0 + 7.6, "#2c6fd1", "LM2596 output trimmer (set to 5.0 V)")
    for nm, dx, dy in (("inductor", -2.5, 0), ("cap_1", 11, -5.2), ("cap_2", 11, 5.2)):
        x, y = m(dx, dy)
        r, h = (6.5, 12.4) if nm == "inductor" else (3.8, 9)
        cyl("lm2596_" + nm, "elec", x, y, r, z0 + 1.6, z0 + 1.6 + h, "#3b3f44" if nm == "inductor" else "#25292d",
            "LM2596 inductor" if nm == "inductor" else "LM2596 capacitor")


def stack(cx, z0, flip=False):
    """Fan, copper heatsink (fins run along X), foam ring, TEC and water plate, bottom to top from z0."""
    FRAME = "#3a4650"
    FL = "SUNON fan frame, 40 x 40 x 28 mm" + (" (turned over in the pull version, so it draws air down out of the fins)" if flip else "")
    box("fan_frame_a", "fan", cx - 20, cx + 20, -20, -17, z0, z0 + 28, FRAME, FL)
    box("fan_frame_b", "fan", cx - 20, cx + 20, 17, 20, z0, z0 + 28, FRAME, FL)
    box("fan_frame_c", "fan", cx - 20, cx - 17, -17, 17, z0, z0 + 28, FRAME, FL)
    box("fan_frame_d", "fan", cx + 17, cx + 20, -17, 17, z0, z0 + 28, FRAME, FL)
    cyl("fan_hub", "fan", cx, 0, 8, z0 + 1, z0 + 27, "#7b8791", "Fan hub")
    for i in range(7):
        a = i * 360.0 / 7
        bx_ = cx + 12.25 * math.cos(math.radians(a)); by = 12.25 * math.sin(math.radians(a))
        box("fan_blade_%d" % (i + 1), "fan", bx_ - 4.25, bx_ + 4.25, by - 0.8, by + 0.8, z0 + 4, z0 + 24, "#98a4ad", "Fan blade", rotz=a)
    COPPER = "#c98a5e"
    for k in range(17):
        yc = -24 + 3 * k
        box("fin_%02d" % (k + 1), "heatsink", cx - 25, cx + 25, yc - 0.45, yc + 0.45, z0 + 28, z0 + 53, COPPER, "Heatsink fin, 0.9 mm thick, 25 mm tall, 3 mm pitch")
    box("heatsink_base", "heatsink", cx - 25, cx + 25, -25, 25, z0 + 53, z0 + 58, COPPER, "Heatsink base, 50 x 50 x 5 mm (proposed, copper)")
    FOAM = "#e0c88a"
    zt = z0 + 58
    box("foam_ring_a", "thermal", cx - 25, cx - 20, -25, 25, zt, zt + 4, FOAM, "Foam ring around the TEC, 4 mm")
    box("foam_ring_b", "thermal", cx + 20, cx + 25, -25, 25, zt, zt + 4, FOAM, "Foam ring around the TEC, 4 mm")
    box("foam_ring_c", "thermal", cx - 20, cx + 20, -25, -20, zt, zt + 4, FOAM, "Foam ring around the TEC, 4 mm")
    box("foam_ring_d", "thermal", cx - 20, cx + 20, 20, 25, zt, zt + 4, FOAM, "Foam ring around the TEC, 4 mm")
    box("tec_hot_face", "thermal", cx - 20, cx + 20, -20, 20, zt, zt + 1, "#e8743b", "TEC1-12706 40 x 40 x 3.8 mm, heatsink side (hot when cooling)")
    box("tec_body", "thermal", cx - 20, cx + 20, -20, 20, zt + 1, zt + 2.8, "#eceff1", "TEC1-12706 40 x 40 x 3.8 mm")
    box("tec_cold_face", "thermal", cx - 20, cx + 20, -20, 20, zt + 2.8, zt + 3.8, "#3d9fd6", "TEC1-12706 40 x 40 x 3.8 mm, water side (cold when cooling)")
    box("water_plate", "thermal", cx - 20, cx + 20, -20, 20, zt + 4, zt + 12, "#b9c2c9", "Water-side plate, 40 x 40 x 8 mm (aluminium or copper)")


def round_inside():
    """Everything that sits inside the round bottles."""
    # battery bay: LM2596 on the floor, pack on a carrier above it, boards standing beside the pack
    lm2596(0, 0, 4, "x")
    box("pack_carrier", "elec", -30, 30, -21, 21, 18, 19, "#8d99a3", "Carrier plate that holds the pack above the buck module, 1 mm")
    for ix, cx in enumerate((-21, 0, 21)):
        for iy, cy in enumerate((-10.5, 10.5)):
            cyl("cell_%d%d" % (ix + 1, iy + 1), "elec", cx, cy, 10.5, 19, 89, "#2f8f6f", "21700 cell, 21 x 70 mm (3S2P pack, 6 cells)")
    box("bms_3s", "elec", -30, 30, -20, 20, 90, 93, "#3f6f9a", "3S battery protection board (BMS), size depends on the part")
    box("bts7960", "elec", -25, 25, 22.5, 34.5, 4, 54, "#1e5aa8", "BTS7960 board without heatsink, about 50 x 50 mm (standing)")
    box("esp32_30pin", "elec", -14, 14, -35.5, -22.5, 5, 57, "#1d2a33", "ESP32 30-pin board, about 52 x 28 mm (standing)")
    cyl("bulkhead", "shell", 0, 0, 43.0, 96, 98, "#8d99a3", "Bulkhead between battery bay and air path, 2 mm (wires pass through)")
    # fan 106-134, fins 134-159, base 159-164, TEC 164-168, plate 168-176
    stack(0, 92 + DZ)
    cyl("cup_floor", "cup", 0, 0, 37, 162 + DZ, 165 + DZ, "#c5ced6", "Cup floor, 3 mm aluminium spreader plate")
    ring("cup_wall", "cup", 0, 0, 36, 37, 165 + DZ, LID0, "#c5ced6", "Water cup wall, inside diameter 72 mm", 0.55)
    ring("insulation_sleeve", "cup", 0, 0, 37, 42.5, 165 + DZ, LID0, "#e0c88a", "Foam insulation sleeve, 5.5 mm", 0.4)
    cyl("water", "water", 0, 0, 36, 165 + DZ, LID0 - 3, "#58b4e2", "Water, about 275 mL (68 mm deep)", 0.55)


def round_display(btn_color, btn_metal=None, bezel=None, bezel_metal=None, btn_r=3.2):
    box("oled_1_5in", "display", -22, 16, -19, 19, TOP, TOP + 3.2, "#0b1218", "1.5 inch OLED module, about 38 x 38 mm (on the lid)")
    box("oled_screen", "display", -19, 13, -16, 16, TOP + 3.2, TOP + 3.4, "#9fe4ff", "OLED screen (128 x 128)")
    if bezel:
        for nm, (x0, x1, y0, y1) in (("a", (-25, 19, -22, -19)), ("b", (-25, 19, 19, 22)), ("c", (-25, -22, -19, 19)), ("d", (16, 19, -19, 19))):
            box("oled_bezel_%s" % nm, "display", x0, x1, y0, y1, TOP, TOP + 3.6, bezel, "Bezel around the display", metal=bezel_metal)
    for sy in (-8, 8):
        cyl("button_%s" % ("1" if sy < 0 else "2"), "display", 25, sy, btn_r, TOP, TOP + 3.2, btn_color, "Push button (GPIO32 / GPIO33)", metal=btn_metal)


def arch(prefix, label, R, Wd, T, n, X0, Z0, color, metal, mount=None, mount_metal=None):
    """Carry loop in the Y-Z plane made of n short straight pieces, plus two mounts."""
    step = 180.0 / n
    seg = 2 * R * math.sin(math.radians(step / 2)) + 0.6
    for i in range(n):
        th = step / 2 + step * i
        py, pz = R * math.cos(math.radians(th)), Z0 + R * math.sin(math.radians(th))
        box("%s_%02d" % (prefix, i + 1), "handle", X0 - Wd / 2, X0 + Wd / 2, py - seg / 2, py + seg / 2, pz - T / 2, pz + T / 2, color, label, rotx=th - 90, metal=metal)
    if mount:
        for sy in (-1, 1):
            box("%s_mount_%s" % (prefix, "L" if sy < 0 else "R"), "handle", X0 - Wd / 2 - 1, X0 + Wd / 2 + 1, min(sy * (R - 3), sy * (R + 3)), max(sy * (R - 3), sy * (R + 3)),
                Z0 - 1.5, Z0 + 2.5, mount, "Handle mount", metal=mount_metal)
    return Z0 + R + T / 2


def base_and_lugs(S, lug_z=(214, 222), plate=True, plate_color=None):
    lathe("base_pad", "shell", [(0, 0), (40, 0), (43, 1.8), (44.2, 3), (0, 3)], S["base"], "Rubber base pad, 3 mm (non-slip)", skin=True)
    for sy in (-1, 1):
        box("strap_lug_%s" % ("L" if sy < 0 else "R"), "shell", -3, 3, min(sy * 43.5, sy * 48.5), max(sy * 43.5, sy * 48.5), lug_z[0], lug_z[1],
            S.get("lug", S["accent"]), "Strap lug for a shoulder strap", skin=True, metal=S.get("lug_metal", S.get("brass")))
    if plate:
        box("nameplate", "shell", 42.8, 46.3, -12, 12, lug_z[0] + 1, lug_z[0] + 9, plate_color or S["accent"], "Name plate, 24 x 8 mm", skin=True, metal=S.get("brass"))


def body_parts(S, LOWER, MID, UPPER, lid_pts, waist_color=None, lid_label="Domed removable lid, 13 mm"):
    lathe("body_lower", "shell", shell_pts(LOWER), S["body"], "Lower body, holds the battery and electronics", skin=True)
    lathe("body_waist", "shell", shell_pts(MID), waist_color or S.get("waist", S["body"]), "Waisted middle band: fan intake and exhaust slots", skin=True)
    lathe("body_upper", "shell", shell_pts(UPPER), S["body"], "Upper body around the insulated water cup", skin=True)
    lathe("lid", "lid", lid_pts, S["lid"], lid_label, skin=True)


def slots(color, MID):
    """Dark slot markers for both fan directions; the viewer shows the set that matches the chosen direction."""
    z_rows = (124 + DZ, 129.5 + DZ, 135 + DZ, 140.5 + DZ)
    row_r = sum(r_at(MID, z + 1.75) for z in z_rows) / 4.0
    ring_r = r_at(MID, 102.0)
    for flow, n, w, lbl in (("push", 8, 14, "Air intake slot"), ("pull", 12, 17, "Air exhaust slot (warm air leaves here)")):
        for k in range(n):
            a = 360.0 / n / 2 + 360.0 / n * k
            px, py = (ring_r - 0.4) * math.cos(math.radians(a)), (ring_r - 0.4) * math.sin(math.radians(a))
            box("%s_slot_%d" % ("intake" if flow == "push" else "exhaust", k + 1), "shell", px - 0.9, px + 0.9, py - w / 2, py + w / 2, 85.5 + DZ, 90.5 + DZ,
                color, lbl, rotz=a, skin=True, flow=flow)
    for flow, nm, lbl in (("push", "exhaust", "Exhaust slot (warm air leaves here)"), ("pull", "intake", "Air intake slot (cool air is drawn in here)")):
        for side, a in (("front", 0), ("rear", 180)):
            px, py = (row_r - 0.2) * math.cos(math.radians(a)), (row_r - 0.2) * math.sin(math.radians(a))
            for j, z in enumerate(z_rows):
                box("%s_slot_%s_%d" % (nm, side, j + 1), "shell", px - 0.9, px + 0.9, py - 18, py + 18, z, z + 3.5, color, lbl, rotz=a, skin=True, flow=flow)


def finish_round(MID_cfg=None):
    ex = {"shell": (0, 0, 0), "lid": (0, 0, 95), "display": (0, 0, 95), "handle": (0, 0, 95), "cup": (0, 0, 58), "water": (0, 0, 58),
          "thermal": (0, 0, 28), "heatsink": (0, 0, 0), "fan": (0, 0, -30), "elec": (0, 0, 0)}
    pex = {"bms_3s": (0, 0, 22), "bts7960": (0, 62, 0), "esp32_30pin": (0, -62, 0)}
    for p in P:
        if p["name"].startswith("lm2596_"):
            p["ex"] = [70, 0, 0]
        else:
            p["ex"] = list(pex.get(p["name"], ex[p["grp"]]))


def arrows_round():
    """Airflow arrows for the viewer: [origin x, y, z, direction x, y, z, length, 'in'/'out', 'push'/'pull']."""
    out = []
    def radial(a_deg, r0, z, length, inward, flow):
        c, sn = math.cos(math.radians(a_deg)), math.sin(math.radians(a_deg))
        d = -1 if inward else 1
        out.append([r0 * c, r0 * sn, z, d * c, d * sn, 0, length, "in" if inward else "out", flow])
    zr = 88 + DZ
    for k in range(8):
        radial(22.5 + 45 * k, 62, zr, 18, True, "push")
    out.append([0, 0, 93 + DZ, 0, 0, 1, 28, "in", "push"])
    for a in (0, 180):
        radial(a, 24, 132.5 + DZ, 36, False, "push")
    for a in (0, 180):
        radial(a, 64, 132.5 + DZ, 36, True, "pull")
    out.append([0, 0, 121 + DZ, 0, 0, -1, 28, "out", "pull"])
    for k in range(12):
        radial(15 + 30 * k, 40, zr, 20, False, "pull")
    return out


def finish_design(name, title, profiles):
    return dict(name=name, title=title, parts=list(P), flow=arrows_round(), profiles=profiles, kind="round")


# ================================================================ the designs
def lid_dome():
    return [(0, LID0), (43.0, LID0), (44.6, LID0 + 1.8), (44.6, LID0 + 5.5), (43.4, LID0 + 8.3), (40.0, LID0 + 10.6), (35, LID0 + 12.2), (30, TOP), (0, TOP)]


def build_classic():
    P.clear()
    S = dict(body="#2f5d49", waist="#e8dfc9", accent="#c9a24a", grip="#8a5a36", lid="#efe8d6", base="#3a2a20", slot="#14201a", brass=0.85)
    LOWER = [(44.2, 3), (45.0, 5), (45.0, 82 + DZ), (44.5, 84 + DZ)]
    MID = waist(44.5, 3.9, 84 + DZ, 160 + DZ)
    UPPER = [(44.5, 160 + DZ), (45.0, 162 + DZ), (45.0, 234 + DZ), (44.4, 236 + DZ)]
    base_and_lugs(S, (200 + DZ, 208 + DZ))
    body_parts(S, LOWER, MID, UPPER, lid_dome())
    for k, (z0, z1) in enumerate(((82.5 + DZ, 86 + DZ), (158 + DZ, 161.5 + DZ), (232.5 + DZ, 236 + DZ)), start=1):
        ring("trim_band_%d" % k, "shell", 0, 0, 44.6, 46.2, z0, z1, S["accent"], "Brass trim band", skin=True, metal=S["brass"])
    ring("grip_wrap", "shell", 0, 0, 44.8, 46.0, 172 + DZ, 226 + DZ, S["grip"], "Leather grip wrap, 54 mm", skin=True, metal=0.05)
    round_inside(); slots(S["slot"], MID)
    round_display("#c9a24a", 0.85, "#c9a24a", 0.85, 3.6)
    arch("strap", "Leather carry strap, 14 mm wide", 20.0, 14.0, 3.0, 12, 32.0, TOP - 1.5, "#8a5a36", 0.05, mount="#c9a24a", mount_metal=0.85)
    finish_round()
    return finish_design("classic", "Classic bottle", (LOWER, MID, UPPER))


def build_modern():
    P.clear()
    S = dict(body="#2b3036", waist="#3c444c", accent="#ff6b2c", grip="#14171a", lid="#1d2125", base="#0f1113", slot="#0a0c0e", brass=0.35)
    LOWER = [(44.2, 3), (45.0, 5), (45.0, 82 + DZ), (44.5, 84 + DZ)]
    MID = waist(44.5, 3.9, 84 + DZ, 160 + DZ)
    UPPER = [(44.5, 160 + DZ), (45.0, 162 + DZ), (45.0, 234 + DZ), (44.4, 236 + DZ)]
    base_and_lugs(S, (200 + DZ, 208 + DZ))
    body_parts(S, LOWER, MID, UPPER, lid_dome())
    for k, (z0, z1) in enumerate(((82.5 + DZ, 86 + DZ), (158 + DZ, 161.5 + DZ), (232.5 + DZ, 236 + DZ)), start=1):
        ring("trim_band_%d" % k, "shell", 0, 0, 44.6, 46.2, z0, z1, S["accent"], "Orange accent ring", skin=True, metal=S["brass"])
    for k in range(9):
        ring("grip_rib_%d" % (k + 1), "shell", 0, 0, 44.8, 46.3, 174 + DZ + 6 * k, 176.2 + DZ + 6 * k, S["grip"], "Soft-touch grip rib", skin=True, metal=0.05)
    round_inside(); slots(S["slot"], MID)
    round_display("#ff6b2c", 0.35)
    arch("loop", "Aluminium carry loop, 8 mm wide", 24.0, 8.0, 3.0, 16, 30.0, TOP - 1.5, "#c3cad1", 0.9, mount="#ff6b2c", mount_metal=0.35)
    finish_round()
    return finish_design("modern", "Modern bottle", (LOWER, MID, UPPER))


def build_trail():
    """Rugged outdoor bottle: olive and sand, chunky rubber bumpers, vertical grip ribs, paracord loop."""
    P.clear()
    S = dict(body="#5b6b3a", waist="#cdbf9a", accent="#f28c28", base="#1b1d1f", lid="#4a5830", slot="#232a16", brass=0.3, lug="#1b1d1f", lug_metal=0.05)
    LOWER = [(44.6, 3), (45.2, 5), (45.2, 82 + DZ), (44.8, 84 + DZ)]
    MID = waist(44.8, 2.0, 84 + DZ, 160 + DZ)
    UPPER = [(44.8, 160 + DZ), (45.2, 162 + DZ), (45.2, 234 + DZ), (44.6, 236 + DZ)]
    base_and_lugs(S, (200 + DZ, 208 + DZ), plate_color="#f28c28")
    lid = [(0, LID0), (43.2, LID0), (44.8, LID0 + 2), (44.8, LID0 + 9), (43.4, LID0 + 11), (41, TOP), (0, TOP)]
    body_parts(S, LOWER, MID, UPPER, lid, lid_label="Flat lid with a chunky knurled rim, 13 mm")
    lathe("bumper_bottom", "shell", [(45, 3), (48.5, 3), (49.8, 6), (49.8, 18), (48.5, 22), (45, 24)], "#1b1d1f", "Rubber bumper ring, bottom (drop protection)", skin=True, metal=0.05)
    lathe("bumper_top", "shell", [(45, 220 + DZ), (48.5, 222 + DZ), (49.8, 226 + DZ), (49.8, 232 + DZ), (48.5, 235 + DZ), (45, 236 + DZ)], "#1b1d1f", "Rubber bumper ring, top (drop protection)", skin=True, metal=0.05)
    ring("accent_ring", "shell", 0, 0, 44.9, 46.0, 160 + DZ, 163 + DZ, S["accent"], "Orange accent ring", skin=True, metal=0.2)
    for k in range(24):
        a = 15.0 * k
        px, py = 45.9 * math.cos(math.radians(a)), 45.9 * math.sin(math.radians(a))
        box("grip_rib_%02d" % (k + 1), "shell", px - 0.7, px + 0.7, py - 1.5, py + 1.5, 178 + DZ, 216 + DZ, "#1b1d1f", "Rubber grip rib", rotz=a, skin=True, metal=0.05)
    box("usb_cover", "shell", 43.5, 47.0, -7, 7, 30, 40, "#f28c28", "Rubber cover over the USB port", skin=True, metal=0.05)
    round_inside(); slots(S["slot"], MID)
    round_display("#f28c28", 0.2)
    arch("cord", "Paracord carry loop, 6 mm", 19.0, 6.0, 6.0, 14, 30.0, TOP - 1.5, "#f28c28", 0.05, mount="#1b1d1f", mount_metal=0.05)
    finish_round()
    return finish_design("trail", "Trail bottle", (LOWER, MID, UPPER))


def build_pebble():
    """Soft minimal bottle: one mint shell with a gentle belly and a low dome, peach silicone loop."""
    P.clear()
    S = dict(body="#b9dfcc", lid="#f4f6f4", accent="#f2a38c", base="#e9eeea", slot="#86bfa4", brass=0.0, lug="#f2a38c", lug_metal=0.0)
    LOWER = [(44.4 + 2.6 * math.sin(math.pi * (z - 3) / (84 + DZ - 3)), float(z)) for z in range(3, 84 + DZ, 8)] + [(44.4, 84 + DZ)]
    MID = waist(44.2, 2.2, 84 + DZ, 160 + DZ)
    UPPER = [(44.4 + 2.2 * math.sin(math.pi * (z - (160 + DZ)) / 76.0), float(z)) for z in range(160 + DZ, 236 + DZ, 8)] + [(44.4, 236 + DZ)]
    base_and_lugs(S, (200 + DZ, 208 + DZ), plate=False)
    lid = [(0, LID0), (43.0, LID0), (44.6, LID0 + 1.8), (44.6, LID0 + 3.5), (42.5, LID0 + 7.5), (38, LID0 + 10.8), (30, LID0 + 12.6), (20, TOP), (0, TOP)]
    body_parts(S, LOWER, MID, UPPER, lid, lid_label="Low soft dome lid, 13 mm")
    round_inside(); slots(S["slot"], MID)
    round_display("#f2a38c", 0.0)
    arch("loop", "Peach silicone carry loop, 16 mm wide", 20.0, 16.0, 7.0, 14, 30.0, TOP - 2.0, "#f2a38c", 0.0, mount="#f2a38c", mount_metal=0.0)
    finish_round()
    return finish_design("pebble", "Pebble bottle", (LOWER, MID, UPPER))


def build_deco():
    """Art-deco bottle: stepped base and top, black with gold, burgundy waist with gold fluting."""
    P.clear()
    S = dict(body="#15161a", waist="#5e1a26", accent="#d4af37", lid="#efe6cf", base="#0b0b0d", slot="#0a0405", brass=0.85, lug_metal=0.85)
    LOWER = [(47.8, 3), (47.8, 14), (46.4, 14), (46.4, 28), (45.0, 28), (45.0, 82 + DZ), (44.5, 84 + DZ)]
    MID = waist(44.5, 3.0, 84 + DZ, 160 + DZ)
    UPPER = [(44.5, 160 + DZ), (45.0, 162 + DZ), (45.0, 234 + DZ), (44.4, 236 + DZ)]
    lathe("base_pad", "shell", [(0, 0), (44, 0), (47.2, 1.8), (47.8, 3), (0, 3)], S["base"], "Base pad", skin=True)
    for sy in (-1, 1):
        box("strap_lug_%s" % ("L" if sy < 0 else "R"), "shell", -3, 3, min(sy * 43.5, sy * 48.5), max(sy * 43.5, sy * 48.5), 200 + DZ, 208 + DZ, S["accent"], "Strap lug for a shoulder strap", skin=True, metal=0.85)
    box("nameplate", "shell", 42.8, 46.3, -12, 12, 204 + DZ, 212 + DZ, S["accent"], "Gold name plate, 24 x 8 mm", skin=True, metal=0.85)
    lid = [(0, LID0), (44.4, LID0), (44.4, LID0 + 2), (41.5, LID0 + 2), (41.5, LID0 + 6), (37, LID0 + 6), (37, LID0 + 9), (32, LID0 + 9), (32, TOP), (0, TOP)]
    body_parts(S, LOWER, MID, UPPER, lid, lid_label="Stepped lid in three tiers, 13 mm")
    for k, (z0, z1) in enumerate(((82.5 + DZ, 86 + DZ), (158 + DZ, 161.5 + DZ), (232.5 + DZ, 236 + DZ)), start=1):
        ring("gold_band_%d" % k, "shell", 0, 0, 44.6, 46.2, z0, z1, S["accent"], "Gold band", skin=True, metal=0.85)
    ring("stripe", "shell", 0, 0, 44.8, 45.8, 196 + DZ, 202 + DZ, "#5e1a26", "Burgundy stripe", skin=True, metal=0.1)
    for nm, z in (("hair_1", 194 + DZ), ("hair_2", 202.5 + DZ)):
        ring(nm, "shell", 0, 0, 44.8, 46.0, z, z + 1.0, S["accent"], "Gold hairline", skin=True, metal=0.85)
    n = 0
    for k in range(20):
        a = 18.0 * k
        if min(abs(a), abs(a - 180), abs(a - 360)) < 30:
            continue                                         # keep the slot zone clear
        n += 1
        px, py = 42.4 * math.cos(math.radians(a)), 42.4 * math.sin(math.radians(a))
        box("flute_%02d" % n, "shell", px - 0.6, px + 0.6, py - 1.1, py + 1.1, 110 + DZ, 160 + DZ - 4, S["accent"], "Gold flute", rotz=a, skin=True, metal=0.85)
    round_inside(); slots(S["slot"], MID)
    round_display("#d4af37", 0.85, "#d4af37", 0.85, 3.4)
    arch("ring", "Gold pull ring, 7 mm", 17.0, 7.0, 5.0, 14, 32.0, TOP - 1.5, "#d4af37", 0.85, mount="#d4af37", mount_metal=0.85)
    finish_round()
    return finish_design("deco", "Deco bottle", (LOWER, MID, UPPER))


def build_duo():
    """Duo: two TEC1-12706 under one wide flat cup, in a compact flask-shaped body (stadium cross-section).
    119 x 69 mm, 250 mm tall. Battery and electronics at the bottom, two fans and one long heatsink in the middle."""
    P.clear()
    NAVY, NAVY2, ALU, COPPER, CHAR, RUBBER, SLOT = "#1f2a44", "#2c3a5c", "#c3cad1", "#c27a4a", "#24272c", "#15171a", "#0c0f16"
    A, R, T = 50.0, 34.5, 1.5                      # straight length, end radius, wall
    TOPD = 250
    # ---- body
    stad("base_pad", "shell", 0, 0, A, R - 0.5, 0, 3, RUBBER, "Rubber base pad, 3 mm", skin=True)
    stad("body_lower", "shell", 0, 0, A, R, 3, 98, NAVY, "Lower body, holds the battery and electronics", t=T, skin=True)
    stad("body_mid", "shell", 0, 0, A, R, 98, 176, NAVY2, "Middle band: two fans, one long heatsink, two Peltiers", t=T, skin=True)
    stad("body_upper", "shell", 0, 0, A, R, 176, 238, NAVY, "Upper body around the insulated flat cup", t=T, skin=True)
    for k, (z0, z1) in enumerate(((96.5, 99.5), (174.5, 177.5), (236.5, 239.5)), start=1):
        stad("trim_band_%d" % k, "shell", 0, 0, A, R + 0.8, z0, z1, COPPER, "Copper trim band", t=1.2, skin=True, metal=0.6)
    stad("lid", "lid", 0, 0, A, R, 238, 246, CHAR, "Removable lid, 12 mm", skin=True)
    stad("lid_cap", "lid", 0, 0, A, R - 2.5, 246, TOPD, CHAR, "Lid top", skin=True)
    stad("lid_ring", "lid", 0, 0, A, R - 2.0, 245.5, 246.5, COPPER, "Copper ring on the lid", t=0.8, skin=True, metal=0.6)
    # exhaust grilles on the two flat faces (the fins run front to back, so the air leaves here)
    for sy in (-1, 1):
        y0, y1 = (R - 0.4, R + 0.6) if sy > 0 else (-R - 0.6, -R + 0.4)
        box("grille_%s" % ("front" if sy < 0 else "rear"), "shell", -40, 40, y0, y1, 131, 162, ALU, "Aluminium exhaust grille", skin=True, metal=0.5)
        for j in range(6):
            z = 133.5 + 4.4 * j
            yy0, yy1 = (R + 0.5, R + 0.8) if sy > 0 else (-R - 0.8, -R - 0.5)
            box("exhaust_slot_%s_%d" % ("front" if sy < 0 else "rear", j + 1), "shell", -36, 36, yy0, yy1, z, z + 2.4, SLOT, "Exhaust slot", skin=True)
    # intake slots round the two rounded ends, under the fans
    n = 0
    for sx in (-1, 1):
        for ang in (-60, -30, 0, 30, 60):
            a = ang if sx > 0 else 180 + ang
            cxe = sx * A / 2
            px, py = cxe + (R - 0.2) * math.cos(math.radians(a)), (R - 0.2) * math.sin(math.radians(a))
            n += 1
            box("intake_slot_%d" % n, "shell", px - 0.9, px + 0.9, py - 6, py + 6, 99.5, 104.5, SLOT, "Air intake slot", rotz=a, skin=True)
    for sx in (-1, 1):
        box("strap_lug_%s" % ("L" if sx < 0 else "R"), "shell", min(sx * 58.5, sx * 63), max(sx * 58.5, sx * 63), -3, 3, 206, 216, COPPER, "Strap lug for a shoulder strap", skin=True, metal=0.6)
    box("nameplate", "shell", -14, 14, -R - 0.9, -R + 0.6, 205, 213, COPPER, "Name plate, 28 x 8 mm", skin=True, metal=0.6)

    # ---- battery bay: LM2596 under the pack, BTS7960 and ESP32 at the two rounded ends
    lm2596(0, 0, 4, "x")
    box("pack_carrier", "elec", -31.5, 31.5, -21, 21, 18, 19, "#8d99a3", "Carrier plate that holds the pack above the buck module, 1 mm")
    for ix, cx in enumerate((-21, 0, 21)):
        for iy, cy in enumerate((-10.5, 10.5)):
            cyl("cell_%d%d" % (ix + 1, iy + 1), "elec", cx, cy, 10.5, 19, 89, "#2f8f6f", "21700 cell, 21 x 70 mm (3S2P pack, 6 cells)")
    box("bms_3s", "elec", -30, 30, -20, 20, 90, 93, "#3f6f9a", "3S battery protection board (BMS), size depends on the part")
    box("bts7960", "elec", 32.5, 44.5, -25, 25, 4, 54, "#1e5aa8", "BTS7960 board without heatsink, about 50 x 50 mm (drives both Peltiers)")
    box("esp32_30pin", "elec", -45.5, -32.5, -14, 14, 5, 57, "#1d2a33", "ESP32 30-pin board, about 52 x 28 mm (standing)")
    stad("bulkhead", "shell", 0, 0, A, R - T - 0.5, 96, 98, "#8d99a3", "Bulkhead between battery bay and air path, 2 mm")

    # ---- two fans, one heatsink (fins run front to back), two Peltiers, one spreader plate
    FRAME = "#3a4650"
    for f, cx in (("L", -21.0), ("R", 21.0)):
        z0 = 106
        box("fan%s_frame_a" % f, "fan", cx - 20, cx + 20, -20, -17, z0, z0 + 28, FRAME, "SUNON fan %s, 40 x 40 x 28 mm" % f)
        box("fan%s_frame_b" % f, "fan", cx - 20, cx + 20, 17, 20, z0, z0 + 28, FRAME, "SUNON fan %s, 40 x 40 x 28 mm" % f)
        box("fan%s_frame_c" % f, "fan", cx - 20, cx - 17, -17, 17, z0, z0 + 28, FRAME, "SUNON fan %s, 40 x 40 x 28 mm" % f)
        box("fan%s_frame_d" % f, "fan", cx + 17, cx + 20, -17, 17, z0, z0 + 28, FRAME, "SUNON fan %s, 40 x 40 x 28 mm" % f)
        cyl("fan%s_hub" % f, "fan", cx, 0, 8, z0 + 1, z0 + 27, "#7b8791", "Fan hub")
        for i in range(7):
            a = i * 360.0 / 7
            bx_ = cx + 12.25 * math.cos(math.radians(a)); by = 12.25 * math.sin(math.radians(a))
            box("fan%s_blade_%d" % (f, i + 1), "fan", bx_ - 4.25, bx_ + 4.25, by - 0.8, by + 0.8, z0 + 4, z0 + 24, "#98a4ad", "Fan blade", rotz=a)
    for k in range(29):
        xc = -42 + 3 * k
        box("fin_%02d" % (k + 1), "heatsink", xc - 0.45, xc + 0.45, -25, 25, 134, 159, "#c98a5e", "Heatsink fin, 0.9 mm thick, 25 mm tall (fins run front to back)")
    box("heatsink_base", "heatsink", -44, 44, -25, 25, 159, 164, "#c98a5e", "Copper heatsink base, 88 x 50 x 5 mm, shared by both Peltiers")
    FOAM = "#e0c88a"
    for nm, (x0, x1, y0, y1) in (("a", (-44, -41, -25, 25)), ("b", (41, 44, -25, 25)), ("c", (-1, 1, -20, 20)), ("d", (-41, 41, -25, -20)), ("e", (-41, 41, 20, 25))):
        box("foam_ring_" + nm, "thermal", x0, x1, y0, y1, 164, 168, FOAM, "Foam frame around the two Peltiers, 4 mm")
    for f, cx in (("L", -21.0), ("R", 21.0)):
        box("tec%s_hot_face" % f, "thermal", cx - 20, cx + 20, -20, 20, 164, 165, "#e8743b", "TEC1-12706 %s, heatsink side (hot when cooling)" % f)
        box("tec%s_body" % f, "thermal", cx - 20, cx + 20, -20, 20, 165, 166.8, "#eceff1", "TEC1-12706 %s, 40 x 40 x 3.8 mm" % f)
        box("tec%s_cold_face" % f, "thermal", cx - 20, cx + 20, -20, 20, 166.8, 167.8, "#3d9fd6", "TEC1-12706 %s, water side (cold when cooling)" % f)
    box("water_plate", "thermal", -44, 44, -25, 25, 168, 176, "#b9c2c9", "Aluminium spreader plate, 88 x 50 x 8 mm, under the whole cup")

    # ---- flat cup, insulation, water
    stad("cup_floor", "cup", 0, 0, A, 28, 176, 179, "#c5ced6", "Cup floor, 3 mm aluminium")
    stad("cup_wall", "cup", 0, 0, A, 28, 179, 238, "#c5ced6", "Flat aluminium cup, 104 x 54 mm inside", t=1.0, alpha=0.55)
    stad("insulation_sleeve", "cup", 0, 0, A, 32.5, 179, 238, "#e0c88a", "Foam insulation, 4.5 mm", t=4.5, alpha=0.4)
    stad("water", "water", 0, 0, A, 27, 179, 235, "#58b4e2", "Water, about 280 mL (56 mm deep)", alpha=0.55)

    # ---- display, buttons, carry loop on the lid
    box("oled_1_5in", "display", -30, 8, -19, 19, TOPD, TOPD + 3.2, "#0b1218", "1.5 inch OLED module, about 38 x 38 mm (on the lid)")
    box("oled_screen", "display", -27, 5, -16, 16, TOPD + 3.2, TOPD + 3.4, "#9fe4ff", "OLED screen (128 x 128)")
    for nm, (x0, x1, y0, y1) in (("a", (-33, 11, -22, -19)), ("b", (-33, 11, 19, 22)), ("c", (-33, -30, -19, 19)), ("d", (8, 11, -19, 19))):
        box("oled_bezel_%s" % nm, "display", x0, x1, y0, y1, TOPD, TOPD + 3.6, COPPER, "Copper bezel around the display", metal=0.6)
    for sy in (-9, 9):
        cyl("button_%s" % ("1" if sy < 0 else "2"), "display", 20, sy, 3.4, TOPD, TOPD + 3.2, COPPER, "Push button (GPIO32 / GPIO33)", metal=0.6)
    arch("loop", "Carry loop, grey webbing, 12 mm wide", 16.0, 12.0, 3.0, 12, 44.0, TOPD - 1.5, "#8b939c", 0.05, mount=COPPER, mount_metal=0.6)

    ex = {"shell": (0, 0, 0), "lid": (0, 0, 85), "display": (0, 0, 85), "handle": (0, 0, 85), "cup": (0, 0, 55), "water": (0, 0, 55),
          "thermal": (0, 0, 28), "heatsink": (0, 0, 0), "fan": (0, 0, -30), "elec": (0, 0, 0)}
    pex = {"bms_3s": (0, 0, 22), "bts7960": (62, 0, 0), "esp32_30pin": (-62, 0, 0)}
    for p in P:
        p["ex"] = [0, -75, 0] if p["name"].startswith("lm2596_") else list(pex.get(p["name"], ex[p["grp"]]))
    arrows = []
    for sx in (-1, 1):
        for ang in (-30, 0, 30):
            a = ang if sx > 0 else 180 + ang
            c, sn = math.cos(math.radians(a)), math.sin(math.radians(a))
            arrows.append([sx * A / 2 + 52 * c, 52 * sn, 102, -c, -sn, 0, 16, "in"])
    for cx in (-21, 21):
        arrows.append([cx, 0, 107, 0, 0, 1, 26, "in"])
    for sy in (-1, 1):
        for cx in (-24, 0, 24):
            arrows.append([cx, sy * 20, 146.5, 0, sy, 0, 30, "out"])
    return dict(name="duo", title="Duo flask", parts=list(P), flow=arrows, profiles=None, kind="duo", body_h=TOPD,
                stadium=dict(a=A, r_in=R - T))


def duo_clearance(d):
    """Smallest gap between the inside parts and the inside of the stadium wall (mm)."""
    a, r = d["stadium"]["a"], d["stadium"]["r_in"]
    worst = (1e9, "")
    for p in d["parts"]:
        if p["grp"] in ("shell", "lid", "display", "handle"):
            continue
        if p["kind"] == "box":
            c = ((p["x0"] + p["x1"]) / 2, (p["y0"] + p["y1"]) / 2, 0)
            pts = [rot3((x, y, 0), c, 0, 0, p["rotz"])[:2] for x in (p["x0"], p["x1"]) for y in (p["y0"], p["y1"])]
            gap = min(r - math.hypot(max(abs(x) - a / 2, 0), y) for x, y in pts)
        elif p["kind"] == "cyl":
            gap = r - (math.hypot(max(abs(p["cx"]) - a / 2, 0), p["cy"]) + p["r"])
        elif p["kind"] == "stad":
            gap = r - p["r"]
        else:
            continue
        worst = min(worst, (round(gap, 2), p["name"]))
    return worst


def build_retro():
    """Retro cooler box: teal and cream, chrome corner beads and belt, front display, chrome handle bar. Water column in front,
    electronics column behind (125 x 75 x 191 mm). Push fan only."""
    P.clear()
    TEAL, CREAM, CHROME, RED, DARK = "#2a9d8f", "#f1e6cf", "#cfd6dc", "#d6453d", "#2b2f33"
    W = 1.5
    # ---- skin panels
    box("front_wall", "shell", 0, W, -37.5, 37.5, 5, 191, TEAL, "Front wall (water column)", skin=True)
    box("side_L", "shell", 0, 75, -37.5, -37.5 + W, 5, 191, TEAL, "Side wall", skin=True)
    box("side_R", "shell", 0, 75, 37.5 - W, 37.5, 5, 191, TEAL, "Side wall", skin=True)
    box("divider", "shell", 75 - W, 75, -37.5, 37.5, 5, 191, TEAL, "Wall between water column and electronics", skin=True)
    box("back_side_L", "shell", 75, 125, -37.5, -37.5 + W, 0, 191, TEAL, "Side wall (electronics column)", skin=True)
    box("back_side_R", "shell", 75, 125, 37.5 - W, 37.5, 0, 191, TEAL, "Side wall (electronics column)", skin=True)
    box("rear_wall", "shell", 125 - W, 125, -37.5, 37.5, 0, 191, TEAL, "Rear wall", skin=True)
    box("back_floor", "shell", 75, 125, -37.5, 37.5, 0, W, DARK, "Floor of the electronics column", skin=True)
    box("back_top", "shell", 75, 125, -37.5, 37.5, 185.4, 191, CREAM, "Top panel of the electronics column", skin=True)
    for i, (fx, fy) in enumerate([(0, -37.5), (0, 27.5), (65, -37.5), (65, 27.5)]):
        box("foot_%d" % (i + 1), "shell", fx, fx + 10, fy, fy + 10, 0, 5, DARK, "Rubber foot, 10 x 10 x 5 mm (air gets in under the fan)", skin=True)
    for k, z in enumerate((53.4, 48.4, 43.4, 38.4)):
        box("exhaust_slot_%d" % (k + 1), "shell", -0.1, 0.6, -20, 20, z, z + 2.6, DARK, "Exhaust slot, 40 x 2.6 mm", skin=True)
    # ---- chrome trim: corner beads, belt, rim
    for i, (cx, cy) in enumerate([(0, -37.5), (0, 37.5), (125, -37.5), (125, 37.5)]):
        cyl("corner_bead_%d" % (i + 1), "shell", cx, cy, 3.5, 5 if cx == 0 else 0, 191, CHROME, "Chrome corner bead", skin=True, metal=0.6)
    box("belt_front", "shell", -0.8, 0.0, -37.5, 37.5, 100, 104, CHROME, "Chrome belt", skin=True, metal=0.6)
    box("belt_side_L", "shell", 0, 125, -38.3, -37.5, 100, 104, CHROME, "Chrome belt", skin=True, metal=0.6)
    box("belt_side_R", "shell", 0, 125, 37.5, 38.3, 100, 104, CHROME, "Chrome belt", skin=True, metal=0.6)
    box("belt_rear", "shell", 125, 125.8, -37.5, 37.5, 100, 104, CHROME, "Chrome belt", skin=True, metal=0.6)
    # ---- lid, handle
    box("lid", "lid", W, 75 - W, -36, 36, 183.4, 191, CREAM, "Removable lid, 72 x 72 x 7.6 mm", skin=True)
    for sy in (-1, 1):
        box("handle_post_%s" % ("L" if sy < 0 else "R"), "handle", 56, 64, min(sy * 29, sy * 34), max(sy * 29, sy * 34), 191, 203, CHROME, "Chrome handle post", metal=0.6)
    box("handle_bar", "handle", 56, 64, -34, 34, 203, 209, CHROME, "Chrome carry handle bar", metal=0.6)
    # ---- display on the front wall, buttons below it
    box("oled_1_5in", "display", -3.2, 0, -19, 19, 142, 180, "#0b1218", "1.5 inch OLED module, about 38 x 38 mm (on the front)")
    box("oled_screen", "display", -3.4, -3.2, -16, 16, 145, 177, "#9fe4ff", "OLED screen (128 x 128)")
    for nm, (y0, y1, z0, z1) in (("t", (-22, 22, 180, 183)), ("b", (-22, 22, 139, 142)), ("l", (-22, -19, 142, 180)), ("r", (19, 22, 142, 180))):
        box("oled_bezel_%s" % nm, "display", -4.4, 0, y0, y1, z0, z1, CHROME, "Chrome bezel around the display", metal=0.6)
    for sy in (-12, 12):
        box("button_%s" % ("1" if sy < 0 else "2"), "display", -4.0, 0, sy - 3.5, sy + 3.5, 125, 132, RED, "Push button (GPIO32 / GPIO33)")
    # ---- inside
    stack(37.5, 5)
    cyl("cup_floor", "cup", 37.5, 0, 31, 75, 77, "#c5ced6", "Cup floor, 2 mm")
    ring("cup_wall", "cup", 37.5, 0, 30, 31, 77, 183.4, "#c5ced6", "Water cup wall, inside diameter 60 mm", 0.55)
    ring("insulation_sleeve", "cup", 37.5, 0, 31, 36, 77, 183.4, "#e0c88a", "Foam insulation sleeve, 5 mm", 0.4)
    cyl("water", "water", 37.5, 0, 30, 77, 171, "#58b4e2", "Water, about 265 mL (94 mm deep)", 0.55)
    box("esp32_30pin", "elec", 79, 93, -14, 14, 130, 182, "#1d2a33", "ESP32 30-pin board, about 52 x 28 mm (standing)")
    box("esp32_usb", "elec", 82, 90, -4, 4, 182, 185, "#aeb7bf", "ESP32 USB port")
    lm2596(108.5, 0, 130, "y")
    box("lm2596_shelf", "elec", 96, 121, -23, 23, 128, 130, "#8d99a3", "Shelf under the buck module, 2 mm")
    for ix, cx in enumerate((88.5, 109.5)):
        for iy, cy in enumerate((-21, 0, 21)):
            cyl("cell_%d%d" % (ix + 1, iy + 1), "elec", cx, cy, 10.5, 57, 127, "#2f8f6f", "21700 cell, 21 x 70 mm (3S2P pack, 6 cells)")
    box("bms_3s", "elec", 79, 119, -30, 30, 52, 55, "#3f6f9a", "3S battery protection board (BMS), size depends on the part")
    box("bts7960", "elec", 79, 91, -25, 25, 1.5, 49.5, "#1e5aa8", "BTS7960 board without heatsink, about 50 x 50 mm (standing)")
    ex = {"shell": (0, 0, 0), "lid": (0, 0, 90), "display": (-60, 0, 0), "handle": (0, 0, 90), "cup": (0, 0, 52), "water": (0, 0, 52),
          "thermal": (0, 0, 24), "heatsink": (0, 0, 0), "fan": (0, 0, -34), "elec": (60, 0, 0)}
    pex = {"esp32_30pin": (60, 0, 30), "esp32_usb": (60, 0, 30), "bms_3s": (60, 0, -22), "bts7960": (60, 0, -44), "lm2596_shelf": (60, 0, 46)}
    for p in P:
        p["ex"] = list(pex.get(p["name"], ex[p["grp"]])) if not p["name"].startswith("lm2596_") or p["name"] == "lm2596_shelf" else [60, 0, 46]
    return dict(name="retro", title="Retro cooler", parts=list(P), flow=[], profiles=None, kind="box")


# ================================================================ mesh helpers (OBJ / STL)
def rot(x, y, cx, cy, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c


def rot3(pt, c, rx, ry, rz):
    """Rotate pt about centre c: first about X, then Y, then Z (degrees), all about the global axes."""
    x, y, z = pt[0] - c[0], pt[1] - c[1], pt[2] - c[2]
    if rx:
        a = math.radians(rx); y, z = y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a)
    if ry:
        a = math.radians(ry); x, z = x * math.cos(a) + z * math.sin(a), -x * math.sin(a) + z * math.cos(a)
    if rz:
        a = math.radians(rz); x, y = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
    return (c[0] + x, c[1] + y, c[2] + z)


def mesh_of(p):
    """Return (vertices, triangles) with outward counter-clockwise faces."""
    v, t = [], []
    if p["kind"] == "box":
        c = ((p["x0"] + p["x1"]) / 2, (p["y0"] + p["y1"]) / 2, (p["z0"] + p["z1"]) / 2)
        for z in (p["z0"], p["z1"]):
            for (x, y) in ((p["x0"], p["y0"]), (p["x1"], p["y0"]), (p["x1"], p["y1"]), (p["x0"], p["y1"])):
                v.append(rot3((x, y, z), c, p.get("rotx", 0), p.get("roty", 0), p["rotz"]))
        t += [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    elif p["kind"] == "stad":
        outer = stad_outline(p["cx"], p["cy"], p["a"], p["r"])
        inner = stad_outline(p["cx"], p["cy"], p["a"], p["r"] - p["t"]) if p.get("t") else None
        n = len(outer)
        for z in (p["z0"], p["z1"]):
            v += [(x, y, z) for x, y in outer]
        for i in range(n):
            j = (i + 1) % n
            t += [(i, j, n + j), (i, n + j, n + i)]                       # outer wall
        if not inner:
            cxy = (p["cx"], p["cy"])
            v += [(cxy[0], cxy[1], p["z0"]), (cxy[0], cxy[1], p["z1"])]
            b, tp = 2 * n, 2 * n + 1
            for i in range(n):
                j = (i + 1) % n
                t += [(b, j, i), (tp, n + i, n + j)]
        else:
            base = len(v)
            for z in (p["z0"], p["z1"]):
                v += [(x, y, z) for x, y in inner]
            for i in range(n):
                j = (i + 1) % n
                t += [(base + i, base + n + j, base + j), (base + i, base + n + i, base + n + j)]
                t += [(i, base + i, base + j), (i, base + j, j)]
                t += [(n + i, n + j, base + n + j), (n + i, base + n + j, base + n + i)]
    elif p["kind"] == "lathe":
        pts = [(max(r, 0.01), z) for r, z in p["pts"]]
        n, m = SEG * 2, len(pts)
        for (r, z) in pts:
            for j in range(n):
                a = 2 * math.pi * j / n
                v.append((r * math.cos(a), r * math.sin(a), z))
        for i in range(m):
            i2 = (i + 1) % m
            for j in range(n):
                j2 = (j + 1) % n
                A, B, C, D = i * n + j, i2 * n + j, i2 * n + j2, i * n + j2
                t += [(A, D, C), (A, C, B)]
    else:
        r_out = p["r"] if p["kind"] == "cyl" else p["r_out"]
        r_in = 0 if p["kind"] == "cyl" else p["r_in"]
        for z in (p["z0"], p["z1"]):
            for i in range(SEG):
                a = 2 * math.pi * i / SEG
                v.append((p["cx"] + r_out * math.cos(a), p["cy"] + r_out * math.sin(a), z))
        n = SEG
        for i in range(n):
            j = (i + 1) % n
            t += [(i, j, n + j), (i, n + j, n + i)]                       # outer wall
        if r_in == 0:
            v += [(p["cx"], p["cy"], p["z0"]), (p["cx"], p["cy"], p["z1"])]
            b, tp = 2 * n, 2 * n + 1
            for i in range(n):
                j = (i + 1) % n
                t += [(b, j, i), (tp, n + i, n + j)]
        else:
            base = len(v)
            for z in (p["z0"], p["z1"]):
                for i in range(n):
                    a = 2 * math.pi * i / n
                    v.append((p["cx"] + r_in * math.cos(a), p["cy"] + r_in * math.sin(a), z))
            for i in range(n):
                j = (i + 1) % n
                t += [(base + i, base + n + j, base + j), (base + i, base + n + i, base + n + j)]   # inner wall
                t += [(i, base + i, base + j), (i, base + j, j)]                                    # bottom ring
                t += [(n + i, n + j, base + n + j), (n + i, base + n + j, base + n + i)]            # top ring
    return v, t


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def write_obj(path_obj, path_mtl):
    with open(path_mtl, "w") as m:
        for p in P:
            r, g, b = hex_rgb(p["color"])
            m.write("newmtl m_%s\nKd %.3f %.3f %.3f\nd %.2f\n\n" % (p["name"], r, g, b, p["alpha"]))
    with open(path_obj, "w") as f:
        f.write("# ThermoX layout draft, millimetres, Z up\nmtllib %s\n" % os.path.basename(path_mtl))
        off = 1
        for p in P:
            v, t = mesh_of(p)
            f.write("g %s\nusemtl m_%s\n" % (p["name"], p["name"]))
            for x, y, z in v:
                f.write("v %.4f %.4f %.4f\n" % (x, y, z))
            for a, b, c in t:
                f.write("f %d %d %d\n" % (a + off, b + off, c + off))
            off += len(v)


def write_stl(path):
    with open(path, "w") as f:
        f.write("solid thermox\n")
        for p in P:
            if p["alpha"] < 0.3 and p["grp"] == "shell":
                continue                                    # glass shell panels stay out of the print file
            v, t = mesh_of(p)
            for a, b, c in t:
                A, B, C = v[a], v[b], v[c]
                u = (B[0] - A[0], B[1] - A[1], B[2] - A[2]); w = (C[0] - A[0], C[1] - A[1], C[2] - A[2])
                n = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
                m = math.sqrt(sum(q * q for q in n)) or 1.0
                f.write(" facet normal %.5f %.5f %.5f\n  outer loop\n" % (n[0] / m, n[1] / m, n[2] / m))
                for q in (A, B, C):
                    f.write("   vertex %.4f %.4f %.4f\n" % q)
                f.write("  endloop\n endfacet\n")
        f.write("endsolid thermox\n")


def write_step(path):
    import cadquery as cq
    asm = cq.Assembly(name="ThermoX_layout_draft")
    for p in P:
        if p["kind"] == "box":
            s = cq.Workplane("XY").box(p["x1"] - p["x0"], p["y1"] - p["y0"], p["z1"] - p["z0"], centered=False)
            s = s.translate((p["x0"], p["y0"], p["z0"]))
            c = ((p["x0"] + p["x1"]) / 2, (p["y0"] + p["y1"]) / 2, (p["z0"] + p["z1"]) / 2)
            for ang, axis in ((p.get("rotx", 0), (1, 0, 0)), (p.get("roty", 0), (0, 1, 0)), (p["rotz"], (0, 0, 1))):
                if ang:
                    s = s.rotate(c, (c[0] + axis[0], c[1] + axis[1], c[2] + axis[2]), ang)
        elif p["kind"] == "cyl":
            s = cq.Workplane("XY").workplane(offset=p["z0"]).center(p["cx"], p["cy"]).circle(p["r"]).extrude(p["z1"] - p["z0"])
        elif p["kind"] == "stad":
            h = p["z1"] - p["z0"]
            s = cq.Workplane("XY").workplane(offset=p["z0"]).center(p["cx"], p["cy"]).slot2D(p["a"] + 2 * p["r"], 2 * p["r"]).extrude(h)
            if p.get("t"):
                ri = p["r"] - p["t"]
                s = s.cut(cq.Workplane("XY").workplane(offset=p["z0"] - 1).center(p["cx"], p["cy"]).slot2D(p["a"] + 2 * ri, 2 * ri).extrude(h + 2))
        elif p["kind"] == "lathe":
            s = cq.Workplane("XZ").polyline([tuple(q) for q in p["pts"]]).close().revolve(360, (0, 0, 0), (0, 1, 0))
        else:
            s = cq.Workplane("XY").workplane(offset=p["z0"]).center(p["cx"], p["cy"]).circle(p["r_out"]).circle(p["r_in"]).extrude(p["z1"] - p["z0"])
        r, g, b = hex_rgb(p["color"])
        asm.add(s, name=p["name"], color=cq.Color(r, g, b, p["alpha"]))
    asm.save(path)


def write_blender(path):
    parts = []
    for p in P:
        q = dict(p)
        if p["kind"] == "stad":
            v, t = mesh_of(p)
            q["mesh"] = [[list(x) for x in v], [list(f) for f in t]]
        parts.append(q)
    data = json.dumps(parts, separators=(",", ":"))
    code = '''# ThermoX layout draft. In Blender: Scripting tab > Open this file > Run Script. Units are millimetres.
# Written to be simple, but not tested inside Blender here. If it errors, File > Import > Wavefront (.obj) with
# thermox_assembly.obj gives the same parts.
import bpy, bmesh, math, json

PARTS = json.loads(r\'\'\'%s\'\'\')

scn = bpy.context.scene
scn.unit_settings.system = 'METRIC'
scn.unit_settings.scale_length = 0.001
scn.unit_settings.length_unit = 'MILLIMETERS'

def material(p):
    m = bpy.data.materials.new("m_" + p["name"])
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    h = p["color"].lstrip("#")
    r, g, b = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (r, g, b, 1)
        bsdf.inputs["Roughness"].default_value = 0.5
        if p["alpha"] < 1:
            bsdf.inputs["Alpha"].default_value = p["alpha"]
    m.diffuse_color = (r, g, b, p["alpha"])
    if p["alpha"] < 1:
        try:
            m.blend_method = 'BLEND'
        except Exception:
            pass
    return m

colls = {}
def coll(name):
    if name not in colls:
        c = bpy.data.collections.new(name)
        scn.collection.children.link(c)
        colls[name] = c
    return colls[name]

def link(obj, grp):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll(grp).objects.link(obj)

for p in PARTS:
    if p["kind"] == "box":
        bpy.ops.mesh.primitive_cube_add(size=1)
        o = bpy.context.active_object
        o.scale = (p["x1"] - p["x0"], p["y1"] - p["y0"], p["z1"] - p["z0"])
        o.location = ((p["x0"] + p["x1"]) / 2, (p["y0"] + p["y1"]) / 2, (p["z0"] + p["z1"]) / 2)
        o.rotation_euler = (math.radians(p.get("rotx", 0)), math.radians(p.get("roty", 0)), math.radians(p["rotz"]))
    elif p["kind"] == "stad":
        me = bpy.data.meshes.new(p["name"])
        me.from_pydata(p["mesh"][0], [], p["mesh"][1])
        me.update()
        o = bpy.data.objects.new(p["name"], me)
        bpy.context.collection.objects.link(o)
        bpy.context.view_layer.objects.active = o
    elif p["kind"] == "lathe":
        bm = bmesh.new()
        vs = [bm.verts.new((max(r, 0.01), 0, z)) for r, z in p["pts"]]
        es = [bm.edges.new((vs[i], vs[(i + 1) %% len(vs)])) for i in range(len(vs))]
        bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi, steps=96)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.005)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new(p["name"])
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new(p["name"], me)
        bpy.context.collection.objects.link(o)
        bpy.context.view_layer.objects.active = o
    elif p["kind"] == "cyl":
        bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=p["r"], depth=p["z1"] - p["z0"])
        o = bpy.context.active_object
        o.location = (p["cx"], p["cy"], (p["z0"] + p["z1"]) / 2)
    else:
        bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=p["r_out"], depth=p["z1"] - p["z0"])
        o = bpy.context.active_object
        o.location = (p["cx"], p["cy"], (p["z0"] + p["z1"]) / 2)
        bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=p["r_in"], depth=p["z1"] - p["z0"] + 2)
        cutter = bpy.context.active_object
        cutter.location = o.location
        mod = o.modifiers.new("hole", 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object = cutter
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier="hole")
        bpy.data.objects.remove(cutter, do_unlink=True)
    o.name = p["name"]
    o.data.materials.append(material(p))
    link(o, p["grp"])

bpy.ops.object.light_add(type='SUN', location=(300, -300, 400))
bpy.context.active_object.data.energy = 3.0
bpy.ops.object.camera_add(location=(330, -330, 260), rotation=(math.radians(66), 0, math.radians(45)))
scn.camera = bpy.context.active_object
print("ThermoX layout draft built:", len(PARTS), "parts")
''' % data
    open(path, "w").write(code)


def write_viewer_data(path, designs):
    keep = ("name", "kind", "grp", "color", "alpha", "rotz", "rotx", "roty", "edges", "skin", "metal", "flow", "label", "ex", "pts", "x0", "x1", "y0", "y1", "z0", "z1", "cx", "cy", "r", "r_in", "r_out", "a", "t")
    out = {}
    for d in designs:
        out[d["name"]] = dict(title=d["title"], kind=d["kind"], dims=d["dims"], flow=d.get("flow", []),
                              parts=[{k: p[k] for k in keep if k in p} for p in d["parts"]])
    open(path, "w").write(json.dumps(out, separators=(",", ":")))


def dims_of(d):
    """Overall size of a design: body diameter (round) and total height including the handle."""
    zs, xs, ys = [], [], []
    for p in d["parts"]:
        if p.get("flow") == "pull":
            continue
        v, _ = mesh_of(p)
        zs += [q[2] for q in v]; xs += [q[0] for q in v]; ys += [q[1] for q in v]
    out = dict(h=round(max(zs), 1))
    if d["kind"] == "round":
        r = 0
        for p in d["parts"]:
            if p["grp"] in ("shell", "lid") and p["kind"] in ("lathe", "ring"):
                r = max(r, max(q[0] for q in p["pts"]) if p["kind"] == "lathe" else p["r_out"])
        out["d"] = round(2 * r, 1)
        out["body_h"] = TOP
    else:
        out["x"] = round(max(xs) - min(xs), 1); out["y"] = round(max(ys) - min(ys), 1)
        out["cx"] = round((max(xs) + min(xs)) / 2, 1)
        if d.get("body_h"):
            out["body_h"] = d["body_h"]
    return out


def overlaps():
    """Report axis-aligned overlaps between solid (non-shell) boxes so mistakes show up."""
    bad = []
    boxes = [p for p in P if p["kind"] == "box" and not (p["rotz"] or p.get("rotx") or p.get("roty")) and p["grp"] != "shell"]
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            dx = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"]); dy = min(a["y1"], b["y1"]) - max(a["y0"], b["y0"]); dz = min(a["z1"], b["z1"]) - max(a["z0"], b["z0"])
            if dx > 0.01 and dy > 0.01 and dz > 0.01:
                bad.append((a["name"], b["name"], round(dx * dy * dz, 2)))
    return bad




def skin_inner(profiles, z0, z1):
    """Smallest inside radius of the body wall between z0 and z1 (the wall is 1.5 mm thick)."""
    pts = [(r - 1.5, z) for prof in profiles for r, z in prof]
    best = 1e9
    for (ra, za), (rb, zb) in zip(pts, pts[1:]):
        lo, hi = min(za, zb), max(za, zb)
        if hi < z0 or lo > z1 or hi == lo:
            continue
        for z in (max(z0, lo), min(z1, hi)):
            best = min(best, ra + (rb - ra) * (z - za) / (zb - za))
    return best


def reach(p):
    """Largest distance of a part from the vertical axis (round designs) in mm."""
    if p["kind"] == "box":
        c = ((p["x0"] + p["x1"]) / 2, (p["y0"] + p["y1"]) / 2, (p["z0"] + p["z1"]) / 2)
        return max(math.hypot(*rot3((x, y, c[2]), c, p.get("rotx", 0), p.get("roty", 0), p["rotz"])[:2])
                   for x in (p["x0"], p["x1"]) for y in (p["y0"], p["y1"]))
    return math.hypot(p["cx"], p["cy"]) + (p["r"] if p["kind"] == "cyl" else p["r_out"])


def clearance_report(profiles):
    """How far every inside part stays from the inside of the wall (mm). Negative would mean a clash."""
    worst = (1e9, "")
    for p in P:
        if p["grp"] in ("shell", "lid", "display", "handle"):
            continue
        z0, z1 = p["z0"], p["z1"]
        if z1 < 3 or z0 > LID0:
            continue
        gap = skin_inner(profiles, max(z0, 3), min(z1, LID0)) - reach(p)
        worst = min(worst, (gap, p["name"]))
    return worst


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    export_flow = "pull" if "--pull" in FLAGS else "push"
    designs = [build_classic(), build_modern(), build_trail(), build_pebble(), build_deco(), build_retro(), build_duo()]
    for d in designs:
        d["dims"] = dims_of(d)
    for d in designs:
        d["export"] = [p for p in d["parts"] if p.get("flow") in (None, export_flow)]
        P[:] = d["export"]
        folder = ("bottle_" if d["kind"] == "round" else "") + d["name"]
        sub = os.path.join(OUT, folder)
        os.makedirs(sub, exist_ok=True)
        tag = "thermox_" + folder + ("_pull" if d["kind"] == "round" and export_flow == "pull" else "")
        write_obj(os.path.join(sub, tag + ".obj"), os.path.join(sub, tag + ".mtl"))
        if "--extras" in FLAGS:
            write_stl(os.path.join(sub, tag + ".stl"))
            write_blender(os.path.join(sub, tag + "_blender.py"))
        try:
            write_step(os.path.join(sub, tag + ".step"))
            step = "STEP ok"
        except Exception as e:                              # cadquery missing is fine
            step = "STEP skipped: " + repr(e)[:80]
        extra = ""
        if d["kind"] == "round":
            gap, who = clearance_report(d["profiles"])
            extra = " | tightest clearance inside the wall: %.1f mm (%s)" % (gap, who)
        elif d["kind"] == "duo":
            gap, who = duo_clearance(d)
            extra = " | tightest clearance inside the wall: %.1f mm (%s)" % (gap, who)
        print("%-8s parts: %3d | box overlaps: %s | %s | %s%s" % (d["name"], len(P), overlaps(), step, d["dims"], extra))
    write_viewer_data(os.path.join(OUT, "viewer_parts.json"), designs)
