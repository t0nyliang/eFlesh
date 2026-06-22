"""
Cuts 3 N52 magnet pockets into the bottom face (Z=0) of the lattice STL.
  - Magnet: 4.8mm diameter (2.4mm radius) x 1.6mm deep
  - Arrangement: N-S-N, evenly spaced at X=6.25, 12.5, 18.75 mm; Y=12.5 mm
  - Pockets open downward at Z=0 (bottom of lattice = top of housing at Z=8)
"""

import trimesh
import numpy as np

MAGNET_RADIUS = 4.8 / 2.0   # 2.4 mm
MAGNET_DEPTH  = 1.6          # mm
POCKET_X      = [6.25, 12.5, 18.75]
POCKET_Y      = 12.5
EPS           = 0.5          # overcut for clean boolean

print("Loading lattice...")
lattice = trimesh.load("output/forearm_pad_lattice.stl", force="mesh")
print(f"  Loaded: {len(lattice.faces)} triangles, watertight={lattice.is_watertight}")

for i, mx in enumerate(POCKET_X):
    print(f"  Cutting pocket {i+1}/3 at X={mx}...")
    cyl_height = MAGNET_DEPTH + 2 * EPS
    cyl = trimesh.creation.cylinder(radius=MAGNET_RADIUS, height=cyl_height, sections=64)
    # Center the cylinder so it spans Z=-EPS to Z=MAGNET_DEPTH+EPS → opens at Z=0
    cyl.apply_translation([mx, POCKET_Y, MAGNET_DEPTH / 2.0])
    lattice = lattice.difference(cyl, engine="manifold")

print(f"After pockets: {len(lattice.faces)} triangles, watertight={lattice.is_watertight}")
print(f"BBox: {lattice.bounding_box.extents}")

lattice.export("output/forearm_pad_lattice.stl")
print("Saved output/forearm_pad_lattice.stl")
