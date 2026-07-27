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

# ---- grid transparency (open-area fraction) ------------------------------
# Each grid must be `phi` open TWICE OVER: by area (the real ion-optics spec) and
# along the applet's cut plane (CAD x = 0), so the cross-section a reader eyeballs
# actually shows the transparency the grid has.
#
# A staggered HEX array cannot do that. The cut plane only meets every other hex
# row, so its open run is 2r/(p*sqrt(3)) <= 1/sqrt(3) = 57.7% no matter how open
# the grid is — a 90.7% open hex grid (holes touching) still sections at 57.7%.
# That ceiling is what made the old 80%-open screen grid read 54% in section.
#
# Fix the row pitch `s` instead and solve for the column period. With holes of
# radius r on rows of pitch s, and TWO columns per period P offset by (P/2, s/2):
#     section along x=0 = 2r/s                     (only the x=0 column is cut)
#     open area         = 2*pi*r^2 / (P*s)         (two holes per P-by-s cell)
# Setting both equal to phi gives r = phi*s/2 and P = pi*phi*s/2. The neighbouring
# column sits at P/2 >= r for every phi <= 2/pi, so it never reaches the cut plane
# and the section stays a clean row of full-diameter bores at pitch s.
#
# `s` is free — it sets how MANY holes there are, not how open the grid is. It is
# pinned to the applet's aperture-row spacing APER_DY = 16*sqrt(3), so the bore
# centres land exactly on the beamlet channels and HOLE_R_* == APER_R_* there.
APER_PITCH    = 16.0 * math.sqrt(3)   # 27.7128 mm — aperture ROW pitch (= applet APER_DY)
SCREEN_OPEN   = 0.80     # screen grid: wide-open extraction optics
ACCEL_OPEN    = 0.30     # accel grid: far tighter (blocks electron backstreaming)

def hole_r(phi, pitch=APER_PITCH):
    """Bore radius giving open fraction `phi` both by area and across the cut plane."""
    return phi * pitch / 2

def hole_period(phi, pitch=APER_PITCH):
    """Column period P for that array (two columns per period)."""
    return math.pi * phi * pitch / 2

SCREEN_HOLE_R = hole_r(SCREEN_OPEN)   # 11.0851 mm — fewer, much larger bores
ACCEL_HOLE_R  = hole_r(ACCEL_OPEN)    #  4.1569 mm — more, smaller bores

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
housing += tube(R_HOUSE, R_CATH + 4,    Z_REAR_BACK, Z_REAR_INNER)  # THICKER rear plate w/ cathode bore (r=14, snug clearance)
# clearance bore through the rear plate so the propellant injector isn't intersected —
# spans the FULL plate depth (Z_REAR_BACK..Z_REAR_INNER) so the injector bore is open all
# the way through the rear body face (was centred at -16/height 14, which stopped short of
# the -32 back face and left the injector capped by solid plate).
housing -= Pos(0, INJ_Y, (Z_REAR_BACK + Z_REAR_INNER) / 2) * Cylinder(radius=INJ_CLEAR, height=(Z_REAR_INNER - Z_REAR_BACK) + 6)
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
def hole_centres(hole_r, pitch=APER_PITCH):
    """Bore centres for the two-column array described above: rows at pitch `pitch`,
    columns at period P, second column offset half a period in BOTH axes. Centres are
    kept where the whole bore still clears the grid rim, so no hole breaks the OD."""
    phi = 2 * hole_r / pitch
    P   = math.pi * phi * pitch / 2
    lim = min(R_GRID_ACTIVE, R_GRID - 2 - hole_r)
    ni  = int(R_GRID_ACTIVE // P) + 2
    nj  = int(R_GRID_ACTIVE // pitch) + 2
    out = []
    for i in range(-ni, ni+1):
        for j in range(-nj, nj+1):
            for dx, dy in ((0.0, 0.0), (P/2, pitch/2)):     # the two columns
                x, y = i*P + dx, j*pitch + dy
                if math.hypot(x, y) <= lim:
                    out.append((x, y))
    return out

def perforate(disc, z0, z1, hole_r):
    cutters = None
    for x, y in hole_centres(hole_r):
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
# Both feed-throughs pass through CLEAR bores in the rear plate (cathode r14, injector r7 —
# verified: no body triangle touches either tube surface). The recurring "the body intersects
# the tube" report is NOT a real intersection: in the applet's cutaway/transparent view the
# discharge-chamber mesh depth-writes and used to occlude each tube's in-chamber length, so the
# rod appeared to stop (be "capped") right at the ionization chamber. The applet fixes that in
# gridded_ion.html buildModel/animate — it (a) draws both feed tubes OVER the ghosted/cut body
# (depthTest off) so they read as one continuous rod, and (b) extends each tube's chamber end a
# little deeper into the discharge chamber so a clear free length reads inside it. Those are
# render/readability patches on the (frozen) tessellated JSON; the parametric lengths below are
# left matching the STEP. If the model is ever re-tessellated, fold the extra reach in here.
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
