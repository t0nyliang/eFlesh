"""
Runs the cut-cell microstructure pipeline equivalent to cut-cell.ipynb.
Called by the GitHub Actions workflow after cut_cells_cli is built.
"""

import json, sys, copy, os
import numpy as np
import meshio

notebook_dir = os.path.abspath("microstructure/microstructure_inflators")
matopt_repo_path = os.path.abspath("microstructure/matopt")

input_surface = os.path.abspath("shapes/forearm_pad.obj")
cut_cells_cli = os.path.join(notebook_dir, "build/isosurface_inflator/cut_cells_cli")
only_cube_cells = False

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
bbox = [np.amin(v, axis=0), np.amax(v, axis=0)]

corner0 = list(map(int, np.ceil(bbox[0] / cell_size) - 1))
corner1 = list(map(int, np.floor(bbox[1] / cell_size)))
print(f"Grid corners: {corner0} -> {corner1}")

out_obj = "output/forearm_pad_lattice.obj"
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

cmd = (
    f"{cut_cells_cli} -p data.json"
    + (f" --surface {input_surface}" if not only_cube_cells else "")
    + f" --gridSize {cell_size} -o {out_obj} -r 50"
)
print("Running:", cmd)
ret = os.system(cmd)
print("Return code:", ret)
if ret != 0:
    sys.exit(1)

# Convert OBJ -> STL
stl_path = "output/forearm_pad_lattice.stl"
try:
    import trimesh
    mesh = trimesh.load(out_obj)
    mesh.export(stl_path)
    print(f"Converted to STL via trimesh: {stl_path}")
    print(f"  Triangles: {len(mesh.faces)}, Watertight: {mesh.is_watertight}")
    print(f"  Bounding box: {mesh.bounding_box.extents}")
except Exception as e:
    print(f"trimesh failed ({e}), trying meshio...")
    m2 = meshio.read(out_obj)
    meshio.write(stl_path, m2)
    print(f"Converted to STL via meshio: {stl_path}")
