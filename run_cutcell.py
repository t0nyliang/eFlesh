"""
Runs the cut-cell microstructure pipeline equivalent to cut-cell.ipynb.

Strategy: run cut_cells_cli WITHOUT --surface (avoids the mesh2sdf crash
that occurs with our simple box OBJ under the bundled OpenVDB version).
The binary generates a pure cubic lattice; we then clip it to the
forearm pad bounding box [0,25]×[0,25]×[0,20] mm using trimesh.
"""

import json, sys, copy, os
import numpy as np
import meshio
import trimesh

notebook_dir = os.path.abspath("microstructure/microstructure_inflators")
matopt_repo_path = os.path.abspath("microstructure/matopt")

input_surface = os.path.abspath("shapes/forearm_pad.obj")
cut_cells_cli = os.path.join(notebook_dir, "build/isosurface_inflator/cut_cells_cli")

E = 0.005
nu = 0.09
cell_size = 8

sys.path.insert(0, os.path.join(matopt_repo_path, "tools/material2geometry"))
from material2geometry import Material2Geometry

mat2geo = Material2Geometry(
    in_path=os.path.join(matopt_repo_path, "tools/material2geometry/0646_geo_1_coeffs.txt")
)

m = meshio.read(input_surface)
v = m.points.astype(float)
bbox_min = np.amin(v, axis=0)
bbox_max = np.amax(v, axis=0)

corner0 = list(map(int, np.ceil(bbox_min / cell_size) - 1))
corner1 = list(map(int, np.floor(bbox_max / cell_size)))
print(f"Grid corners: {corner0} -> {corner1}")

out_obj = "output/forearm_pad_lattice_raw.obj"
os.makedirs("output", exist_ok=True)

pattern_file = os.path.join(notebook_dir, "data/patterns/3D/reference_wires/pattern0646.wire")
entry = {"params": [], "symmetry": "Cubic", "pattern": pattern_file, "index": [0, 0, 0]}
patterns = []
for i in range(corner0[0], 1 + corner1[0]):
    for j in range(corner0[1], 1 + corner1[1]):
        for k in range(corner0[2], 1 + corner1[2]):
            geo_params = mat2geo.evaluate(nu, E)
            entry["params"] = geo_params
            entry["index"] = [i, j, k]
            patterns.append(copy.deepcopy(entry))

with open("data.json", "w") as fp:
    json.dump(patterns, fp)
print(f"Generated {len(patterns)} cell entries in data.json")

# Run WITHOUT --surface to avoid the mesh2sdf crash; clip in Python below.
cmd = (
    f"{cut_cells_cli} -p data.json"
    f" --gridSize {cell_size} -o {out_obj} -r 50"
)
print("Running:", cmd)
ret = os.system(cmd)
print("Return code:", ret)
if ret != 0:
    sys.exit(1)

if not os.path.exists(out_obj):
    print("ERROR: cut_cells_cli did not produce output")
    sys.exit(1)

# Clip the raw cubic lattice to the pad bounding box [0,25]×[0,25]×[0,20].
# The raw lattice extends one cell-width beyond the surface on each side.
print("Clipping lattice to pad bounding box...")
raw = trimesh.load(out_obj, force="mesh")
print(f"  Raw lattice: {len(raw.faces)} triangles, watertight={raw.is_watertight}")

pad_box = trimesh.creation.box([bbox_max[0] - bbox_min[0],
                                 bbox_max[1] - bbox_min[1],
                                 bbox_max[2] - bbox_min[2]])
center = (bbox_min + bbox_max) / 2.0
pad_box.apply_translation(center)

lattice = raw.intersection(pad_box, engine="manifold")
print(f"  Clipped lattice: {len(lattice.faces)} triangles, watertight={lattice.is_watertight}")

stl_path = "output/forearm_pad_lattice.stl"
lattice.export(stl_path)
print(f"Saved {stl_path}")
print(f"  Bounding box: {lattice.bounding_box.extents}")
