"""
Generates the 25x25x8mm housing base STL with:
  - PCB slide-in slot (Adafruit MLX90393: 23.0x19.2x2.8mm, slot is 23.4x19.4x3.0mm)
  - Cable notch on X=0 wall (STEMMA QT exit)
  - Cord slot A: upper, through X walls, centered Z=6.5
  - Cord slot B: lower, through X walls, centered Z=2.0
  - 1mm solid floor below PCB slot

Boolean CSG computed with trimesh+manifold3d; result saved via numpy-stl.
"""

import trimesh
import numpy as np
from stl import mesh as stl_mesh

EPS = 0.5  # overcut to avoid coincident faces in CSG

# --- Solid housing block 25 x 25 x 8 mm ---
housing = trimesh.creation.box([25.0, 25.0, 8.0])
housing.apply_translation([12.5, 12.5, 4.0])

# --- PCB slot ---
# 23.4mm wide (X), centered: X from 0.8 to 24.2
# Open at Y=25 face, hard stop wall at Y=5.6
# Floor Z=1.0, ceiling Z=4.0
slot_w = 23.4   # X
slot_d = 25.0 - 5.6 + EPS   # Y: 5.6 to 25+EPS (open face + overcut)
slot_h = 3.0    # Z: 1.0 to 4.0
pcb_slot = trimesh.creation.box([slot_w, slot_d, slot_h])
pcb_slot.apply_translation([
    12.5,                            # X center
    5.6 + slot_d / 2.0 - EPS / 2.0, # Y center (pulled toward open end)
    1.0 + slot_h / 2.0,             # Z center = 2.5
])
housing = housing.difference(pcb_slot, engine="manifold")

# --- Cable notch ---
# Through X=0 wall, 8mm wide (Y) x 4mm tall (Z)
# Centered Y=12.5, Z=0 to 4 (connects floor to PCB slot ceiling)
notch_w = 1.0 + EPS   # X: -EPS to ~1mm (through left wall only)
notch_d = 8.0          # Y
notch_h = 4.0 + EPS   # Z (0 to 4+EPS)
cable_notch = trimesh.creation.box([notch_w, notch_d, notch_h])
cable_notch.apply_translation([
    notch_w / 2.0 - EPS,   # X: left of housing
    12.5,                   # Y center
    notch_h / 2.0 - EPS,   # Z: from below floor to slot ceiling
])
housing = housing.difference(cable_notch, engine="manifold")

# --- Cord slot A (upper) ---
# 6mm wide (Y) x 4mm tall (Z) tunnel through both X walls
# Centered at Z=6.5, Y=12.5
cord_a = trimesh.creation.box([25.0 + 2 * EPS, 6.0, 4.0])
cord_a.apply_translation([12.5, 12.5, 6.5])
housing = housing.difference(cord_a, engine="manifold")

# --- Cord slot B (lower) ---
# 6mm wide (Y) x 4mm tall (Z) tunnel through both X walls
# Centered at Z=2.0, Y=12.5
cord_b = trimesh.creation.box([25.0 + 2 * EPS, 6.0, 4.0])
cord_b.apply_translation([12.5, 12.5, 2.0])
housing = housing.difference(cord_b, engine="manifold")

# --- Export via numpy-stl ---
verts = housing.vertices
faces = housing.faces

np_mesh = stl_mesh.Mesh(np.zeros(len(faces), dtype=stl_mesh.Mesh.dtype))
for i, face in enumerate(faces):
    for j in range(3):
        np_mesh.vectors[i][j] = verts[face[j]]

np_mesh.save("output/forearm_pad_housing.stl")
print("Housing STL saved: output/forearm_pad_housing.stl")
print(f"  Bounding box: {housing.bounding_box.extents}")
print(f"  Is watertight: {housing.is_watertight}")
print(f"  Triangles: {len(housing.faces)}")
