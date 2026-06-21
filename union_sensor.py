"""
Unions the housing base and lattice pad into the final print-ready STL.
Equivalent to the OpenSCAD union_sensor.scad approach but uses trimesh+manifold3d.

Housing: 25x25x8mm, Z=0 to Z=8
Lattice: 25x25x20mm, translated to sit at Z=8 → Z=8 to Z=28
Final bounding box: 25x25x28mm
"""

import trimesh

housing = trimesh.load("output/forearm_pad_housing.stl")
lattice = trimesh.load("output/forearm_pad_lattice.stl")

# Translate lattice to sit directly on top of housing (Z=8)
lattice.apply_translation([0, 0, 8.0])

print(f"Housing triangles: {len(housing.faces)}, watertight: {housing.is_watertight}")
print(f"Lattice triangles: {len(lattice.faces)}, watertight: {lattice.is_watertight}")

sensor = housing.union(lattice, engine="manifold")

sensor.export("output/eflesh_forearm_sensor_FINAL.stl")
print(f"\nFinal sensor STL saved: output/eflesh_forearm_sensor_FINAL.stl")
print(f"  Bounding box: {sensor.bounding_box.extents}")
print(f"  Is watertight: {sensor.is_watertight}")
print(f"  Triangles: {len(sensor.faces)}")
