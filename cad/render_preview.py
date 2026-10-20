#!/usr/bin/env python3
"""PNG previews of the ThermoX designs (needs numpy and matplotlib).

  python3 render_preview.py OUTDIR [name ...]     e.g. python3 render_preview.py previews classic onepcb
  python3 render_preview.py OUTDIR --onepcb       round bottles with the one-board PCB in the battery bay (adds a close-up)

Each picture is a simple flat-shaded view of the same part lists that make_models.py exports (push-fan version).
Glass shell panels are drawn see-through. Use the OBJ/STEP files for a real look in Blender or Fusion 360.
"""
import os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

FLAGS = [a for a in sys.argv[1:] if a.startswith("--")]
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = ARGS[0] if ARGS else "previews"
ONLY = ARGS[1:]
sys.argv = [sys.argv[0], OUT] + FLAGS                      # make_models reads its own arguments at import
import make_models as mm


def hexc(h):
    return np.array(mm.hex_rgb(h))


def collect(parts, see_through=False):
    """Triangles, colours and alphas of all parts; see_through draws the outside shell and lid almost transparent."""
    tris, cols, alph = [], [], []
    for p in parts:
        if p.get("flow") not in (None, "push"):
            continue
        v, t = mm.mesh_of(p)
        v = np.array(v, float)
        for a, b, c in t:
            tr = v[[a, b, c]]
            tris.append(tr); cols.append(hexc(p["color"]))
            alph.append(0.07 if see_through and p["grp"] in ("shell", "lid", "cup", "water") else p["alpha"])
    return np.array(tris), np.array(cols), np.array(alph)


def draw(ax, parts, elev, azim, see_through=False):
    tris, cols, alph = collect(parts, see_through)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= (np.linalg.norm(n, axis=1)[:, None] + 1e-12)
    el, az = np.radians(elev), np.radians(azim)
    view = np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])
    light = view * 0.6 + np.array([0.3, -0.4, 0.7])
    light /= np.linalg.norm(light)
    shade = 0.45 + 0.55 * np.clip(np.abs(n @ light), 0, 1)
    depth = (tris.mean(axis=1) @ view)
    order = np.argsort(depth)
    rgba = np.concatenate([np.clip(cols * shade[:, None], 0, 1), alph[:, None]], axis=1)
    pc = Poly3DCollection(tris[order], facecolors=rgba[order], edgecolors=(0, 0, 0, 0.05), linewidths=0.15)
    ax.add_collection3d(pc)
    lo, hi = tris.reshape(-1, 3).min(axis=0), tris.reshape(-1, 3).max(axis=0)
    ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect(tuple(hi - lo), zoom=(1.2 if hi[2] - lo[2] < 60 else 0.95)); ax.view_init(elev, azim); ax.set_axis_off()


def main():
    os.makedirs(OUT, exist_ok=True)
    builders = dict(classic=mm.build_classic, modern=mm.build_modern, trail=mm.build_trail, pebble=mm.build_pebble,
                    deco=mm.build_deco, retro=mm.build_retro, duo=mm.build_duo, onepcb=mm.build_onepcb)
    for name, fn in builders.items():
        if (ONLY and name not in ONLY) or (mm.ONEPCB and name in ("retro", "duo", "onepcb")):
            continue
        d = fn()
        if name == "onepcb":
            views = [("top view", 90, -90, False), ("3D view", 38, -60, False)]
            fig = plt.figure(figsize=(14, 7), dpi=100)
        else:
            views = [("outside", 12, -55, False), ("see-through", 12, -55, True)]
            if mm.ONEPCB:
                views.append(("battery bay close-up", 28, -55, True))
            fig = plt.figure(figsize=(7 * len(views), 9), dpi=100)
        for i, (tag, el, az, see) in enumerate(views):
            ax = fig.add_subplot(1, len(views), i + 1, projection="3d")
            draw(ax, [p for p in d["parts"] if "close-up" not in tag or (p["grp"] == "elec" and p["name"] not in ("plate_low", "pack_carrier", "bms_3s") and not p["name"].startswith("cell_") and max(q[2] for q in mm.mesh_of(p)[0]) < 125 + mm.PCB_SHIFT)]
                 if name != "onepcb" else d["parts"], el, az, see)
            ax.set_title("%s (%s)" % (d["title"], tag), fontsize=11)
        fig.tight_layout()
        path = os.path.join(OUT, "thermox_%s%s.png" % (name, "_onepcb" if mm.ONEPCB else ""))
        fig.savefig(path, facecolor="white"); plt.close(fig)
        print(path)


if __name__ == "__main__":
    main()
