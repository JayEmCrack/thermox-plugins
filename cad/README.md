# ThermoX layout drafts: 3D model files

First-draft designs, in millimetres, Z up. The parts and sizes match the "ThermoX Layout" drawing and the "ThermoX 3D View" page.

| Folder | Design | Size |
|---|---|---|
| `bottle_classic/` | Round bottle, forest green and ivory, brass trim, leather strap and grip wrap | 92 mm at the widest, 252 mm tall (272 with the strap up) |
| `bottle_modern/` | Same bottle, graphite with orange rings, soft-touch grip ribs, slim aluminium carry loop | 92 mm at the widest, 252 mm tall (276 with the loop up) |
| `box/` | Earlier layout study: water column in front, electronics column behind | 125 x 75 x 191 mm |

Both bottles hold the same parts in the same places: battery at the bottom, then the fan, the copper heatsink, the TEC and the water cup, with a domed lid carrying the OLED and buttons. Only the outside differs.

Each folder has:

| File | Use |
|---|---|
| `thermox_<name>.step` | Fusion 360 (and most CAD): every part is its own solid with a name and colour. File > Open > Open from my computer. |
| `thermox_<name>.obj` + `.mtl` | Blender: File > Import > Wavefront (.obj). Keep both files together. |
| `thermox_<name>.stl` | Any mesh tool or slicer. The glass shell panels of the box are left out. |
| `thermox_<name>_blender.py` | Optional Blender script (Scripting tab > Run Script). Not tested inside Blender. Use the OBJ if it errors. |

`make_models.py` holds the part list for all three designs. Edit it and run `python3 make_models.py cad` to rebuild every file and the viewer data. STEP needs `pip install cadquery`; the other files need only Python.

Checks run on a computer: no overlapping boxes, every mesh closed and facing outward, every STEP file re-opens with all its solids (103 classic, 111 modern, 75 box) and the expected bounding box, and in the bottles every inside part stays at least 0.4 mm inside the wall (the tightest is the foam sleeve around the cup). Sizes for the ESP32, BTS7960, OLED and BMS are typical values; measure your parts. The weight (about 1.4 kg with water, plastic shell) is my estimate. Finishes and materials are suggestions, not tested.
