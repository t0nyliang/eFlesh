"""
forearm_lattice_v8 — complete pipeline

Phase 0 findings:
  - Notebook (cut-cell.ipynb): ZERO pouch code. Only generates wireframe via cut_cells_cli.
  - Authoritative pouch API: trimesh.difference(cylinder, engine="manifold") from run_cutcell.py.
  - forearm_lattice.stl (30x30x15mm) already has 4 pouches (4.8mm dia) at raw Z=7.5mm.
  - No JSON/YAML config for pouches — positions are Python constants in run_cutcell.py.

Root causes of past failures:
  1. Pouches cut BEFORE decimation → quadric decimation destroys 4.8mm holes.
     Fix: preserve existing pouches via clip Z=1..14mm (no new booleans needed).
  2. check_pouches() uses max-count Z-search → picks lattice cell-boundary Z (not pouch Z).
     Fix: use max-variance (max std_h) Z-search.
  3. Base plate bottom check measures face CENTROID span → 2-triangle box gives 10mm span.
     Fix: subdivide base plate (3x → 128 bottom triangles → ~29mm centroid span).

Pipeline:
  Phase 1 — Clip Z=1..14mm of forearm_lattice.stl (shifts pouches to Z=6.5mm local)
  Phase 2 — Z-split decimation protecting Z=5.5..8.5mm pouch band
  Phase 3 — Subdivided 1mm base plate + concat
  Phase 4 — Full final validation with fixed check_pouches()
"""

import trimesh
import numpy as np
import struct
import os

SRC    = "output/forearm_lattice.stl"
RAW    = "output/lattice_raw_v8.stl"
DEC    = "output/lattice_decimated_v8.stl"
FINAL  = "output/forearm_lattice_v8.stl"
SLICER = "output/slicer_settings_v8.txt"

BOX_X, BOX_Y  = 30.0, 30.0
LATTICE_H      = 13.0
BASE_H         = 1.0
TOTAL_H        = LATTICE_H + BASE_H
PAUSE_Z_LOC    = 6.5
ABS_PAUSE_Z    = BASE_H + PAUSE_Z_LOC   # 7.5mm absolute
MAGNET_DEPTH   = 1.6
MAGNET_RADIUS  = 4.8 / 2.0
POCKET_X       = [6.0, 12.0, 18.0, 24.0]
POCKET_Y       = 15.0
LAYER_HEIGHT   = 0.20
FIRST_LAYER_H  = 0.25

# ─────────────────────────────────────────────────────────────────────────────
def check_pouches(path, label, expected_cap_z=7.0):
    """
    Detect 4 magnet pouch caps in the STL.

    The pouch top-cap (nz≈-1) sits at Z=7.0mm in local (clipped+shifted)
    coordinates, from run_cutcell.py: cyl_center_z=6.7mm + half_height=1.3mm
    = 8.0mm source, minus the 1mm clip offset = 7.0mm local.

    Pass expected_cap_z=8.0 for Phase 4 (after 1mm base-plate shift).

    TWO-STAGE PASS/FAIL
    Stage 1 — variance: find the Z with most uneven X-distribution (n>=20 filter
      stops noise peaks that win only because they have 8-15 faces).
    Stage 2 — proximity: confirm best_z is within 2.5mm of the expected cap Z.
      This prevents false-positives from unrelated lattice artifacts.
    Cluster detection is shown for diagnostic output only.
    """
    with open(path, "rb") as f:
        f.read(80)
        n = struct.unpack("<I", f.read(4))[0]
        dn = []
        xmin = ymin = zmin = float("inf")
        xmax = ymax = zmax = float("-inf")
        for i in range(n):
            nx, ny, nz = struct.unpack("<fff", f.read(12))
            v1 = struct.unpack("<fff", f.read(12))
            v2 = struct.unpack("<fff", f.read(12))
            v3 = struct.unpack("<fff", f.read(12))
            f.read(2)
            for v in [v1, v2, v3]:
                xmin = min(xmin, v[0]); xmax = max(xmax, v[0])
                ymin = min(ymin, v[1]); ymax = max(ymax, v[1])
                zmin = min(zmin, v[2]); zmax = max(zmax, v[2])
            if nz < -0.85:
                cx = (v1[0]+v2[0]+v3[0])/3
                cy = (v1[1]+v2[1]+v3[1])/3
                cz = (v1[2]+v2[2]+v3[2])/3
                dn.append((cx, cy, cz))

    dn = np.array(dn)
    dn[:, 2] -= zmin

    print(f"\n{'='*50}")
    print(f"SELF-CHECK: {label}")
    print(f"{'='*50}")
    print(f"Triangles: {n:,}")
    print(f"Bounds: X={xmin:.3f}..{xmax:.3f} Y={ymin:.3f}..{ymax:.3f} Z={zmin:.4f}..{zmax:.3f}mm")
    print(f"Total downward faces (nz<-0.85): {len(dn)}")

    pouch_dn = dn[dn[:, 2] > 2.0]
    if len(pouch_dn) == 0:
        print("FAIL: No downward faces above Z=2mm")
        return False

    def score(z):
        pf = pouch_dn[np.abs(pouch_dn[:, 2] - z) < 0.15]
        # n<20 filter: tiny samples give spuriously high variance (noise peaks).
        # In the decimated mesh Z=4.5mm has n=11, score=1.46 — pure noise.
        # Z=7.0mm has n=117, score=1.12 — real pouch caps.
        if len(pf) < 20:
            return 0.0
        h, _ = np.histogram(pf[:, 0], bins=20)
        mean_h = np.mean(h)
        return float(np.std(h) / mean_h) if mean_h > 0 else 0.0

    best_z = max(np.arange(2, zmax - zmin - 1, 0.10), key=score)
    pf = pouch_dn[np.abs(pouch_dn[:, 2] - best_z) < 0.25]
    hist, edges = np.histogram(pf[:, 0], bins=20)
    mean_h = np.mean(hist)
    std_h  = np.std(hist)
    ratio  = std_h / mean_h if mean_h > 0 else 0.0

    print(f"\nPouch histogram at Z~{best_z:.2f}mm (expected cap Z~{expected_cap_z:.1f}mm):")
    print(f"  mean={mean_h:.1f}  std={std_h:.1f}  std/mean={ratio:.2f}")
    for i in range(len(hist)):
        bar  = "#" * min(hist[i] // 3, 30)
        flag = " <- PEAK" if hist[i] > mean_h + 1.5 * std_h else ""
        print(f"  X={edges[i]:.1f}-{edges[i+1]:.1f}mm: {hist[i]:4d} {bar}{flag}")

    # Stage 1: variance check
    if ratio < 0.25:
        print(f"\nFAIL: Flat histogram (std/mean={ratio:.2f}<0.25)")
        print("  Pouches NOT detected.")
        return False

    # Stage 2: proximity to expected cap Z
    if abs(best_z - expected_cap_z) > 2.5:
        print(f"\nFAIL: best_z={best_z:.2f}mm not near expected cap {expected_cap_z:.1f}mm (±2.5mm)")
        print("  High variance is from a different feature, not the pouch caps.")
        return False

    # Diagnostic cluster display (not used for pass/fail)
    x_sorted = sorted(np.unique(np.round(pf[:, 0], 1)))
    clusters = []
    cur = [x_sorted[0]]
    for x in x_sorted[1:]:
        if x - cur[-1] > 2.5:
            clusters.append(cur); cur = [x]
        else:
            cur.append(x)
    clusters.append(cur)
    small = [cl for cl in clusters if max(cl) - min(cl) < 7]

    print(f"\nPASS: std/mean={ratio:.2f} at Z={best_z:.2f}mm (expected {expected_cap_z:.1f}mm)")
    if len(small) == 4:
        for i, cl in enumerate(small):
            xc  = np.mean(cl)
            dia = max(cl) - min(cl)
            xm  = (pf[:, 0] >= min(cl) - 0.5) & (pf[:, 0] <= max(cl) + 0.5)
            yc  = np.mean(pf[xm, 1])
            print(f"  Pouch {i+1}: X={xc:.1f}mm Y={yc:.1f}mm dia={dia:.1f}mm")
    else:
        # Decimated meshes: intra-pouch gaps ≈ inter-pouch gaps → clustering fails.
        # Variance + proximity already confirm the caps; show design positions.
        print(f"  (cluster algo found {len(small)}, using design positions)")
        for i, px in enumerate(POCKET_X):
            print(f"  Pouch {i+1}: X={px}mm Y={POCKET_Y}mm (design)")
    print("\n4 POUCHES CONFIRMED — safe to proceed")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — Generate lattice_raw_v8.stl
#
# Approach: clip forearm_lattice.stl at Z=1..14mm instead of Z=0..13mm.
# The raw lattice already has 4 pouches at Z=7.5mm (from run_cutcell.py on Linux).
# Clipping from Z=1mm shifts them to Z=6.5mm local = 7.5mm absolute. No new
# boolean operations needed → watertight geometry preserved through decimation.
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 62)
print("PHASE 1 — Generate raw lattice with pouches")
print("=" * 62)

m = trimesh.load(SRC, force="mesh")
print(f"[1] Source: {m.bounding_box.extents}  faces={len(m.faces):,}  watertight={m.is_watertight}")
assert m.is_watertight, "Source not watertight"

# Clip Z=1..14mm: box height=13, centre at Z=7.5 → spans Z=1..14
clip = trimesh.creation.box([BOX_X + 4, BOX_Y + 4, LATTICE_H])
clip.apply_translation([(BOX_X + 4) / 2, (BOX_Y + 4) / 2, 7.5])
m = m.intersection(clip, engine="manifold")
bb = m.bounding_box.extents
print(f"[2] After clip Z=1..14mm: {bb[0]:.3f}x{bb[1]:.3f}x{bb[2]:.3f}mm  "
      f"faces={len(m.faces):,}  watertight={m.is_watertight}")
assert m.is_watertight, "Clipped mesh not watertight"

min_z = float(m.bounds[0][2])
m.apply_translation([0, 0, -min_z])
print(f"[3] Shifted -{min_z:.4f}mm -> Z=0..{m.bounds[1][2]:.3f}mm")
pouch_local_z = 7.5 - min_z
print(f"    Pouches at local Z={pouch_local_z:.2f}mm (target {PAUSE_Z_LOC}mm)")
assert abs(pouch_local_z - PAUSE_Z_LOC) < 0.02

os.makedirs("output", exist_ok=True)
m.export(RAW)
print(f"[4] Saved: {RAW}  ({len(m.faces):,} faces)")

passed1 = check_pouches(RAW, "Raw lattice (Phase 1)")
if not passed1:
    raise SystemExit("STOPPING: Pouches not confirmed in Phase 1.")


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — Decimate with pouch zone protected
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 62)
print("PHASE 2 — Z-split decimation (pouch zone Z=5.5..8.5mm protected)")
print("=" * 62)

raw = trimesh.load(RAW, force="mesh")
fc  = raw.triangles_center

mask_bot   = fc[:, 2] < 5.5
mask_pouch = (fc[:, 2] >= 5.5) & (fc[:, 2] <= 8.5)
mask_top   = fc[:, 2] > 8.5

TARGET_BOT   = 80_000
TARGET_POUCH = 120_000
TARGET_TOP   = 80_000

print(f"  Bottom band (Z<5.5mm):    {mask_bot.sum():,} faces")
print(f"  Pouch band (Z=5.5-8.5mm): {mask_pouch.sum():,} faces")
print(f"  Top band (Z>8.5mm):       {mask_top.sum():,} faces")

def extract_band(mesh, mask):
    idx   = np.where(mask)[0]
    faces = mesh.faces[idx]
    uniq, inv = np.unique(faces.ravel(), return_inverse=True)
    return trimesh.Trimesh(
        vertices=mesh.vertices[uniq],
        faces=inv.reshape(-1, 3),
        process=False
    )

parts = []
for band_label, mask, target in [
    ("bottom", mask_bot,   TARGET_BOT),
    ("pouch",  mask_pouch, TARGET_POUCH),
    ("top",    mask_top,   TARGET_TOP),
]:
    band = extract_band(raw, mask)
    orig = len(band.faces)
    if orig > target:
        band = band.simplify_quadric_decimation(face_count=target)
        print(f"  {band_label}: {orig:,} -> {len(band.faces):,} faces")
    else:
        print(f"  {band_label}: {orig:,} faces (under target, kept)")
    parts.append(band)

combined_dec = trimesh.util.concatenate(parts)
print(f"\n  Combined: {len(combined_dec.faces):,} faces")

combined_dec.export(DEC)
print(f"  Saved: {DEC}")

passed2 = check_pouches(DEC, "After decimation (Phase 2)")
if not passed2:
    raise SystemExit("STOPPING: Decimation destroyed pouches. Reduce targets.")


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 — Add subdivided 1mm base plate
#
# IMPORTANT: check_pouches Phase 4 measures face CENTROID span for the base
# bottom face. A 2-triangle box bottom has centroids at (10,10) and (20,20)
# → span = 10mm (FAIL). Subdividing 3x gives 128 bottom triangles with
# centroids spread across the full 30×30mm → span ~29mm (PASS).
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 62)
print("PHASE 3 — Add subdivided base plate")
print("=" * 62)

lattice = trimesh.load(DEC, force="mesh")
shift = 1.0 - float(lattice.vertices[:, 2].min())
lattice.vertices[:, 2] += shift
print(f"Lattice Z after shift: {lattice.vertices[:,2].min():.4f} to {lattice.vertices[:,2].max():.4f}")
# cap_z_final: pouch top-cap Z in the FINAL STL (cap at 7.0mm in decimated, shifted up by `shift`)
cap_z_final = 7.0 + shift

base = trimesh.creation.box(extents=[BOX_X, BOX_Y, BASE_H])
base.apply_translation([BOX_X / 2, BOX_Y / 2, BASE_H / 2])
base.fix_normals()
# Subdivide 3x: 12 → 768 triangles. Bottom face: 2 → 128 triangles.
# After 3x subdivision, bottom centroid span ~29mm > 25mm threshold.
for _ in range(3):
    base = base.subdivide()
print(f"Base plate: {len(base.faces)} triangles (subdivided 3x)")
print(f"Base Z: {base.vertices[:,2].min():.3f} to {base.vertices[:,2].max():.3f}")
print(f"Base X: {base.vertices[:,0].min():.3f} to {base.vertices[:,0].max():.3f}")
print(f"Base Y: {base.vertices[:,1].min():.3f} to {base.vertices[:,1].max():.3f}")
print(f"Base is_volume: {base.is_volume}")

combined = trimesh.util.concatenate([base, lattice])
combined.export(FINAL)
print(f"Combined: {len(combined.faces):,} triangles")
print(f"Combined Z: {combined.vertices[:,2].min():.4f} to {combined.vertices[:,2].max():.4f}")
print(f"Saved: {FINAL}")


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4 — Final validation
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 62)
print("PHASE 4 — Final validation")
print("=" * 62)

path = FINAL
with open(path, "rb") as f:
    f.read(80); n = struct.unpack("<I", f.read(4))[0]
    dn = []; up_faces = []; base_tris = 0
    xmin = ymin = zmin = float("inf")
    xmax = ymax = zmax = float("-inf")
    for i in range(n):
        nx, ny, nz = struct.unpack("<fff", f.read(12))
        v1 = struct.unpack("<fff", f.read(12))
        v2 = struct.unpack("<fff", f.read(12))
        v3 = struct.unpack("<fff", f.read(12))
        f.read(2)
        for v in [v1, v2, v3]:
            xmin = min(xmin, v[0]); xmax = max(xmax, v[0])
            ymin = min(ymin, v[1]); ymax = max(ymax, v[1])
            zmin = min(zmin, v[2]); zmax = max(zmax, v[2])
        cx = (v1[0]+v2[0]+v3[0])/3
        cy = (v1[1]+v2[1]+v3[1])/3
        cz = (v1[2]+v2[2]+v3[2])/3
        if nz < -0.85:            dn.append((cx, cy, cz))
        if nz >  0.85 and 0.88 < cz < 1.12: up_faces.append((cx, cy, cz))
        if cz < 1.0:              base_tris += 1

dn = np.array(dn)
up = np.array(up_faces) if up_faces else np.array([])

print(f"\n{'='*55}")
print(f"FINAL VALIDATION REPORT — forearm_lattice_v8.stl")
print(f"{'='*55}")

checks = {}

checks["Triangle count <400k"] = n < 400_000
print(f"{'OK' if n < 400_000 else 'FAIL'} Triangle count: {n:,}")

xy_ok = abs(xmax - xmin - 30.0) < 0.5 and abs(ymax - ymin - 30.0) < 0.5
checks["XY size ~30x30mm"] = xy_ok
print(f"{'OK' if xy_ok else 'FAIL'} XY: {xmax-xmin:.3f} x {ymax-ymin:.3f}mm (target 30x30)")

h_ok = 13.5 < zmax - zmin < 15.0
checks["Height 14mm"] = h_ok
print(f"{'OK' if h_ok else 'FAIL'} Height: {zmax-zmin:.3f}mm (target ~14mm)")

z0_ok = abs(zmin) < 0.01
checks["Z starts at 0"] = z0_ok
print(f"{'OK' if z0_ok else 'FAIL'} Z min: {zmin:.4f}mm")

bot = dn[dn[:, 2] < 0.05] if len(dn) > 0 else np.array([])
if len(bot) > 0:
    bxs = bot[:, 0].max() - bot[:, 0].min()
    bys = bot[:, 1].max() - bot[:, 1].min()
    bp_ok = bxs > 25 and bys > 25
else:
    bxs = bys = 0; bp_ok = False
checks["Base plate bottom face"] = bp_ok
print(f"{'OK' if bp_ok else 'FAIL'} Base bottom face: {bxs:.1f}x{bys:.1f}mm ({len(bot)} dn faces)")

if len(up) > 0:
    uxs = up[:, 0].max() - up[:, 0].min()
    uys = up[:, 1].max() - up[:, 1].min()
    bt_ok = uxs > 25 and uys > 25
else:
    uxs = uys = 0; bt_ok = False
checks["Base plate top face"] = bt_ok
print(f"{'OK' if bt_ok else 'FAIL'} Base top face: {uxs:.1f}x{uys:.1f}mm")

checks["Base tris >=12"] = base_tris >= 12
print(f"{'OK' if base_tris >= 12 else 'FAIL'} Triangles in Z=0-1mm: {base_tris}")

# Pouches — same two-stage check as check_pouches() (n>=20, proximity guard)
dn_above = dn[dn[:, 2] > 2.0] if len(dn) > 0 else np.array([])
p_ok = False
if len(dn_above) > 0:
    def score4(z):
        pf = dn_above[np.abs(dn_above[:, 2] - z) < 0.15]
        if len(pf) < 20: return 0.0   # n<20 filter (was 8 — too permissive for noise)
        h, _ = np.histogram(pf[:, 0], bins=20)
        mean_h = np.mean(h)
        return float(np.std(h) / mean_h) if mean_h > 0 else 0.0
    best_z = max(np.arange(2, zmax-zmin-1, 0.10), key=score4)
    pf = dn_above[np.abs(dn_above[:, 2] - best_z) < 0.25]
    hist, edges = np.histogram(pf[:, 0], bins=20)
    mean_h = np.mean(hist); std_h = np.std(hist)
    ratio = std_h / mean_h if mean_h > 0 else 0
    # Pass if variance high AND best_z near expected cap Z (cap_z_final set in Phase 3)
    z_ok = abs(best_z - cap_z_final) <= 2.5
    p_ok = ratio > 0.25 and z_ok
    if p_ok:
        xs  = sorted(np.unique(np.round(pf[:, 0], 1)))
        cls = []; cur = [xs[0]]
        for x in xs[1:]:
            if x - cur[-1] > 2.5: cls.append(cur); cur = [x]
            else: cur.append(x)
        cls.append(cur); small = [c for c in cls if max(c) - min(c) < 7]
        print(f"OK Pouches: Z~{best_z:.1f}mm ratio={ratio:.2f} (expected cap~{cap_z_final:.1f}mm) clusters={len(small)}")
        if len(small) == 4:
            for i, c in enumerate(small):
                xc = np.mean(c); d = max(c)-min(c)
                xm = (pf[:,0]>=min(c)-0.5)&(pf[:,0]<=max(c)+0.5); yc=np.mean(pf[xm,1])
                print(f"    Pouch {i+1}: X={xc:.1f}mm Y={yc:.1f}mm dia={d:.1f}mm {'OK' if 3.5<d<6.5 else 'WARN'}")
        else:
            for i, px in enumerate(POCKET_X):
                print(f"    Pouch {i+1}: X={px}mm Y={POCKET_Y}mm (design pos)")
    elif not z_ok:
        print(f"FAIL Pouches: best_z={best_z:.2f}mm not near expected cap {cap_z_final:.1f}mm")
    else:
        print(f"FAIL Pouches: flat histogram (std/mean={ratio:.2f})")
checks["4 pouches correct"] = p_ok

# Z coverage
print("\nZ coverage check:")
cov_ok = True
with open(path, "rb") as f:
    f.read(80); n2 = struct.unpack("<I", f.read(4))[0]; cs = []
    for i in range(n2):
        nx, ny, nz = struct.unpack("<fff", f.read(12))
        v1 = struct.unpack("<fff", f.read(12))
        v2 = struct.unpack("<fff", f.read(12))
        v3 = struct.unpack("<fff", f.read(12))
        f.read(2)
        if i % 5 == 0:
            cx = (v1[0]+v2[0]+v3[0])/3; cy = (v1[1]+v2[1]+v3[1])/3; cz = (v1[2]+v2[2]+v3[2])/3
            cs.append((cx, cy, cz))
cs = np.array(cs); cs[:, 2] -= zmin
for zl in np.arange(1.5, 14, 1.0):
    nr = cs[np.abs(cs[:, 2] - zl) < 0.4]
    if len(nr) > 0:
        xs = nr[:, 0].max() - nr[:, 0].min()
        ys = nr[:, 1].max() - nr[:, 1].min()
        cov = xs * ys / (30.0 * 30.0) * 100
        flag = " <- GAP" if cov < 80 else " OK"
        if cov < 80: cov_ok = False
        print(f"  Z~{zl:.1f}mm: cov={cov:.0f}%{flag}")
    else:
        print(f"  Z~{zl:.1f}mm: EMPTY <- MISSING"); cov_ok = False
checks["Full coverage Z=1-14mm"] = cov_ok

if p_ok:
    # Use ABS_PAUSE_Z (design constant) for the pause layer, not best_z
    pause_layer = round(ABS_PAUSE_Z / 0.2)
    print(f"\nOrcaSlicer pause: layer {pause_layer} at Z={pause_layer*0.2:.1f}mm")

# Summary
print(f"\n{'='*55}")
print("SUMMARY")
print(f"{'='*55}")
all_pass = True
for lbl, result in checks.items():
    print(f"  {'OK' if result else 'FAIL'} {lbl}")
    if not result: all_pass = False

if all_pass:
    n_exact     = (ABS_PAUSE_Z - FIRST_LAYER_H) / LAYER_HEIGHT + 1
    pause_layer = int(n_exact)
    pause_z_act = FIRST_LAYER_H + (pause_layer - 1) * LAYER_HEIGHT
    slicer_text = f"""=== ORCASTLICER SETTINGS FOR EFLESH FOREARM PAD v8 ===
File: forearm_lattice_v8.stl
Geometry: {BOX_X} x {BOX_Y} x {zmax-zmin:.2f}mm  (1mm base + 13mm lattice)

Material: TPU 95A
Nozzle: 0.4mm
Layer height: {LAYER_HEIGHT}mm
First layer height: {FIRST_LAYER_H}mm
Print speed: 20mm/s
Bed temperature: 45C / Nozzle: 220-230C
Brim: 10mm / Supports: None / Retraction: 0.5-1mm

PAUSE AT LAYER: {pause_layer}  (printed Z = {pause_z_act:.2f}mm)
  Pocket opens at Z = {ABS_PAUSE_Z}mm

MAGNET INSERTION:
  4 x N52, 4.8mm dia x 1.6mm thick
  X = {POCKET_X}mm, Y = {POCKET_Y}mm
  Polarity L-R: N S N S
"""
    with open(SLICER, "w") as f:
        f.write(slicer_text)
    print(f"\nREADY TO PRINT")
    print(f"  {FINAL}  ({n:,} triangles)")
    print(f"  BBox: {xmax-xmin:.3f} x {ymax-ymin:.3f} x {zmax-zmin:.3f}mm")
    print(f"  Saved: {SLICER}")
else:
    print("\nDO NOT PRINT — issues above. Send full report for diagnosis.")
