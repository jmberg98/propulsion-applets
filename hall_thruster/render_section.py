#!/usr/bin/env python3
"""render_section.py - true 2D CAD sections of the Hall thruster, for eyeballing
the interior the way gridded_ion's section renders were used.

matplotlib's 3D Poly3DCollection cannot depth-sort hollow solids, so an iso view
is useless for judging interior geometry. Instead this cuts each solid with a
half-space, meshes the RESULT, and fills every triangle that lies exactly on the
cut plane. That gives a genuine filled cross-section with no sorting involved.

  python render_section.py section_x.png x   # cut on CAD x = 0 (plots z vs y)
                                             #   shows the cathode, the feed line
                                             #   and the +/-Y return legs + coils
  python render_section.py section_y.png y   # cut on CAD y = 0 (plots z vs x)
  python render_section.py anode.png x 10,60,25,60      # ... zoomed to z,vert window
"""
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from build123d import Box, Pos

import mesher
import build_thruster as B

BIG = 2000.0
EPS = 1e-6


def cut_triangles(solid, axis):
    """Triangles of `solid` lying on the plane axis = 0, after removing axis > 0."""
    half = {"x": Pos(-BIG / 2, 0, 0), "y": Pos(0, -BIG / 2, 0)}[axis] * Box(BIG, BIG, BIG)
    part = solid & half
    # A component wholly on the discarded side comes back as an EMPTY Shape, not
    # None. Its `.wrapped` property ASSERTS rather than returning None, so test the
    # backing attribute directly instead of touching the property.
    if part is None or getattr(part, "_wrapped", None) is None:
        return np.empty((0, 3, 3))
    P, _, I = mesher.mesh_shape(part, lin=0.25, ang=0.25)
    tri = P[I].reshape(-1, 3, 3)
    k = {"x": 0, "y": 1}[axis]
    on_plane = np.all(np.abs(tri[:, :, k]) < EPS, axis=1)
    return tri[on_plane]


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "section_x.png"
    axis = sys.argv[2] if len(sys.argv) > 2 else "x"
    # horizontal = CAD z (the thrust axis); vertical = the in-plane radial axis
    vert = {"x": 1, "y": 0}[axis]

    fig, ax = plt.subplots(figsize=(13, 9), dpi=110)
    fig.patch.set_facecolor("#101215")
    ax.set_facecolor("#101215")

    for solid, name, color in B.parts:
        tri = cut_triangles(solid, axis)
        if not len(tri):
            print(f"  {name:24s} (nothing on the cut plane)")
            continue
        polys = np.stack([tri[:, :, 2], tri[:, :, vert]], axis=-1)   # (n, 3, 2)
        ax.add_collection(PolyCollection(polys, facecolors=color, edgecolors=color,
                                         linewidths=0.25))
        print(f"  {name:24s} {len(tri):6d} cut triangles")

    ax.set_aspect("equal")
    ax.autoscale_view()
    if len(sys.argv) > 3:
        z0, z1, v0, v1 = (float(v) for v in sys.argv[3].split(","))
        ax.set_xlim(z0, z1)
        ax.set_ylim(v0, v1)
    ax.set_xlabel("z  (thrust axis, exhaust to the right)  [mm]", color="#9aa0aa")
    ax.set_ylabel(f"{'y' if axis == 'x' else 'x'}  [mm]", color="#9aa0aa")
    ax.tick_params(colors="#9aa0aa")
    for s in ax.spines.values():
        s.set_color("#2a2e34")
    ax.set_title(f"Hall thruster - section on CAD {axis} = 0", color="#d6d6d6")
    ax.grid(True, color="#22262c", linewidth=0.5)
    fig.tight_layout()
    fig.savefig(out, facecolor=fig.get_facecolor())
    print("WROTE", out)


if __name__ == "__main__":
    main()
