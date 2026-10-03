# ThermoX layout drafts: 3D model files

Two first-draft layouts, in millimetres, Z up. The sizes match the "ThermoX Layout" drawing and the "ThermoX 3D View" page.

| Folder | Design | Size |
|---|---|---|
| `bottle/` | Portable round bottle: battery at the bottom, fan and heatsink above it, water cup on top, carry handle and strap lugs | 90 mm across, 249 mm tall (268 with the handle) |
| `box/` | Earlier box layout: water column in front, electronics column behind | 125 x 75 x 191 mm |

Each folder has:

| File | Use |
|---|---|
| `thermox_<name>.step` | Fusion 360 (and most CAD): every part is its own solid with a name and colour. File > Open > Open from my computer. |
| `thermox_<name>.obj` + `.mtl` | Blender: File > Import > Wavefront (.obj). Keep both files together. |
| `thermox_<name>.stl` | Any mesh tool or slicer. The glass shell panels are left out. |
| `thermox_<name>_blender.py` | Optional Blender script (Scripting tab > Run Script). Not tested inside Blender. Use the OBJ if it errors. |

`make_models.py` holds the part list for both designs. Edit it and run `python3 make_models.py cad` to rebuild every file and the viewer data. STEP needs `pip install cadquery`; the other files need only Python.

Checks run on a computer: no overlapping boxes, every mesh closed and facing outward, every STEP file re-opens with all its solids (75 box, 81 bottle) and the expected bounding box, and in the bottle every inner part stays inside the 43.5 mm inner radius (the tightest is the BTS7960 at 42.6 mm). Sizes for the ESP32, BTS7960, OLED and BMS are typical values; measure your parts. Weight (about 1.4 kg with water) is my estimate.
