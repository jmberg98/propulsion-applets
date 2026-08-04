#!/usr/bin/env python3
"""build_model.py — regenerate the applet's gridded_ion_model.json from parametric CAD.

Re-establishes the STEP->JSON tessellation pipeline that was lost. Emits the SAME 11
named components (name/label/role/color) the applet's 5000-line code depends on, so the
viewer is untouched. CAD axis = +Z; viewer/raw mapping is (vx,vy,vz) = (cz,cy,cx), applied
to positions AND normals (this is the rotation the original tessellator used). center/size/
bounds are kept EXACTLY at the frozen values the overlays (plume orifice, callouts, field
lines) are pinned to.

Usage: python build_model.py [out.json]
"""
import sys, json, base64, math
import numpy as np
import mesher
import build_thruster as B
from build123d import Cylinder, Cone, Box, Pos, Compound

# ---- geometry, split into the 11 applet components -----------------------
cyl, tube, ring, perforate = B.cyl, B.tube, B.ring, B.perforate

def build_solids(fix=False):
    R_HOUSE, R_CHAMBER_OUT, R_GRID = B.R_HOUSE, B.R_CHAMBER_OUT, B.R_GRID
    Z_REAR_INNER, Z_REAR_BACK, L = B.Z_REAR_INNER, B.Z_REAR_BACK, B.L_CHAMBER
    R_CATH, INJ_Y, INJ_R, INJ_CLEAR = B.R_CATH, B.INJ_Y, B.INJ_R, B.INJ_CLEAR
    Z_SPLIT = -20.0   # rear plate is split shell(-20..-12) | back-wall(-32..-20)
    front_ring_z1 = B.Z_SCREEN0 + B.SCREEN_T + B.GRID_GAP + B.ACCEL_T + 2

    # ---- discharge chamber (anode) ----
    chamber = tube(R_CHAMBER_OUT, B.R_PLASMA, Z_REAR_INNER, L)
    rear_wall = cyl(R_CHAMBER_OUT, Z_REAR_INNER, Z_REAR_INNER + 3) - cyl(R_CATH + 2, Z_REAR_INNER, Z_REAR_INNER + 3)
    rear_wall -= Pos(0, INJ_Y, Z_REAR_INNER + 1.5) * Cylinder(radius=INJ_R + 1, height=6)
    chamber += rear_wall

    # ---- outer shell (rear plate FRONT slab -20..-12) ----
    # The rear plate carries a two-diameter feed-through for each channel: a snug close-fit
    # bore through the BACK slab (Back_Wall_Extension) that guides the tube, opening into a
    # wider RECESSED SOCKET (counterbore) in the chamber-side (shell) slab. The step between
    # them reads as a machined seat, so each channel is unmistakably drilled THROUGH the end
    # face rather than butting against it.  (fix=False keeps the old single-diameter bore.)
    CB_CATH = 16.0 if fix else (R_CATH + 4)     # chamber-side socket radius, cathode
    CB_INJ  = 10.0 if fix else INJ_CLEAR        # chamber-side socket radius, injector
    shell  = tube(R_HOUSE, R_CHAMBER_OUT, Z_REAR_INNER, L)
    shell += tube(R_HOUSE, R_GRID, L, front_ring_z1)
    shell += tube(R_HOUSE, CB_CATH, Z_SPLIT, Z_REAR_INNER)
    shell -= Pos(0, INJ_Y, (Z_SPLIT + Z_REAR_INNER) / 2) * Cylinder(radius=CB_INJ, height=(Z_REAR_INNER - Z_SPLIT) + 6)

    # ---- back-wall extension (rear plate BACK slab -32..-20) — snug guide bores ----
    backwall = tube(R_HOUSE, R_CATH + 4, Z_REAR_BACK, Z_SPLIT)
    backwall -= Pos(0, INJ_Y, (Z_REAR_BACK + Z_SPLIT) / 2) * Cylinder(radius=INJ_CLEAR, height=(Z_SPLIT - Z_REAR_BACK) + 6)

    # ---- neutralizer housing (mount block + keeper enclosure) ----
    mount = Pos(0, 128.5, 183) * Box(18, 10, 30)
    enc_outer = Pos(0, 140, (162 + 207) / 2) * Box(24, 24, 207 - 162)
    enc_cav   = Pos(0, 140, (165 + 204) / 2) * Box(18, 18, 204 - 165)
    enclosure = enc_outer - enc_cav
    enclosure -= Pos(0, 140, 205) * Cylinder(radius=8, height=10)
    neut_house = mount + enclosure

    # ---- ion-optics grids ----
    z_s0, z_s1 = B.Z_SCREEN0, B.Z_SCREEN0 + B.SCREEN_T
    z_a0, z_a1 = z_s1 + B.GRID_GAP, z_s1 + B.GRID_GAP + B.ACCEL_T
    screen = perforate(cyl(R_GRID, z_s0, z_s1), z_s0, z_s1, B.SCREEN_HOLE_R)
    accel  = perforate(cyl(R_GRID, z_a0, z_a1), z_a0, z_a1, B.ACCEL_HOLE_R)

    # ---- magnet rings ----
    mag_side = ring(18) + ring(98) + ring(183)
    if fix:
        # Back-wall magnet as TWO discrete blocks (top & bottom bands) instead of a full
        # annulus. The annulus' HOLE coincided with the cathode/injector bores, and its
        # stencil cap bled a dark block straight across the bore openings (glaring during the
        # 3D<->section morph, where it renders last and paints over the rear-plate cut face —
        # the "ring/anomalous geometry"). Two compact blocks have no hole, so each caps as a
        # clean box at its band (matching the two back-wall POLE_MARKERS at y=39.5 / -62.5) and
        # nothing paints across the axis. Real ring-cusp thrusters carry discrete back-plate
        # magnets anyway. Bands: r 44..58 -> CAD y +-(44..58), centered y=+-51, at z=-21+-7.
        mag_back = Pos(0, 51, -21) * Box(56, 14, 14) + Pos(0, -51, -21) * Box(56, 14, 14)
    else:
        mag_back = ring(-21, ro=58, ri=44)

    # ---- feed-throughs ----
    # The channels are bored deep into the discharge chamber so a clear open length reads
    # INSIDE the plasma cavity, past the rear wall (chamber rear wall at z=-12). fix=True bakes
    # the reach the applet used to add at runtime; the tubes stay hollow (open bore).
    CATH_TIP = 34.0 if fix else (45 + B.FEED_SHIFT)   # 34 -> ~46mm into the chamber
    INJ_TIP  = 26.0 if fix else -5.0                  # 26 -> ~38mm into the chamber
    cathode = tube(R_CATH, B.R_CATH_BORE, -70 + B.FEED_SHIFT, CATH_TIP)
    inj = Pos(0, INJ_Y, 0) * tube(INJ_R, INJ_R - 2, -72, INJ_TIP)

    # ---- neutralizer cathode ----
    NCY = 140.0
    def zc(r, z0, z1, y=NCY):
        return Pos(0, y, (z0 + z1) / 2) * Cylinder(radius=r, height=z1 - z0)
    neut  = zc(9, 165, 202)
    neut += Pos(0, NCY, 206) * Cone(bottom_radius=9, top_radius=5, height=8)
    neut += zc(5, 210, 224) - zc(2.4, 214, 226)

    # component order MUST match the current JSON
    return [
        ("Outer_Shell_Housing",        "Outer Housing",             "structure",   "#d5d8e4", shell),
        ("Anode_Discharge_Chamber",    "Discharge Chamber (Anode)", "anode",       "#d5d8e4", chamber),
        ("Screen_Grid_Positive",       "Screen Grid  (+)",          "grid-pos",    "#4c515a", screen),
        ("Accel_Grid_Negative",        "Accel Grid  (−)",      "grid-neg",    "#2f333a", accel),
        ("Magnet_Ring_Cathode",        "Magnet Rings",              "magnet",      "#616670", mag_side),
        ("Hollow_Cathode",             "Hollow Cathode",            "cathode",     "#d8b62e", cathode),
        ("Propellant_Injector",        "Propellant Injector",       "feed",        "#d5d8e4", inj),
        ("Neutralizer_Hollow_Cathode", "Neutralizer Cathode",       "neutralizer", "#d8b62e", neut),
        ("Neutralizer_Housing",        "Neutralizer Housing",       "structure",   "#d5d8e4", neut_house),
        ("Back_Wall_Extension",        "Back Wall",                 "structure",   "#d5d8e4", backwall),
        ("Magnet_Ring_BackWall",       "Magnet Rings",              "magnet",      "#616670", mag_back),
    ]

# frozen framing constants (overlays are pinned to these — DO NOT recompute)
CENTER = [64.5, 11.518184661865234, 0.0]
SIZE   = [319.0, 274.95804595947266, 252.0]
BOUNDS = [[-95.0, -125.9608383178711, -126.0], [224.0, 148.99720764160156, 126.0]]

def b64(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode("ascii")

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "model_regen.json"
    fix = "--nofix" not in sys.argv   # the fixed geometry IS the desired state; --nofix = old parity
    comps = []
    allmin = np.array([1e9]*3); allmax = np.array([-1e9]*3)
    for name, label, role, color, solid in build_solids(fix=fix):
        # Grids get a MUCH finer deflection than the bodies: at 0.5 each aperture bore
        # tessellates to 32 segments and reads visibly polygonal in the cross-section.
        # 0.1/0.1 gives 126 segments per bore — the density the shipped model uses.
        lin = 0.1 if role.startswith("grid") else 0.4
        P, N, I = mesher.mesh_shape(solid, lin=lin, ang=(0.1 if role.startswith("grid") else 0.4))
        # CAD (cx,cy,cz) -> viewer (cz,cy,cx) for positions AND normals
        Pv = np.column_stack([P[:, 2], P[:, 1], P[:, 0]]).astype("<f4")
        Nv = np.column_stack([N[:, 2], N[:, 1], N[:, 0]]).astype("<f4")
        allmin = np.minimum(allmin, Pv.min(0)); allmax = np.maximum(allmax, Pv.max(0))
        comps.append(dict(name=name, label=label, role=role, color=color,
                          pos=b64(Pv), nrm=b64(Nv), idx=b64(I.astype("<u4"))))
        print(f"  {name:26s} verts={len(Pv):6d} tris={len(I)//3:6d} "
              f"rawX[{Pv[:,0].min():7.1f},{Pv[:,0].max():7.1f}]", file=sys.stderr)
    print(f"  REGEN raw bounds min={allmin.round(2).tolist()} max={allmax.round(2).tolist()}", file=sys.stderr)
    print(f"  frozen bounds       {BOUNDS[0]} {BOUNDS[1]}", file=sys.stderr)
    doc = dict(units="mm", bounds=BOUNDS, center=CENTER, size=SIZE, components=comps)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, separators=(", ", ": "))
    print("WROTE", out, file=sys.stderr)

if __name__ == "__main__":
    main()
