#!/usr/bin/env python3
"""
build_thruster.py — parametric rebuild of the gridded-ion thruster.

Rebuilds the assembly (axis = +Z, downstream/grids at high Z) with three
requested changes vs the original SolidWorks export:
  1. Screen grid thicker  (2.0 -> SCREEN_T mm)
  2. Accel  grid thicker  (3.0 -> ACCEL_T mm)
  3. Larger gap between grids (4.0 -> GRID_GAP mm)
  4. NO annular gap between outer housing and discharge chamber:
     the housing is filled inward so its inner wall meets the chamber
     wall, keeping the housing grey (#9096a0).

Exports gridded_ion_3D_v2.STEP with per-part colours.
"""
import sys, math
from build123d import (
    Cylinder, Cone, Box, Pos, Rot, Compound, Color, export_step, Align,
)

# ---- parameters (mm) ----------------------------------------------------
R_PLASMA      = 97.0     # inner (plasma cavity) radius of discharge chamber
CHAMBER_WALL  = 3.0      # chamber wall thickness  -> outer radius 100
R_CHAMBER_OUT = R_PLASMA + CHAMBER_WALL
R_HOUSE       = 126.0    # outer housing radius
L_CHAMBER     = 200.0    # chamber length (z = 0 .. 200)
Z_REAR        = -12.0    # housing rear face

R_GRID        = 106.0    # grid outer radius
R_GRID_ACTIVE = 96.0     # perforated region radius
SCREEN_T      = 3.5      # CHANGED (was 2.0)
ACCEL_T       = 5.0      # CHANGED (was 3.0)
GRID_GAP      = 8.0      # CHANGED (was 4.0)
Z_SCREEN0     = L_CHAMBER + 2.0            # 202
HOLE_PITCH    = 16.0
SCREEN_HOLE_R = 6.0      # screen-grid aperture radius (larger — open extraction optics)
ACCEL_HOLE_R  = 3.0      # accel-grid apertures are SMALLER (blocks electron backstreaming)

R_CATH        = 10.0     # hollow cathode outer radius
R_CATH_BORE   = 5.0

Z_REAR_INNER  = -12.0    # inner rear face of the shell; chamber rear edge is flush here
FEED_SHIFT    = -25.0    # push cathode & injector further OUT of the chamber (more -z)
INJ_Y         = 27.0     # radial offset of the propellant injector
INJ_R         = 5.0
INJ_CLEAR     = 7.0      # clearance-bore radius through the shell for the injector

COL = dict(
    housing   = "#9096a0",
    chamber   = "#5b6470",
    cathode   = "#c79a2b",
    magnet    = "#2b2e34",
    screen    = "#b6bcc6",
    accel     = "#4a4e56",
    feed      = "#c79a2b",
)

def hexcol(h):
    h = h.lstrip("#")
    return Color(int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255)

def cyl(r, z0, z1):
    """Solid cylinder spanning z0..z1 on the Z axis."""
    return Pos(0, 0, (z0+z1)/2) * Cylinder(radius=r, height=(z1-z0))

def tube(ro, ri, z0, z1):
    return cyl(ro, z0, z1) - cyl(ri, z0, z1)

# ---- discharge chamber (anode) -----------------------------------------
# rear (left) edge is flush with the inner rear face of the shell (Z_REAR_INNER)
chamber = tube(R_CHAMBER_OUT, R_PLASMA, Z_REAR_INNER, L_CHAMBER)
# rear wall closing the chamber, bored for the cathode (centre) and injector (offset)
rear_wall = cyl(R_CHAMBER_OUT, Z_REAR_INNER, Z_REAR_INNER + 3) - cyl(R_CATH + 2, Z_REAR_INNER, Z_REAR_INNER + 3)
rear_wall -= Pos(0, INJ_Y, Z_REAR_INNER + 1.5) * Cylinder(radius=INJ_R + 1, height=6)
chamber += rear_wall

# ---- outer housing (fills the annular gap: inner wall meets chamber) ----
# The rear plate is THICKENED (rear face pushed from Z_REAR_INNER-8 out to
# Z_REAR_BACK) so a back-wall magnet ring can be fully buried inside it, the way
# a real ring-cusp thruster carries magnets on the back plate as well as the side
# wall (the buried ring then forms an extra cusp with the rearmost side ring).
Z_REAR_BACK  = Z_REAR_INNER - 20    # thicker rear plate: back face at -32 (was -20)
housing  = tube(R_HOUSE, R_CHAMBER_OUT, Z_REAR_INNER, L_CHAMBER)   # solid annulus, no void
housing += tube(R_HOUSE, R_GRID,        L_CHAMBER, Z_SCREEN0 + SCREEN_T + GRID_GAP + ACCEL_T + 2)  # front ring around grids
housing += tube(R_HOUSE, R_CATH + 4,    Z_REAR_BACK, Z_REAR_INNER)  # THICKER rear plate w/ cathode bore
# clearance bore through the rear plate so the propellant injector isn't intersected
housing -= Pos(0, INJ_Y, Z_REAR_INNER - 4) * Cylinder(radius=INJ_CLEAR, height=14)
# metal mounting block that ties the neutralizer cathode to the thruster body
housing += Pos(0, 128.5, 183) * Box(18, 10, 30)
# neutralizer enclosure (keeper housing): a box wrapping the neutralizer cathode
# FLUSH to its Ø18 body (no clearance gap), with a bored front plate so the cavity
# is closed — you cannot see inside in the 3-D view; the snout pokes out the bore.
# axis = +Z; cathode centred at (0,140), body z 165..202, snout to z 224.
enc_outer  = Pos(0, 140, (162 + 207) / 2) * Box(24, 24, 207 - 162)   # X,Y = 24 (±12), Z 162..207
enc_cav    = Pos(0, 140, (165 + 204) / 2) * Box(18, 18, 204 - 165)   # hollow interior, flush to the Ø18 cathode
enclosure  = enc_outer - enc_cav
enclosure -= Pos(0, 140, 205) * Cylinder(radius=8, height=10)        # front-plate bore (r=8 = cone radius at z=204)
housing   += enclosure

# ---- ion-optics grids (perforated discs) --------------------------------
def perforate(disc, z0, z1, hole_r):
    cutters = None
    n = int(R_GRID_ACTIVE // HOLE_PITCH) + 1
    for i in range(-n, n+1):
        for j in range(-n, n+1):
            x = i*HOLE_PITCH + (HOLE_PITCH/2 if j % 2 else 0)  # hex-ish stagger
            y = j*HOLE_PITCH*math.sqrt(3)/2
            if math.hypot(x, y) <= R_GRID_ACTIVE:
                h = Pos(x, y, (z0+z1)/2) * Cylinder(radius=hole_r, height=(z1-z0)+2)
                cutters = h if cutters is None else cutters + h
    return disc - cutters

z_s0, z_s1 = Z_SCREEN0, Z_SCREEN0 + SCREEN_T
z_a0, z_a1 = z_s1 + GRID_GAP, z_s1 + GRID_GAP + ACCEL_T
screen = perforate(cyl(R_GRID, z_s0, z_s1), z_s0, z_s1, SCREEN_HOLE_R)
accel  = perforate(cyl(R_GRID, z_a0, z_a1), z_a0, z_a1, ACCEL_HOLE_R)

# ---- magnet rings (EMBEDDED in the thruster wall, not the plasma cavity) --
# Ring radius sits between the chamber outer wall (R_CHAMBER_OUT) and the housing
# OD (R_HOUSE), so each magnet is buried inside the wall material. The chamber
# wall in front occludes it from the plasma cavity, so in section it reads as a
# dark box embedded in the wall rather than a ring protruding into the chamber.
def ring(zc, h=14, ro=R_HOUSE-10, ri=R_CHAMBER_OUT+2):
    return tube(ro, ri, zc-h/2, zc+h/2)   # default r = 102 .. 116 (side wall)
# Side-wall rings at z = 18, 98, 183, PLUS a new back-wall ring buried in the
# thickened rear plate (z = -21, i.e. inside Z_REAR_BACK..Z_REAR_INNER). Sits at
# r 44..58 on the back plate: inboard, encircling the cathode/injector, but held
# OFF the injector (r<=32) so there is a clear radial gap. It pairs with the z=18
# side ring to close a new ring cusp.
magnets = ring(-21, ro=58, ri=44) + ring(18) + ring(98) + ring(183)

# ---- hollow cathode (central) — shifted further out of the chamber ------
cathode = tube(R_CATH, R_CATH_BORE, -70 + FEED_SHIFT, 45 + FEED_SHIFT)

# ---- propellant injector (offset feed tube) — mostly outside, tip ~5mm in -
inj = Pos(0, INJ_Y, 0) * tube(INJ_R, INJ_R - 2, -72, -5)

# ---- neutralizer cathode (stepped hollow-cathode) + mount block ---------
# axis = +z, mounted outside the housing at top-front; snout points downstream
NCY = 140.0
def zc(r, z0, z1, y=NCY):
    return Pos(0, y, (z0+z1)/2) * Cylinder(radius=r, height=z1-z0)
neut  = zc(9, 165, 202)                                   # fat cathode body (SOLID — no interior cavity)
neut += Pos(0, NCY, 206) * Cone(bottom_radius=9, top_radius=5, height=8)  # tapered shoulder
neut += zc(5, 210, 224) - zc(2.4, 214, 226)               # bored snout / keeper-orifice tip only

# ---- assemble, colour, export ------------------------------------------
parts = [
    (housing, "Outer_Housing",       COL["housing"]),
    (chamber, "Discharge_Chamber",   COL["chamber"]),
    (screen,  "Screen_Grid_Pos",     COL["screen"]),
    (accel,   "Accel_Grid_Neg",      COL["accel"]),
    (magnets, "Magnet_Rings",        COL["magnet"]),
    (cathode, "Hollow_Cathode",      COL["cathode"]),
    (inj,     "Propellant_Injector", COL["feed"]),
    (neut,    "Neutralizer_Cathode", COL["feed"]),
]
solids = []
for shp, name, c in parts:
    shp.label = name
    shp.color = hexcol(c)
    solids.append(shp)

if __name__ == "__main__":
    asm = Compound(children=solids)
    asm.label = "gridded_ion_thruster"
    out = sys.argv[1] if len(sys.argv) > 1 else "gridded_ion_3D_v2.STEP"
    export_step(asm, out)
    print("WROTE", out)
    for shp, name, c in parts:
        bb = shp.bounding_box()
        print(f"  {name:22s} z[{bb.min.Z:7.1f},{bb.max.Z:7.1f}]  r<= {max(abs(bb.min.X),abs(bb.max.X),abs(bb.min.Y),abs(bb.max.Y)):6.1f}")
