#!/usr/bin/env python3
"""Re-tessellate ONLY the two ion-optics grids and splice them into
gridded_ion_model.json and the <script id="model-data"> blob in gridded_ion.html.

Every other component is left byte-identical, so this is a scoped geometry swap
rather than a full model regeneration. Hole radii come from build_thruster's
SCREEN_OPEN / ACCEL_OPEN transparencies.
"""
import sys, json, base64, math
import numpy as np
import mesher
import build_thruster as B

HTML = "gridded_ion.html"
JSON = "gridded_ion_model.json"
TAG  = '<script id="model-data" type="application/json">'

def build_grids():
    z_s0, z_s1 = B.Z_SCREEN0, B.Z_SCREEN0 + B.SCREEN_T
    z_a0, z_a1 = z_s1 + B.GRID_GAP, z_s1 + B.GRID_GAP + B.ACCEL_T
    screen = B.perforate(B.cyl(B.R_GRID, z_s0, z_s1), z_s0, z_s1, B.SCREEN_HOLE_R)
    accel  = B.perforate(B.cyl(B.R_GRID, z_a0, z_a1), z_a0, z_a1, B.ACCEL_HOLE_R)
    return {"Screen_Grid_Positive": screen, "Accel_Grid_Negative": accel}

def b64(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode("ascii")

def tessellate(solid):
    # lin/ang=0.1 reproduces the density the shipped grids were meshed at: 126 segments
    # round each bore (506 verts/hole). build_model.py's default 0.5/0.4 gives 32 — visibly
    # polygonal apertures in the cross-section, so don't coarsen these.
    P, N, I = mesher.mesh_shape(solid, lin=0.1, ang=0.1)
    # CAD (cx,cy,cz) -> viewer (cz,cy,cx), positions AND normals
    Pv = np.column_stack([P[:, 2], P[:, 1], P[:, 0]]).astype("<f4")
    Nv = np.column_stack([N[:, 2], N[:, 1], N[:, 0]]).astype("<f4")
    return dict(pos=b64(Pv), nrm=b64(Nv), idx=b64(I.astype("<u4"))), len(Pv), len(I) // 3

def main():
    print(f"SCREEN_HOLE_R={B.SCREEN_HOLE_R:.4f} (phi={B.SCREEN_OPEN})  "
          f"ACCEL_HOLE_R={B.ACCEL_HOLE_R:.4f} (phi={B.ACCEL_OPEN})")
    new = {}
    for name, solid in build_grids().items():
        payload, nv, nt = tessellate(solid)
        new[name] = payload
        print(f"  {name:24s} verts={nv:6d} tris={nt:6d}")

    # ---- the HTML blob is the LIVE model; the .json file had gone stale, so
    # rebuild the json from the blob and splice the new grids into both.
    # Byte-level splice so the other 7 MB of the file (incl. line endings) is untouched.
    raw = open(HTML, "rb").read()
    tag = TAG.encode()
    a = raw.find(tag) + len(tag)
    b = raw.find(b"</script>", a)
    assert a > len(tag) and b > a
    doc = json.loads(raw[a:b].decode("utf-8"))
    hit = 0
    for c in doc["components"]:
        if c["name"] in new:
            c.update(new[c["name"]]); hit += 1
    assert hit == 2, hit
    blob = json.dumps(doc, separators=(", ", ": ")).encode("utf-8")

    open(JSON, "wb").write(blob)
    open(HTML, "wb").write(raw[:a] + blob + raw[b:])
    print(f"WROTE {JSON} ({len(blob)} bytes) and re-embedded into {HTML}")

if __name__ == "__main__":
    main()
