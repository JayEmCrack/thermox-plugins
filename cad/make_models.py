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


def box(name, grp, x0, x1, y0, y1, z0, z1, color, label=None, alpha=1.0, rotz=0.0, edges=False):
    P.append(dict(kind="box", name=name, grp=grp, x0=x0, x1=x1, y0=y0, y1=y1, z0=z0, z1=z1, color=color,
                  alpha=alpha, rotz=rotz, edges=edges, label=label or name))


def cyl(name, grp, cx, cy, r, z0, z1, color, label=None, alpha=1.0):
    P.append(dict(kind="cyl", name=name, grp=grp, cx=cx, cy=cy, r=r, z0=z0, z1=z1, color=color, alpha=alpha,
                  rotz=0.0, edges=False, label=label or name))


def ring(name, grp, cx, cy, r_in, r_out, z0, z1, color, label=None, alpha=1.0):
    P.append(dict(kind="ring", name=name, grp=grp, cx=cx, cy=cy, r_in=r_in, r_out=r_out, z0=z0, z1=z1, color=color,
                  alpha=alpha, rotz=0.0, edges=False, label=label or name))


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
box("fan_frame_a", "fan", 17.5, 57.5, -20, -17, 5, 33, FRAME, "SUNON fan frame, 40 x 40 x 28 mm")
box("fan_frame_b", "fan", 17.5, 57.5, 17, 20, 5, 33, FRAME, "SUNON fan frame, 40 x 40 x 28 mm")
box("fan_frame_c", "fan", 17.5, 20.5, -17, 17, 5, 33, FRAME, "SUNON fan frame, 40 x 40 x 28 mm")
box("fan_frame_d", "fan", 54.5, 57.5, -17, 17, 5, 33, FRAME, "SUNON fan frame, 40 x 40 x 28 mm")
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


# ================================================================ mesh helpers (OBJ / STL)
def rot(x, y, cx, cy, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c


def mesh_of(p):
    """Return (vertices, triangles) with outward counter-clockwise faces."""
    v, t = [], []
    if p["kind"] == "box":
        cx, cy = (p["x0"] + p["x1"]) / 2, (p["y0"] + p["y1"]) / 2
        for z in (p["z0"], p["z1"]):
            for (x, y) in ((p["x0"], p["y0"]), (p["x1"], p["y0"]), (p["x1"], p["y1"]), (p["x0"], p["y1"])):
                rx, ry = rot(x, y, cx, cy, p["rotz"])
                v.append((rx, ry, z))
        t += [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
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
            if p["rotz"]:
                s = s.rotate(((p["x0"] + p["x1"]) / 2, (p["y0"] + p["y1"]) / 2, 0), ((p["x0"] + p["x1"]) / 2, (p["y0"] + p["y1"]) / 2, 1), p["rotz"])
        elif p["kind"] == "cyl":
            s = cq.Workplane("XY").workplane(offset=p["z0"]).center(p["cx"], p["cy"]).circle(p["r"]).extrude(p["z1"] - p["z0"])
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
import bpy, math, json

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
        o.rotation_euler[2] = math.radians(p["rotz"])
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


def write_viewer_data(path):
    keep = ("name", "kind", "grp", "color", "alpha", "rotz", "edges", "label", "ex", "x0", "x1", "y0", "y1", "z0", "z1", "cx", "cy", "r", "r_in", "r_out")
    slim = [{k: p[k] for k in keep if k in p} for p in P]
    open(path, "w").write(json.dumps(slim, separators=(",", ":")))


def overlaps():
    """Report axis-aligned overlaps between solid (non-shell) boxes so mistakes show up."""
    bad = []
    boxes = [p for p in P if p["kind"] == "box" and p["rotz"] == 0 and p["grp"] != "shell"]
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            dx = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"]); dy = min(a["y1"], b["y1"]) - max(a["y0"], b["y0"]); dz = min(a["z1"], b["z1"]) - max(a["z0"], b["z0"])
            if dx > 0.01 and dy > 0.01 and dz > 0.01:
                bad.append((a["name"], b["name"], round(dx * dy * dz, 2)))
    return bad


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    write_obj(os.path.join(OUT, "thermox_assembly.obj"), os.path.join(OUT, "thermox_assembly.mtl"))
    write_stl(os.path.join(OUT, "thermox_assembly.stl"))
    write_blender(os.path.join(OUT, "thermox_blender.py"))
    write_viewer_data(os.path.join(OUT, "viewer_parts.json"))
    try:
        write_step(os.path.join(OUT, "thermox_assembly.step"))
        print("STEP written")
    except Exception as e:                                 # cadquery missing is fine
        print("STEP skipped:", repr(e)[:120])
    xs = [p.get("x1", p.get("cx", 0) + p.get("r", p.get("r_out", 0))) for p in P]
    print("parts:", len(P), "| box overlaps:", overlaps())
