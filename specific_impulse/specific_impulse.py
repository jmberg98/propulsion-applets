#Created by Jordan Bergmann
#Created 6/1/2026

"""
Thrust & Specific Impulse — interactive applet prototype
MIT Propulsion

Physics (vacuum, negligible exit pressure):
  mdot   = flow_rate [particles/s] × m_particle [kg]  →  [kg/s]
  P_jet  = power [W] × η                              →  [W]
  ve     = sqrt(2 × P_jet / mdot)                     →  [m/s]  (= Isp in m/s)
  Thrust = mdot × ve                                  →  [N]
  Isp    = ve / g₀                                    →  [s]
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.widgets import Slider, RadioButtons
from matplotlib.animation import FuncAnimation

# ── Constants ────────────────────────────────────────────────────────────────
G0 = 9.80665   # standard gravity, m/s²

LABELS = ['1 g (small)', '5 g (medium)', '25 g (large)']
M_KG   = {'1 g (small)': 0.001, '5 g (medium)': 0.005, '25 g (large)': 0.025}
R_ORB  = {'1 g (small)': 0.065, '5 g (medium)': 0.120, '25 g (large)': 0.210}

def compute(flow_rate, power_W, eta, m_kg):
    """Return (thrust [N], ve [m/s], Isp [s])."""
    mdot  = flow_rate * m_kg
    P_jet = power_W * eta
    if mdot < 1e-12 or P_jet < 1e-12:
        return 0.0, 0.0, 0.0
    ve     = np.sqrt(2.0 * P_jet / mdot)
    thrust = mdot * ve
    return thrust, ve, ve / G0

# ── Figure layout ─────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(12, 6), facecolor='white')
fig.suptitle('Thrust & Specific Impulse', fontsize=14, fontweight='bold', y=0.98)

ax   = fig.add_axes([0.02, 0.22, 0.44, 0.73], facecolor='#eaedff')  # animation canvas
ax_o = fig.add_axes([0.02, 0.01, 0.44, 0.19])                        # output panel
ax.set_xlim(0, 10);  ax.set_ylim(0, 6);  ax.axis('off')
ax_o.axis('off')

# ── Spacecraft (drawn once, static) ───────────────────────────────────────────
SX, SY, SW, SH = 1.1, 2.0, 2.6, 2.2   # body x, y, width, height
CY = SY + SH / 2                        # vertical centre-line
NX = SX + SW                            # nozzle root x
EX = NX + 0.35                          # nozzle exit x  (orb spawn point)

ax.add_patch(patches.Rectangle(
    (SX, SY), SW, SH, lw=2, edgecolor='black', facecolor='#cccccc', zorder=3
))
ax.plot([NX, EX], [CY + 0.35, CY + 0.15], 'k-', lw=2, zorder=3)   # upper nozzle lip
ax.plot([NX, EX], [CY - 0.35, CY - 0.15], 'k-', lw=2, zorder=3)   # lower nozzle lip
ax.annotate('', xy=(SX - 1.2, CY), xytext=(SX - 0.05, CY),
            arrowprops=dict(arrowstyle='->', color='red', lw=2.5), zorder=4)
ax.text(SX + SW/2, CY + 0.15, 'a', color='red',
        fontsize=16, fontweight='bold', ha='center', va='center', zorder=5)
ax.text(0.3, 5.62, 'In space  ·  No gravity  ·  No drag',
        fontsize=8.5, color='dimgray')

# ── Right-side controls ───────────────────────────────────────────────────────
# Radio: propellant mass per particle
ax_r = fig.add_axes([0.50, 0.73, 0.22, 0.22], facecolor='white')
ax_r.set_title('Propellant Mass\n(per particle)', fontsize=9, pad=4)
radio = RadioButtons(ax_r, LABELS, active=1, activecolor='steelblue')

def _slider(rect, label, lo, hi, v0, step=None):
    a  = fig.add_axes(rect)
    kw = dict(color='steelblue')
    if step is not None:
        kw['valstep'] = step
    return Slider(a, label, lo, hi, valinit=v0, **kw)

sl_flow  = _slider([0.62, 0.62, 0.32, 0.04], 'Flow Rate\n(particles / s)', 0.1, 10.0,  5.0, 0.1)
sl_power = _slider([0.62, 0.49, 0.32, 0.04], 'Power (W)',                   1.0, 100.0, 50.0)
sl_eta   = _slider([0.62, 0.36, 0.32, 0.04], 'Efficiency  η',               0.01, 1.0,   0.5)

# ── Output panel ──────────────────────────────────────────────────────────────
ax_o.axhline(0.92, color='black', lw=0.8)
ax_o.text(0.04, 1.00, 'Thrust',           fontsize=10, fontweight='bold',
          transform=ax_o.transAxes, va='top')
ax_o.text(0.52, 1.00, 'Specific Impulse', fontsize=10, fontweight='bold',
          transform=ax_o.transAxes, va='top')

t_T  = ax_o.text(0.04, 0.48, '---  N',       fontsize=14, transform=ax_o.transAxes, va='center')
t_Is = ax_o.text(0.52, 0.68, '---  s',       fontsize=13, transform=ax_o.transAxes,
                  va='center', color='darkblue')
t_ve = ax_o.text(0.52, 0.18, 'or  ---  m/s', fontsize=13, transform=ax_o.transAxes,
                  va='center', color='darkgreen')

# ── Orb animation state ───────────────────────────────────────────────────────
orbs   = []                       # each entry: [x, y, v_visual, Circle]
timer  = [0.0]                    # time accumulated since last spawn
mstate = {'key': '5 g (medium)'}
DT     = 0.05                     # simulated seconds per frame → ~20 fps

def on_radio(label):
    """Clear existing orbs when particle mass changes."""
    mstate['key'] = label
    for o in orbs:
        o[3].remove()
    orbs.clear()
    timer[0] = 0.0
    fig.canvas.draw_idle()

radio.on_clicked(on_radio)

def animate(_):
    key = mstate['key']
    thrust, ve, isp_s = compute(sl_flow.val, sl_power.val, sl_eta.val, M_KG[key])

    # Update numeric outputs
    t_T.set_text (f'{thrust:.5f}  N')
    t_Is.set_text(f'{isp_s:.2f}  s')
    t_ve.set_text(f'or  {ve:.2f}  m/s')

    # Spawn orbs at a rate matching the flow rate slider
    timer[0] += DT
    interval = 1.0 / max(sl_flow.val, 0.01)
    while timer[0] >= interval:
        timer[0] -= interval
        y0    = CY + np.random.uniform(-0.18, 0.18)
        # Visual speed: proportional to ve, clamped for readability
        #   ve = 0 m/s  → v_vis = 2.0  (baseline drift)
        #   ve = 500 m/s → v_vis = 5.0  (fast)
        v_vis = 2.0 + 3.0 * np.clip(ve / 500.0, 0.0, 1.0)
        c = plt.Circle((EX, y0), R_ORB[key], color='steelblue', alpha=0.85, zorder=5)
        ax.add_patch(c)
        orbs.append([EX, y0, v_vis, c])

    # Advance all orbs; remove those that leave the canvas
    dead = [o for o in orbs if o[0] > 10.5]
    for o in dead:
        o[3].remove()
        orbs.remove(o)
    for o in orbs:
        o[0] += o[2] * DT
        o[3].center = (o[0], o[1])

    return []

ani = FuncAnimation(fig, animate, interval=50, blit=False, cache_frame_data=False)
plt.show()