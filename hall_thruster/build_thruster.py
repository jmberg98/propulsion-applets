#!/usr/bin/env python3
"""
build_thruster.py - parametric SPT-type Hall thruster, built the same way as
gridded_ion/build_thruster.py (build123d -> colored STEP -> tessellated JSON).

Reference: the axisymmetric SPT section schematic Jordan supplied - battery
across cathode and anode, mass flow into the anode, RED coil packs stacked in
the slots of a gray iron structure, an olive dielectric channel with the anode
in its upstream end, and the plume off the right. Used as a SHAPE GUIDE only;
every dimension below is illustrative and was picked to read well in the
applet's cutaway, not taken from any real thruster drawing.

The thing that figure gets across, and that the earlier 3-D concept figure did
not, is that the whole magnetic circuit is a body of REVOLUTION:

  * A back plate at the upstream end with four concentric cylindrical walls
    standing off it, all reaching the same front plane. In section that is the
    comb of gray arms; in the round it is a set of annular slots.
  * A coil pack sitting in three of those slots - one inboard of the channel,
    two outboard. Not windings on discrete return legs: at each radius the
    conductor circles the thrust axis, so a pack is a stack of turns running
    azimuthally, laid up along Z. That is why COIL_PITCH slices each pack into
    rings rather than sweeping a helix.
  * A cover plate roofing each coil slot at the front, so NO copper shows on the
    front face and the only thing open there is the channel mouth.
  * The discharge channel occupying the remaining slot, filling it to the full
    depth, its ceramic closing across the upstream end so the anode sits in the
    bottom of a cup.
  * The walls flanking the channel ending at the front plane as the two pole
    faces, which is where B crosses the annulus.

There is no separate outer skin. The outermost wall IS the exterior, the way
the schematic draws it, so nothing needs covering up.

Layout: axis = +Z, exhaust downstream at high Z (same convention as the
gridded-ion model). Radial stack-up, axis outward:

    r 0     ..  12    center stem            (inner magnetic branch)
    r 14    ..  26    inner coil, a ring about the thrust axis
    r 28    ..  33    inner pole wall        (inner magnetic branch)
    r 33    ..  67    ceramic discharge channel, plasma annulus r 38 .. 62
    r 67    ..  72    outer pole wall
    r 73    .. 103    four discrete outer solenoids on their own legs, at 90 deg
    r 104   .. 110    outer return wall = the thruster's outside surface

The two coil kinds are NOT the same object. The inner coil has to be a ring -
there is one center stem and the winding circles it, so it is coaxial with the
thrust axis. The four OUTER coils are discrete solenoids spaced around the
thruster, each wound on its own axial leg, exactly as a real SPT arranges them.
Modeling the outer pair as rings was wrong however well it read in section.

A discrete solenoid costs twice the radial budget a ring does, because it needs
room on BOTH sides of its own axis: the pack spends 2 x its winding depth of the
thruster's radius instead of 1 x. That is what set the leg at r 88 with a slim
Ø12 core, and why the outer pole wall thinned to 5 mm to free the annulus.

The channel is 24 mm wide, i.e. 0.22 of the outer radius, which is both what the
schematic draws and what makes the injector plate legible. At 14 mm it was a
3.4 : 1 slot - 47 mm from the plate face to the mouth on a 14 mm gap - and the
anode sat at the bottom of it in near-total shadow, so its orifices could not be
made out from any angle. Widening the annulus is the fix; moving the anode
downstream is not, because it belongs against the upstream end - it is a shallow
ring taking 14 % of the channel length, its face 12 mm off the chamber floor.

Exports hall_thruster_3D.STEP with per-part colors.
"""
import math
import sys
from build123d import (
    Cylinder, Cone, Box, Pos, Rot, Compound, Color, export_step,
)

# ---- axial stations (mm) -------------------------------------------------
# Length 84 against a 220 diameter, i.e. L/D = 0.38. The schematic draws a flat
# disk, near 0.34; the earlier model was 0.57 and read as a drum.
Z_BACK0    = 0.0     # rear face of the magnetic back plate
Z_BACK1    = 14.0    # front face of the back plate - the walls stand off this
Z_FRONT    = 84.0    # front plane: every wall ends here, poles included
Z_EXIT     = Z_FRONT  # the ceramic fills its slot to the full depth
Z_COVER0   = 80.0    # front cover plates close the three coil slots from here

# ---- discharge channel ---------------------------------------------------
R_CH_IN    = 38.0    # plasma-side inner radius of the annular channel
R_CH_OUT   = 62.0    # plasma-side outer radius            -> 24 mm channel width
CER_T      = 5.0     # ceramic (BN) wall thickness
R_CER_IN   = R_CH_IN  - CER_T     # 37 - inner wall inner radius
R_CER_OUT  = R_CH_OUT + CER_T     # 61 - outer wall outer radius
Z_CH0      = Z_BACK1              # ceramic seats on the back plate
Z_CH_FLOOR = Z_CH0 + CER_T        # 19 - inside face of the ceramic back wall

# ---- magnetic circuit ----------------------------------------------------
R_YOKE     = 110.0   # outer radius of the back plate and of the thruster
R_STEM     = 12.0    # center stem
WALL_A     = (28.0, 33.0)    # inner pole wall, seats the channel's inner wall
WALL_B     = (67.0, 72.0)    # outer pole wall, seats the channel's outer wall
WALL_D     = (104.0, R_YOKE)  # outer return wall = the outside surface

N_LEG      = 4       # discrete outer poles, at 0/90/180/270 deg
R_LEG      = 88.0    # leg centerline radius - midway across the 72..104 annulus
R_LEG_ROD  = 6.0     # leg radius (Ø12); slim, to leave the solenoid its depth

# ---- coils ---------------------------------------------------------------
# Every pack is a stack of annular turns laid up along Z, because a turn is a
# CIRCLE about whatever core it is wound on and the winding advances axially.
# The ribbing you see down a pack is its individual turns. What differs between
# the two kinds is only the axis the turns circle:
#
#   inner - the thrust axis, so the turns are rings and the pack is annular.
#   outer - each leg's own axis, so a pack is a stack of washers around that
#           leg and there are N_LEG of them spaced around the thruster.
#
# Modeling them as stacked tubes rather than swept helices is what makes them
# cheap: a tube is four analytic faces and OCC meshes it without subdividing
# along a path. An equivalent set of helices cost ~86 k triangles.
COIL_PITCH = 2.6     # turn-to-turn spacing along the axis
COIL_W     = 2.1     # axial width of one turn -> 0.5 mm of air between turns
COIL_Z0    = 18.0    # 4 mm clear of the back plate
COIL_Z1    = 78.0    # 6 mm shy of the front plane, so the covers clear them
R_COIL_I   = (14.0, 26.0)   # inner ring pack, radii about the THRUST axis
R_COIL_O   = (7.5, 15.0)    # outer solenoid, radii about its own LEG axis
                            # -> reaches r 73 .. 103 from the thrust axis

# ---- coil formers --------------------------------------------------------
# The bobbin each winding is wound onto, filling the space between the winding's
# bore and the pole it stands off. It exists to fix a shading problem, and it is
# also simply what holds a coil off its core.
#
# That space used to be a VOID, and in section a void reads as whatever the eye
# finds down it. Either side of a leg it appeared as a band, and the two bands did
# not match: (127,91,48) on the outer side against (82,50,24) on the inner, 1.7x
# apart, while the CENTRAL coil's equivalent pair agreed exactly at (82,50,24)
# because that coil is coaxial with the thrust axis and its two sides are mirror
# images. Three of the four bands agreed and one was wrong, and it stayed wrong
# through every attempt to change what lay behind it - the depth fog, an iron pole
# cup, a copper overwrap - all within 3 of the same 40.
#
# Filling the space settles it by construction: a solid's cut face is a flat,
# unlit cap, so both bands are now one component painted one color and cannot
# disagree. FORMER_COL is set to the tone the three GOOD bands already had, so
# what changes is only the band that was wrong.
FORMER_GAP = 0.1     # clearance to the pole and to the winding; sub-pixel in section

# ---- anode / gas distributor --------------------------------------------
# ONE part does both jobs, the way the schematic draws it: the anode baseplate
# seated in the bottom of the ceramic cup IS the propellant injector. There is
# no separate distributor - the supply lines feed its plenum from behind and the
# neutrals leave through the orifice ring in its downstream face.
#
# It is a SHALLOW ring, 10 mm deep on a 70 mm channel, sitting its face 12 mm off
# the chamber floor. The plenum it carries is not decoration: the orifices choke,
# so what each one passes is set by the stagnation pressure just behind it, and the
# cavity is what equalizes that pressure around the azimuth from only two inlets.
# Drill straight through from feed to orifice instead and the two orifices in line
# with the feeds pass nearly all the flow. Depth is the one dimension free to come
# down, though - the cavity only has to be big enough that the azimuthal pressure
# drop along it stays small next to the critical drop across the orifices.
R_AN_IN    = 39.0    # anode bore  (1 mm clear of the channel inner wall)
R_AN_OUT   = 61.0    # anode OD    (1 mm clear of the channel outer wall)
Z_AN0      = 21.0    # 2 mm off the ceramic floor at Z_CH_FLOOR = 19
Z_AN1      = 31.0    # anode downstream face - 12 mm off the chamber floor
PLENUM_T   = 3.0     # anode wall thickness around the gas plenum
# EIGHT injector orifices, at 45 deg spacing. At 8 they have to be big to read at
# all - a 30-odd hole ring can be fine because the holes crowd each other into a
# visible dotted line, but eight small ones just disappear. Ø7 on a Ø100 circle
# is a 39 mm pitch, so they stay eight distinct dots rather than merging.
#
# Sizing them is a plate-width problem, not a hole problem: the orifice has to
# open fully into the plenum cavity AND leave visible plate either side of it,
# and the section has to still read as a hole in a plate rather than a gap
# between two walls. On the 12 mm-wide plate this replaced, a Ø5 hole ate most
# of the 6 mm cavity and the cut plane came out looking like an open-ended box.
#
# Phase 0, so two of them land at 90/270 deg, directly downstream of the two
# feed lines: on the viewer's cut plane the section then shows the whole gas
# path on one radial line, tube in -> plenum -> orifice out.
N_GAS_HOLE = 8
R_GAS_HOLE = 3.5
CSINK_D    = 2.0     # countersink depth on the downstream face, 45 deg
R_FEED     = 50.0    # propellant feed / orifice circle radius (channel midline)
FEED_R     = 4.0     # feed tube outer radius
FEED_BORE  = 2.0
Z_FEED0    = -14.0   # feed tubes poke out the back of the thruster

# TWO injector lines, diametrically opposed. A single feed into one side of an
# annular plenum leaves a pressure gradient around the ring, so the neutral flow
# out of the distributor holes is not azimuthally uniform; opposed feeds halve
# the path from either inlet to the farthest holes. Both sit in the CAD x = 0
# plane, which is the viewer's cut plane, so the section shows both.
INJ_ANGLES = (90.0, 270.0)   # azimuths, degrees

# ---- cathode-neutralizer -------------------------------------------------
# Canted, the way the schematic mounts it: up off the outer wall near the front,
# tilted in so the keeper orifice aims at the beam edge just downstream of the
# exit plane. NEUT_TILT is measured off the thrust axis, so the cathode axis
# points along (0, -sin, +cos) - inward in Y and downstream in Z.
NEUT_TILT  = 35.0    # degrees off the thrust axis
NEUT_Y0    = 156.0   # Y of the cathode's back end - set by the ENCLOSURE, below
NEUT_Z0    = 53.0    # Z of the cathode's back end
NEUT_BODY  = (0.0, 40.0)     # local axial stations, measured from the back end
NEUT_CONE  = 43.0            # Cone is CENTER-placed, so this spans 40 .. 46
# The snout is what stands PROUD of the keeper housing, so its length is set by how
# much cathode should read outside the pod, not by the tube itself: at 8 mm only a
# nub cleared the front plate and the assembly read as a plain box. 16 mm leaves 13
# outside, i.e. about a quarter of the shell's length, which is the proportion the
# gridded-ion neutralizer shows.
NEUT_SNOUT = (46.0, 62.0)
NEUT_BORE  = (58.0, 64.0)
NEUT_R     = 9.0     # body radius (Ø18)
NEUT_TIP_R = 5.5     # snout radius
NEUT_ORF_R = 2.6     # keeper orifice radius

# ---- neutralizer housing -------------------------------------------------
# A KEEPER ENCLOSURE around the cathode body plus a slab carrying it, in place of
# the bare tube on an open boom this started as. The cathode is then a snout poking
# out of a gray pod, not a large exposed gold cylinder hanging off a boom, which is
# how gridded_ion/build_model.py's `neut_house` presents its neutralizer and is what
# makes the two applets read as the same hardware family. Proportions are taken from
# there: Ø24 over the Ø18 body, so 3 mm of wall, a 3 mm rear plate and a 3 mm front
# plate bored to clear the cone. You cannot see inside it from any angle; only the
# taper and the snout come out of the bore.
#
# The gridded-ion pod is a square BOX and this one started that way too, but Jordan
# circled it and asked for the pod - and only the pod, not the slab behind it - to
# be CYLINDRICAL. So the shell and its cavity are turned about the cathode axis
# while the slab stays prismatic, and the two meet on the pod's rear plate. On that
# plane the slab's section is exactly the 24 x 24 square that CIRCUMSCRIBES the Ø24
# rim: tangent on all four faces, with only the four corners standing proud. That
# tangency is not arranged, it falls out of MOUNT_Y0/MOUNT_Y1 already being the
# rim's extreme points in y - see `_corner_y`, which is unchanged by the switch
# because the local x direction contributes nothing to global y.
#
# It is built in the CATHODE's canted frame, so the pod is coaxial with the cathode
# and only the slab is square to the thruster.
ENC_D      = 24.0            # pod outside diameter - 3 mm of wall on the Ø18 body
ENC_Z      = (-3.0, 45.0)    # local axial stations of the shell
ENC_CAV_Z  = (0.0, 42.0)     # cavity: 3 mm rear plate, 3 mm front plate. Its rear
                             # face is FLUSH on the cathode's back face, as in the
                             # gridded-ion build - stand it off and the section
                             # shows a black slot behind the cathode instead of a
                             # seated part.
# The cavity can no longer be flush on the body's SIDES. As a box it was tangent
# along four lines and shared zero volume with the Ø18 cathode, which is what let it
# sit hard against it; turned, "flush" would mean the cavity's wall and the body's
# wall are the SAME cylinder - coincident surfaces, which z-fight and which OCC's
# booleans have no reason to resolve one way or the other. So it takes the same
# 0.1 mm standoff FORMER_GAP uses a few dozen lines up, for the same reason: nothing
# shares a surface and the gap stays sub-pixel (0.4 px at the framing the applet
# opens on).
ENC_GAP    = 0.1
ENC_CAV_R  = NEUT_R + ENC_GAP     # 9.1
ENC_BORE_R = 8.0             # front-plate bore; the cone is r 7.83 at local z 42

# Behind the pod, the housing continues as a plain slab square to the THRUSTER -
# the piece that reconciles the two frames, the same job gridded_ion's Box(18, 10,
# 30) does. It began as a slim post under the pod's rear end, which left a large
# black notch between the pod and the thruster's upstream side and made the pod read
# as perched on a stalk; Jordan marked that void out and had the housing EXTENDED
# through it, so it now runs from the thruster's rear face at z = 0 forward to the
# pod, and stands as tall as the pod's own rear-top corner.
#
# THE HOUSING NO LONGER TOUCHES THE THRUSTER. The slab used to run down to r 104,
# six millimeters inside the outer wall, so the assembly was bolted on. Jordan drew
# a line across it and asked for the cathode to be cut free - external, as the name
# says, connecting to the thruster nowhere. Nothing spans the gap, no bracket and no
# strut, so the whole neutralizer floats, carried by the spacecraft rather than by
# the thruster. (Real hardware does bracket the cathode to the thruster or to a
# gimbal plate; this is a presentational choice, and the clearance is what makes the
# point.) `check_clearance.py` no longer whitelists Neutralizer_Housing against
# Magnetic_Core_Outer, so a nonzero reading between them is the regression that
# catches this being undone. A zero interference volume alone is NOT enough, since
# touching also scores zero - measure the real gap with BRepExtrema_DistShapeShape.
# It is 10.4 mm, set by the POD's lower front corner rather than by the slab.
#
# The slab stops dead on the pod's rear plate, and its own square section is sized
# from the pod's rear rim, so the two are concentric on that plate and the joint is
# one clean square-to-round transition.
#
# MOUNT_GROW is how much PROUD of the rim the slab stands. It ran through three
# values, and the history is the reason it is a named factor rather than a number:
#   0.75  the slab was 18 against the pod's 24, so the POD overhung the SLAB and the
#         two met in a sliver and a groove down the top face. Jordan circled it.
#   1.00  exactly circumscribing - tangent on all four faces, only the corners proud.
#         From the front the base then barely showed behind the tube.
#   1.30  a square base standing 3.6 mm proud all round, so it reads as a base
#         rather than as something the tube not quite covers.
#   1.69  current - another 30 % on top of that, i.e. 1.30 squared. A Ø24 tube on a
#         40.6 mm square, standing 8.3 mm proud all round.
# Note that going past 1.0 deliberately reintroduces a step at the joint, including
# on the underside, where 1.0 had given one continuous line from slab to pod. That is
# what a flange IS, and "by 30% on ALL sides" asks for it on the bottom too.
MOUNT_GROW = 1.69
MOUNT_W    = ENC_D * MOUNT_GROW     # 40.56
MOUNT_Z    = (0.0, 64.0)     # from the thruster's rear face; the pod's plate trims it

# Colors follow the gridded-ion applet's convention: one light gray for every
# structural body, and gold reserved for hollow cathodes. That applet spends its
# DARKEST tone on the functional electrodes (the two grids) and keeps the bodies
# light, so the piece the panel names is the piece that reads on the hardware.
# Applied here that puts the dark on the ANODE, not on the magnetic core: the
# core is a soft-iron flux path, i.e. structure, and painting that whole mass
# dark buried the anode inside it.
#
# The schematic's own palette (red coils, blue anode, olive ceramic) is cartoon
# coding, not materials, and red and blue are both spoken for in this codebase.
COL = dict(
    shell      = "#d5d8e4",   # aluminum: the propellant feed lines
    # The KEEPER HOUSING is its own material, not the feed lines' aluminum. It used
    # to share that tone, which said the pod was the same stuff as the two Ø8 tubes
    # it sits nowhere near, and left the panel unable to name either one: a single
    # swatch cannot caption two unrelated parts, so neither got a legend row.
    #
    # Stainless is the honest call for a keeper enclosure and its mount - it runs
    # hot next to an emitter and gets no structural help from being light, which is
    # the opposite of the case for feed plumbing. It also has to survive the
    # cathode's own thermal cycling without an aluminum's expansion mismatch.
    #
    # Tonally it is a WARM neutral, on purpose. The three grays already in the model
    # are all cool - aluminum #d5d8e4 and soft iron #7a808b are blue-cast, the anode
    # #3a3f48 nearly black - so a fourth cool gray would have read as one of them
    # under a different light rather than as another material. Luminance separation
    # is what stops the housing merging into the core it floats beside: 167 here
    # against the core's 127 and the feed lines' 216, i.e. ~40-50 clear of each,
    # where the section work upstream in this file treats ~20 as the marginal case.
    keeper     = "#a9a6a0",   # stainless: cathode keeper enclosure + its mount block
    core_outer = "#7a808b",   # soft iron: back plate, outer pole and return walls
    # The inner branch is the SAME soft iron as the outer one and is continuous with
    # it through the back plate, so it takes the same tone. It used to be a shade
    # lighter, to make the inner circuit legible on its own, but that put a hard seam
    # straight across the back-plate joint at z = 14 - (123,129,140) stepping to
    # (139,145,154) along the axis - which reads as two materials butted together
    # rather than one part. The panel calls them one component, so they look like one.
    core_inner = "#7a808b",
    coil       = "#b9773a",   # copper windings
    channel    = "#eef0ea",   # boron nitride: the chalk-white discharge channel
    former     = "#523218",   # coil bobbin - exactly the tone the good bands read
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


def coil_pack(radii, x=0.0, y=0.0, z0=COIL_Z0, z1=COIL_Z1,
              pitch=COIL_PITCH, w=COIL_W):
    """A solenoid: turns circling the axis through (x, y), stacked along Z.

    `radii` is (bore, outside) measured about THAT axis, so the same call builds
    the inner ring pack (x = y = 0, turns circling the thrust axis) and one of
    the discrete outer solenoids (x = R_LEG, turns circling its leg).

    Whole turns only - a trailing partial turn at the downstream end would read
    as a chipped coil, so the pack is however many complete turns fit and the
    remainder is left as air at z1.
    """
    ri, ro = radii
    n = int((z1 - z0 + (pitch - w)) // pitch)
    return union(*[tube(ro, ri, z0 + k * pitch, z0 + k * pitch + w, x, y)
                   for k in range(n)])


# ---- magnetic core, outer branch ----------------------------------------
# Back plate + the outer pole wall + the two return walls. The outermost wall is
# the thruster's exterior; there is no skin over it.
back_plate = cyl(R_YOKE, Z_BACK0, Z_BACK1)
for _a in INJ_ANGLES:
    back_plate -= Rot(Z=_a) * cyl(FEED_R + 2.0, Z_BACK0 - 2, Z_BACK1 + 2, x=R_FEED)

def wall(rr, z0=Z_BACK1, z1=Z_FRONT):
    """One of the concentric walls standing off the back plate, (r_in, r_out)."""
    return tube(rr[1], rr[0], z0, z1)


def cover(r_in, r_out):
    """Front cover closing a coil slot, flush with the pole faces.

    Each slot is roofed over so no copper shows on the front face - the coils
    are buried, the way they are on real hardware, and the only thing open at
    the front is the channel mouth. It bridges two walls of the SAME magnetic
    branch every time, so it shorts nothing that was not already common iron.
    """
    return tube(r_out, r_in, Z_COVER0, Z_FRONT)


# The four outer poles each carry one discrete solenoid; the annular cover over
# them roofs the whole 72..104 space in one piece, so no copper shows at the
# front however the legs are clocked.
legs = [Rot(Z=k * 360.0 / N_LEG) * cyl(R_LEG_ROD, Z_BACK1, Z_FRONT, x=R_LEG)
        for k in range(N_LEG)]

core_outer = union(back_plate, wall(WALL_B), wall(WALL_D), *legs,
                   cover(WALL_B[1], WALL_D[0]))      # over the outer solenoids

# ---- magnetic core, inner branch ----------------------------------------
core_inner = union(cyl(R_STEM, Z_BACK1, Z_FRONT), wall(WALL_A),
                   cover(R_STEM, WALL_A[0]))         # over the inner coil

# ---- coils ---------------------------------------------------------------
# One ring about the center stem, plus N_LEG discrete solenoids about the legs.
coil_inner = coil_pack(R_COIL_I)
coil_outer = union(*[Rot(Z=k * 360.0 / N_LEG) * coil_pack(R_COIL_O, x=R_LEG)
                     for k in range(N_LEG)])

# One former per winding, spanning core-surface + gap .. winding-bore - gap.
former = union(
    tube(R_COIL_I[0] - FORMER_GAP, R_STEM + FORMER_GAP, COIL_Z0, COIL_Z1),
    *[Rot(Z=k * 360.0 / N_LEG)
      * tube(R_COIL_O[0] - FORMER_GAP, R_LEG_ROD + FORMER_GAP,
             COIL_Z0, COIL_Z1, x=R_LEG)
      for k in range(N_LEG)])

# ---- ceramic discharge channel ------------------------------------------
# A CUP, not two loose tubes: the schematic's dielectric walls close across the
# upstream end, so the ceramic is a U in section and the anode sits in the
# bottom of it. The back wall is bored for the feed lines.
channel_back = tube(R_CER_OUT, R_CER_IN, Z_CH0, Z_CH_FLOOR)
for _a in INJ_ANGLES:
    channel_back -= Rot(Z=_a) * cyl(FEED_R + 1.0, Z_CH0 - 2, Z_CH_FLOOR + 2, x=R_FEED)

channel = union(tube(R_CH_IN, R_CER_IN,  Z_CH0, Z_EXIT),    # inner wall
                tube(R_CER_OUT, R_CH_OUT, Z_CH0, Z_EXIT),   # outer wall
                channel_back)                                # upstream back wall

# ---- anode / gas distributor --------------------------------------------
# The baseplate seated in the bottom of the ceramic cup, doing both jobs at once
# the way the schematic draws it. Hollow: gas enters from the feed lines, fills
# the plenum, and meters out through the eight orifices in the downstream face,
# so the neutral flow is uniform in azimuth by the time it reaches the ionization
# zone. The orifice circle sits on the channel midline, and the plenum cavity is
# 0.5 mm wider than the orifice either side so every hole opens fully into it.
anode = tube(R_AN_OUT, R_AN_IN, Z_AN0, Z_AN1)
anode -= tube(R_AN_OUT - PLENUM_T, R_AN_IN + PLENUM_T, Z_AN0 + PLENUM_T, Z_AN1 - PLENUM_T)
anode -= union(*[
    Rot(Z=k * 360.0 / N_GAS_HOLE) * cyl(R_GAS_HOLE, Z_AN1 - PLENUM_T - 1, Z_AN1 + 2, x=R_FEED)
    for k in range(N_GAS_HOLE)])
# Countersink every orifice. Real injector orifices are chamfered, and here it is
# also what makes them legible: the plate is the darkest body in the model and it
# sits at the bottom of the channel, so a bare hole is dark-on-dark and vanishes.
# The cone is a surface at 45 deg to the face, so it catches light the flat face
# does not and rings each orifice with a lighter outline.
anode -= union(*[
    Rot(Z=k * 360.0 / N_GAS_HOLE)
    * Pos(R_FEED, 0, Z_AN1 - CSINK_D / 2)
    * Cone(bottom_radius=R_GAS_HOLE, top_radius=R_GAS_HOLE + CSINK_D, height=CSINK_D)
    for k in range(N_GAS_HOLE)])
# Carry each feed bore on through the anode's upstream wall, same radius as the
# tube's own bore, so the two line up into ONE passage: tube -> wall -> plenum.
for _a in INJ_ANGLES:
    anode -= Rot(Z=_a) * cyl(FEED_BORE, Z_AN0 - 2, Z_AN0 + PLENUM_T + 1, x=R_FEED)

# The tube stops flush ON the anode's upstream face - butted, not inserted.
#
# It used to run to Z_AN0 + PLENUM_T + 2, i.e. 5 mm past that face and out into the
# plenum, while the bore it passed through was only FEED_BORE. A Ø8 tube through a
# Ø4 hole buried 226 mm^3 of tube wall inside the anode, which the viewer drew as a
# z-fighting hatch across the joint, and left the tube's mouth hanging in mid-plenum
# with a gap between it and the far wall. Ending it on the face fixes both: nothing
# overlaps, and the tube's bore meets the anode's bore exactly, concentric and
# tangent, so the gas path reads as one continuous passage.
feed = union(*[Rot(Z=_a) * tube(FEED_R, FEED_BORE, Z_FEED0, Z_AN0, x=R_FEED)
               for _a in INJ_ANGLES])

# ---- cathode-neutralizer -------------------------------------------------
# Built along +Z at the origin, then canted and carried out to the mount. `Pos *
# Rot * shape` applies the rotation first, so NEUT_PLACE puts local +Z along
# (0, -sin, +cos) and drops local z = 0 on the cathode's back end.
NEUT_PLACE = Pos(0, NEUT_Y0, NEUT_Z0) * Rot(X=NEUT_TILT)

cathode = NEUT_PLACE * union(
    cyl(NEUT_R, *NEUT_BODY),
    Pos(0, 0, NEUT_CONE) * Cone(bottom_radius=NEUT_R, top_radius=NEUT_TIP_R, height=6),
    cyl(NEUT_TIP_R, *NEUT_SNOUT),
)
cathode -= NEUT_PLACE * cyl(NEUT_ORF_R, *NEUT_BORE)          # keeper orifice

# ---- neutralizer housing -------------------------------------------------
# Keeper enclosure + mount block, per the note on the constants above.
#
# What sets NEUT_Y0 is now the ENCLOSURE clearing the outer wall over the span
# where the two overlap axially - it used to be the bare Ø18 body, and wrapping
# that body in a 24 mm shell moved the binding point out by 5.6 mm. The shell's
# lower front corner is the one that binds: it sits at (y 120.4, z 83.0), i.e.
# 10.4 mm outboard of the R_YOKE surface and 1 mm shy of the front plane, so it
# clears the thruster at the last station where the two still overlap.
# The slab's two horizontal faces are placed off the pod's own rear rim, scaled by
# MOUNT_GROW, so the square base stays centered on the tube whatever either is sized
# to. Derived from NEUT_PLACE rather than typed in, so both track the cant.
#
# The rim being a CIRCLE rather than the square it once was changes nothing here:
# local x maps to global x and contributes nothing to global y, so the circle's
# extreme y is exactly where the old square's corners were. That is also what keeps
# the base concentric with the tube instead of merely overlapping it - at
# MOUNT_GROW = 1 it circumscribed the rim tangentially, and above 1 it stands the
# same amount proud on all four sides.
def _slab_y(sign):
    """Y of the slab's top (+1) or bottom (-1) face, off the pod's rear rim."""
    return (NEUT_Y0 + sign * (ENC_D / 2) * MOUNT_GROW * math.cos(math.radians(NEUT_TILT))
            - ENC_Z[0] * math.sin(math.radians(NEUT_TILT)))


MOUNT_Y1 = _slab_y(+1)       # 170.5 - the highest point on the whole assembly
MOUNT_Y0 = _slab_y(-1)       # 144.9 - the slab's underside, 35 mm clear of R_YOKE

mount = Pos(0, (MOUNT_Y0 + MOUNT_Y1) / 2, sum(MOUNT_Z) / 2) * Box(
    MOUNT_W, MOUNT_Y1 - MOUNT_Y0, MOUNT_Z[1] - MOUNT_Z[0])

# Stop the slab dead on the pod's rear plate: cut the WHOLE half-space downstream of
# it, not just the part level with the pod. Cutting only that part left a wedge of
# slab hanging below the pod, sloping down to the thruster, which is the material
# Jordan's second line cut away. It also has to be the whole half-space now that
# MOUNT_GROW puts the slab OUTSIDE the pod: cut any less and the base's proud edges
# would run on downstream as fins alongside the tube.
BIG = 400.0
mount -= NEUT_PLACE * (Pos(0, 0, BIG / 2 + ENC_Z[0]) * Box(BIG, BIG, BIG))

# Pod and cavity are both turned about the cathode axis. The front plate is
# unaffected: the cavity stops at ENC_CAV_Z[1], so the plate is still solid stock
# that ENC_BORE_R opens to Ø16 - an annulus r 8 .. 12 now instead of a bored square,
# with the cone (r 7.83 at that station) passing through exactly as before.
neut_house = union(NEUT_PLACE * cyl(ENC_D / 2, *ENC_Z), mount)
neut_house -= NEUT_PLACE * cyl(ENC_CAV_R, *ENC_CAV_Z)
neut_house -= NEUT_PLACE * cyl(ENC_BORE_R, ENC_CAV_Z[1] - 1, ENC_Z[1] + 2)

# ---- assemble, color, export --------------------------------------------
parts = [
    (core_outer, "Magnetic_Core_Outer",   COL["core_outer"]),
    (core_inner, "Magnetic_Core_Inner",   COL["core_inner"]),
    (coil_outer, "Coil_Outer",            COL["coil"]),
    (coil_inner, "Coil_Inner",            COL["coil"]),
    (former,     "Coil_Former",           COL["former"]),
    (channel,    "Discharge_Channel",     COL["channel"]),
    (anode,      "Anode_Gas_Distributor", COL["anode"]),
    (feed,       "Propellant_Feed",       COL["shell"]),
    (cathode,    "Cathode_Neutralizer",   COL["cathode"]),
    (neut_house, "Neutralizer_Housing",   COL["keeper"]),
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
