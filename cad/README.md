# ThermoX design drafts: 3D model files

Six first-draft designs, in millimetres, Z up. They share one set of parts inside: 3S2P 21700 pack, **LM2596 buck module** (43 x 21 x 14 mm, 9-12.6 V in, 5 V out for the ESP32), BTS7960 without heatsink, 30-pin ESP32, SUNON 40 x 40 x 28 mm fan, copper heatsink, TEC1-12706 and a water cup. Only the outside, the handle and the slots differ. The parts and sizes match the "ThermoX Layout" drawing and the "ThermoX 3D View" page.

| Folder | Design | Size |
|---|---|---|
| `bottle_classic/` | Forest green and ivory, brass trim, leather strap and grip wrap | 92 mm across, 263 mm tall (283 with the strap up) |
| `bottle_modern/` | Graphite with orange rings, soft-touch grip ribs, aluminium loop | 93 mm across, 263 mm tall (287 with the loop up) |
| `bottle_trail/` | Olive and sand, rubber bumpers, grip ribs, paracord loop | 100 mm across at the bumpers, 263 mm tall (284) |
| `bottle_pebble/` | Smooth mint body with a gentle belly, low dome lid, peach silicone loop | 94 mm across, 263 mm tall (285) |
| `bottle_deco/` | Black, burgundy and gold, stepped base and lid, fluted waist | 96 mm across, 263 mm tall (281) |
| `retro/` | Teal and cream box, chrome corner beads, front display, chrome handle bar | 133 x 82 x 209 mm |

The bottles are 14 mm taller than the first drafts because the LM2596 module lies under the battery. In the retro box it lies on a shelf above the battery.

Each folder holds the **push-fan** version (fan blows up into the heatsink, air in at the bottom ring, out at the front and rear slots):

| File | Use |
|---|---|
| `thermox_<name>.step` | Fusion 360 (and most CAD): every part is its own solid with a name and colour. File > Open > Open from my computer. |
| `thermox_<name>.obj` + `.mtl` | Blender: File > Import > Wavefront (.obj). Keep both files together. |

`make_models.py` holds the part list for every design. Edit it and run:

```
python3 make_models.py cad            # STEP + OBJ for every design (push fan)
python3 make_models.py cad --pull     # the pull-fan version of the round bottles
python3 make_models.py cad --extras   # also STL files and Blender scripts
```

STEP needs `pip install cadquery`; the other files need only Python. The Blender script is not tested inside Blender; use the OBJ if it errors.

Checks run on a computer: no overlapping boxes, every mesh closed and facing outward, every STEP file re-opens with all its solids (109 classic, 117 modern, 131 trail, 102 pebble, 127 deco, 96 retro) and the expected bounding box, and in the bottles every inside part stays at least 0.4 mm inside the wall (the tightest are the foam sleeve around the cup and, in the Pebble bottle, the BTS7960 board). Sizes for the ESP32, BTS7960, OLED, BMS and LM2596 are typical values; measure your parts. The weight (about 1.4 kg with water, plastic shell) is my estimate. Finishes and materials are suggestions, not tested.
