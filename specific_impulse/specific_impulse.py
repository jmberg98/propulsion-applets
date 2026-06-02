#Created by Jordan Bergmann
#Created 6/1/2026

"""
Thrust & Specific Impulse — interactive applet prototype
MIT Propulsion

Physics (vacuum, negligible exit pressure):
  mdot   = flow_rate [mol/s] × M_molar [kg/mol]  →  [kg/s]
  P_jet  = power [kW] × 1000 × η                 →  [W]
  ve     = sqrt(2 × P_jet / mdot)                 →  [m/s]
  Thrust = mdot × ve                              →  [N]
  Isp    = ve / g₀                                →  [s]
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyArrowPatch
from matplotlib.widgets import Slider, RadioButtons
from matplotlib.animation import FuncAnimation

# ── Constants ────────────────────────────────────────────────────────────────
G0 = 9.80665   # m/s²

# ── Propellant table ─────────────────────────────────────────────────────────
LABELS = ['H\u2082O', 'Hydrazine', 'Argon', 'Lithium']

M_MOLAR = {                  # molar mass [kg/mol]
    'H\u2082O':   0.018015,  # water
    'Hydrazine':  0.032045,  # N₂H₄
    'Argon':      0.039948,  # Ar
    'Lithium':    0.006941,  # Li
}

# Particle radii — small, loosely proportional to molar mass
R_ORB = {
    'H\u2082O':   0.018,
    'Hydrazine':  0.025,
    'Argon':      0.030,
    'Lithium':    0.013,
}

# Per-propellant particle colours
ORB_COLOR = {
    'H\u2082O':   '#4fc3f7',  # sky blue
    'Hydrazine':  '#ff9800',  # amber
    'Argon':      '#ab47bc',  # purple
    'Lithium':    '#ef5350',  # red  (Li flame colour)
}

# ── Visual-scaling ceilings ───────────────────────────────────────────────────
# Max thrust ≈ 49 N   (Ar, 3 mol/s, 10 kW, η=1)
# Max ve     ≈ 17 km/s (Li, 0.01 mol/s, 10 kW, η=1)
MAX_THRUST_VIS = 50.0
MAX_VE_VIS     = 17_000.0
MAX_ORBS       = 200


def compute(flow_mol_s, power_kW, eta, m_molar):
    """Return (thrust [N], ve [m/s], Isp [s])."""
    mdot  = flow_mol_s * m_molar          # mol/s × kg/mol = kg/s
    P_jet = power_kW * 1_000.0 * eta      # kW → W, apply efficiency
    if mdot < 1e-12 or P_jet < 1e-12:
        return 0.0, 0.0, 0.0
    ve     = np.sqrt(2.0 * P_jet / mdot)
    thrust = mdot * ve
    return thrust, ve, ve / G0


# ── Figure layout ─────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(12, 6), facecolor='white')
fig.suptitle('Thrust & Specific Impulse', fontsize=14, fontweight='bold', y=0.98)

ax   = fig.add_axes([0.02, 0.22, 0.44, 0.73], facecolor='#eaedff')
ax_o = fig.add_axes([0.02, 0.01, 0.44, 0.19])
ax.set_xlim(0, 10);  ax.set_ylim(0, 6);  ax.axis('off')
ax_o.axis('off')

# ── Spacecraft (static) ───────────────────────────────────────────────────────
SX, SY, SW, SH = 1.1, 2.0, 2.6, 2.2
CY             = SY + SH / 2
NX             = SX + SW
EX             = NX + 0.35
ARROW_TAIL_X   = SX - 0.05

ax.add_patch(patches.Rectangle(
    (SX, SY), SW, SH, lw=2, edgecolor='black', facecolor='#cccccc', zorder=3
))
ax.plot([NX, EX], [CY + 0.35, CY + 0.15], 'k-', lw=2, zorder=3)
ax.plot([NX, EX], [CY - 0.35, CY - 0.15], 'k-', lw=2, zorder=3)

acc_arrow = FancyArrowPatch(
    posA=(ARROW_TAIL_X, CY), posB=(ARROW_TAIL_X - 0.5, CY),
    arrowstyle='->', mutation_scale=18,
    color='red', linewidth=2.5, zorder=4,
)
ax.add_patch(acc_arrow)
acc_arrow.set_visible(False)

ax.text(SX + SW / 2, CY + 0.15, 'a', color='red',
        fontsize=16, fontweight='bold', ha='center', va='center', zorder=5)
ax.text(0.3, 5.62, 'In space  ·  No gravity  ·  No drag',
        fontsize=8.5, color='dimgray')

# ── Right-side controls ───────────────────────────────────────────────────────
# Taller axes to fit 4 propellant radio options comfortably
ax_r = fig.add_axes([0.50, 0.65, 0.22, 0.32], facecolor='white')
ax_r.set_title('Propellant', fontsize=9, pad=4)
radio = RadioButtons(ax_r, LABELS, active=0,
                     activecolor=ORB_COLOR[LABELS[0]])

# Colour label text and radio-circle edges/fill per propellant
for i, key in enumerate(LABELS):
    radio.labels[i].set_color(ORB_COLOR[key])
    try:
        radio.circles[i].set_edgecolor(ORB_COLOR[key])
        if i == 0:   # first option starts active
            radio.circles[i].set_facecolor(ORB_COLOR[key])
    except (AttributeError, IndexError):
        pass


def _slider(rect, label, lo, hi, v0, step=None):
    a  = fig.add_axes(rect)
    kw = dict(color='steelblue')
    if step is not None:
        kw['valstep'] = step
    return Slider(a, label, lo, hi, valinit=v0, **kw)


sl_flow  = _slider([0.62, 0.54, 0.32, 0.04], 'Flow Rate\n(mol / s)', 0.0, 3.0, 0.5, 0.01)
sl_power = _slider([0.62, 0.42, 0.32, 0.04], 'Power (kW)',            0.0, 10.0, 1.0, 0.1)
sl_eta   = _slider([0.62, 0.30, 0.32, 0.04], 'Efficiency  η',         0.0, 1.0,  0.5, 0.01)

# ── Output panel ──────────────────────────────────────────────────────────────
ax_o.axhline(0.92, color='black', lw=0.8)
ax_o.text(0.04, 1.00, 'Thrust',           fontsize=10, fontweight='bold',
          transform=ax_o.transAxes, va='top')
ax_o.text(0.52, 1.00, 'Specific Impulse', fontsize=10, fontweight='bold',
          transform=ax_o.transAxes, va='top')

t_T  = ax_o.text(0.04, 0.48, '0  N',       fontsize=14, transform=ax_o.transAxes, va='center')
t_Is = ax_o.text(0.52, 0.68, '0  s',       fontsize=13, transform=ax_o.transAxes,
                  va='center', color='darkblue')
t_ve = ax_o.text(0.52, 0.18, 'or  0  m/s', fontsize=13, transform=ax_o.transAxes,
                  va='center', color='darkgreen')

# ── Animation state ───────────────────────────────────────────────────────────
orbs   = []
timer  = [0.0]
mstate = {'key': LABELS[0]}   # starts on H₂O
DT     = 0.05                 # simulated seconds per frame (~20 fps)


def on_radio(label):
    mstate['key'] = label
    for o in orbs:
        o[3].remove()
    orbs.clear()
    timer[0] = 0.0
    # Update radio circle fill/edge colours to reflect new selection
    try:
        for i, key in enumerate(LABELS):
            is_active = (key == label)
            radio.circles[i].set_facecolor(ORB_COLOR[key] if is_active else 'white')
            radio.circles[i].set_edgecolor(ORB_COLOR[key])
    except (AttributeError, IndexError):
        pass
    fig.canvas.draw_idle()


radio.on_clicked(on_radio)


def animate(_):
    key = mstate['key']
    thrust, ve, isp_s = compute(sl_flow.val, sl_power.val, sl_eta.val, M_MOLAR[key])

    # ── Numeric readouts ──────────────────────────────────────────────────────
    t_T .set_text(f'{thrust:.4g}  N')
    t_Is.set_text(f'{isp_s:.4g}  s')
    t_ve.set_text(f'or  {ve:.4g}  m/s')

    # ── Thrust arrow: length ∝ thrust ─────────────────────────────────────────
    if thrust > 1e-12:
        frac    = np.clip(thrust / MAX_THRUST_VIS, 0.0, 1.0)
        arw_len = 0.15 + 0.80 * frac
        acc_arrow.set_positions((ARROW_TAIL_X, CY), (ARROW_TAIL_X - arw_len, CY))
        acc_arrow.set_visible(True)
    else:
        acc_arrow.set_visible(False)

    # ── Visual speed: √-normalised over MAX_VE_VIS, range 0.5 – 12.0 ─────────
    ve_norm = np.sqrt(np.clip(ve / MAX_VE_VIS, 0.0, 1.0))
    v_vis   = 0.5 + 11.5 * ve_norm

    # Update all flying orbs to the current speed immediately
    for o in orbs:
        o[2] = v_vis

    # ── Spawn: mol/s × 4 = visual particles/s; suppressed when thrust == 0 ───
    if thrust > 1e-12:
        timer[0]  += DT
        spawn_rate = sl_flow.val * 4.0          # mol/s → visual particles/s
        interval   = 1.0 / max(spawn_rate, 0.01)
        while timer[0] >= interval:
            timer[0] -= interval
            if len(orbs) < MAX_ORBS:
                y0 = CY + np.random.uniform(-0.18, 0.18)
                c  = plt.Circle((EX, y0), R_ORB[key],
                                 color=ORB_COLOR[key], alpha=0.85, zorder=5)
                ax.add_patch(c)
                orbs.append([EX, y0, v_vis, c])
    else:
        timer[0] = 0.0   # reset: prevents burst when conditions return non-zero

    # ── Advance orbs; remove those that leave the canvas ──────────────────────
    dead = [o for o in orbs if o[0] > 10.5]
    for o in dead:
        o[3].remove()
        orbs.remove(o)
    for o in orbs:
        o[0]       += o[2] * DT
        o[3].center = (o[0], o[1])

    return []


ani = FuncAnimation(fig, animate, interval=50, blit=False, cache_frame_data=False)
plt.show()