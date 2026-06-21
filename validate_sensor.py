"""Final mesh validation for eflesh_forearm_sensor_FINAL.stl"""

import trimesh
import numpy as np

mesh = trimesh.load("output/eflesh_forearm_sensor_FINAL.stl")

bbox = mesh.bounding_box.extents
print("=== eFlesh Forearm Sensor — Mesh Validation ===")
print(f"  File:          output/eflesh_forearm_sensor_FINAL.stl")
print(f"  Triangles:     {len(mesh.faces)}")
print(f"  Vertices:      {len(mesh.vertices)}")
print(f"  Bounding box:  {bbox[0]:.2f} x {bbox[1]:.2f} x {bbox[2]:.2f} mm")

watertight = mesh.is_watertight
print(f"  Watertight:    {watertight}")

# Degenerate face check: faces with zero area
areas = mesh.area_faces
degen = np.sum(areas < 1e-10)
print(f"  Degenerate faces: {degen}")

# Manifold check: every edge should be shared by exactly 2 faces
edge_counts = np.bincount(mesh.edges_sorted.ravel() * 0 + 1,
                          minlength=1)  # placeholder; use face_adjacency
non_manifold_edges = len(mesh.edges) - len(mesh.edges_unique) * 2
print(f"  Non-manifold edges: {non_manifold_edges}")

# Bounding box sanity check (~25x25x28mm)
expected = np.array([25.0, 25.0, 28.0])
tol = 0.5
bbox_ok = np.all(np.abs(bbox - expected) < tol)
print(f"  Bbox ~25x25x28: {bbox_ok}")

print()
if watertight and degen == 0 and bbox_ok:
    print("PASS — mesh is valid and print-ready.")
else:
    issues = []
    if not watertight:
        issues.append("not watertight")
    if degen > 0:
        issues.append(f"{degen} degenerate faces")
    if not bbox_ok:
        issues.append(f"unexpected bounding box {bbox.tolist()}")
    print(f"FAIL — {', '.join(issues)}")
