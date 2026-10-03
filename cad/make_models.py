#!/usr/bin/env python3
"""ThermoX layout draft: one parts list -> viewer data, Blender script, OBJ/MTL, STL, STEP.

Units: millimetres. Axes: X = depth (0 = front wall, 125 = back), Y = width (centred, +-37.5), Z = up (0 = bottom).
The numbers match the side-view drawing ("ThermoX Layout"). Edit PARTS below, run `python3 make_models.py`, and every
output file is rebuilt. STEP needs `pip install cadquery`; everything else needs only the standard library.
"""
import json, math, os, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
SEG = 48                      # segments on round parts
P = []                        # the parts


def box(name, grp, x0, x1, y0, y1, z0, z1, color, label=None, alpha=1.0, rotz=0.0, edges=False, rotx=0.0, roty=0.0, skin=False, metal=None):
    """Axis-aligned box; rotx/roty/rotz (degrees) turn it about its own centre, applied in that order about the global axes."""
    P.append(dict(kind="box", name=name, grp=grp, x0=x0, x1=x1, y0=y0, y1=y1, z0=z0, z1=z1, color=color,
                  alpha=alpha, rotz=rotz, rotx=rotx, roty=roty, edges=edges, skin=skin, metal=metal, label=label or name))


def cyl(name, grp, cx, cy, r, z0, z1, color, label=None, alpha=1.0, skin=False, metal=None):
    P.append(dict(kind="cyl", name=name, grp=grp, cx=cx, cy=cy, r=r, z0=z0, z1=z1, color=color, alpha=alpha,
                  rotz=0.0, rotx=0.0, roty=0.0, edges=False, skin=skin, metal=metal, label=label or name))


def ring(name, grp, cx, cy, r_in, r_out, z0, z1, color, label=None, alpha=1.0, skin=False, metal=None):
    P.append(dict(kind="ring", name=name, grp=grp, cx=cx, cy=cy, r_in=r_in, r_out=r_out, z0=z0, z1=z1, color=color,
                  alpha=alpha, rotz=0.0, rotx=0.0, roty=0.0, edges=False, skin=skin, metal=metal, label=label or name))


def lathe(name, grp, pts, color, label=None, alpha=1.0, skin=False, metal=None):
    """Solid of revolution about the Z axis. pts = closed outline of (radius, z), counter-clockwise (radius to the right, z up)."""
    P.append(dict(kind="lathe", name=name, grp=grp, pts=[list(q) for q in pts], cx=0.0, cy=0.0, color=color, alpha=alpha,
                  rotz=0.0, rotx=0.0, roty=0.0, edges=False, skin=skin, metal=metal, label=label or name))


def shell_pts(outer, t=1.5):
    """Hollow wall of thickness t from the outer profile (bottom to top)."""
    return [tuple(q) for q in outer] + [(r - t, z) for r, z in reversed(outer)]


def build_box():
    """Box layout: water column in front, electronics column behind (125 x 75 x 191 mm)."""
    P.clear()
    # ---------------------------------------------------------------- shell (5 mm feet, 1.5 mm walls)
    W = 1.5
    GLASS = "#9db3c2"
    box("shell_front_wall", "shell", 0, W, -37.5, 37.5, 5, 191, GLASS, "Shell, front wall with exhaust slots", 0.14, edges=True)
    box("shell_side_L", "shell", 0, 75, -37.5, -37.5 + W, 5, 191, GLASS, "Shell, side wall", 0.14, edges=True)
    box("shell_side_R", "shell", 0, 75, 37.5 - W, 37.5, 5, 191, GLASS, "Shell, side wall", 0.14, edges=True)
    box("shell_divider", "shell", 75 - W, 75, -37.5, 37.5, 5, 191, GLASS, "Wall between water column and electronics", 0.14, edges=True)
    for i, (fx, fy) in enumerate([(0, -37.5), (0, 27.5), (65, -37.5), (65, 27.5)]):
        box("foot_%d" % (i + 1), "shell", fx, fx + 10, fy, fy + 10, 0, 5, "#3a4650", "Foot, 10 x 10 x 5 mm (air gets in under the fan)")
    box("back_side_L", "shell", 75, 125, -37.5, -37.5 + W, 0, 191, GLASS, "Shell, electronics column side wall", 0.14, edges=True)
    box("back_side_R", "shell", 75, 125, 37.5 - W, 37.5, 0, 191, GLASS, "Shell, electronics column side wall", 0.14, edges=True)
    box("back_rear_wall", "shell", 125 - W, 125, -37.5, 37.5, 0, 191, GLASS, "Shell, rear wall", 0.14, edges=True)
    box("back_bottom", "shell", 75, 125, -37.5, 37.5, 0, W, GLASS, "Shell, electronics column floor", 0.3, edges=True)
    box("back_top_panel", "shell", 75, 125, -37.5, 37.5, 185.4, 191, "#dde4e9", "Top panel of the electronics column, 5.6 mm", 0.9)
    for k, z in enumerate((53.4, 48.4, 43.4, 38.4)):
        box("exhaust_slot_%d" % (k + 1), "shell", -0.1, 0.6, -20, 20, z, z + 2.6, "#101820", "Exhaust slot, 40 x 2.6 mm")

    # ---------------------------------------------------------------- lid, cup, insulation, water
    box("lid", "lid", W, 75 - W, -36, 36, 183.4, 191, "#dde4e9", "Removable lid, 72 x 72 x 7.6 mm")
    ring("cup_wall", "cup", 37.5, 0, 30, 31, 77, 183.4, "#c5ced6", "Water cup wall, inside diameter 60 mm (stainless or aluminium)", 0.55)
    cyl("cup_floor", "cup", 37.5, 0, 31, 75, 77, "#c5ced6", "Cup floor, 2 mm")
    ring("insulation_sleeve", "cup", 37.5, 0, 31, 36, 77, 183.4, "#e0c88a", "Foam insulation sleeve, 5 mm", 0.4)
    cyl("water", "water", 37.5, 0, 30, 77, 171, "#58b4e2", "Water, about 300 mL cup filled to 94 mm", 0.55)

    # ---------------------------------------------------------------- water plate, foam ring, TEC
    box("water_plate", "thermal", 17.5, 57.5, -20, 20, 67, 75, "#b9c2c9", "Water-side plate, 40 x 40 x 8 mm (aluminium or copper)")
    FOAM = "#e0c88a"
    box("foam_ring_a", "thermal", 12.5, 17.5, -25, 25, 63, 67, FOAM, "Foam ring around the TEC, 4 mm")
    box("foam_ring_b", "thermal", 57.5, 62.5, -25, 25, 63, 67, FOAM, "Foam ring around the TEC, 4 mm")
    box("foam_ring_c", "thermal", 17.5, 57.5, -25, -20, 63, 67, FOAM, "Foam ring around the TEC, 4 mm")
    box("foam_ring_d", "thermal", 17.5, 57.5, 20, 25, 63, 67, FOAM, "Foam ring around the TEC, 4 mm")
    box("tec_hot_face", "thermal", 17.5, 57.5, -20, 20, 63, 64, "#e8743b", "TEC1-12706 40 x 40 x 3.8 mm, heatsink side (hot when cooling)")
    box("tec_body", "thermal", 17.5, 57.5, -20, 20, 64, 65.8, "#eceff1", "TEC1-12706 40 x 40 x 3.8 mm")
    box("tec_cold_face", "thermal", 17.5, 57.5, -20, 20, 65.8, 66.8, "#3d9fd6", "TEC1-12706 40 x 40 x 3.8 mm, water side (cold when cooling)")

    # ---------------------------------------------------------------- heatsink (copper), fins run front to back
    COPPER = "#c98a5e"
    box("heatsink_base", "heatsink", 12.5, 62.5, -25, 25, 58, 63, COPPER, "Heatsink base, 50 x 50 x 5 mm (proposed, copper)")
    for k in range(17):
        yc = -24 + 3 * k
        box("fin_%02d" % (k + 1), "heatsink", 12.5, 62.5, yc - 0.45, yc + 0.45, 33, 58, COPPER, "Heatsink fin, 0.9 mm thick, 25 mm tall, 3 mm pitch")

    # ---------------------------------------------------------------- SUNON fan 40 x 40 x 28 under the heatsink
    FRAME = "#3a4650"
    FL = "SUNON fan frame, 40 x 40 x 28 mm"
    box("fan_frame_a", "fan", 17.5, 57.5, -20, -17, 5, 33, FRAME, FL)
    box("fan_frame_b", "fan", 17.5, 57.5, 17, 20, 5, 33, FRAME, FL)
    box("fan_frame_c", "fan", 17.5, 20.5, -17, 17, 5, 33, FRAME, FL)
    box("fan_frame_d", "fan", 54.5, 57.5, -17, 17, 5, 33, FRAME, FL)
    cyl("fan_hub", "fan", 37.5, 0, 8, 6, 32, "#7b8791", "Fan hub")
    for i in range(7):
        a = i * 360.0 / 7
        cx = 37.5 + 12.25 * math.cos(math.radians(a))
        cy = 12.25 * math.sin(math.radians(a))
        box("fan_blade_%d" % (i + 1), "fan", cx - 4.25, cx + 4.25, cy - 0.8, cy + 0.8, 9, 29, "#98a4ad", "Fan blade", rotz=a)

    # ---------------------------------------------------------------- electronics column
    box("esp32_30pin", "elec", 79, 93, -14, 14, 130, 182, "#1d2a33", "ESP32 30-pin board, about 52 x 28 mm (standing)")
    box("esp32_usb", "elec", 82, 90, -4, 4, 182, 185, "#aeb7bf", "ESP32 USB port")
    box("buck_12v_5v", "elec", 97, 106, -8.5, 8.5, 160, 182, "#3d7f9a", "12 V to 5 V buck converter, about 22 x 17 mm")
    for ix, cx in enumerate((88.5, 109.5)):
        for iy, cy in enumerate((-21, 0, 21)):
            cyl("cell_%d%d" % (ix + 1, iy + 1), "elec", cx, cy, 10.5, 57, 127, "#2f8f6f", "21700 cell, 21 x 70 mm (3S2P pack, 6 cells)")
    box("bms_3s", "elec", 79, 119, -30, 30, 52, 55, "#3f6f9a", "3S battery protection board (BMS), size depends on the part")
    box("bts7960", "elec", 79, 91, -25, 25, 1.5, 49.5, "#1e5aa8", "BTS7960 board without heatsink, about 50 x 50 mm (standing)")
    box("oled_1_5in", "display", 79, 117, -19, 19, 191, 194.2, "#0b1218", "1.5 inch OLED module, about 38 x 38 mm")
    box("oled_screen", "display", 82, 114, -16, 16, 194.2, 194.4, "#9fe4ff", "OLED screen (128 x 128)")
    for sy in (-12, 12):
        cyl("button_%s" % ("1" if sy < 0 else "2"), "display", 121, sy, 3.2, 191, 194, "#d94f3a", "Push button (GPIO32 / GPIO33)")

    # explode vectors (X, Y, Z in mm at 100 %), by group; some parts get their own
    GROUP_EX = {"shell": (0, 0, 0), "lid": (0, 0, 90), "display": (0, 0, 90), "cup": (0, 0, 52), "water": (0, 0, 52),
                "thermal": (0, 0, 24), "heatsink": (0, 0, 0), "fan": (0, 0, -34), "elec": (60, 0, 0)}
    PART_EX = {"esp32_30pin": (60, 0, 30), "esp32_usb": (60, 0, 30), "buck_12v_5v": (60, 0, 46),
               "bms_3s": (60, 0, -22), "bts7960": (60, 0, -44)}
    for p in P:
        p["ex"] = list(PART_EX.get(p["name"], GROUP_EX[p["grp"]]))


    return dict(name="box", title="Box layout", height=191, cx=62.5, cz=97, parts=list(P))


def stack(cx, z0, flip=False):
    """Fan, copper heatsink (fins run X to X), foam ring, TEC and water plate, bottom to top from z0."""
    FRAME = "#3a4650"
    FL = "SUNON fan frame, 40 x 40 x 28 mm" + (" (mounted upside down, so it draws air down out of the fins)" if flip else "")
    box("fan_frame_a", "fan", cx - 20, cx + 20, -20, -17, z0, z0 + 28, FRAME, FL)
    box("fan_frame_b", "fan", cx - 20, cx + 20, 17, 20, z0, z0 + 28, FRAME, FL)
    box("fan_frame_c", "fan", cx - 20, cx - 17, -17, 17, z0, z0 + 28, FRAME, FL)
    box("fan_frame_d", "fan", cx + 17, cx + 20, -17, 17, z0, z0 + 28, FRAME, FL)
    cyl("fan_hub", "fan", cx, 0, 8, z0 + 1, z0 + 27, "#7b8791", "Fan hub")
    for i in range(7):
        a = i * 360.0 / 7
        bx = cx + 12.25 * math.cos(math.radians(a)); by = 12.25 * math.sin(math.radians(a))
        box("fan_blade_%d" % (i + 1), "fan", bx - 4.25, bx + 4.25, by - 0.8, by + 0.8, z0 + 4, z0 + 24, "#98a4ad", "Fan blade", rotz=a)
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


STYLES = {
    "classic": dict(title="Classic", body="#2f5d49", waist="#e8dfc9", accent="#c9a24a", grip="#8a5a36", lid="#efe8d6",
                    base="#3a2a20", handle="#8a5a36", btn="#c9a24a", slot="#14201a", brass=0.85, handle_metal=0.05),
    "modern": dict(title="Modern", body="#2b3036", waist="#3c444c", accent="#ff6b2c", grip="#14171a", lid="#1d2125",
                   base="#0f1113", handle="#c3cad1", btn="#ff6b2c", slot="#0a0c0e", brass=0.35, handle_metal=0.9),
}
TOP = 252                                             # top face of the lid
LOWER = [(44.2, 3), (45.0, 5), (45.0, 82), (44.5, 84)]
MID = [(44.5, 84)] + [(44.5 - 3.9 * math.sin(math.pi * (z - 84) / 76.0), z) for z in range(88, 160, 4)] + [(44.5, 160)]
UPPER = [(44.5, 160), (45.0, 162), (45.0, 234), (44.4, 236)]


def skin_inner(z0, z1):
    """Smallest inside radius of the body wall between z0 and z1 (the wall is 1.5 mm thick)."""
    pts = [(r - 1.5, z) for prof in (LOWER, MID, UPPER) for r, z in prof]
    best = 1e9
    for (ra, za), (rb, zb) in zip(pts, pts[1:]):
        lo, hi = min(za, zb), max(za, zb)
        if hi < z0 or lo > z1 or hi == lo:
            continue
        for z in (max(z0, lo), min(z1, hi)):
            best = min(best, ra + (rb - ra) * (z - za) / (zb - za))
    return best


def build_bottle(style, flow="push"):
    """Portable bottle, 92 mm at the widest and 252 mm tall. Waisted body, domed lid, trim bands, carry loop.
    flow="push": air in at the bottom ring, up through the fan, out of the fins at the sides.
    flow="pull": the fan is turned over; air in at the side slots, drawn through the fins and down, out at the bottom ring."""
    S = STYLES[style]
    pull = flow == "pull"
    P.clear()
    # ---- outer skin (hollow lathe walls, 1.5 mm)
    lathe("base_pad", "shell", [(0, 0), (40, 0), (43, 1.8), (44.2, 3), (0, 3)], S["base"], "Rubber base pad, 3 mm (non-slip)", skin=True)
    lathe("body_lower", "shell", shell_pts(LOWER), S["body"], "Lower body, holds the battery, 90 mm across", skin=True)
    lathe("body_waist", "shell", shell_pts(MID), S["waist"], "Waisted middle band: fan intake at the bottom, exhaust slots on two sides", skin=True)
    lathe("body_upper", "shell", shell_pts(UPPER), S["body"], "Upper body around the insulated water cup", skin=True)
    lathe("lid_dome", "lid", [(0, 236), (43.0, 236), (44.6, 238), (44.6, 243), (43.6, 246.5), (40.5, 249.2), (35, 251.2), (30, TOP), (0, TOP)],
          S["lid"], "Domed removable lid, 16 mm", skin=True)
    for k, (z0, z1) in enumerate(((82.5, 86), (158, 161.5), (232.5, 236)), start=1):
        ring("trim_band_%d" % k, "shell", 0, 0, 44.6, 46.2, z0, z1, S["accent"], "Trim band", skin=True, metal=S["brass"])
    if style == "classic":
        ring("grip_wrap", "shell", 0, 0, 44.8, 46.0, 172, 226, S["grip"], "Leather grip wrap, 54 mm", skin=True, metal=0.05)
    else:
        for k in range(9):
            ring("grip_rib_%d" % (k + 1), "shell", 0, 0, 44.8, 46.3, 174 + 6 * k, 176.2 + 6 * k, S["grip"], "Soft-touch grip rib", skin=True, metal=0.05)
    box("nameplate", "shell", 42.8, 46.3, -12, 12, 201, 209, S["accent"], "Name plate, 24 x 8 mm", skin=True, metal=S["brass"])
    for sy in (-1, 1):
        box("strap_lug_%s" % ("L" if sy < 0 else "R"), "shell", -3, 3, min(sy * 43.5, sy * 48.5), max(sy * 43.5, sy * 48.5), 200, 208,
            S["accent"], "Strap lug for a shoulder strap", skin=True, metal=S["brass"])

    # ---- air slots (dark markers on the wall)
    if pull:
        ring_n, ring_w, ring_lbl, side_lbl = 12, 17, "Air exhaust slot (hot air leaves here)", "Air intake slot (cool air is drawn in here)"
    else:
        ring_n, ring_w, ring_lbl, side_lbl = 8, 14, "Air intake slot", "Exhaust slot"
    for k in range(ring_n):
        a = 360.0 / ring_n / 2 + 360.0 / ring_n * k
        px, py = 44.1 * math.cos(math.radians(a)), 44.1 * math.sin(math.radians(a))
        box("%s_slot_%d" % ("exhaust" if pull else "intake", k + 1), "shell", px - 0.9, px + 0.9, py - ring_w / 2, py + ring_w / 2, 85.5, 90.5, S["slot"], ring_lbl, rotz=a, skin=True)
    for side, a in (("front", 0), ("rear", 180)):
        px, py = 41.2 * math.cos(math.radians(a)), 41.2 * math.sin(math.radians(a))
        for j, z in enumerate((124, 129.5, 135, 140.5)):
            box("%s_slot_%s_%d" % ("intake" if pull else "exhaust", side, j + 1), "shell", px - 0.9, px + 0.9, py - 18, py + 18, z, z + 3.5, S["slot"], side_lbl, rotz=a, skin=True)
    cyl("bulkhead", "shell", 0, 0, 43.0, 82, 84, "#8d99a3", "Bulkhead between battery bay and air path, 2 mm (wires pass through)")

    # ---- fan, heatsink, foam ring, TEC, water plate: fan 92-120, fins 120-145, base 145-150, TEC 150-154, plate 154-162
    stack(0, 92, flip=pull)

    # ---- water cup, insulation, water
    cyl("cup_floor", "cup", 0, 0, 37, 162, 165, "#c5ced6", "Cup floor, 3 mm aluminium spreader plate")
    ring("cup_wall", "cup", 0, 0, 36, 37, 165, 236, "#c5ced6", "Water cup wall, inside diameter 72 mm", 0.55)
    ring("insulation_sleeve", "cup", 0, 0, 37, 42.5, 165, 236, "#e0c88a", "Foam insulation sleeve, 5.5 mm", 0.4)
    cyl("water", "water", 0, 0, 36, 165, 233, "#58b4e2", "Water, about 275 mL (68 mm deep)", 0.55)

    # ---- display and buttons on the lid
    box("oled_1_5in", "display", -22, 16, -19, 19, TOP, TOP + 3.2, "#0b1218", "1.5 inch OLED module, about 38 x 38 mm (on the lid)")
    box("oled_screen", "display", -19, 13, -16, 16, TOP + 3.2, TOP + 3.4, "#9fe4ff", "OLED screen (128 x 128)")
    if style == "classic":
        for nm, (x0, x1, y0, y1) in (("a", (-25, 19, -22, -19)), ("b", (-25, 19, 19, 22)), ("c", (-25, -22, -19, 19)), ("d", (16, 19, -19, 19))):
            box("oled_bezel_%s" % nm, "display", x0, x1, y0, y1, TOP, TOP + 3.6, S["accent"], "Brass bezel around the display", metal=S["brass"])
    for sy in (-8, 8):
        cyl("button_%s" % ("1" if sy < 0 else "2"), "display", 25, sy, 3.6 if style == "classic" else 3.2, TOP, TOP + 3.2, S["btn"],
            "Push button (GPIO32 / GPIO33)", metal=S["brass"])

    # ---- carry loop: a strap (classic) or a slim aluminium bail (modern), made of short straight pieces
    if style == "classic":
        R, Wd, T, n, X0, Z0, hc = 20.0, 14.0, 3.0, 12, 32.0, 250.5, S["handle"]
        label = "Leather carry strap, 14 mm wide"
    else:
        R, Wd, T, n, X0, Z0, hc = 24.0, 8.0, 3.0, 16, 30.0, 250.5, S["handle"]
        label = "Aluminium carry loop, 8 mm wide"
    step = 180.0 / n
    seg = 2 * R * math.sin(math.radians(step / 2)) + 0.6
    for i in range(n):
        th = step / 2 + step * i
        py, pz = R * math.cos(math.radians(th)), Z0 + R * math.sin(math.radians(th))
        box("handle_%02d" % (i + 1), "handle", X0 - Wd / 2, X0 + Wd / 2, py - seg / 2, py + seg / 2, pz - T / 2, pz + T / 2, hc, label,
            rotx=th - 90, metal=S["handle_metal"])
    for sy in (-1, 1):
        box("handle_mount_%s" % ("L" if sy < 0 else "R"), "handle", X0 - Wd / 2 - 1, X0 + Wd / 2 + 1, min(sy * (R - 3), sy * (R + 3)), max(sy * (R - 3), sy * (R + 3)),
            249, 253, S["accent"], "Handle mount", metal=S["brass"])
    hand_top = Z0 + R + T / 2

    # ---- battery bay (3 to 82)
    for ix, cx in enumerate((-21, 0, 21)):
        for iy, cy in enumerate((-10.5, 10.5)):
            cyl("cell_%d%d" % (ix + 1, iy + 1), "elec", cx, cy, 10.5, 4, 74, "#2f8f6f", "21700 cell, 21 x 70 mm (3S2P pack, 6 cells)")
    box("bms_3s", "elec", -30, 30, -20, 20, 75, 78, "#3f6f9a", "3S battery protection board (BMS), size depends on the part")
    box("bts7960", "elec", -25, 25, 22.5, 34.5, 4, 54, "#1e5aa8", "BTS7960 board without heatsink, about 50 x 50 mm (standing)")
    box("esp32_30pin", "elec", -14, 14, -35.5, -22.5, 5, 57, "#1d2a33", "ESP32 30-pin board, about 52 x 28 mm (standing)")
    box("buck_12v_5v", "elec", -8.5, 8.5, -34, -25, 59, 81, "#3d7f9a", "12 V to 5 V buck converter, about 22 x 17 mm")

    ex = {"shell": (0, 0, 0), "lid": (0, 0, 95), "display": (0, 0, 95), "handle": (0, 0, 95), "cup": (0, 0, 58), "water": (0, 0, 58),
          "thermal": (0, 0, 28), "heatsink": (0, 0, 0), "fan": (0, 0, -30), "elec": (0, 0, 0)}
    pex = {"bms_3s": (0, 0, 22), "bts7960": (0, 62, 0), "esp32_30pin": (0, -62, 0), "buck_12v_5v": (0, -62, 18)}
    for p in P:
        p["ex"] = list(pex.get(p["name"], ex[p["grp"]]))
    # ---- airflow arrows for the viewer only: [origin x, y, z, direction x, y, z, length, "in"/"out"]
    arrows = []
    def radial(a_deg, r0, z, length, inward):
        c, sn = math.cos(math.radians(a_deg)), math.sin(math.radians(a_deg))
        d = -1 if inward else 1
        arrows.append([r0 * c, r0 * sn, z, d * c, d * sn, 0, length, "in" if inward else "out"])
    if pull:
        for a in (0, 180):
            radial(a, 64, 132.5, 36, True)                  # cool air in through the fin-level slots
        arrows.append([0, 0, 121, 0, 0, -1, 28, "out"])      # drawn down through the turned-over fan
        for k in range(12):
            radial(15 + 30 * k, 40, 88, 20, False)          # warm air out of the lower ring
    else:
        for k in range(8):
            radial(22.5 + 45 * k, 62, 88, 18, True)         # cool air in through the lower ring
        arrows.append([0, 0, 93, 0, 0, 1, 28, "in"])         # blown up through the fan
        for a in (0, 180):
            radial(a, 24, 132.5, 36, False)                 # warm air out of the fin-level slots
    name = "bottle_" + style + ("_pull" if pull else "")
    return dict(name=name, title=S["title"] + " bottle" + (", pull fan" if pull else ""), height=round(hand_top), cx=0, cz=round(hand_top / 2),
                parts=list(P), flow=arrows)


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
        elif p["kind"] == "lathe":
            s = cq.Workplane("XZ").polyline([tuple(q) for q in p["pts"]]).close().revolve(360, (0, 0, 0), (0, 1, 0))
        else:
            s = cq.Workplane("XY").workplane(offset=p["z0"]).center(p["cx"], p["cy"]).circle(p["r_out"]).circle(p["r_in"]).extrude(p["z1"] - p["z0"])
        r, g, b = hex_rgb(p["color"])
        asm.add(s, name=p["name"], color=cq.Color(r, g, b, p["alpha"]))
    asm.save(path)


def write_blender(path):
    data = json.dumps(P, separators=(",", ":"))
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
    keep = ("name", "kind", "grp", "color", "alpha", "rotz", "rotx", "roty", "edges", "skin", "metal", "label", "ex", "pts", "x0", "x1", "y0", "y1", "z0", "z1", "cx", "cy", "r", "r_in", "r_out")
    out = {}
    for d in designs:
        out[d["name"]] = dict(title=d["title"], height=d["height"], cx=d["cx"], cz=d["cz"], flow=d.get("flow", []),
                              parts=[{k: p[k] for k in keep if k in p} for p in d["parts"]])
    open(path, "w").write(json.dumps(out, separators=(",", ":")))


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


def reach(p):
    """Largest distance of a part from the vertical axis (round design) in mm."""
    if p["kind"] == "box":
        cx, cy = (p["x0"] + p["x1"]) / 2, (p["y0"] + p["y1"]) / 2
        best = 0
        for x in (p["x0"], p["x1"]):
            for y in (p["y0"], p["y1"]):
                rx, ry = rot(x, y, cx, cy, p["rotz"])
                best = max(best, math.hypot(rx, ry))
        return best
    return math.hypot(p["cx"], p["cy"]) + (p["r"] if p["kind"] == "cyl" else p["r_out"])


def clearance_report():
    """For the bottle: how far every inside part stays from the inside of the wall (mm). Negative would mean a clash."""
    worst = (1e9, "")
    for p in P:
        if p["grp"] in ("shell", "lid", "display", "handle"):                 # wall, lid, trim and the bulkhead that touches the wall on purpose
            continue
        if p["kind"] == "lathe":
            continue
        z0, z1 = p["z0"], p["z1"]
        if z1 < 3 or z0 > 236:
            continue
        gap = skin_inner(max(z0, 3), min(z1, 236)) - reach(p)
        worst = min(worst, (gap, p["name"]))
    return worst


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    designs = [build_bottle("classic"), build_bottle("classic", "pull"), build_bottle("modern"), build_bottle("modern", "pull"), build_box()]
    for d in designs:
        P[:] = d["parts"]
        sub = os.path.join(OUT, d["name"])
        os.makedirs(sub, exist_ok=True)
        write_obj(os.path.join(sub, "thermox_%s.obj" % d["name"]), os.path.join(sub, "thermox_%s.mtl" % d["name"]))
        write_stl(os.path.join(sub, "thermox_%s.stl" % d["name"]))
        write_blender(os.path.join(sub, "thermox_%s_blender.py" % d["name"]))
        try:
            write_step(os.path.join(sub, "thermox_%s.step" % d["name"]))
            step = "STEP ok"
        except Exception as e:                              # cadquery missing is fine
            step = "STEP skipped: " + repr(e)[:80]
        extra = ""
        if d["name"].startswith("bottle"):
            gap, who = clearance_report()
            extra = " | tightest inside clearance: %.1f mm (%s)" % (gap, who)
        print("%-15s parts: %d | box overlaps: %s | %s%s" % (d["name"], len(P), overlaps(), step, extra))
    write_viewer_data(os.path.join(OUT, "viewer_parts.json"), designs)
