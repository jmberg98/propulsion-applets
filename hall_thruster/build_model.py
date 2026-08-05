#!/usr/bin/env python3
"""build_model.py - tessellate the parametric Hall thruster into the viewer's JSON.

Same pipeline as gridded_ion/build_model.py: build123d solids -> mesher.mesh_shape
(smooth per-face normals) -> base64 float32/uint32 blobs -> one JSON document the
viewer decodes with atob().

CAD -> viewer axis map. The CAD model is built on +Z (see build_thruster.py), but
the viewer frames the thruster with its axis running across the screen and cuts on
viewer z = 0, matching the gridded-ion applet. The map is

    (vx, vy, vz) = (cz, cy, -cx)

which is a proper +90 deg rotation about Y (det = +1), NOT the reflection the
gridded-ion tessellator used - so triangle winding stays consistent with the
normals and single-sided lighting is correct. CAD +Z (downstream) becomes viewer
+X, and the CAD x = 0 plane becomes the viewer's z = 0 cut plane.

Usage: python build_model.py [out.json]
"""
import sys
import json
import base64

import numpy as np

import mesher
import build_thruster as B

# name, label, role, viewer color, solid
#
# Labels repeat on purpose where the reference image uses one callout for several
# solids ("Magnetic core" covers the outer yoke and the inner stem; "Magnetic
# coils" covers the inner and outer windings) - the same thing gridded_ion does
# with its two Magnet_Ring_* components.
COMPONENTS = [
    ("Outer_Shell",           "Outer Shell",              "structure", "#d5d8e4", "shell"),
    ("Magnetic_Core_Outer",   "Magnetic Core",            "core",      "#7a808b", "core_outer"),
    ("Magnetic_Core_Inner",   "Magnetic Core",            "core",      "#8a9099", "core_inner"),
    ("Coil_Outer",            "Magnetic Coils",           "coil",      "#b9773a", "coil_outer"),
    ("Coil_Inner",            "Magnetic Coils",           "coil",      "#b9773a", "coil_inner"),
    ("Discharge_Channel",     "Discharge Channel",        "channel",   "#eef0ea", "channel"),
    ("Anode_Gas_Distributor", "Anode",                    "anode",     "#3a3f48", "anode"),
    ("Propellant_Feed",       "Propellant Feed",          "structure", "#d5d8e4", "feed"),
    ("Cathode_Neutralizer",   "Cathode-Neutralizer",      "cathode",   "#d8b62e", "cathode"),
    ("Neutralizer_Housing",   "Neutralizer Housing",      "structure", "#d5d8e4", "neut_house"),
]

# Meshing deflection (linear, angular) per role. The coils are swept circles of
# radius 1.04 mm and the anode's gas holes are radius 1.5 mm; at the 0.4 used for
# the big bodies both tessellate to ~7 segments and read as faceted prisms, so
# they get a finer pass. The ANGULAR term is what actually governs those two - it
# is also what sets how finely the helical sweep is subdivided along its path,
# which is where the coils' triangle count comes from, so it is kept only as fine
# as it needs to be.
#
# 0.4 rad is the coil setting: ~16 segments around the conductor and ~26 steps
# per turn along the helix. It is finer than a thin wire would justify because
# turn count moves inversely with WIRE_R (see build_thruster.py) - a fatter
# conductor means fewer turns, which buys back the triangles the extra roundness
# spends. Going finer still is what gets expensive: at 0.25 rad the five helices
# alone tessellate to ~14 MB of embedded mesh.
DEFLECTION = {"coil": (0.2, 0.4), "anode": (0.3, 0.3)}
DEFAULT_DEFLECTION = (0.4, 0.4)


def b64(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode("ascii")


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "hall_thruster_model.json"
    comps = []
    allmin = np.array([1e30] * 3)
    allmax = np.array([-1e30] * 3)

    for name, label, role, color, attr in COMPONENTS:
        solid = getattr(B, attr)
        lin, ang = DEFLECTION.get(role, DEFAULT_DEFLECTION)
        P, N, I = mesher.mesh_shape(solid, lin=lin, ang=ang)
        # CAD (cx, cy, cz) -> viewer (cz, cy, -cx), for positions AND normals
        Pv = np.column_stack([P[:, 2], P[:, 1], -P[:, 0]]).astype("<f4")
        Nv = np.column_stack([N[:, 2], N[:, 1], -N[:, 0]]).astype("<f4")
        allmin = np.minimum(allmin, Pv.min(0))
        allmax = np.maximum(allmax, Pv.max(0))
        comps.append(dict(name=name, label=label, role=role, color=color,
                          pos=b64(Pv), nrm=b64(Nv), idx=b64(I.astype("<u4"))))
        print(f"  {name:24s} verts={len(Pv):6d} tris={len(I)//3:6d}", file=sys.stderr)

    bounds = [allmin.tolist(), allmax.tolist()]
    center = ((allmin + allmax) / 2).tolist()
    size = (allmax - allmin).tolist()
    print(f"  bounds min={[round(v,1) for v in bounds[0]]} "
          f"max={[round(v,1) for v in bounds[1]]}", file=sys.stderr)

    doc = dict(units="mm", bounds=bounds, center=center, size=size, components=comps)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, separators=(", ", ": "))
    print("WROTE", out, file=sys.stderr)


if __name__ == "__main__":
    main()
