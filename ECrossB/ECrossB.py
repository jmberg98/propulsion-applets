#!/usr/bin/env python3
"""
ECrossB.py — E × B Drift Applet
Single-file, stdlib-only. Run: python ECrossB.py

Three modes, switchable live in the UI:
  Mode 1 — E field only (electrostatic accelerator):  v_e = sqrt(2 (|q|/m) |E| d)
  Mode 2 — E & B fields (single particle E×B drift / cycloid)
  Mode 3 — E×B drift for an ion and an electron simultaneously
"""

import json
import math
import webbrowser
from socketserver import ThreadingMixIn
from http.server import HTTPServer, BaseHTTPRequestHandler

class _Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True

AMU = 1.66053906660e-27
E_C = 1.602176634e-19


def _finite(name, val):
    if not math.isfinite(float(val)):
        raise ValueError(f"'{name}' must be a finite number.")


# ── Mode 1 — electrostatic acceleration ────────────────────────────────────────
def compute_accel(m_amu, q_e, d, E):
    for n, v in (("m_amu", m_amu), ("q_e", q_e), ("d", d), ("E", E)):
        _finite(n, v)
    if float(m_amu) <= 0:
        raise ValueError("Mass must be positive.")
    if float(d) <= 0:
        raise ValueError("Accelerator length d must be positive.")
    if float(E) < 0:
        raise ValueError("|E| must be non-negative.")

    m    = float(m_amu) * AMU
    q    = float(q_e) * E_C
    absq = abs(q)
    Ef   = float(E)
    df   = float(d)

    dV = Ef * df                              # ΔV = |E| d
    a  = q * Ef / m                           # signed acceleration along +x
    ve = math.sqrt(2.0 * absq * Ef * df / m)  # exhaust speed magnitude
    t_d = math.sqrt(2.0 * df / abs(a)) if a != 0 else None

    return {"mode": "accel", "ve": ve, "dV": dV, "a": a, "t_d": t_d,
            "stationary": (a == 0),           # q=0 or E=0 → no acceleration
            "sign": 1 if q > 0 else (-1 if q < 0 else 0)}


# ── Mode 2 / 3 — E × B drift ────────────────────────────────────────────────────
def compute_drift(m_amu, q_e, E, B):
    for n, v in (("m_amu", m_amu), ("q_e", q_e), ("E", E), ("B", B)):
        _finite(n, v)
    if float(m_amu) <= 0:
        raise ValueError("Mass must be positive.")
    if float(B) < 0:
        raise ValueError("|B| must be non-negative.")
    if float(E) < 0:
        raise ValueError("|E| must be non-negative.")

    m    = float(m_amu) * AMU
    q    = float(q_e) * E_C
    absq = abs(q)
    Bf   = float(B)
    Ef   = float(E)
    sign = 1 if q > 0 else (-1 if q < 0 else 0)

    # No charge → no force → the particle stays put.
    if q == 0:
        return {"mode": "drift", "stationary": True, "B_zero": False,
                "omega_c": 0.0, "v_drift": 0.0, "r_L": 0.0, "T_c": None,
                "v_gyro": 0.0, "a": 0.0, "sign": 0}

    # No magnetic field → straight-line acceleration along the E direction (±ĵ).
    if Bf == 0:
        a = q * Ef / m                        # signed acceleration along +ĵ
        return {"mode": "drift", "B_zero": True, "stationary": (Ef == 0),
                "omega_c": 0.0, "v_drift": 0.0, "r_L": None, "T_c": None,
                "v_gyro": 0.0, "a": a, "sign": sign}

    omega   = q * Bf / m            # signed cyclotron frequency (sign = rotation sense)
    v_drift = Ef / Bf               # |E|/|B|, charge-independent, along +x
    v_gyro  = Ef / Bf               # gyro speed for a particle released from rest (cycloid)
    r_L     = m * v_gyro / (absq * Bf)   # = m|E| / (|q| B^2)
    T_c     = 2.0 * math.pi / abs(omega) if omega != 0 else None

    return {"mode": "drift", "omega_c": omega, "v_drift": v_drift,
            "r_L": r_L, "T_c": T_c, "v_gyro": v_gyro,
            "B_zero": False, "stationary": (Ef == 0), "a": 0.0,
            "sign": sign}


def compute(payload):
    mode = payload.get("mode")
    if mode == "accel":
        return compute_accel(payload["m_amu"], payload["q_e"],
                             payload["d"], payload["E"])
    elif mode == "drift":
        return compute_drift(payload["m_amu"], payload["q_e"],
                             payload["E"], payload["B"])
    raise ValueError(f"Unknown mode '{mode}'.")


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>E &#215; B Drift Applet</title>
<script type="importmap">
{"imports":{
  "three":"https://unpkg.com/three@0.160.0/build/three.module.js",
  "three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"
}}
</script>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{
  display:flex;height:100vh;
  background:#0b0e14;color:#cfd8dc;
  font-family:'Segoe UI',system-ui,sans-serif;font-size:13px;
  overflow:hidden;
}
#panel{
  width:300px;min-width:300px;
  display:flex;flex-direction:column;gap:12px;
  background:#111720;border-right:1px solid #1e2a35;
  padding:16px 14px 14px;overflow-y:auto;
}
h1{font-size:13px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
   color:#90caf9;padding-bottom:8px;border-bottom:1px solid #1e2a35;}
.sec{font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:#546e7a;margin-bottom:6px;}
.field{display:flex;flex-direction:column;gap:3px}
.field label{font-size:11px;color:#90a4ae}
input[type="number"],select{
  background:#0d1117;border:1px solid #263238;border-radius:4px;
  color:#eceff1;padding:5px 8px;font-size:12px;outline:none;width:100%;transition:border-color .15s;}
input[type="number"]:focus,select:focus{border-color:#42a5f5}
input:disabled,select:disabled{opacity:.5;cursor:not-allowed}
input[type="range"]{
  -webkit-appearance:none;appearance:none;width:100%;height:4px;border-radius:3px;
  background:#1c2733;outline:none;margin:7px 0 1px;cursor:pointer;}
input[type="range"]::-webkit-slider-thumb{
  -webkit-appearance:none;appearance:none;width:15px;height:15px;border-radius:50%;
  background:#42a5f5;border:2px solid #0d1117;cursor:pointer;transition:background .15s;}
input[type="range"]::-webkit-slider-thumb:hover{background:#64b5f6}
input[type="range"]::-moz-range-thumb{width:15px;height:15px;border-radius:50%;
  background:#42a5f5;border:2px solid #0d1117;cursor:pointer;}
.field label .val{float:right;color:#4fc3f7;
  font-family:'Cascadia Code','Fira Mono',monospace;font-weight:600;}
/* typable value field that mirrors each slider */
.valnum{float:right;width:82px;background:#0d1117;border:1px solid #263238;border-radius:4px;
  color:#4fc3f7;font-family:'Cascadia Code','Fira Mono',monospace;font-weight:600;font-size:11px;
  text-align:right;padding:1px 5px;outline:none;-moz-appearance:textfield;transition:border-color .15s;}
.valnum:focus{border-color:#42a5f5}
.valnum::-webkit-outer-spin-button,.valnum::-webkit-inner-spin-button{-webkit-appearance:none;margin:0}
.row2{display:flex;gap:6px}
.row2 input{flex:1}
.row2 select{width:52px;flex:none}
.readout{font-size:10px;color:#607d8b;margin-top:2px}
.readout b{color:#90caf9;font-family:'Cascadia Code','Fira Mono',monospace;font-weight:600}
.pblock{background:#0d1117;border:1px solid #182330;border-radius:6px;
        padding:11px;display:flex;flex-direction:column;gap:9px;}
.phead{font-size:11px;font-weight:600;letter-spacing:.04em;color:#b0bec5;
       display:flex;align-items:center;padding-bottom:4px;border-bottom:1px solid #182330;}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:8px}
.chk{display:flex;align-items:center;gap:8px;font-size:11px;color:#90a4ae;cursor:pointer;
     user-select:none;background:#0d1117;border:1px solid #182330;border-radius:5px;padding:7px 10px;}
.chk input{accent-color:#42a5f5;width:14px;height:14px}
/* ── mode tabs ── */
#tabs{display:flex;gap:4px}
.tab{flex:1;background:#0d1117;border:1px solid #263238;border-radius:5px;color:#90a4ae;
     cursor:pointer;font-size:11px;font-weight:600;padding:8px 4px;text-align:center;
     transition:background .15s,color .15s,border-color .15s;letter-spacing:.02em;}
.tab:hover{background:#16202c}
.tab.active{background:#1565c0;border-color:#1565c0;color:#fff}
.tab small{display:block;font-size:9px;font-weight:400;opacity:.85;margin-top:2px}
#otable{width:100%;border-collapse:collapse;font-size:10px}
#otable th{font-size:9px;color:#546e7a;text-transform:uppercase;letter-spacing:.05em;
           padding:3px 4px;text-align:right;font-weight:700;}
#otable th:first-child{text-align:left}
#otable td{padding:3px 4px;font-family:'Cascadia Code','Fira Mono',monospace;
           text-align:right;color:#4fc3f7;}
#otable td:first-child{text-align:left;color:#607d8b;
                       font-family:'Segoe UI',sans-serif;font-size:10px;}
#otable tr+tr td{border-top:1px solid #141d27}
.col-B.hide,.m-only.hide{display:none}
#error-msg{background:#4a0000;border:1px solid #c62828;border-radius:4px;
           color:#ef9a9a;font-size:11px;padding:7px 9px;display:none;}
#legend{margin-top:auto;background:#0d1117;border:1px solid #182330;
        border-radius:5px;padding:8px 10px;font-size:10px;line-height:2.0;}
#legend span.sw{display:inline-block;width:9px;height:9px;border-radius:50%;
             margin-right:6px;vertical-align:middle;}
#legend .row.hide{display:none}
#viewport{flex:1;overflow:hidden;position:relative}
#viewport canvas{display:block}
.hide{display:none}
</style>
</head>
<body>

<div id="panel">
  <h1>E &#215; B Drift</h1>

  <!-- ── mode tabs ── -->
  <div id="tabs">
    <div class="tab active" data-mode="accel">Mode 1<small>E field</small></div>
    <div class="tab" data-mode="drift">Mode 2<small>E &amp; B</small></div>
    <div class="tab" data-mode="pair">Mode 3<small>ion + e&#8315;</small></div>
  </div>

  <!-- ══ single-particle block (Modes 1 & 2) ══ -->
  <div class="pblock" id="block-S">
    <div class="phead"><span class="dot" style="background:#ff7043"></span><span id="S-head">Particle</span></div>
    <div class="field">
      <label>Preset</label>
      <select id="S-preset">
        <option value="custom">Custom</option>
        <option value="xenon" selected>Xenon&#8314; (131.29 amu)</option>
        <option value="krypton">Krypton&#8314; (83.80 amu)</option>
        <option value="argon">Argon&#8314; (39.95 amu)</option>
        <option value="iodine">Iodine&#8314; (126.90 amu)</option>
        <option value="electron" id="S-opt-electron">Electron (e&#8315;)</option>
      </select>
    </div>
    <div class="field">
      <label>Mass <i>m</i> [amu] <input type="number" class="valnum" id="S-mass-v" min="0" step="0.1" value="131.3"></label>
      <input type="range" id="S-mass" min="-4" max="2.5" step="0.01" value="2.1184">
    </div>
    <div class="field">
      <label>Charge <i>q</i> [e] <input type="number" class="valnum" id="S-q-v" min="-3" max="3" step="1" value="1"></label>
      <input type="range" id="S-q" min="-3" max="3" step="1" value="1">
    </div>
  </div>

  <!-- ══ ion block (Mode 3) ══ -->
  <div class="pblock hide" id="block-A">
    <div class="phead"><span class="dot" style="background:#ff7043"></span><span>Ion (clockwise)</span></div>
    <div class="field">
      <label>Preset</label>
      <select id="A-preset">
        <option value="custom">Custom</option>
        <option value="xenon" selected>Xenon&#8314; (131.29 amu)</option>
        <option value="krypton">Krypton&#8314; (83.80 amu)</option>
        <option value="argon">Argon&#8314; (39.95 amu)</option>
        <option value="iodine">Iodine&#8314; (126.90 amu)</option>
      </select>
    </div>
    <div class="field">
      <label>Mass <i>m</i> [amu] <input type="number" class="valnum" id="A-mass-v" min="0" step="0.1" value="131.3"></label>
      <input type="range" id="A-mass" min="-4" max="2.5" step="0.01" value="2.1184">
    </div>
    <div class="field">
      <label>Charge <i>q</i> [e] <input type="number" class="valnum" id="A-q-v" min="-3" max="3" step="1" value="1"></label>
      <input type="range" id="A-q" min="-3" max="3" step="1" value="1">
    </div>
  </div>

  <!-- ══ electron block (Mode 3) ══ -->
  <div class="pblock hide" id="block-B">
    <div class="phead"><span class="dot" style="background:#4fc3f7"></span><span>Electron (counter-cw)</span></div>
    <div class="field">
      <label>Mass <i>m</i> [amu] <input type="number" class="valnum" id="B-mass-v" min="0" step="0.0001" value="5.49e-4"></label>
      <input type="range" id="B-mass" min="-4" max="2.5" step="0.01" value="-3.2609">
    </div>
    <div class="field">
      <label>Charge <i>q</i> [e] <input type="number" class="valnum" id="B-q-v" min="-3" max="3" step="1" value="-1"></label>
      <input type="range" id="B-q" min="-3" max="3" step="1" value="-1">
    </div>
  </div>

  <!-- ══ Mode 1 fields ══ -->
  <div id="grp-accel">
    <div class="field">
      <label>Accelerator length <i>d</i> [m] <input type="number" class="valnum" id="d-v" min="0.001" step="0.005" value="0.050"></label>
      <input type="range" id="inp-d" value="0.35" min="0.005" max="0.5" step="0.005">
    </div>
    <div class="field" style="margin-top:8px">
      <label>Field strength |<b style="color:#ef5350">E</b>| [V/m] <input type="number" class="valnum" id="E1-v" min="0" step="500" value="20000"></label>
      <input type="range" id="inp-E1" value="20000" min="0" max="50000" step="500">
    </div>
    <div class="field" style="margin-top:8px">
      <label>Potential &#916;V [V] <input type="number" class="valnum" id="dV-v" min="0" step="100" value="1000"></label>
      <input type="range" id="inp-dV" value="1000" min="0" max="25000" step="100">
      <div class="readout"><i>&#916;V = |E| d</i></div>
    </div>
  </div>

  <!-- ══ Mode 2/3 fields ══ -->
  <div id="grp-drift" class="hide">
    <div class="field">
      <label>Field strength |<b style="color:#ef5350">E</b>| [V/m] <input type="number" class="valnum" id="E2-v" min="0" step="500" value="10000"></label>
      <input type="range" id="inp-E2" value="10000" min="0" max="50000" step="500">
    </div>
    <div class="field" style="margin-top:8px">
      <label>Flux density |<b style="color:#5c6bc0">B</b>| [G] <input type="number" class="valnum" id="B-v" min="0" max="5000" step="50" value="1000"></label>
      <input type="range" id="inp-B" value="1000" min="0" max="5000" step="50">
      <div class="readout">Equivalent: <b id="b-tesla">0.1000 T</b></div>
    </div>
  </div>

  <!-- ── overlay toggles ── -->
  <label class="chk" for="chk-labels">
    <input type="checkbox" id="chk-labels" checked>
    Show charge labels &amp; axes
  </label>
  <label class="chk" for="chk-vel">
    <input type="checkbox" id="chk-vel" checked>
    Show velocity <b style="color:#ffd54f">v</b>
  </label>
  <label class="chk m-only drift hide" for="chk-drift">
    <input type="checkbox" id="chk-drift" checked>
    Show drift <b style="color:#66bb6a">v<sub>d</sub></b>
  </label>
  <label class="chk" for="chk-fe">
    <input type="checkbox" id="chk-fe">
    Show electric force <b style="color:#ef5350">F<sub>E</sub></b>
  </label>
  <label class="chk m-only drift hide" for="chk-fb">
    <input type="checkbox" id="chk-fb">
    Show magnetic force <b style="color:#5c6bc0">F<sub>B</sub></b>
  </label>
  <label class="chk m-only drift hide" for="chk-fnet">
    <input type="checkbox" id="chk-fnet">
    Show net force <b style="color:#ffffff">F<sub>net</sub></b>
  </label>

  <div id="error-msg"></div>

  <div>
    <div class="sec">Outputs</div>
    <table id="otable">
      <tr>
        <th></th>
        <th id="th-A" style="color:#ff7043">Particle</th>
        <th id="th-B" class="col-B hide" style="color:#4fc3f7">Electron</th>
      </tr>
      <!-- accel rows -->
      <tr class="r-accel"><td>v<sub>e</sub> [m/s]</td><td id="A-ve">&#x2014;</td><td class="col-B hide">&#x2014;</td></tr>
      <tr class="r-accel"><td>&#916;V [V]</td>        <td id="A-dV">&#x2014;</td><td class="col-B hide">&#x2014;</td></tr>
      <tr class="r-accel"><td>a [m/s&#178;]</td>      <td id="A-acc">&#x2014;</td><td class="col-B hide">&#x2014;</td></tr>
      <!-- drift rows -->
      <tr class="r-drift hide"><td>v<sub>drift</sub> [m/s]</td><td id="A-vd">&#x2014;</td><td id="B-vd" class="col-B hide">&#x2014;</td></tr>
      <tr class="r-drift hide"><td>&#969;<sub>c</sub> [rad/s]</td><td id="A-wc">&#x2014;</td><td id="B-wc" class="col-B hide">&#x2014;</td></tr>
      <tr class="r-drift hide"><td>r<sub>L</sub> [m]</td>        <td id="A-rL">&#x2014;</td><td id="B-rL" class="col-B hide">&#x2014;</td></tr>
      <tr class="r-drift hide"><td>T<sub>c</sub> [s]</td>        <td id="A-Tc">&#x2014;</td><td id="B-Tc" class="col-B hide">&#x2014;</td></tr>
    </table>
  </div>

  <div id="legend">
    <div class="row"><span class="sw" style="background:#ff7043"></span><b id="leg-A">Particle</b></div>
    <div class="row col-B hide"><span class="sw" style="background:#4fc3f7"></span>Electron</div>
    <div class="row"><span class="sw" style="background:#ffd54f"></span>v velocity</div>
    <div class="row drift hide"><span class="sw" style="background:#66bb6a"></span>v<sub>d</sub> E&#215;B drift</div>
    <div class="row"><span class="sw" style="background:#ef5350"></span><b style="color:#ef5350">E</b> field</div>
    <div class="row drift hide"><span class="sw" style="background:#5c6bc0"></span><b style="color:#5c6bc0">B</b> field (out of screen)</div>
  </div>
</div>

<div id="viewport"></div>

<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ── constants ───────────────────────────────────────────────────────────────
const SCENE_R        = 5.0;
const GAUSS_TO_TESLA = 1e-4;
const END_PAUSE      = 0.6;
const AMU            = 1.66053906660e-27;
const E_C            = 1.602176634e-19;

// accelerator (Mode 1)
const ACCEL_D     = SCENE_R * 1.55;   // scene length of the accelerator gap (reference)
const ACCEL_SEC   = 4.0;              // wall-clock time to cross the gap (reference)
const D_REF1      = 0.05;             // reference accelerator length [m]
// reference crossing time & exhaust speed (default xenon+, E=20000 V/m, d=0.05 m)
const T_D_REF     = Math.sqrt(2*D_REF1 / (E_C*20000/(131.293*AMU)));
const VE_REF      = Math.sqrt(2*E_C*20000*D_REF1/(131.293*AMU));
const E_REF1      = 20000;            // reference |E| for force-arrow scaling [V/m]

// drift (Mode 2/3)
const DRIFT_W     = SCENE_R * 3.0;    // scene width swept by the drift
const DRIFT_SEC   = 9.0;              // wall-clock time to sweep across
const ARCH_BASE   = 1.0;              // arches a reference ion shows (fewer → larger humps)
const ARCH_MIN    = 1;
// Ion arches are capped LOW so ion loops always stay large — they never shrink into the
// electron's range. Worst case (ion at ARCH_MAX, electron at ARCH_E_MIN) the electron still
// has 3× more arches, so the ion loop is always clearly the bigger of the two.
const ARCH_MAX    = 4;                // hard floor on ion loop size (large, never tiny)
const E_REF2      = 10000;            // reference |E| for drift force-arrow scaling [V/m]
// reference Larmor radius (xenon+, E=10000 V/m, B=0.1 T): sets the arch count
const R_L_REF     = (131.293*AMU)*E_REF2 / (E_C*0.1*0.1);
// The electron's true r_L is ~5 orders of magnitude smaller than the ion's, so feeding it
// through archesFor() always pins it at ARCH_MAX — its loops never respond to E or B. Give
// it its OWN reference r_L (electron, E=10000 V/m, B=0.1 T) and a compressed mapping so the
// loop count lands in a readable band and still grows with B (and shrinks with E).
const R_L_REF_E   = (5.48579909e-4*AMU)*E_REF2 / (E_C*0.1*0.1);
// Electron arches live in a band that starts ABOVE the ion's max (ARCH_MAX=4) so electron
// loops are always smaller than ion loops, and run very high so the loops get very, very
// tight at maximum B. base·(factor)^exp with factor=(E_REF2/E)·(B/0.1)² ⇒ ≈16 at the
// reference field, ≈80 (tiny) at full B.
const ARCH_E_BASE = 16;               // electron arches at the reference field (more → smaller loops)
const ARCH_E_EXP  = 0.5;              // map the wide r_L range across the legible band
const ARCH_E_MIN  = 12;               // always > ARCH_MAX ⇒ electron loop always < ion loop
const ARCH_E_MAX  = 80;               // very high cap ⇒ very, very small loops at max B
// reference E×B drift speed (E_REF2, B=0.1 T) = 1e5 m/s; sets the drift-arrow length
const V_DRIFT_REF = E_REF2 / 0.1;
// smoothstep duration for cycloid path resizing (demos 2 & 3) when a slider drags
const R_TWEEN_SEC = 0.45;

const clamp = (x,a,b) => Math.min(b, Math.max(a, x));

const PRESETS = {
  custom:   null,
  xenon:    { m: 131.293,        q: +1 },
  krypton:  { m: 83.798,         q: +1 },
  argon:    { m: 39.948,         q: +1 },
  iodine:   { m: 126.90447,      q: +1 },
  electron: { m: 5.48579909e-4,  q: -1 },
};

const COL = {
  ion:   0xff7043,
  elec:  0x4fc3f7,
  vel:   0xffd54f,
  drift: 0x66bb6a,
  E:     0xef5350,
  B:     0x5c6bc0,
  Fres:  0xffffff,
};

let mode = 'accel';          // 'accel' | 'drift' | 'pair'
let dragging = false;        // true while a drift/pair slider is held (particle hidden)
let showLabels = true, showVel = true, showDrift = true;
let showFE = false, showFB = false, showFnet = false;
let accelGrid = null, accelGridX = 0;   // Mode-1 exit grid (fades as particle passes)

// ── generic rounded-rect text sprite ──────────────────────────────────────────
function makeTextSprite(text, color, height = SCENE_R * 0.28) {
  const canvas = document.createElement('canvas');
  const ctx    = canvas.getContext('2d');
  const fs = 72, px = 24, py = 16;

  ctx.font = `700 ${fs}px Segoe UI,Arial,sans-serif`;
  const tw = ctx.measureText(text).width;
  canvas.width  = Math.ceil(tw + px*2);
  canvas.height = Math.ceil(fs*1.25 + py*2);

  ctx.font = `700 ${fs}px Segoe UI,Arial,sans-serif`;
  ctx.fillStyle = 'rgba(11,14,20,0.72)';
  ctx.strokeStyle = 'rgba(207,216,220,0.25)';
  ctx.lineWidth = 4;

  const r = 18, [x,y,w,h] = [2,2,canvas.width-4,canvas.height-4];
  ctx.beginPath();
  ctx.moveTo(x+r,y); ctx.lineTo(x+w-r,y);
  ctx.quadraticCurveTo(x+w,y,x+w,y+r); ctx.lineTo(x+w,y+h-r);
  ctx.quadraticCurveTo(x+w,y+h,x+w-r,y+h); ctx.lineTo(x+r,y+h);
  ctx.quadraticCurveTo(x,y+h,x,y+h-r); ctx.lineTo(x,y+r);
  ctx.quadraticCurveTo(x,y,x+r,y); ctx.closePath();
  ctx.fill(); ctx.stroke();

  ctx.fillStyle = color;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, canvas.width/2, canvas.height/2);

  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({
    map:tex, transparent:true, depthTest:false, depthWrite:false
  }));
  sp.scale.set(height*(canvas.width/canvas.height), height, 1);
  sp.renderOrder = 999;
  return sp;
}

// ── scene globals ─────────────────────────────────────────────────────────────
let renderer, scene, camera, controls, clock;
let fieldGroup, guideGroup, axisGroup;
let parts = [];

let cycleT = 0, cyclePauseT = 0;
function resetCycle() { cycleT = 0; cyclePauseT = 0; }

// ── charge sprite ─────────────────────────────────────────────────────────────
function setChargeSprite(p, sign) {
  if (p.chargeSprite && p.curSign === sign) return;
  if (p.chargeSprite) {
    scene.remove(p.chargeSprite);
    if (p.chargeSprite.material.map) p.chargeSprite.material.map.dispose();
    p.chargeSprite.material.dispose();
  }
  const hexC  = '#'+p.color.toString(16).padStart(6,'0');
  const glyph = sign < 0 ? '−' : (sign > 0 ? '+' : '0');
  p.chargeSprite = makeTextSprite(glyph, hexC, SCENE_R*0.40);
  scene.add(p.chargeSprite);
  p.curSign = sign;
}

// ── build one particle ────────────────────────────────────────────────────────
function makeParticle(color, sphereScale) {
  const p = { color, data:null, cur:null, chargeSprite:null, curSign:null };

  p.mesh = new THREE.Mesh(
    new THREE.SphereGeometry(SCENE_R*sphereScale, 24, 24),
    new THREE.MeshStandardMaterial({ color, emissive:color, emissiveIntensity:0.45,
                                     roughness:0.3, transparent:true })
  );
  scene.add(p.mesh);

  // vibrant particle path
  p.trail = new THREE.Line(
    new THREE.BufferGeometry(),
    new THREE.LineBasicMaterial({ color, transparent:true, opacity:0.92 })
  );
  scene.add(p.trail);

  const mkArrow = (c, len) => {
    const a = new THREE.ArrowHelper(new THREE.Vector3(1,0,0), new THREE.Vector3(),
                                    len, c, len*0.28, len*0.16);
    a.visible = false; scene.add(a); return a;
  };
  p.velArrow   = mkArrow(COL.vel,   SCENE_R*0.85);
  p.driftArrow = mkArrow(COL.drift, SCENE_R*0.9);
  p.feArrow    = mkArrow(COL.E,     SCENE_R*0.7);
  p.fbArrow    = mkArrow(COL.B,     SCENE_R*0.7);
  p.fnetArrow  = mkArrow(COL.Fres,  SCENE_R*0.7);

  const mkLabel = (txt, hex) => {
    const s = makeTextSprite(txt, hex, SCENE_R*0.24); s.visible = false; scene.add(s); return s;
  };
  p.velLabel   = mkLabel('v',     '#ffd54f');
  p.driftLabel = mkLabel('v_d',   '#66bb6a');
  p.feLabel    = mkLabel('F_E',   '#ef5350');
  p.fbLabel    = mkLabel('F_B',   '#5c6bc0');
  p.fnetLabel  = mkLabel('F_net', '#ffffff');
  return p;
}

// ── init ──────────────────────────────────────────────────────────────────────
function initViz(container) {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b0e14);

  const w = container.clientWidth, h = container.clientHeight;
  renderer = new THREE.WebGLRenderer({ antialias:true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(w,h);
  container.appendChild(renderer.domElement);

  camera = new THREE.PerspectiveCamera(50, w/h, 0.01, 5000);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.07;

  scene.add(new THREE.AmbientLight(0xffffff, 0.6));
  const dl = new THREE.DirectionalLight(0xffffff, 0.8);
  dl.position.set(1,2,3); scene.add(dl);

  fieldGroup = new THREE.Group();
  guideGroup = new THREE.Group();
  axisGroup  = new THREE.Group();
  scene.add(fieldGroup, guideGroup, axisGroup);

  buildAxes();
  clock = new THREE.Clock();

  window.addEventListener('resize', () => {
    const w2 = container.clientWidth, h2 = container.clientHeight;
    camera.aspect = w2/h2; camera.updateProjectionMatrix();
    renderer.setSize(w2,h2);
  });

  animate();
}

// ── axis triad (î ĵ k̂) ────────────────────────────────────────────────────────
function buildAxes() {
  axisGroup.clear();
  const o = new THREE.Vector3(-SCENE_R*1.35, -SCENE_R*1.15, 0);
  const L = SCENE_R*0.55;
  const mk = (dir, col, lbl) => {
    axisGroup.add(new THREE.ArrowHelper(dir, o, L, col, L*0.25, L*0.16));
    const s = makeTextSprite(lbl, '#'+col.toString(16).padStart(6,'0'), SCENE_R*0.2);
    s.position.copy(o).addScaledVector(dir, L*1.2);
    axisGroup.add(s);
  };
  mk(new THREE.Vector3(1,0,0), 0xe57373, 'î');       // î
  mk(new THREE.Vector3(0,1,0), 0x81c784, 'ĵ');       // ĵ
  mk(new THREE.Vector3(0,0,1), 0x9fa8da, 'k̂');      // k̂
}

// ── field arrow with adjustable opacity (transparent field lattices) ───────────
function mkFieldArrow(dir, pos, len, color, opacity, head, headW) {
  const a = new THREE.ArrowHelper(dir, pos, len, color, head, headW);
  a.line.material.transparent = true; a.line.material.opacity = opacity;
  a.cone.material.transparent = true; a.cone.material.opacity = opacity;
  return a;
}

// ════════════════════════════════════════════════════════════════════════════
//  FIELD VISUALS
// ════════════════════════════════════════════════════════════════════════════
function buildField() {
  fieldGroup.clear();
  guideGroup.clear();
  accelGrid = null;

  if (mode === 'accel') buildFieldAccel();
  else                  buildFieldDrift();
}

// scene length of the Mode-1 gap, scaled by the user's d input.
// sqrt mapping compresses the dynamic range so short chambers don't snap to a
// floor (no "massive jump" at small d) while long chambers stay readable.
function sceneAccelD() {
  const d = (window._lastAccel && window._lastAccel.d) ? window._lastAccel.d : D_REF1;
  // Map the full d-slider span [0.005, 0.5] m monotonically onto the visual gap
  // length: every increase in d now lengthens the gap (no plateau past 0.225 m).
  // Endpoints are pinned so the shortest gap (slider min) and longest gap (slider
  // max) keep the same visual length as before — the max simply now lands at d=0.5.
  const dLo = 0.005, dHi = 0.5;
  const fMin = Math.sqrt(dLo   / D_REF1);   // visual factor at the slider minimum
  const fMax = Math.sqrt(0.225 / D_REF1);   // visual factor at the slider maximum
  const t = clamp((Math.sqrt(d)   - Math.sqrt(dLo)) /
                  (Math.sqrt(dHi) - Math.sqrt(dLo)), 0, 1);
  return ACCEL_D * (fMin + (fMax - fMin) * t);
}

function buildFieldAccel() {
  // E field arrows along +î across the gap; an entry source and an exit grid at +d.
  const sign  = (parts[0] && parts[0].data) ? parts[0].data.sign : 1;
  const sD    = sceneAccelD();
  const halfY = SCENE_R*0.95, halfZ = SCENE_R*0.95;
  const rows  = [-1,0,1];

  // E lattice fills the gap from the source (x=0) to the grid (x=sign*sD),
  // oriented along the acceleration direction (sign).
  const baseX = -sign*SCENE_R*0.1;          // base sits just behind the source
  const len   = sD + SCENE_R*0.2;
  for (const iy of rows) for (const iz of rows) {
    const y = iy*halfY*0.85, z = iz*halfZ*0.85;
    fieldGroup.add(mkFieldArrow(
      new THREE.Vector3(sign,0,0), new THREE.Vector3(baseX, y, z),
      len, COL.E, 0.5, SCENE_R*0.2, SCENE_R*0.09
    ));
  }

  // accelerating charged plate at the origin (x=0): a stubby disk the ions launch from.
  // Cylinder axis is along +y by default; rotate onto +x so the flat face fronts the gap.
  const plateGrp = new THREE.Group();
  const disk = new THREE.Mesh(
    new THREE.CylinderGeometry(SCENE_R*0.62, SCENE_R*0.62, SCENE_R*0.14, 40),
    new THREE.MeshStandardMaterial({ color:0xb0623a, emissive:0x3a1c0e,
                                     emissiveIntensity:0.5, metalness:0.6, roughness:0.45 })
  );
  disk.rotation.z = Math.PI/2;
  // sit just behind the source so ions emerge from its downstream face
  disk.position.x = -sign*SCENE_R*0.07;
  plateGrp.add(disk);
  // a faint "+" on the plate face to read it as the positive accelerating electrode
  const plus = makeTextSprite('+', '#ffd0b0', SCENE_R*0.3);
  plus.position.set(-sign*SCENE_R*0.16, 0, 0);
  plateGrp.add(plus);
  guideGroup.add(plateGrp);

  // exit grid plate a distance d from the source; faded live as the particle passes
  const gx = sign*sD;
  const plate = new THREE.GridHelper(SCENE_R*1.8, 9, 0x607d8b, 0x37474f);
  plate.rotation.z = Math.PI/2;          // make it lie in the j-k plane
  plate.position.x = gx;
  plate.material.transparent = true; plate.material.opacity = 0.55;
  guideGroup.add(plate);
  accelGrid = plate; accelGridX = gx;

  // d dimension label
  const dTxt = (window._lastAccel && window._lastAccel.d != null)
             ? ('d = ' + window._lastAccel.d + ' m') : 'd';
  const dl = makeTextSprite(dTxt, '#90a4ae', SCENE_R*0.24);
  dl.position.set(gx*0.5, -SCENE_R*0.55, 0);
  guideGroup.add(dl);

  const eLbl = makeTextSprite('E', '#ef5350', SCENE_R*0.34);
  eLbl.position.set(gx*0.55, SCENE_R*0.95, 0);
  guideGroup.add(eLbl);
}

function buildFieldDrift() {
  // 3D, semi-transparent lattices: E along +ĵ; B out of screen (+k̂), both as arrows.
  // Each field is only drawn when present, so the physics reads from the picture:
  //   E=0,B≠0 → stationary;  E≠0,B=0 → straight-line acceleration along ±ĵ.
  const N = 6, step = DRIFT_W/(2*N);
  const H = SCENE_R;                       // half-extent of the field cube
  const LEN = 2*H;                          // E and B arrows share this length
  const zLayers = [-H, 0, H];              // E lives on these depth (k̂) planes
  const yRows   = [-H, -H/3, H/3, H];      // B threads through these heights
  const Eon = +$('E2-v').value > 0;
  const Bon = +$('inp-B').value > 0;

  // E field: vertical arrows along +ĵ spanning y∈[-H,H] on each depth plane.
  // Their tips/tails sit exactly where the B arrows' ends pass, so the two lattices touch.
  if (Eon) {
    for (let i=-N; i<=N; i++) for (const z of zLayers) {
      const op = z === 0 ? 0.26 : 0.14;
      fieldGroup.add(mkFieldArrow(
        new THREE.Vector3(0,1,0), new THREE.Vector3(i*step, -H, z),
        LEN, COL.E, op, SCENE_R*0.16, SCENE_R*0.08
      ));
    }
    const eLbl = makeTextSprite('E', '#ef5350', SCENE_R*0.32);
    eLbl.position.set(DRIFT_W*0.5+SCENE_R*0.2, SCENE_R*0.9, 0);
    guideGroup.add(eLbl);
  }

  // B field: arrows along +k̂ (out of screen) spanning z∈[-H,H] — same length as E.
  // The tip lands on the front E-plane (z=+H) and the tail on the back E-plane (z=-H),
  // so each B arrow stretches from one set of E lines to the other.
  if (Bon) {
    for (let i=-N; i<=N; i+=2) for (const yf of yRows) {
      const op = yf === 0 ? 0.30 : 0.22;
      fieldGroup.add(mkFieldArrow(
        new THREE.Vector3(0,0,1), new THREE.Vector3(i*step, yf, -H),
        LEN, COL.B, op, SCENE_R*0.16, SCENE_R*0.08
      ));
    }
    const bLbl = makeTextSprite('B', '#5c6bc0', SCENE_R*0.30);
    bLbl.position.set(-DRIFT_W*0.5-SCENE_R*0.1, SCENE_R*1.5, 0);
    guideGroup.add(bLbl);
  }
}

// ════════════════════════════════════════════════════════════════════════════
//  TRAJECTORIES
// ════════════════════════════════════════════════════════════════════════════
// arch count ∝ 1/r_L  (so BOTH |E| and |B| change the trajectory shape)
function archesFor(r_L) {
  if (!r_L || !Number.isFinite(r_L)) return ARCH_BASE;
  return Math.round(clamp(ARCH_BASE * R_L_REF / r_L, ARCH_MIN, ARCH_MAX));
}

// electron-scale loops: normalize to the electron's own reference r_L and compress, so the
// hump count sits in a readable band [ARCH_E_MIN, ARCH_E_MAX] and visibly tracks B (r_L ∝ 1/B²).
function archesForElectron(r_L) {
  if (!r_L || !Number.isFinite(r_L)) return ARCH_E_BASE;
  return Math.round(clamp(
    ARCH_E_BASE * Math.pow(R_L_REF_E / r_L, ARCH_E_EXP), ARCH_E_MIN, ARCH_E_MAX));
}

function setStationaryTrail(p) {
  p.trail.geometry.setFromPoints(
    [new THREE.Vector3(0,0,0), new THREE.Vector3(0,0,0)]);
}

function buildTrajectory(p, data) {
  p.rTweening = false;                            // only the cycloid branch re-arms this
  if (mode === 'accel') {
    if (data.stationary) {                       // q=0 or E=0 → nothing happens
      p.cur = { kind:'stationary', duration: 3.0 };
      p.veN = 0;
      setStationaryTrail(p);
    } else {
      const dir = data.sign;                       // +1 -> +î, -1 -> -î
      const sD  = sceneAccelD();
      // travel well past the exit grid so the particle stays visible for longer
      const x1  = dir*sD*1.9;
      // wall-clock duration tracks the real crossing time, exaggerated (^1.5) and given a
      // wide range so raising the potential is clearly visible as a faster launch.
      const ratio = Math.pow((data.t_d || T_D_REF)/T_D_REF, 1.5);
      const dur = ACCEL_SEC * clamp(ratio, 0.12, 3.2);
      p.cur = { kind:'accel', x1, dir, duration: dur };
      p.veN = clamp((data.ve || VE_REF)/VE_REF, 0.35, 3.0);
      // path line
      const pts = [];
      for (let i=0;i<=24;i++){ const u=i/24; pts.push(new THREE.Vector3(x1*u*u,0,0)); }
      p.trail.geometry.setFromPoints(pts);
    }
  } else if (data.stationary) {                  // E=0 with B>0 (or q=0) → at rest
    p.cur = { kind:'stationary', duration: 3.0 };
    setStationaryTrail(p);
  } else if (data.B_zero) {                       // E≠0, B=0 → straight-line acceleration ±ĵ
    const range = SCENE_R*1.6;
    // higher |E| → shorter traversal so the acceleration reads as faster
    const Eval = +$('E2-v').value || E_REF2;
    const dur  = DRIFT_SEC*0.7 * clamp(Math.sqrt(E_REF2/Math.max(Eval,1)), 0.35, 2.5);
    p.cur = { kind:'vaccel', sign:data.sign, range, duration: dur };
    const pts = [];
    for (let i=0;i<=48;i++){ const u=i/48; pts.push(new THREE.Vector3(0, data.sign*range*u*u, 0)); }
    p.trail.geometry.setFromPoints(pts);
  } else {
    // smooth-stepping cycloid: ease the hump radius from its current drawn size to the
    // new one so dragging E/B grows/shrinks the path instead of snapping (demos 2 & 3).
    // negative charge ⇒ the electron (ion charge is locked positive in pair mode): its tiny
    // r_L would otherwise saturate archesFor(), so use the compressed electron mapping.
    const archesTarget = (data.sign < 0)
      ? archesForElectron(data.r_L)
      : archesFor(data.r_L);
    const rTo   = DRIFT_W/(archesTarget*2*Math.PI);
    const fromR = (p.cycInit && p.dispR != null) ? p.dispR : rTo;
    p.cycSignQ  = data.sign;
    p.rFrom = fromR; p.rTo = rTo; p.rTweenT = 0;
    p.rTweening = Math.abs(fromR - rTo) > 1e-9;
    p.dispR = fromR; p.cycInit = true;
    setCycloidCur(p, fromR);
    return;                                        // trail/bounding handled in setCycloidCur
  }
  p.cycInit = false;                               // non-cycloid: next cycloid snaps fresh
  p.trail.geometry.computeBoundingSphere();
}

function cycloidPoint(cur, phi) {
  const x = cur.x0 + cur.r*(phi - Math.sin(phi));
  const y = cur.signQ * cur.r*(1 - Math.cos(phi));
  return new THREE.Vector3(x, y, 0);
}

// rebuild a particle's cycloid trail at the given hump radius. arches = DRIFT_W/(r·2π)
// keeps the path spanning the full width, so only the hump height/count morphs.
function buildCycloidTrail(p, cur) {
  const steps = Math.max(64, Math.ceil(cur.arches)*48);
  const pts = [];
  for (let i=0;i<=steps;i++){
    const phi = (i/steps)*cur.arches*2*Math.PI;
    pts.push(cycloidPoint(cur, phi));
  }
  p.trail.geometry.setFromPoints(pts);
  p.trail.geometry.computeBoundingSphere();
}

// set the live cycloid (p.cur) + trail at hump radius r; arches derived to keep full width
function setCycloidCur(p, r) {
  const arches = DRIFT_W/(r*2*Math.PI);
  p.cur = { kind:'cycloid', r, arches, signQ:p.cycSignQ,
            x0:-DRIFT_W/2, duration: DRIFT_SEC };
  buildCycloidTrail(p, p.cur);
}

// position + velocity (unit) at linear-time fraction u in [0,1]
function stateAt(cur, u) {
  u = clamp(u,0,1);
  if (cur.kind === 'stationary') {
    return { pos:new THREE.Vector3(0,0,0), vel:new THREE.Vector3(1,0,0), speed:0 };
  }
  if (cur.kind === 'accel') {
    const x = cur.x1*u*u;
    return { pos:new THREE.Vector3(x,0,0), vel:new THREE.Vector3(cur.dir,0,0), speed:u };
  }
  if (cur.kind === 'vaccel') {
    const y = cur.sign*cur.range*u*u;            // released from rest at the origin
    return { pos:new THREE.Vector3(0,y,0), vel:new THREE.Vector3(0,cur.sign,0), speed:u };
  }
  const phi = u*cur.arches*2*Math.PI;
  const pos = cycloidPoint(cur, phi);
  // d/dphi
  const dx = cur.r*(1 - Math.cos(phi));
  const dy = cur.signQ*cur.r*Math.sin(phi);
  const v  = new THREE.Vector3(dx, dy, 0);
  const speed = v.length()/(2*cur.r);          // 0 at cusps, 1 at top
  const vel = v.lengthSq() > 1e-12 ? v.normalize() : new THREE.Vector3(1,0,0);
  return { pos, vel, speed };
}

// ── camera framing per mode ───────────────────────────────────────────────────
function frameCamera() {
  if (mode === 'accel') {
    // panned farther downstream (right) so the plate sits a small margin from the left edge
    controls.target.set(SCENE_R*1.8, -SCENE_R*0.3, 0);
    camera.position.set(SCENE_R*3.5, SCENE_R*0.85, SCENE_R*3.0);
  } else {
    controls.target.set(0, 0, 0);
    camera.position.set(SCENE_R*0.15, SCENE_R*0.35, SCENE_R*4.6);
  }
  controls.update();
}

// ════════════════════════════════════════════════════════════════════════════
//  ANIMATION
// ════════════════════════════════════════════════════════════════════════════
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  const dt  = Math.min(clock.getDelta(), 0.05);
  const off = new THREE.Vector3(SCENE_R*0.14, SCENE_R*0.18, SCENE_R*0.14);

  for (const p of parts) {
    if (!p.cur) continue;

    // ease the cycloid path size toward its new value (smoothstep), rebuilding the
    // geometry at the interpolated radius each frame while the tween is active.
    if (p.rTweening && p.cur.kind === 'cycloid') {
      p.rTweenT += dt;
      const tu = clamp(p.rTweenT / R_TWEEN_SEC, 0, 1);
      const te = tu*tu*(3 - 2*tu);
      p.dispR = p.rFrom + (p.rTo - p.rFrom)*te;
      setCycloidCur(p, p.dispR);
      if (tu >= 1) { p.dispR = p.rTo; p.rTweening = false; }
    }

    // while a drift/pair slider is held, hide the particle + vectors; the path stays
    // visible and keeps resizing. On release the cycle resets, respawning it at the start.
    if (dragging) {
      p.mesh.visible = false;
      p.chargeSprite.visible = false;
      p.velArrow.visible   = p.velLabel.visible   = false;
      p.driftArrow.visible = p.driftLabel.visible = false;
      p.feArrow.visible    = p.feLabel.visible    = false;
      p.fbArrow.visible    = p.fbLabel.visible    = false;
      p.fnetArrow.visible  = p.fnetLabel.visible  = false;
      continue;
    }
    p.mesh.visible = true;

    const u  = Math.min(cycleT / Math.max(p.cur.duration,1e-9), 1.0);
    const st = stateAt(p.cur, u);
    const pos = st.pos;
    p.mesh.position.copy(pos);

    // fade out near the very end of an acceleration run
    let alpha = 1.0;
    if (p.cur.kind === 'accel' && u > 0.92) alpha = clamp((1.0-u)/0.08, 0, 1);
    p.mesh.material.opacity = alpha;

    // charge label
    p.chargeSprite.position.copy(pos).add(off);
    p.chargeSprite.visible = showLabels;
    p.chargeSprite.material.opacity = alpha;

    // per-particle vector gate: in Mode 3 only the ion shows v/F arrows (electron stays bare)
    const sV     = showVel   && !p.noVectors;
    const sDrift = showDrift && !p.noVectors;
    const sFE    = showFE    && !p.noVectors;
    const sFB    = showFB    && !p.noVectors;
    const sFnet  = showFnet  && !p.noVectors;

    const setForce = (arrow, label, vec, show) => {
      const L = vec.length();
      if (show && L > 1e-4) {
        arrow.position.copy(pos);
        arrow.setDirection(vec.clone().normalize());
        arrow.setLength(L, L*0.3, L*0.17);
        arrow.visible = true;
        label.position.copy(pos).addScaledVector(vec.clone().normalize(), L+SCENE_R*0.14);
        label.visible = true;
      } else { arrow.visible = false; label.visible = false; }
    };

    // stationary (no field / no charge): particle sits still, every vector disabled
    if (p.cur.kind === 'stationary') {
      p.velArrow.visible = p.velLabel.visible = false;
      p.driftArrow.visible = p.driftLabel.visible = false;
      p.feArrow.visible = p.feLabel.visible = false;
      p.fbArrow.visible = p.fbLabel.visible = false;
      p.fnetArrow.visible = p.fnetLabel.visible = false;
      continue;
    }

    // velocity arrow — for accel, peak length tracks the exhaust speed v_e(E,d,m)
    const veN  = (p.cur.kind === 'accel') ? (p.veN || 1) : 1;
    const vlen = SCENE_R*(0.3 + 0.62*clamp(st.speed,0,1)*veN);
    p.velArrow.position.copy(pos);
    p.velArrow.setDirection(st.vel);
    p.velArrow.setLength(vlen, vlen*0.3, vlen*0.17);
    p.velArrow.visible = sV && alpha > 0.2;
    p.velLabel.position.copy(pos).addScaledVector(st.vel, vlen+SCENE_R*0.12);
    p.velLabel.visible = sV && alpha > 0.2;

    if (p.cur.kind === 'accel') {
      // Mode 1: electric force F_E = qE along the field; length scales with |E|
      const Emag = +$('E1-v').value;
      const fLen = SCENE_R*(0.35 + 0.85*clamp(Emag/E_REF1, 0, 1.8));
      const fE   = new THREE.Vector3(p.cur.dir, 0, 0).multiplyScalar(fLen);
      setForce(p.feArrow, p.feLabel, fE, sFE && alpha > 0.2);
      p.driftArrow.visible = p.driftLabel.visible = false;
      p.fbArrow.visible = p.fbLabel.visible = false;
      p.fnetArrow.visible = p.fnetLabel.visible = false;
    } else if (p.cur.kind === 'vaccel') {
      // Mode 2/3 with B=0: pure electric force F_E = qE along ±ĵ; no B, so F_net = F_E
      const Emag = +$('E2-v').value;
      const fLen = SCENE_R*(0.35 + 0.85*clamp(Emag/E_REF2, 0, 1.8));
      const fE   = new THREE.Vector3(0, p.cur.sign, 0).multiplyScalar(fLen);
      setForce(p.feArrow,   p.feLabel,   fE, sFE);
      setForce(p.fnetArrow, p.fnetLabel, fE, sFnet);
      p.driftArrow.visible = p.driftLabel.visible = false;
      p.fbArrow.visible = p.fbLabel.visible = false;
    } else if (p.cur.kind === 'cycloid') {
      // drift arrow length tracks v_drift = E/B, so changing either field visibly resizes it
      const vd   = (p.data && Number.isFinite(p.data.v_drift)) ? p.data.v_drift : 0;
      const dLen = SCENE_R*0.9 * clamp(vd / V_DRIFT_REF, 0.2, 2.4);
      p.driftArrow.position.copy(pos);
      p.driftArrow.setDirection(new THREE.Vector3(1,0,0));
      p.driftArrow.setLength(dLen, dLen*0.3, dLen*0.17);
      p.driftArrow.visible = sDrift;
      p.driftLabel.position.copy(pos).add(new THREE.Vector3(dLen+SCENE_R*0.14, 0, 0));
      p.driftLabel.visible = sDrift;

      // consistent scale: a base length represents |qE|, scaled by the |E| slider
      const Emag  = +$('E2-v').value;
      const baseL = SCENE_R*0.55 * clamp(Emag/E_REF2, 0.25, 1.7);
      const sq    = p.cur.signQ;

      // F_E = qE  ->  +ĵ for +q, -ĵ for -q
      const fE = new THREE.Vector3(0, sq, 0).multiplyScalar(baseL);
      // F_B = q v×B,  B = +k̂.  |F_B|/|F_E| = v/v_drift = 2·speed (cycloid from rest)
      const fB = new THREE.Vector3(st.vel.y, -st.vel.x, 0)
                   .multiplyScalar(sq * baseL * 2 * st.speed);
      const fNet = fE.clone().add(fB);

      setForce(p.feArrow,   p.feLabel,   fE,   sFE);
      setForce(p.fbArrow,   p.fbLabel,   fB,   sFB);
      setForce(p.fnetArrow, p.fnetLabel, fNet, sFnet);
    }
  }

  // Mode 1: keep the exit grid fully visible (no fade as the particle passes through)
  if (mode === 'accel' && accelGrid) {
    accelGrid.material.opacity = 0.55;
  }

  renderer.render(scene, camera);

  // advance / loop
  const active = parts.filter(p => p.cur);
  if (active.length) {
    const maxDur = Math.max(...active.map(p => p.cur.duration));
    if (cycleT >= maxDur) {
      cyclePauseT += dt;
      if (cyclePauseT >= END_PAUSE) resetCycle();
    } else {
      cycleT = Math.min(cycleT + dt, maxDur);
      cyclePauseT = 0;
    }
  }
}

// ════════════════════════════════════════════════════════════════════════════
//  OUTPUTS
// ════════════════════════════════════════════════════════════════════════════
const $ = id => document.getElementById(id);

function fmt(x) {
  if (x===null||x===undefined||isNaN(x)) return '—';
  if (x===0) return '0';
  const a = Math.abs(x);
  return (a>=1e4||a<1e-2) ? x.toExponential(3) : x.toPrecision(4);
}
function fmtTesla(x){
  if(!Number.isFinite(x)) return '— T';
  if(x===0) return '0 T';
  const a=Math.abs(x);
  return ((a>=1e3||a<1e-3)?x.toExponential(3):x.toPrecision(4))+' T';
}
function updateBReadout(){ $('b-tesla').textContent = fmtTesla(+$('inp-B').value*GAUSS_TO_TESLA); }

function showError(msg){ $('error-msg').textContent=msg; $('error-msg').style.display='block'; }
function clearError(){ $('error-msg').style.display='none'; }

function writeAccel(key, d){
  $(key+'-ve').textContent  = fmt(d.ve);
  $(key+'-dV').textContent  = fmt(d.dV);
  $(key+'-acc').textContent = fmt(d.a);
}
function writeDrift(key, d){
  $(key+'-vd').textContent = fmt(d.v_drift);
  $(key+'-wc').textContent = fmt(d.omega_c);
  $(key+'-rL').textContent = fmt(d.r_L);
  $(key+'-Tc').textContent = fmt(d.T_c);
}

// ── preset fill (mass slider is log10(amu); charge slider is signed e) ──────────
function applyPreset(key){
  const pr = PRESETS[$(key+'-preset').value];
  if (!pr) return;
  $(key+'-mass').value = Math.log10(pr.m);
  $(key+'-q').value    = pr.q;
  updateParticleDisplay(key);
}

// ── read a particle's inputs (typable fields are authoritative; clamp mass/charge
//    to the active slider range so each mode's physical bounds are respected) ────
function readParticle(key){
  const amu  = +$(key+'-mass-v').value;
  const logm = clamp(Math.log10(amu > 0 ? amu : 1),
                     +$(key+'-mass').min, +$(key+'-mass').max);
  const m = Math.pow(10, logm);
  const q = clamp(Math.round(+$(key+'-q-v').value),
                  +$(key+'-q').min, +$(key+'-q').max);
  return { m_amu:m, q_e:q };
}

// ── slider <-> typable-field displays ─────────────────────────────────────────
function fmtMass(m){
  return (m>=1e3||m<1e-2) ? m.toExponential(2) : (+m.toPrecision(4)).toString();
}
// sliders -> fields (programmatic .value assignments don't fire 'input', no loops)
function updateParticleDisplay(key){
  const m = Math.pow(10, +$(key+'-mass').value);
  const q = Math.round(+$(key+'-q').value);
  $(key+'-mass-v').value = fmtMass(m);
  $(key+'-q-v').value    = q;
}
function updateFieldDisplays(){
  $('d-v').value  = +(+$('inp-d').value).toFixed(3);
  $('E1-v').value = Math.round(+$('inp-E1').value);
  $('dV-v').value = Math.round(+$('inp-dV').value);
  $('E2-v').value = Math.round(+$('inp-E2').value);
  $('B-v').value  = Math.round(+$('inp-B').value);
}

// Mode-1 coupling ΔV = E·d.  E1/ΔV fields are authoritative and may exceed their
// slider range (the slider thumb just pins), so a small d no longer freezes E.
function syncMode1FromED(){            // d and/or E changed -> recompute ΔV
  const d = +$('inp-d').value, E = +$('E1-v').value;
  const dV = E * d;
  $('dV-v').value   = +dV.toFixed(2);
  $('inp-dV').value = clamp(dV, +$('inp-dV').min, +$('inp-dV').max);
}
function syncMode1FromDV(){            // ΔV changed -> recompute E
  const d = +$('inp-d').value, dV = +$('dV-v').value;
  if (d > 0){
    const E = dV / d;
    $('E1-v').value   = +E.toFixed(2);
    $('inp-E1').value = clamp(E, +$('inp-E1').min, +$('inp-E1').max);
  }
}

async function api(payload){
  const res = await fetch('/api/compute', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  return res.json();
}

// ── main update ───────────────────────────────────────────────────────────────
async function runUpdate(){
  clearError();
  updateBReadout();

  try {
    if (mode === 'accel') {
      const pin = readParticle('S');
      const data = await api({ mode:'accel', ...pin,
                               d:+$('inp-d').value, E:+$('E1-v').value });
      if (data.error){ showError(data.error); return; }
      window._lastAccel = { d:+$('inp-d').value };
      parts[0].data = data;
      setChargeSprite(parts[0], data.sign);
      writeAccel('A', data);

    } else if (mode === 'drift') {
      const pin = readParticle('S');
      const data = await api({ mode:'drift', ...pin,
                               E:+$('E2-v').value, B:+$('inp-B').value*GAUSS_TO_TESLA });
      if (data.error){ showError(data.error); return; }
      parts[0].data = data;
      setChargeSprite(parts[0], data.sign);
      writeDrift('A', data);

    } else { // pair
      const E = +$('E2-v').value, B = +$('inp-B').value*GAUSS_TO_TESLA;
      const dA = await api({ mode:'drift', ...readParticle('A'), E, B });
      const dB = await api({ mode:'drift', ...readParticle('B'), E, B });
      if (dA.error){ showError('Ion: '+dA.error); return; }
      if (dB.error){ showError('Electron: '+dB.error); return; }
      parts[0].data = dA; parts[1].data = dB;
      setChargeSprite(parts[0], dA.sign);
      setChargeSprite(parts[1], dB.sign);
      writeDrift('A', dA); writeDrift('B', dB);
    }
  } catch(e){ showError('Server error: '+e.message); return; }

  parts.forEach(p => { if (p.data) buildTrajectory(p, p.data); });
  buildField();
  resetCycle();
}

// ════════════════════════════════════════════════════════════════════════════
//  MODE SWITCHING
// ════════════════════════════════════════════════════════════════════════════
function clearParticles(){
  for (const p of parts){
    scene.remove(p.mesh, p.trail, p.velArrow, p.driftArrow,
                 p.feArrow, p.fbArrow, p.fnetArrow,
                 p.velLabel, p.driftLabel, p.feLabel, p.fbLabel, p.fnetLabel);
    if (p.chargeSprite) scene.remove(p.chargeSprite);
    p.mesh.geometry.dispose(); p.trail.geometry.dispose();
  }
  parts = [];
}

function setMode(m){
  mode = m;
  clearParticles();

  if (m === 'pair') {
    parts = [ makeParticle(COL.ion, 0.085), makeParticle(COL.elec, 0.05) ];
    parts[1].noVectors = true;   // electron: keep its "−" label, hide v/F vectors
  } else {
    parts = [ makeParticle(COL.ion, 0.08) ];
  }

  // tabs
  document.querySelectorAll('.tab').forEach(t =>
    t.classList.toggle('active', t.dataset.mode === m));

  // input groups
  const isAccel = (m === 'accel');
  const isPair  = (m === 'pair');
  $('grp-accel').classList.toggle('hide', !isAccel);
  $('grp-drift').classList.toggle('hide',  isAccel);
  $('block-S').classList.toggle('hide', isPair);
  $('block-A').classList.toggle('hide', !isPair);
  $('block-B').classList.toggle('hide', !isPair);

  // single-particle head text
  $('S-head').textContent = 'Particle';

  // overlay toggles that only apply to drift
  document.querySelectorAll('.m-only.drift').forEach(el => el.classList.toggle('hide', isAccel));

  // output rows
  document.querySelectorAll('.r-accel').forEach(el => el.classList.toggle('hide', !isAccel));
  document.querySelectorAll('.r-drift').forEach(el => el.classList.toggle('hide',  isAccel));

  // electron column (Mode 3 only)
  document.querySelectorAll('.col-B').forEach(el => el.classList.toggle('hide', !isPair));
  document.querySelectorAll('#legend .drift').forEach(el => el.classList.toggle('hide', isAccel));
  $('leg-A').textContent = isPair ? 'Ion' : 'Particle';
  $('th-A').textContent  = isPair ? 'Ion' : 'Particle';

  // Mode 1 (electrostatic accelerator): positive ions only, 5–200 amu.
  if (isAccel) {
    $('S-mass').min = Math.log10(5);     // ≈0.699
    $('S-mass').max = Math.log10(200);   // ≈2.301
    $('S-mass').value = clamp(+$('S-mass').value, Math.log10(5), Math.log10(200));
    $('S-q').min = '1';                   // no neutral or negative ions here
    if (+$('S-q').value < 1) $('S-q').value = 1;
    $('S-opt-electron').disabled = true; $('S-opt-electron').hidden = true;
    if ($('S-preset').value === 'electron') { $('S-preset').value = 'xenon'; applyPreset('S'); }
  } else {
    $('S-mass').min = '-4'; $('S-mass').max = '2.5';
    $('S-q').min = '-3';
    $('S-opt-electron').disabled = false; $('S-opt-electron').hidden = false;
  }
  updateParticleDisplay('S');

  // Mode 3: the electron is a fixed physical species — lock its mass & charge to the
  // preset; the ion may vary in mass/charge magnitude but its charge stays positive.
  if (isPair) {
    const e = PRESETS.electron;
    $('B-mass-v').value = fmtMass(e.m);
    $('B-mass').value   = Math.log10(e.m);
    $('B-q-v').value    = e.q;
    $('B-q').value      = e.q;
    ['B-mass','B-mass-v','B-q','B-q-v'].forEach(id => $(id).disabled = true);

    $('A-q').min = '1'; $('A-q-v').min = '1';   // ion charge locked positive
    if (+$('A-q').value   < 1) $('A-q').value   = 1;
    if (+$('A-q-v').value < 1) $('A-q-v').value = 1;
    updateParticleDisplay('A');
  } else {
    ['B-mass','B-mass-v','B-q','B-q-v'].forEach(id => $(id).disabled = false);
    $('A-q').min = '-3'; $('A-q-v').min = '-3';
  }

  frameCamera();
  runUpdate();
}

// ── event wiring ──────────────────────────────────────────────────────────────
let _deb = null;
const debounced = () => { clearTimeout(_deb); _deb = setTimeout(runUpdate,150); };

document.querySelectorAll('.tab').forEach(t =>
  t.addEventListener('click', () => setMode(t.dataset.mode)));

// presets
$('S-preset').addEventListener('change', () => { applyPreset('S'); debounced(); });
$('A-preset').addEventListener('change', () => { applyPreset('A'); debounced(); });

// particle mass/charge: slider <-> typable field (field snaps to range on blur)
[['S',true],['A',true],['B',false]].forEach(([key,hasPreset]) => {
  const setCustom = () => { if (hasPreset) $(key+'-preset').value = 'custom'; };
  ['-mass','-q'].forEach(suf =>
    $(key+suf).addEventListener('input', () => { setCustom(); updateParticleDisplay(key); debounced(); }));

  $(key+'-mass-v').addEventListener('input', () => {
    const amu = +$(key+'-mass-v').value;
    if (amu > 0) $(key+'-mass').value = clamp(Math.log10(amu), +$(key+'-mass').min, +$(key+'-mass').max);
    setCustom(); debounced();
  });
  $(key+'-mass-v').addEventListener('change', () => updateParticleDisplay(key));

  $(key+'-q-v').addEventListener('input', () => {
    $(key+'-q').value = clamp(Math.round(+$(key+'-q-v').value), +$(key+'-q').min, +$(key+'-q').max);
    setCustom(); debounced();
  });
  $(key+'-q-v').addEventListener('change', () => updateParticleDisplay(key));
});

// Mode 1: d / |E| / ΔV — each has a slider and a typable field, coupled by ΔV=E·d.
$('inp-d').addEventListener('input',  () => { $('d-v').value = +(+$('inp-d').value).toFixed(3); syncMode1FromED(); debounced(); });
$('d-v').addEventListener('input',    () => { const v=+$('d-v').value; if (isFinite(v)) $('inp-d').value = clamp(v, +$('inp-d').min, +$('inp-d').max); syncMode1FromED(); debounced(); });
$('d-v').addEventListener('change',   () => { $('d-v').value = +(+$('inp-d').value).toFixed(3); syncMode1FromED(); });

$('inp-E1').addEventListener('input', () => { $('E1-v').value = Math.round(+$('inp-E1').value); syncMode1FromED(); debounced(); });
$('E1-v').addEventListener('input',   () => { const v=+$('E1-v').value; if (isFinite(v)) $('inp-E1').value = clamp(v, +$('inp-E1').min, +$('inp-E1').max); syncMode1FromED(); debounced(); });

$('inp-dV').addEventListener('input', () => { $('dV-v').value = Math.round(+$('inp-dV').value); syncMode1FromDV(); debounced(); });
$('dV-v').addEventListener('input',   () => { const v=+$('dV-v').value; if (isFinite(v)) $('inp-dV').value = clamp(v, +$('inp-dV').min, +$('inp-dV').max); syncMode1FromDV(); debounced(); });

// Mode 2/3: |E| (may exceed its slider) / |B|
$('inp-E2').addEventListener('input', () => { $('E2-v').value = Math.round(+$('inp-E2').value); debounced(); });
$('E2-v').addEventListener('input',   () => { const v=+$('E2-v').value; if (isFinite(v)) $('inp-E2').value = clamp(v, +$('inp-E2').min, +$('inp-E2').max); debounced(); });
$('inp-B').addEventListener('input',  () => { $('B-v').value = Math.round(+$('inp-B').value); updateBReadout(); debounced(); });
$('B-v').addEventListener('input',    () => { const v=+$('B-v').value; if (isFinite(v)) $('inp-B').value = clamp(v, +$('inp-B').min, +$('inp-B').max); updateBReadout(); debounced(); });
$('B-v').addEventListener('change',   () => { $('B-v').value = Math.round(+$('inp-B').value); updateBReadout(); });

$('chk-labels').addEventListener('change', () => { showLabels = $('chk-labels').checked; axisGroup.visible = showLabels; });
$('chk-vel').addEventListener('change',    () => { showVel    = $('chk-vel').checked; });
$('chk-drift').addEventListener('change',  () => { showDrift  = $('chk-drift').checked; });
$('chk-fe').addEventListener('change',     () => { showFE     = $('chk-fe').checked; });
$('chk-fb').addEventListener('change',     () => { showFB     = $('chk-fb').checked; });
$('chk-fnet').addEventListener('change',   () => { showFnet   = $('chk-fnet').checked; });

// Demos 2 & 3: hide the particle while a slider is dragged, then respawn it at the
// start of the path once released. (Mode 1 is left untouched — gated on mode.)
['inp-E2','inp-B','S-mass','S-q','A-mass','A-q','B-mass','B-q'].forEach(id => {
  const el = $(id);
  if (el) el.addEventListener('pointerdown', () => { if (mode !== 'accel') dragging = true; });
});
window.addEventListener('pointerup', () => {
  if (!dragging) return;
  dragging = false;
  resetCycle();          // particle reappears at the spawn point
});

// ── boot ──────────────────────────────────────────────────────────────────────
initViz(document.getElementById('viewport'));
updateBReadout();
updateFieldDisplays();
['S','A','B'].forEach(updateParticleDisplay);
setMode('accel');
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", HTML.encode("utf-8"))
        else:
            self._send(404, "text/plain", b"Not found")

    def do_POST(self):
        if self.path != "/api/compute":
            self._send(404, "text/plain", b"Not found")
            return
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        try:
            p = json.loads(raw)
            r = compute(p)
            self._send(200, "application/json", json.dumps(r).encode())
        except (ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
            self._send(400, "application/json", json.dumps({"error": str(exc)}).encode())


HOST, PORT = "127.0.0.1", 8001

if __name__ == "__main__":
    srv = _Server((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"\n  E x B Drift Applet -> {url}\n  Ctrl-C to quit.\n")
    webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        srv.shutdown()
