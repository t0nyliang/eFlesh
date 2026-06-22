"""
eFlesh forearm lattice generation pipeline.

Lattice spec:
  - Shape:      30 x 30 x 15 mm
  - Cell size:  4.0 mm  (fine cell for beam_radius ~0.4 mm)
  - Stiffness:  depth-graded — softer near magnets (low Z), stiffer at skin side (high Z)
  - Magnets:    4 x N52, 4.8mm dia x 1.6mm deep, evenly spaced in X, opening at Z=7.5mm
  - Output:     output/forearm_lattice.stl

Runs cut_cells_cli WITHOUT --surface (avoids mesh2sdf crash in bundled OpenVDB).
Clips the cubic lattice to the pad bounding box with trimesh, then cuts magnet pouches.
"""

import json, sys, copy, os
import numpy as np
import meshio
import trimesh

# ── paths ────────────────────────────────────────────────────────────────────
notebook_dir    = os.path.abspath("microstructure/microstructure_inflators")
matopt_repo_path = os.path.abspath("microstructure/matopt")
input_surface   = os.path.abspath("shapes/forearm_pad.obj")
cut_cells_cli   = os.path.join(notebook_dir, "build/isosurface_inflator/cut_cells_cli")

# ── lattice parameters ────────────────────────────────────────────────────────
nu         = 0.09
cell_size  = 4.0     # mm — fine cell for ~0.4mm beam radius
resolution = 50      # voxel resolution per cell (voxel = 4/49 ≈ 0.082mm)

# Depth-graded Young's modulus: softer lower half (near magnets), stiffer upper half.
# k is the Z-cell index; with cell_size=4 the pad spans k=0..3:
#   k=0 → Z 0–4 mm  (soft, amplifies magnet displacement)
#   k=1 → Z 4–8 mm  (medium-soft, contains the pause/pouch layer at Z=7.5)
#   k=2 → Z 8–12 mm (medium-stiff)
#   k=3 → Z 12–16mm (stiff, skin-contact side)
YOUNG_BY_K = {-1: 0.001, 0: 0.001, 1: 0.002, 2: 0.005, 3: 0.010}

def young(i, j, k):
    return YOUNG_BY_K.get(k, 0.005)

# ── magnet pouch parameters ───────────────────────────────────────────────────
MAGNET_RADIUS   = 4.8 / 2.0   # 2.4 mm
MAGNET_DEPTH    = 1.6          # mm
PAUSE_Z         = 7.5          # mm — pouches open upward at this Z
POCKET_X        = [6.0, 12.0, 18.0, 24.0]   # 4 positions evenly spaced in 30mm
POCKET_Y        = 15.0         # mid-Y of 30mm pad

# ── material→geometry mapper ──────────────────────────────────────────────────
sys.path.insert(0, os.path.join(matopt_repo_path, "tools/material2geometry"))
from material2geometry import Material2Geometry

mat2geo = Material2Geometry(
    in_path=os.path.join(matopt_repo_path, "tools/material2geometry/0646_geo_1_coeffs.txt")
)

# ── read pad shape for bounding box ──────────────────────────────────────────
m        = meshio.read(input_surface)
v        = m.points.astype(float)
bbox_min = np.amin(v, axis=0)
bbox_max = np.amax(v, axis=0)

corner0 = list(map(int, np.ceil(bbox_min / cell_size) - 1))
corner1 = list(map(int, np.floor(bbox_max / cell_size)))
print(f"Pad bbox: {bbox_min} → {bbox_max}")
print(f"Grid corners: {corner0} → {corner1}")

# ── build cell pattern JSON ───────────────────────────────────────────────────
os.makedirs("output", exist_ok=True)
pattern_file = os.path.join(notebook_dir, "data/patterns/3D/reference_wires/pattern0646.wire")
entry    = {"params": [], "symmetry": "Cubic", "pattern": pattern_file, "index": [0, 0, 0]}
patterns = []
for i in range(corner0[0], 1 + corner1[0]):
    for j in range(corner0[1], 1 + corner1[1]):
        for k in range(corner0[2], 1 + corner1[2]):
            e = young(i, j, k)
            geo_params = mat2geo.evaluate(nu, e)
            entry["params"] = geo_params
            entry["index"]  = [i, j, k]
            patterns.append(copy.deepcopy(entry))

with open("data.json", "w") as fp:
    json.dump(patterns, fp)
print(f"Generated {len(patterns)} cell entries (cell_size={cell_size}, res={resolution})")

# ── run cut_cells_cli (no --surface; avoids mesh2sdf crash) ──────────────────
out_obj = "output/forearm_lattice_raw.obj"
cmd = (
    f"{cut_cells_cli} -p data.json"
    f" --gridSize {cell_size} -o {out_obj} -r {resolution}"
)
print("Running:", cmd)
ret = os.system(cmd)
print("Return code:", ret)
if ret != 0 or not os.path.exists(out_obj):
    print("ERROR: cut_cells_cli failed")
    sys.exit(1)

# ── clip cubic lattice to pad bounding box ────────────────────────────────────
print("Clipping lattice to pad bounding box...")
raw = trimesh.load(out_obj, force="mesh")
print(f"  Raw lattice: {len(raw.faces)} triangles, watertight={raw.is_watertight}")

pad_dims   = bbox_max - bbox_min
pad_center = (bbox_min + bbox_max) / 2.0
pad_box    = trimesh.creation.box(pad_dims)
pad_box.apply_translation(pad_center)

lattice = raw.intersection(pad_box, engine="manifold")
print(f"  Clipped: {len(lattice.faces)} triangles, watertight={lattice.is_watertight}")
print(f"  BBox: {lattice.bounding_box.extents}")

# ── cut 4 magnet pouches ──────────────────────────────────────────────────────
# Pouches open UPWARD at Z=PAUSE_Z (the print-pause layer).
# During printing: pause at Z=7.5mm, drop magnets in, resume.
# Pocket: cylinder from Z=(PAUSE_Z - MAGNET_DEPTH) to Z=PAUSE_Z.
print(f"Cutting 4 magnet pouches at Z={PAUSE_Z}mm (opening upward)...")
EPS = 0.5
for idx, mx in enumerate(POCKET_X):
    cyl_height = MAGNET_DEPTH + 2 * EPS
    cyl = trimesh.creation.cylinder(radius=MAGNET_RADIUS, height=cyl_height, sections=64)
    # Center cylinder at Z = PAUSE_Z - MAGNET_DEPTH/2 so it spans
    # Z=(PAUSE_Z - MAGNET_DEPTH - EPS) to Z=(PAUSE_Z + EPS)
    cyl_center_z = PAUSE_Z - MAGNET_DEPTH / 2.0
    cyl.apply_translation([mx, POCKET_Y, cyl_center_z])
    lattice = lattice.difference(cyl, engine="manifold")
    print(f"  Pocket {idx+1}/4 at X={mx}, Y={POCKET_Y}, centre Z={cyl_center_z:.2f}")

print(f"After pouches: {len(lattice.faces)} triangles, watertight={lattice.is_watertight}")

# ── save ──────────────────────────────────────────────────────────────────────
stl_path = "output/forearm_lattice.stl"
lattice.export(stl_path)
print(f"\nSaved: {stl_path}")
print(f"  BBox:      {lattice.bounding_box.extents}")
print(f"  Watertight: {lattice.is_watertight}")
print(f"  Triangles:  {len(lattice.faces)}")
print(f"\nPouch summary:")
print(f"  Count:     4 (N-S-N-S alternating — insert in order X={POCKET_X})")
print(f"  Diameter:  {MAGNET_RADIUS*2:.1f}mm, Depth: {MAGNET_DEPTH}mm")
print(f"  Opening Z: {PAUSE_Z}mm (top of pocket), bottom Z: {PAUSE_Z-MAGNET_DEPTH:.1f}mm")
print(f"  Pause layer (0.2mm layers): layer {int(PAUSE_Z/0.2)}")
print(f"  Pause layer (0.15mm layers): layer {int(PAUSE_Z/0.15)}")
