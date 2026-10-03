# ThermoX layout draft: 3D model files

First draft of the compact body, in millimetres, Z up. The sizes match the "ThermoX Layout" drawing and the "ThermoX 3D View" page.

| File | Use |
|---|---|
| `thermox_assembly.step` | Fusion 360 (and most CAD): 75 separate solids with names and colours. File > Open > Open from my computer. |
| `thermox_assembly.obj` + `.mtl` | Blender: File > Import > Wavefront (.obj). Keep both files together. |
| `thermox_assembly.stl` | Any mesh tool or slicer. The glass shell panels are left out. |
| `thermox_blender.py` | Optional Blender script (Scripting tab > Run Script). Not tested inside Blender. Use the OBJ if it errors. |
| `make_models.py` | The one part list all of the above come from. Edit it and run `python3 make_models.py cad` to rebuild everything. STEP needs `pip install cadquery`. |

Checks run on a computer: no overlapping solids, every mesh closed and facing outward, and the STEP file re-opens with 75 solids and the expected 125 x 75 x 194 mm bounding box. Sizes for the ESP32, BTS7960, OLED and BMS are typical values; measure your parts.
