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
  "Cathode-neutralizer"    -> Cathode_Neutralizer + Neutralizer_Housing

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
Z_CH0      = 20.0   # upstream end of the ceramic, seated on the back plate
Z_EXIT     = 112.0  # channel exit plane (recessed behind the pole faces)

# ---- magnetic circuit ----------------------------------------------------
R_YOKE     = 100.0      # outer radius of the back plate / front pole plate
Z_BACK0    = 0.0    # rear face of the magnetic back plate
Z_BACK1    = 20.0   # front face of the back plate
Z_POLE0    = 104.0  # rear face of the front pole plates
Z_POLE1    = 122.0  # front face of the front pole plates (thruster front face)

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

# ---- coils ---------------------------------------------------------------
# Wound directly on the stem and on each return leg, as magnet wire: a 2.08 mm
# conductor laid at a 2.47 mm pitch, so consecutive turns very nearly touch and
# the winding reads as a ribbed copper sleeve rather than a handful of fat rings.
# Over the 66 mm axial span that is ~27 turns per helix.
#
# WIRE_R is the one dial here; everything else follows from it, because a single
# layer cannot be wound tighter than the wire is wide - do that and consecutive
# turns interpenetrate and the swept solid self-intersects. So the turn count
# moves INVERSELY with WIRE_R: this carried ~69 turns at 0.4 mm and ~35 at
# 0.8 mm. Getting more turns AND a fatter conductor needs a second layer, not a
# tighter pitch.
#
# Likewise the helix radii: a single layer is only as deep as the wire is wide,
# so they ride COIL_GAP clear of the iron they are wound on (leg r = 9, stem
# r = 12) rather than standing off it. The packs land at r = 9.6 .. 11.68 about
# each leg and r = 12.6 .. 14.68 about the stem, both still well clear of the
# ceramic OD (55) and the yoke (100).
WIRE_R     = 1.04    # conductor radius (2.08 mm magnet wire)
COIL_GAP   = 0.6     # clearance between the winding and the iron it sits on
TURN_GAP   = 0.39    # air between consecutive turns
COIL_PITCH = 2 * WIRE_R + TURN_GAP        # 2.47 - the tightest a single layer winds
COIL_R_OUT = R_LEG_ROD + COIL_GAP + WIRE_R  # 10.64, helix radius about each return leg
COIL_R_IN  = R_STEM   + COIL_GAP + WIRE_R   # 13.64, helix radius about the center stem
COIL_Z0    = 28.0
COIL_Z1    = 94.0

# ---- anode / gas distributor --------------------------------------------
R_AN_IN    = 36.0    # anode ring bore   (1 mm clear of the channel inner wall)
R_AN_OUT   = 49.0    # anode ring OD     (1 mm clear of the channel outer wall)
Z_AN0      = 26.0
Z_AN1      = 48.0   # anode downstream face
PLENUM_T   = 3.0     # anode wall thickness around the gas plenum
N_GAS_HOLE = 24
R_GAS_HOLE = 1.5
R_FEED     = 42.5    # propellant feed / gas-hole circle radius (channel midline)
FEED_R     = 4.0     # feed tube outer radius
FEED_BORE  = 2.0
Z_FEED0    = -18.0   # feed tubes poke out the back of the thruster

# TWO injector lines, diametrically opposed. A single feed into one side of an
# annular plenum leaves a pressure gradient around the ring, so the neutral flow
# out of the distributor holes is not azimuthally uniform; opposed feeds halve
# the path from either inlet to the farthest holes. Both sit in the CAD x = 0
# plane, which is the viewer's cut plane, so the section shows both.
INJ_ANGLES = (90.0, 270.0)   # azimuths, degrees

# ---- cathode-neutralizer -------------------------------------------------
# Sized and housed like the gridded-ion thruster's neutralizer: a stepped Ø18
# hollow cathode inside a boxed keeper enclosure with a bored front plate, on a
# block that ties it to the thruster body. Axis-parallel, like that one. The
# dimensions are gridded_ion/build_thruster.py's, shifted by NEUT_DZ.
NCY        = 124.0   # cathode centreline radius (clears the shell + enclosure wall)
NEUT_DZ    = -89.0   # axial shift from the gridded-ion layout onto this one
NEUT_BODY  = (165.0 + NEUT_DZ, 202.0 + NEUT_DZ)
NEUT_CONE  = 206.0 + NEUT_DZ
NEUT_SNOUT = (210.0 + NEUT_DZ, 224.0 + NEUT_DZ)
NEUT_BORE  = (214.0 + NEUT_DZ, 226.0 + NEUT_DZ)
NEUT_R     = 9.0     # body radius (Ø18)
NEUT_TIP_R = 5.0     # snout radius
NEUT_ORF_R = 2.4     # keeper orifice radius
ENC_OUT    = (162.0 + NEUT_DZ, 207.0 + NEUT_DZ)
ENC_CAV    = (165.0 + NEUT_DZ, 204.0 + NEUT_DZ)
ENC_W      = 24.0    # enclosure outside width/height
ENC_CAV_W  = 18.0    # cavity width/height
ENC_BORE_R = 8.0     # front-plate bore = the cone's radius where it passes through

# Colors follow the gridded-ion applet's convention: one light gray for every
# structural body, and gold reserved for hollow cathodes. That applet spends its
# DARKEST tone on the functional electrodes (the two grids) and keeps the bodies
# light, so the piece the panel names is the piece that reads on the hardware.
# Applied here that puts the dark on the ANODE, not on the magnetic core: the
# core is a soft-iron flux path, i.e. structure, and painting that whole mass
# dark buried the anode inside it.
COL = dict(
    shell      = "#d5d8e4",   # aluminum: outer shell, neutralizer housing, feed lines
    core_outer = "#7a808b",   # soft iron: back plate, return legs, outer pole
    core_inner = "#8a9099",   # soft iron, a shade up so the inner circuit reads
    coil       = "#b9773a",   # copper windings
    channel    = "#eef0ea",   # boron nitride: the chalk-white discharge channel
    anode      = "#3a3f48",   # the electrode - darkest thing in the model
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
# clearance bore through the back plate for each propellant feed line
for _a in INJ_ANGLES:
    back_plate -= Rot(Z=_a) * cyl(FEED_R + 2.0, Z_BACK0 - 2, Z_BACK1 + 2, x=R_FEED)

core_outer = union(back_plate, *legs,
                   tube(R_YOKE, R_POLE_OUT, Z_POLE0, Z_POLE1))

# ---- outer shell --------------------------------------------------------
shell = tube(R_SHELL_OUT, R_SHELL_IN, Z_BACK0, Z_POLE1)

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
# lines, fills the plenum, and meters out through a ring of holes in the
# downstream face, so the neutral flow is uniform in azimuth.
anode = tube(R_AN_OUT, R_AN_IN, Z_AN0, Z_AN1)
anode -= tube(R_AN_OUT - PLENUM_T, R_AN_IN + PLENUM_T, Z_AN0 + PLENUM_T, Z_AN1 - PLENUM_T)
gas_holes = union(*[
    Rot(Z=k * 360.0 / N_GAS_HOLE) * cyl(R_GAS_HOLE, Z_AN1 - PLENUM_T - 1, Z_AN1 + 2, x=R_FEED)
    for k in range(N_GAS_HOLE)])
anode -= gas_holes
# open a feed bore through the anode's upstream wall for each injector - the tubes
# are separate solids that merely butt into it, so without this the gas path
# dead-ends against solid material
for _a in INJ_ANGLES:
    anode -= Rot(Z=_a) * cyl(FEED_BORE, Z_AN0 - 2, Z_AN0 + PLENUM_T + 1, x=R_FEED)

feed = union(*[Rot(Z=_a) * tube(FEED_R, FEED_BORE, Z_FEED0, Z_AN0 + PLENUM_T + 2, x=R_FEED)
               for _a in INJ_ANGLES])

# ---- cathode-neutralizer -------------------------------------------------
def _nz(r, z0, z1):
    return cyl(r, z0, z1, y=NCY)

cathode = union(_nz(NEUT_R, *NEUT_BODY),
                Pos(0, NCY, NEUT_CONE) * Cone(bottom_radius=NEUT_R,
                                              top_radius=NEUT_TIP_R, height=8),
                _nz(NEUT_TIP_R, *NEUT_SNOUT))
cathode -= _nz(NEUT_ORF_R, *NEUT_BORE)                   # keeper orifice

# ---- neutralizer housing -------------------------------------------------
# Keeper enclosure wrapping the cathode FLUSH to its Ø18 body (no clearance gap),
# with a bored front plate so the cavity is closed and you cannot see inside; the
# snout pokes out through the bore. Plus the block tying it to the outer shell.
enclosure = (Pos(0, NCY, sum(ENC_OUT) / 2) * Box(ENC_W, ENC_W, ENC_OUT[1] - ENC_OUT[0])
             - Pos(0, NCY, sum(ENC_CAV) / 2) * Box(ENC_CAV_W, ENC_CAV_W, ENC_CAV[1] - ENC_CAV[0]))
enclosure -= _nz(ENC_BORE_R, ENC_CAV[1], ENC_OUT[1] + 3)  # front-plate bore
mount = Pos(0, 108, 95) * Box(18, 12, 30)                  # y 102..114, z 80..110
neut_house = union(enclosure, mount)

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
    (neut_house, "Neutralizer_Housing",   COL["shell"]),
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
