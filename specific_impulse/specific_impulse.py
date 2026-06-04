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
from matplotlib.widgets import Slider, RadioButtons, TextBox
from matplotlib.animation import FuncAnimation

# ── Constants ────────────────────────────────────────────────────────────────
G0 = 9.80665   # m/s²

# ── Propellant keys ──────────────────────────────────────────────────────────
PROP_KEYS = ['H\u2082O', 'Hydrazine', 'Argon', 'Lithium']

M_MOLAR = {
    'H\u2082O':   0.018015,
    'Hydrazine':  0.032045,
    'Argon':      0.039948,
    'Lithium':    0.006941,
}

LABELS    = [f'{k}  ({M_MOLAR[k] * 1e3:.4g} g/mol)' for k in PROP_KEYS]
LABEL_KEY = {lbl: key for lbl, key in zip(LABELS, PROP_KEYS)}

R_ORB = {
    'H\u2082O':   0.018,
    'Hydrazine':  0.025,
    'Argon':      0.030,
    'Lithium':    0.013,
}

ORB_COLOR = {
    'H\u2082O':   '#4fc3f7',
    'Hydrazine':  '#ff9800',
    'Argon':      '#ab47bc',
    'Lithium':    '#ef5350',
}

# ── Visual-scaling ceilings ───────────────────────────────────────────────────
# Max thrust: Ar 10 mol/s, 5000 kW, η=1  →  ~2000 N
# Max ve:     Li at low flow, 5000 kW    →  capped at 50 000 m/s for colour
MAX_THRUST_VIS = 2000.0
MAX_VE_VIS     = 50_000.0
MAX_ORBS       = 200


def compute(flow_mol_s, power_kW, eta, m_molar):
    """Return (thrust [N], mdot [kg/s], ve [m/s], Isp [s])."""
    mdot  = flow_mol_s * m_molar
    P_jet = power_kW * 1_000.0 * eta
    if mdot < 1e-12 or P_jet < 1e-12:
        return 0.0, 0.0, 0.0, 0.0
    ve     = np.sqrt(2.0 * P_jet / mdot)
    thrust = mdot * ve
    return thrust, mdot, ve, ve / G0


# ── Figure layout ─────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(13, 6), facecolor='white')
fig.suptitle('Thrust & Specific Impulse', fontsize=14, fontweight='bold', y=0.98)

ax   = fig.add_axes([0.02, 0.22, 0.44, 0.73], facecolor='#eaedff')
ax_o = fig.add_axes([0.02, 0.01, 0.44, 0.19])
ax.set_xlim(0, 10);  ax.set_ylim(0, 6);  ax.axis('off')
ax_o.axis('off')

# ── Spacecraft ────────────────────────────────────────────────────────────────
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
ax_r = fig.add_axes([0.48, 0.65, 0.30, 0.32], facecolor='white')
ax_r.set_title('Propellant', fontsize=9, pad=4)
radio = RadioButtons(ax_r, LABELS, active=0,
                     activecolor=ORB_COLOR[PROP_KEYS[0]])

for i, key in enumerate(PROP_KEYS):
    radio.labels[i].set_color(ORB_COLOR[key])
    radio.labels[i].set_fontsize(8.5)
    try:
        radio.circles[i].set_edgecolor(ORB_COLOR[key])
        if i == 0:
            radio.circles[i].set_facecolor(ORB_COLOR[key])
    except (AttributeError, IndexError):
        pass


def _slider(rect, label, lo, hi, v0, step=None):
    """
    lo   – range start    ← EDIT to change
    hi   – range end      ← EDIT to change
    v0   – initial value  ← EDIT to change
    step – snap size      ← EDIT to change  (None = continuous)
    """
    a  = fig.add_axes(rect)
    kw = dict(color='steelblue')
    if step is not None:
        kw['valstep'] = step
    return Slider(a, label, lo, hi, valinit=v0, **kw)


# ── Sliders ── lo ────── hi ───── v0 ── step ─────────────────────────────────
#   Slider width is 0.21 (shortened to make room for the textbox on the right)
sl_flow  = _slider([0.62, 0.54, 0.21, 0.04], 'Flow Rate\n(mol / s)',  0.0, 10.0,    0.5,  0.0001)
sl_power = _slider([0.62, 0.42, 0.21, 0.04], 'Power (kW)',            0.0,  5000.0, 10.0,  0.1)
sl_eta   = _slider([0.62, 0.30, 0.21, 0.04], 'Efficiency  η',         0.0,     1.0,  0.5,  0.01)

sl_flow .vline.set_visible(False)
sl_power.vline.set_visible(False)
sl_eta  .vline.set_visible(False)

# ── Typeable text boxes (one per slider, positioned immediately to the right) ─
def _textbox(rect, init_str):
    """Small entry box; no label; text centred."""
    return TextBox(fig.add_axes(rect), '', initial=init_str, textalignment='center')

#                       left   bottom  width  height
tb_flow  = _textbox([0.845,  0.540,  0.085, 0.040], f'{sl_flow.valinit:.4g}')
tb_power = _textbox([0.845,  0.420,  0.085, 0.040], f'{sl_power.valinit:.4g}')
tb_eta   = _textbox([0.845,  0.300,  0.085, 0.040], f'{sl_eta.valinit:.4g}')


# ── Bidirectional slider ↔ textbox connections ────────────────────────────────
def _link(slider, textbox):
    """Drag slider → refresh textbox.  Press Enter in textbox → move slider."""

    # Slider → TextBox  (fires every time the handle moves)
    def _slider_changed(val):
        textbox.set_val(f'{val:.4g}')

    slider.on_changed(_slider_changed)

    # TextBox → Slider  (fires only on Enter key)
    def _text_submitted(text):
        try:
            val = float(text)
            # Clamp to slider range
            val = float(np.clip(val, slider.valmin, slider.valmax))
            # Snap to nearest step if one is defined
            if slider.valstep is not None:
                steps = round((val - slider.valmin) / slider.valstep)
                val   = round(slider.valmin + steps * slider.valstep, 8)
                val   = float(np.clip(val, slider.valmin, slider.valmax))
            slider.set_val(val)
            # The slider.on_changed callback above then refreshes the
            # textbox with the properly snapped value automatically.
        except ValueError:
            pass   # silently ignore non-numeric input

    textbox.on_submit(_text_submitted)


for _sl, _tb in [(sl_flow, tb_flow), (sl_power, tb_power), (sl_eta, tb_eta)]:
    _link(_sl, _tb)

# ── Output panel ──────────────────────────────────────────────────────────────
# Three columns: Thrust | Mass Flow Rate | Specific Impulse
ax_o.axhline(0.92, color='black', lw=0.8)

ax_o.text(0.02, 1.00, 'Thrust',           fontsize=10, fontweight='bold',
          transform=ax_o.transAxes, va='top')
ax_o.text(0.36, 1.00, 'Mass Flow Rate',   fontsize=10, fontweight='bold',
          transform=ax_o.transAxes, va='top')
ax_o.text(0.65, 1.00, 'Specific Impulse', fontsize=10, fontweight='bold',
          transform=ax_o.transAxes, va='top')

t_T    = ax_o.text(0.02, 0.42, '0  N',
                    fontsize=13, transform=ax_o.transAxes, va='center')
t_mdot = ax_o.text(0.36, 0.42, '0  kg/s',
                    fontsize=13, transform=ax_o.transAxes, va='center',
                    color='darkorange')
t_Is   = ax_o.text(0.65, 0.68, '0  s',
                    fontsize=13, transform=ax_o.transAxes, va='center',
                    color='darkblue')
t_ve   = ax_o.text(0.65, 0.18, 'or  0  m/s',
                    fontsize=13, transform=ax_o.transAxes, va='center',
                    color='darkgreen')

# ── Animation state ───────────────────────────────────────────────────────────
orbs   = []
timer  = [0.0]
mstate = {'key': PROP_KEYS[0]}
DT     = 0.05


def on_radio(label):
    key = LABEL_KEY[label]
    mstate['key'] = key
    for o in orbs:
        o[3].remove()
    orbs.clear()
    timer[0] = 0.0
    try:
        for i, k in enumerate(PROP_KEYS):
            is_active = (k == key)
            radio.circles[i].set_facecolor(ORB_COLOR[k] if is_active else 'white')
            radio.circles[i].set_edgecolor(ORB_COLOR[k])
    except (AttributeError, IndexError):
        pass
    fig.canvas.draw_idle()


radio.on_clicked(on_radio)


def animate(_):
    key = mstate['key']
    thrust, mdot, ve, isp_s = compute(
        sl_flow.val, sl_power.val, sl_eta.val, M_MOLAR[key]
    )

    # ── Numeric readouts ──────────────────────────────────────────────────────
    t_T   .set_text(f'{thrust:.4g}  N')
    t_mdot.set_text(f'{mdot:.4g}  kg/s')
    t_Is  .set_text(f'{isp_s:.4g}  s')
    t_ve  .set_text(f'or  {ve:.4g}  m/s')

    # ── Thrust arrow ──────────────────────────────────────────────────────────
    if thrust > 1e-12:
        frac    = np.clip(thrust / MAX_THRUST_VIS, 0.0, 1.0)
        arw_len = 0.15 + 0.80 * frac
        acc_arrow.set_positions((ARROW_TAIL_X, CY), (ARROW_TAIL_X - arw_len, CY))
        acc_arrow.set_visible(True)
    else:
        acc_arrow.set_visible(False)

    # ── Visual exhaust speed ──────────────────────────────────────────────────
    ve_norm = np.sqrt(np.clip(ve / MAX_VE_VIS, 0.0, 1.0))
    v_vis   = 0.5 + 11.5 * ve_norm

    for o in orbs:
        o[2] = v_vis

    # ── Spawn particles  (mol/s → visual particles/s) ─────────────────────────
    if thrust > 1e-12:
        timer[0]  += DT
        spawn_rate = sl_flow.val * 4.0
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
        timer[0] = 0.0

    # ── Advance / remove orbs ─────────────────────────────────────────────────
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