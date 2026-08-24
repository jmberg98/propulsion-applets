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
    # `ang` alone sets the segment count round a bore — measured, it is radius-independent:
    # 0.10 -> 126 segments (506 verts/hole), 0.35 -> 36 (146), 0.50 -> 26 (106). The old 0.10 was
    # sized for the Ø22 bores of the coarse lattice; on the dense lattice's Ø9.3 screen / Ø4.2
    # accel bores 36 segments leaves facets of 0.8 mm / 0.4 mm, smooth at every zoom the viewer
    # reaches, and it is what keeps 926 bores inside the vertex budget 220 used to cost.
    # `lin` still governs the grid's own Ø212 rim (72 segments), so leave it at 0.1.
    P, N, I = mesher.mesh_shape(solid, lin=0.1, ang=0.35)
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
