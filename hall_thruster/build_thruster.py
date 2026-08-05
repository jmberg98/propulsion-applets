#!/usr/bin/env python3
"""
build_thruster.py - parametric SPT-type Hall thruster, built the same way as
gridded_ion/build_thruster.py (build123d -> colored STEP -> tessellated JSON).

Reference image: "Hall thruster concept", Princeton Plasma Physics Laboratory,
Hall Thruster Experiment (HTX), https://htx.pppl.gov/thrusters.html - used as a
SHAPE GUIDE only. Every dimension below is illustrative and was chosen to read
well in the applet's cutaway; none of it is taken from a real thruster drawing.

Layout: axis = +Z, exhaust downstream at high Z (same convention as the
gridded-ion model). The parts the reference image labels map to:

  "Magnetic core"          -> Magnetic_Core_Outer + Magnetic_Core_Inner
  "Magnetic coils"         -> Coil_Outer (4 legs) + Coil_Inner (center stem)
  "Anode / gas distributor"-> Anode_Gas_Distributor + Propellant_Feed
  "Cathode-neutralizer"    -> Cathode_Neutralizer + Cathode_Mount

The annular ceramic Discharge_Channel between the poles is where the crossed
E (axial, from anode to exit) and B (radial, across the pole gap) live, so the
electron Hall current I_H closes azimuthally around the annulus.

Exports hall_thruster_3D.STEP with per-part colors.
"""
import sys
import math
from build123d import (
    Cylinder, Cone, Box, Pos, Rot, Compound, Color, Helix, Circle, Plane,
    sweep, export_step,
)

# ---- discharge channel (mm) ---------------------------------------------
R_CH_IN    = 35.0    # plasma-side inner radius of the annular channel
R_CH_OUT   = 50.0    # plasma-side outer radius            -> 15 mm channel width
CER_T      = 5.0     # ceramic (BN) wall thickness
R_CER_IN   = R_CH_IN  - CER_T     # 30 - inner wall inner radius
R_CER_OUT  = R_CH_OUT + CER_T     # 55 - outer wall outer radius
Z_CH0      = 20.0    # upstream end of the ceramic, seated on the back plate
Z_EXIT     = 112.0   # channel exit plane (recessed behind the pole faces)

# ---- magnetic circuit ----------------------------------------------------
R_YOKE     = 100.0   # outer radius of the back plate / front pole plate
Z_BACK0    = 0.0     # rear face of the magnetic back plate
Z_BACK1    = 20.0    # front face of the back plate
Z_POLE0    = 104.0   # rear face of the front pole plates
Z_POLE1    = 122.0   # front face of the front pole plates (thruster front face)

R_STEM     = 12.0    # inner magnetic core stem radius
R_POLE_IN  = 29.0    # inner front pole radius   (1 mm clear of the ceramic ID)
R_POLE_OUT = 57.0    # outer front pole bore     (2 mm clear of the ceramic OD)

N_LEG      = 4       # outer return legs, at 0/90/180/270 deg
R_LEG      = 77.0    # leg centreline radius
R_LEG_ROD  = 9.0     # leg radius

# ---- outer shell --------------------------------------------------------
# A structural skin over the whole body, bored to sit flush on the magnetic core
# OD, so the return legs and their coils are enclosed the way they are on a real
# thruster. It is its own component, so hiding it (or cutting away) exposes the
# magnetic circuit underneath.
R_SHELL_IN  = R_YOKE     # bore sits exactly on the core OD - no double-modeled wall
R_SHELL_OUT = 106.0

N_FIN      = 32      # radial cooling ribs around the front rim (the "gear tooth" edge)
FIN_IN     = 103.0   # ribs bite into the shell wall so they fuse to it
FIN_OUT    = 112.0   # rib tip radius - the outermost thing on the thruster
FIN_W      = 4.0     # rib tangential thickness

# ---- coils ---------------------------------------------------------------
# Wound directly on the stem and on each return leg. Only ~45 mm of radial room
# exists between the ceramic OD (55) and the yoke (100), so the outer coil pack
# is sized to sit inside it: pack spans r = 58.5 .. 95.5, clear of both. The
# inner coil is wound wider than its stem so it fills the bore under the channel.
WIRE_R     = 4.0     # conductor radius
COIL_R_OUT = 14.5    # helix radius about each return leg -> pack r = 10.5 .. 18.5
COIL_R_IN  = 18.0    # helix radius about the center stem -> pack r = 14 .. 22
COIL_PITCH = 9.5     # axial pitch -> 7 turns over the 66 mm winding length
COIL_Z0    = 28.0
COIL_Z1    = 94.0

# ---- anode / gas distributor --------------------------------------------
R_AN_IN    = 36.0    # anode ring bore   (1 mm clear of the channel inner wall)
R_AN_OUT   = 49.0    # anode ring OD     (1 mm clear of the channel outer wall)
Z_AN0      = 26.0
Z_AN1      = 48.0    # anode downstream face -> 64 mm of channel to the exit
PLENUM_T   = 3.0     # anode wall thickness around the gas plenum
N_GAS_HOLE = 24
R_GAS_HOLE = 1.5
R_FEED     = 42.5    # propellant feed / gas-hole circle radius (channel midline)
FEED_R     = 4.0     # feed tube outer radius
FEED_BORE  = 2.0
Z_FEED0    = -18.0   # feed tube pokes out the back of the thruster

# ---- cathode-neutralizer -------------------------------------------------
# Mounted outboard on the front pole plate and canted in toward the axis, so its
# keeper orifice sits just downstream of the channel exit - the geometry the
# reference image shows spraying electrons across the plume.
CATH_TILT  = 25.0                       # degrees, toward the axis
CATH_BASE  = (0.0, 149.0, 78.0)         # where the cathode's local z = 0 lands
                                        # (set so the body stays clear of the
                                        # FIN_OUT rim all the way to z = Z_POLE1)
CATH_R     = 13.0                       # body radius
CATH_BODY  = 48.0                       # body length (local z)
CATH_SNOUT = 7.0                        # snout radius
CATH_LEN   = 72.0                       # overall length (local z)

# Colors follow the gridded-ion applet's convention: one light gray for every
# structural body, a dark tone for the magnetic circuit, and gold reserved for
# hollow cathodes. Each tone keys to what the piece is actually made of, which is
# what the viewer's Component Materials legend reads off.
# The gridded-ion applet spends its DARKEST tone on the functional electrodes (the
# two grids) and keeps the bodies light, so the piece the panel names is the piece
# that reads on the hardware. Applied here that puts the dark on the ANODE, not on
# the magnetic core: the core is a soft-iron flux path, i.e. structure, and painting
# that whole mass dark buried the anode inside it.
COL = dict(
    shell      = "#d5d8e4",   # aluminum: outer shell, cathode mount, feed line
    core_outer = "#7a808b",   # soft iron: back plate, return legs, outer pole
    core_inner = "#8a9099",   # soft iron, a shade up so the inner circuit reads
    coil       = "#b9773a",   # copper windings
    channel    = "#eef0ea",   # boron nitride: the chalk-white discharge channel
    anode      = "#3a3f48",   # the electrode — darkest thing in the model
    cathode    = "#d8b62e",   # hollow cathode (same gold the gridded-ion applet uses)
)


def hexcol(h):
    h = h.lstrip("#")
    return Color(int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255)


def cyl(r, z0, z1, x=0.0, y=0.0):
    """Solid cylinder spanning z0..z1, parallel to Z, centered on (x, y)."""
    return Pos(x, y, (z0 + z1) / 2) * Cylinder(radius=r, height=(z1 - z0))


def tube(ro, ri, z0, z1, x=0.0, y=0.0):
    return cyl(ro, z0, z1, x, y) - cyl(ri, z0, z1, x, y)


def union(*shapes):
    """One BOPAlgo fuse over the whole list - much faster than chained `+`."""
    shapes = [s for s in shapes if s is not None]
    return shapes[0] if len(shapes) == 1 else shapes[0].fuse(*shapes[1:]).clean()


def helix_coil(z0, z1, hr, x=0.0, y=0.0, wr=WIRE_R, pitch=COIL_PITCH):
    """A swept-circle helix wound about the axis through (x, y).

    The section must sit at the helix start point, normal to the path, or OCC
    sweeps a skewed pipe. The tangent at the start (hr, 0, 0) is
    (0, 2*pi*hr, pitch) normalized.
    """
    path = Helix(pitch=pitch, height=(z1 - z0), radius=hr)
    tx, ty, tz = 0.0, 2 * math.pi * hr, pitch
    n = math.hypot(ty, tz)
    section = Plane(origin=(hr, 0, 0), z_dir=(tx, ty / n, tz / n)) * Circle(wr)
    return Pos(x, y, z0) * sweep(section, path=path, is_frenet=True)


# ---- magnetic core, outer branch ----------------------------------------
# Back plate + four return legs + the front pole annulus, all inside the shell.
legs = [Rot(Z=k * 360.0 / N_LEG) * cyl(R_LEG_ROD, Z_BACK1, Z_POLE0, x=R_LEG)
        for k in range(N_LEG)]

back_plate = cyl(R_YOKE, Z_BACK0, Z_BACK1)
# clearance bore for the propellant feed line through the back plate
back_plate -= cyl(FEED_R + 2.0, Z_BACK0 - 2, Z_BACK1 + 2, y=R_FEED)

core_outer = union(back_plate, *legs,
                   tube(R_YOKE, R_POLE_OUT, Z_POLE0, Z_POLE1))

# ---- outer shell --------------------------------------------------------
# Full-length skin plus a finned collar around the front rim. The ribs start
# INSIDE the shell wall (FIN_IN < R_SHELL_OUT) so they fuse into it rather than
# hanging off it as 32 separate tangent blocks.
fins = [Rot(Z=k * 360.0 / N_FIN)
        * (Pos((FIN_IN + FIN_OUT) / 2, 0, (Z_POLE0 + Z_POLE1) / 2)
           * Box(FIN_OUT - FIN_IN, FIN_W, Z_POLE1 - Z_POLE0))
        for k in range(N_FIN)]
shell = union(tube(R_SHELL_OUT, R_SHELL_IN, Z_BACK0, Z_POLE1), *fins)

# ---- magnetic core, inner branch ----------------------------------------
core_inner = union(cyl(R_STEM, Z_BACK1, Z_POLE0),
                   cyl(R_POLE_IN, Z_POLE0, Z_POLE1))

# ---- coils ---------------------------------------------------------------
coil_inner = helix_coil(COIL_Z0, COIL_Z1, COIL_R_IN)
coil_outer = union(*[Rot(Z=k * 360.0 / N_LEG)
                     * helix_coil(COIL_Z0, COIL_Z1, COIL_R_OUT, x=R_LEG)
                     for k in range(N_LEG)])

# ---- ceramic discharge channel ------------------------------------------
channel = union(tube(R_CH_IN, R_CER_IN,  Z_CH0, Z_EXIT),    # inner wall
                tube(R_CER_OUT, R_CH_OUT, Z_CH0, Z_EXIT))   # outer wall

# ---- anode / gas distributor --------------------------------------------
# Hollow ring seated at the upstream end of the annulus: gas enters from the feed
# line, fills the plenum, and meters out through a ring of holes in the
# downstream face, so the neutral flow is uniform in azimuth.
anode = tube(R_AN_OUT, R_AN_IN, Z_AN0, Z_AN1)
anode -= tube(R_AN_OUT - PLENUM_T, R_AN_IN + PLENUM_T, Z_AN0 + PLENUM_T, Z_AN1 - PLENUM_T)
gas_holes = union(*[
    Rot(Z=k * 360.0 / N_GAS_HOLE) * cyl(R_GAS_HOLE, Z_AN1 - PLENUM_T - 1, Z_AN1 + 2, x=R_FEED)
    for k in range(N_GAS_HOLE)])
anode -= gas_holes
# open the feed bore through the anode's upstream wall - the tube is a separate
# solid that merely butts into it, so without this the gas path dead-ends there
anode -= cyl(FEED_BORE, Z_AN0 - 2, Z_AN0 + PLENUM_T + 1, y=R_FEED)

feed = tube(FEED_R, FEED_BORE, Z_FEED0, Z_AN0 + PLENUM_T + 2, y=R_FEED)

# ---- cathode-neutralizer -------------------------------------------------
# Built along local +Z, then canted toward the axis and translated onto the
# front pole plate.
_cath = union(cyl(CATH_R, 0, CATH_BODY),
              Pos(0, 0, CATH_BODY + 5) * Cone(bottom_radius=CATH_R,
                                              top_radius=CATH_SNOUT, height=10),
              cyl(CATH_SNOUT, CATH_BODY + 10, CATH_LEN))
_cath -= cyl(3.0, CATH_BODY + 14, CATH_LEN + 2)          # keeper orifice / bore
cathode = Pos(*CATH_BASE) * Rot(X=CATH_TILT) * _cath

# mount bracket tying the cathode body to the shell's finned front rim
mount = Pos(0, 124, 112) * Box(18, 46, 16)                # y 101..147, z 104..120
mount -= cathode                                          # clean saddle around the body

# ---- assemble, color, export --------------------------------------------
parts = [
    (shell,      "Outer_Shell",           COL["shell"]),
    (core_outer, "Magnetic_Core_Outer",   COL["core_outer"]),
    (core_inner, "Magnetic_Core_Inner",   COL["core_inner"]),
    (coil_outer, "Coil_Outer",            COL["coil"]),
    (coil_inner, "Coil_Inner",            COL["coil"]),
    (channel,    "Discharge_Channel",     COL["channel"]),
    (anode,      "Anode_Gas_Distributor", COL["anode"]),
    (feed,       "Propellant_Feed",       COL["shell"]),
    (cathode,    "Cathode_Neutralizer",   COL["cathode"]),
    (mount,      "Cathode_Mount",         COL["shell"]),
]

solids = []
for shp, name, c in parts:
    shp.label = name
    shp.color = hexcol(c)
    solids.append(shp)

if __name__ == "__main__":
    asm = Compound(children=solids)
    asm.label = "hall_thruster"
    out = sys.argv[1] if len(sys.argv) > 1 else "hall_thruster_3D.STEP"
    export_step(asm, out)
    print("WROTE", out)
    for shp, name, c in parts:
        bb = shp.bounding_box()
        r = max(abs(bb.min.X), abs(bb.max.X), abs(bb.min.Y), abs(bb.max.Y))
        print(f"  {name:22s} z[{bb.min.Z:7.1f},{bb.max.Z:7.1f}]  r<= {r:6.1f}")
