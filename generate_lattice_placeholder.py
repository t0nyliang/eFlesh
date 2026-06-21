"""
Generates the forearm pad lattice STL as a solid 25x25x20mm TPU block with
3 cylindrical magnet pockets (4.8mm dia x 1.6mm deep) on the bottom face.

NOTE: The real cut-cell microstructure generation requires the C++ cut_cells_cli
binary built from microstructure_inflators/build.sh on Linux. This placeholder
provides the correct external geometry (magnet pockets, bounding box) for
print testing and housing fit verification.

Pockets open at Z=0 (bottom of lattice, interfaces flush with housing top at Z=8).
3 magnets symmetrically spaced in X at Y=12.5, alternating polarity N-S-N.
"""

import trimesh
import numpy as np

MAGNET_DIAM = 4.8
MAGNET_DEPTH = 1.6
MAGNET_RADIUS = MAGNET_DIAM / 2.0

block = trimesh.creation.box([25.0, 25.0, 20.0])
block.apply_translation([12.5, 12.5, 10.0])

magnet_x_positions = [6.25, 12.5, 18.75]
magnet_y = 12.5

EPS = 0.5
for mx in magnet_x_positions:
    # Pocket opens at Z=0 (bottom face) and goes UP into block to Z=MAGNET_DEPTH.
    # Cylinder straddles Z=0: from Z=-EPS to Z=MAGNET_DEPTH+EPS for a clean cut.
    cyl_height = MAGNET_DEPTH + 2 * EPS
    cyl = trimesh.creation.cylinder(
        radius=MAGNET_RADIUS,
        height=cyl_height,
        sections=64,
    )
    # trimesh cylinder is centered at origin; translate center to Z = (MAGNET_DEPTH/2)
    cyl.apply_translation([mx, magnet_y, MAGNET_DEPTH / 2.0])
    block = block.difference(cyl, engine="manifold")

block.export("output/forearm_pad_lattice.stl")
print(f"Lattice STL saved: output/forearm_pad_lattice.stl")
print(f"  Bounding box: {block.bounding_box.extents}")
print(f"  Is watertight: {block.is_watertight}")
print(f"  Triangles: {len(block.faces)}")
