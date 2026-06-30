#!/usr/bin/env python3
"""
magnetic_mirror.py — Magnetism Applets (three modes)
Single-file, stdlib-only. Run: python magnetic_mirror.py

Three modes, switchable live in the UI:

  Mode 1 — Induced Magnetic Field
      A moving charge induces a magnetic field that circles its velocity axis
      (right-hand rule for +q, reversed for -q).  Input: charge sign (+ speed).

  Mode 2 — Magnetic Moment
      A charge gyrating in a uniform B forms a current loop.  Inputs: m, q, v_perp, |B|.
      Outputs: Larmor radius r_L = m v_perp / (|q| B), cyclotron frequency
      omega_c = |q| B / m, magnetic moment mu = m v_perp^2 / (2 B).

  Mode 3 — Magnetic Mirror
      A charged particle gyrates along a magnetic bottle B(x) (weak at the centre
      B0, strong at the throats B_max = R*B0).  mu is conserved, so v_perp grows
      and v_par shrinks toward the throats; it reflects where B = B0 csc^2(theta0).
      For the parabolic mirror B(x) = B0 (1 + (R-1)(x/L)^2) the parallel motion of
      the guiding centre is simple-harmonic, giving a smooth, closed bounce orbit.
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


# ── Mode 1 — Induced magnetic field ─────────────────────────────────────────────
def compute_induced(q_e, v):
    for n, x in (("q_e", q_e), ("v", v)):
        _finite(n, x)
    q    = float(q_e) * E_C
    sign = 1 if q > 0 else (-1 if q < 0 else 0)
    # Point-charge (Biot-Savart) field B = (mu0/4pi) q (v x r-hat)/r^2 circles the
    # velocity axis: right-hand sense about v for +q, reversed for -q.
    if sign > 0:
        circ = "Right-hand rule about v"
    elif sign < 0:
        circ = "Reversed (−q flips it)"
    else:
        circ = "No field (q = 0)"
    return {"mode": "induced", "sign": sign, "v": float(v),
            "moving": float(v) != 0.0 and sign != 0, "circ": circ}


# ── Mode 2 — Magnetic moment (uniform-field gyration) ───────────────────────────
def compute_moment(m_amu, q_e, v_perp, B):
    for n, x in (("m_amu", m_amu), ("q_e", q_e), ("v_perp", v_perp), ("B", B)):
        _finite(n, x)
    if float(m_amu) <= 0:
        raise ValueError("Mass must be positive.")
    if float(B) <= 0:
        raise ValueError("|B| must be positive.")
    if float(v_perp) < 0:
        raise ValueError("Perpendicular speed must be non-negative.")

    m    = float(m_amu) * AMU
    q    = float(q_e) * E_C
    absq = abs(q)
    Bf   = float(B)
    vp   = float(v_perp)
    sign = 1 if q > 0 else (-1 if q < 0 else 0)

    mu = m * vp ** 2 / (2.0 * Bf)
    if absq == 0:
        return {"mode": "moment", "sign": 0, "v_perp": vp, "B": Bf,
                "r_L": None, "omega_c": None, "mu": mu, "T_c": None,
                "I": None, "A": None}

    omega_c = absq * Bf / m
    r_L     = m * vp / (absq * Bf)
    T_c     = 2.0 * math.pi / omega_c
    I       = absq * omega_c / (2.0 * math.pi)   # loop current  q*f
    A       = math.pi * r_L ** 2                 # loop area
    return {"mode": "moment", "sign": sign, "v_perp": vp, "B": Bf,
            "r_L": r_L, "omega_c": omega_c, "mu": mu, "T_c": T_c,
            "I": I, "A": A}


# ── Mode 3 — Magnetic mirror ────────────────────────────────────────────────────
def compute_mirror(m_amu, q_e, v0, theta_deg, B0, R):
    for n, v in (("m_amu", m_amu), ("q_e", q_e), ("v0", v0),
                 ("theta_deg", theta_deg), ("B0", B0), ("R", R)):
        _finite(n, v)

    if float(m_amu) <= 0:
        raise ValueError("Mass must be positive.")
    if float(B0) <= 0:
        raise ValueError("Initial magnetic flux density B0 must be positive.")
    if float(v0) < 0:
        raise ValueError("Speed |v0| must be non-negative.")
    if not (0.0 <= float(theta_deg) <= 90.0):
        raise ValueError("Pitch angle must be between 0 and 90 degrees.")
    if float(R) <= 1.0:
        raise ValueError("Mirror ratio R = B_max/B0 must be greater than 1.")

    m    = float(m_amu) * AMU
    q    = float(q_e) * E_C
    absq = abs(q)
    B0f  = float(B0)
    v0f  = float(v0)
    Rf   = float(R)
    th   = math.radians(float(theta_deg))
    s    = math.sin(th)
    c    = math.cos(th)
    sign = 1 if q > 0 else (-1 if q < 0 else 0)

    v_perp0 = v0f * s
    v_par0  = v0f * c
    mu = m * v_perp0 ** 2 / (2.0 * B0f)
    B_max = Rf * B0f

    if absq > 0 and v0f > 0:
        omega_c0 = absq * B0f / m
        r_L0     = m * v_perp0 / (absq * B0f) if v_perp0 > 0 else 0.0
        T_c0     = 2.0 * math.pi / omega_c0
    else:
        omega_c0 = 0.0
        r_L0     = None
        T_c0     = None

    loss_cone_deg = math.degrees(math.asin(min(1.0, math.sqrt(1.0 / Rf))))

    no_charge = (absq == 0)
    at_rest   = (v0f == 0)

    if s <= 0.0:
        B_stop    = None
        turn_frac = 1.0
        trapped   = False
    else:
        B_stop = B0f / (s * s)
        f = (c / s) / math.sqrt(Rf - 1.0)
        trapped   = (f <= 1.0)
        turn_frac = min(f, 1.0)

    if no_charge:
        trapped = False

    if at_rest:
        status = "At rest"
    elif no_charge:
        status = "No coupling (q = 0)"
    elif trapped:
        status = "Trapped (reflected)"
    else:
        status = "Escapes (loss cone)"

    return {
        "mode": "mirror",
        "sign": sign,
        "v0": v0f, "v_par0": v_par0, "v_perp0": v_perp0,
        "mu": mu,
        "B0": B0f, "B_max": B_max, "B_stop": B_stop,
        "R": Rf, "theta_deg": float(theta_deg),
        "turn_frac": turn_frac, "trapped": bool(trapped),
        "escapes": bool(not trapped and not at_rest),
        "no_charge": bool(no_charge), "at_rest": bool(at_rest),
        "loss_cone_deg": loss_cone_deg,
        "r_L0": r_L0, "omega_c0": omega_c0, "T_c0": T_c0,
        "status": status,
    }


def compute(payload):
    mode = payload.get("mode")
    if mode == "induced":
        return compute_induced(payload["q_e"], payload["v"])
    if mode == "moment":
        return compute_moment(payload["m_amu"], payload["q_e"],
                              payload["v_perp"], payload["B"])
    if mode == "mirror":
        return compute_mirror(payload["m_amu"], payload["q_e"], payload["v0"],
                              payload["theta_deg"], payload["B0"], payload["R"])
    raise ValueError(f"Unknown mode '{mode}'.")


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Magnetism Applets</title>
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
#otable td{padding:3px 4px;font-family:'Cascadia Code','Fira Mono',monospace;
           text-align:right;color:#4fc3f7;}
#otable td:first-child{text-align:left;color:#607d8b;
                       font-family:'Segoe UI',sans-serif;font-size:10px;}
#otable tr+tr td{border-top:1px solid #141d27}
#status-row td{color:#ffb74d;font-weight:700}
#error-msg{background:#4a0000;border:1px solid #c62828;border-radius:4px;
           color:#ef9a9a;font-size:11px;padding:7px 9px;display:none;}
#legend{margin-top:auto;background:#0d1117;border:1px solid #182330;
        border-radius:5px;padding:8px 10px;font-size:10px;line-height:2.0;}
#legend span.sw{display:inline-block;width:9px;height:9px;border-radius:50%;
             margin-right:6px;vertical-align:middle;}
#legend .row.hide{display:none}
#viewport{flex:1;overflow:hidden;position:relative}
#viewport canvas{display:block}
#livebox{position:absolute;top:12px;left:12px;background:rgba(13,17,23,0.82);
         border:1px solid #1e2a35;border-radius:6px;padding:9px 12px;font-size:11px;
         color:#90a4ae;line-height:1.8;pointer-events:none;}
#livebox b{color:#4fc3f7;font-family:'Cascadia Code','Fira Mono',monospace;font-weight:600}
#livebox .lp{color:#66bb6a}
#livebox .lq{color:#29b6f6}
.hide{display:none}
</style>
</head>
<body>

<div id="panel">
  <h1 id="title">Magnetism</h1>

  <!-- ── mode tabs ── -->
  <div id="tabs">
    <div class="tab active" data-mode="induced">Mode 1<small>induced B</small></div>
    <div class="tab" data-mode="moment">Mode 2<small>moment</small></div>
    <div class="tab" data-mode="mirror">Mode 3<small>mirror</small></div>
  </div>

  <!-- ══ particle block ══ -->
  <div class="pblock" id="block-P">
    <div class="phead"><span class="dot" style="background:#ff7043"></span><span>Particle</span></div>
    <div class="field" id="row-preset">
      <label>Preset</label>
      <select id="preset">
        <option value="custom">Custom</option>
        <option value="proton" selected>Proton (1.007 amu)</option>
        <option value="electron">Electron (e&#8315;)</option>
        <option value="deuteron">Deuteron (2.014 amu)</option>
        <option value="xenon">Xenon&#8314; (131.29 amu)</option>
        <option value="krypton">Krypton&#8314; (83.80 amu)</option>
      </select>
    </div>
    <div class="field" id="row-mass">
      <label>Mass <i>m</i> [amu]</label>
      <input type="number" id="inp-mass" value="1.007276" min="0.0000001" step="0.001">
    </div>
    <div class="field">
      <label>Charge <i>q</i> [e]</label>
      <div class="row2">
        <input type="number" id="inp-qmag" value="1" min="0" step="1">
        <select id="inp-sign">
          <option value="+">+</option>
          <option value="-">&#x2212;</option>
        </select>
      </div>
    </div>
  </div>

  <!-- ══ Mode 1 (induced) fields ══ -->
  <div id="grp-induced">
    <div class="field">
      <label>Speed |<i>v</i>| [m/s]</label>
      <input type="number" id="ind-speed" value="200000" min="0" step="10000">
    </div>
    <div class="readout">B circulates around the velocity axis (Biot&#8211;Savart).
      Flip the charge sign to reverse it.</div>
  </div>

  <!-- ══ Mode 2 (moment) fields ══ -->
  <div id="grp-moment" class="hide">
    <div class="field">
      <label>Perp. speed <i>v</i><sub>&#x22A5;</sub> [m/s]</label>
      <input type="number" id="mom-vperp" value="300000" min="0" step="10000">
    </div>
    <div class="field" style="margin-top:8px">
      <label>Flux density |<i>B</i>| [T]</label>
      <input type="number" id="mom-B" value="0.5" min="0.0001" step="0.05">
    </div>
  </div>

  <!-- ══ Mode 3 (mirror) fields ══ -->
  <div id="grp-mirror" class="hide">
    <div class="field">
      <label>Speed |<i>v</i><sub>0</sub>| [m/s]</label>
      <input type="number" id="mir-speed" value="300000" min="0" step="10000">
    </div>
    <div class="field" style="margin-top:8px">
      <label>Pitch angle &#952;<sub>0</sub> = <b id="theta-disp">45</b>&#xB0;
             <span style="float:right;color:#607d8b">0&#x2013;90</span></label>
      <input type="range" id="theta-r" min="0" max="90" value="45" step="1">
    </div>
    <div class="field" style="margin-top:8px">
      <label>Initial flux density <i>B</i><sub>0</sub> [T]</label>
      <input type="number" id="mir-B0" value="0.5" min="0.0001" step="0.05">
    </div>
    <div class="field" style="margin-top:8px">
      <label>Mirror ratio <i>R</i> = <i>B</i><sub>max</sub>/<i>B</i><sub>0</sub> =
             <b id="R-disp">6.0</b></label>
      <input type="range" id="R-r" min="1.2" max="20" value="6" step="0.1">
      <div class="readout">Loss cone: <b id="b-loss">24.1&#xB0;</b> &nbsp; |
                           <i>B</i><sub>max</sub> = <b id="b-bmax">3.000 T</b></div>
    </div>
  </div>

  <!-- ── overlay toggles ── -->
  <label class="chk" for="chk-labels">
    <input type="checkbox" id="chk-labels" checked>
    Show field &amp; labels
  </label>
  <label class="chk" for="chk-vel">
    <input type="checkbox" id="chk-vel" checked>
    Show velocity <b style="color:#ffd54f">v</b>
  </label>
  <label class="chk m-comp hide" for="chk-comp">
    <input type="checkbox" id="chk-comp">
    Show <b style="color:#66bb6a">v&#x2225;</b> / <b style="color:#29b6f6">v&#x22A5;</b> components
  </label>
  <label class="chk m-mu hide" for="chk-mu">
    <input type="checkbox" id="chk-mu" checked>
    Show magnetic moment <b style="color:#ec407a">&#956;</b>
  </label>

  <button id="btn-run" style="background:#1565c0;border:none;border-radius:5px;color:#fff;
          cursor:pointer;font-size:13px;font-weight:600;padding:9px;width:100%;letter-spacing:.04em;">
    &#9654;&#xFE0E;&nbsp; Run / Update</button>
  <div id="error-msg"></div>

  <div id="out-wrap">
    <div class="sec">Demo Outputs</div>
    <table id="otable">
      <!-- induced -->
      <tr class="r-induced"><td>Charge</td>              <td id="o-ind-q">&#x2014;</td></tr>
      <tr class="r-induced"><td>B circulation</td>       <td id="o-ind-c" style="font-size:9px">&#x2014;</td></tr>
      <!-- moment -->
      <tr class="r-moment hide"><td>r<sub>L</sub> [m]</td>            <td id="o-mom-rL">&#x2014;</td></tr>
      <tr class="r-moment hide"><td>&#969;<sub>c</sub> [rad/s]</td>   <td id="o-mom-wc">&#x2014;</td></tr>
      <tr class="r-moment hide"><td>&#956; [J/T]</td>                 <td id="o-mom-mu">&#x2014;</td></tr>
      <tr class="r-moment hide"><td>T<sub>c</sub> [s]</td>            <td id="o-mom-Tc">&#x2014;</td></tr>
      <!-- mirror -->
      <tr class="r-mirror hide"><td>&#956; [J/T]</td>                   <td id="o-mir-mu">&#x2014;</td></tr>
      <tr class="r-mirror hide"><td>v&#x22A5;<sub>0</sub> [m/s]</td>    <td id="o-mir-vperp">&#x2014;</td></tr>
      <tr class="r-mirror hide"><td>v&#x2225;<sub>0</sub> [m/s]</td>    <td id="o-mir-vpar">&#x2014;</td></tr>
      <tr class="r-mirror hide"><td>B<sub>B</sub> stop [T]</td>         <td id="o-mir-bstop">&#x2014;</td></tr>
      <tr class="r-mirror hide"><td>B<sub>max</sub> [T]</td>            <td id="o-mir-bmax">&#x2014;</td></tr>
      <tr class="r-mirror hide"><td>&#952;<sub>loss</sub> [&#xB0;]</td> <td id="o-mir-loss">&#x2014;</td></tr>
      <tr class="r-mirror hide" id="status-row"><td>Result</td>         <td id="o-mir-status">&#x2014;</td></tr>
    </table>
  </div>

  <div id="legend">
    <div class="row"><span class="sw" style="background:#ff7043"></span><b>Particle</b></div>
    <div class="row"><span class="sw" style="background:#ffd54f"></span>v velocity</div>
    <div class="row m-comp hide"><span class="sw" style="background:#66bb6a"></span>v&#x2225; parallel</div>
    <div class="row m-comp hide"><span class="sw" style="background:#29b6f6"></span>v&#x22A5; perpendicular</div>
    <div class="row m-mu hide"><span class="sw" style="background:#ec407a"></span>&#956; magnetic moment</div>
    <div class="row m-field"><span class="sw" style="background:#5c6bc0"></span><b style="color:#5c6bc0">B</b> field</div>
    <div class="row m-mirror hide"><span class="sw" style="background:#ffb300"></span>Mirror point</div>
    <div class="row m-mirror hide"><span class="sw" style="background:#ef5350"></span>Throat (B<sub>max</sub>)</div>
  </div>
</div>

<div id="viewport">
  <div id="livebox" class="hide">
    <div>At particle:</div>
    <div>B = <b id="live-B">&#x2014;</b></div>
    <div class="lp">v&#x2225; = <b id="live-vpar" class="lp">&#x2014;</b></div>
    <div class="lq">v&#x22A5; = <b id="live-vperp" class="lq">&#x2014;</b></div>
  </div>
</div>

<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ── constants ───────────────────────────────────────────────────────────────
const SCENE_R     = 5.0;
const BOTTLE_L    = SCENE_R * 2.6;     // mirror half-length: throats at x = ±L
const R_FL_MAX    = SCENE_R * 1.05;    // mirror field-line radius at the centre
const TRAVEL_TRAP = 8.5, TRAVEL_ESC = 5.0, END_PAUSE = 0.6;
const NS          = 1800;
const OMEGA_REF   = 5.0e7;
const BASE_GYRO   = 9, GYRO_MIN = 4, GYRO_MAX = 34;

// induced (Mode 1)
const IND_L       = SCENE_R * 2.6;     // travel half-length along x
const IND_SEC     = 5.0;
const V_REF_IND   = 2.0e5;

// moment (Mode 2)
const MOM_RREF    = 5.0e-3;             // reference r_L → mid-scale display
const MOM_WREF    = 4.8e7;             // reference ω_c → mid animation speed

const clamp = (x,a,b) => Math.min(b, Math.max(a, x));

const PRESETS = {
  custom:   null,
  proton:   { m: 1.007276,       q: +1 },
  electron: { m: 5.48579909e-4,  q: -1 },
  deuteron: { m: 2.013553,       q: +1 },
  xenon:    { m: 131.293,        q: +1 },
  krypton:  { m: 83.798,         q: +1 },
};

const COL = {
  part:  0xff7043,
  vel:   0xffd54f,
  vpar:  0x66bb6a,
  vperp: 0x29b6f6,
  mu:    0xec407a,
  field: 0x5c6bc0,
  axis:  0x546e7a,
  turn:  0xffb300,
  throat:0xef5350,
  curr:  0xffa726,
};

let mode = 'induced';
let showField = true, showVel = true, showComp = false, showMu = true;

// ── generic rounded-rect text sprite ──────────────────────────────────────────
function makeTextSprite(text, color, height = SCENE_R * 0.26) {
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
let fieldGroup, guideGroup, extraGroup;
let particle = null;
let curData = null;
let path = null;          // mirror playback path
let momView = null;       // { rDisp, visOmega, rotSign }
let firstRenderDone = false;
let liveTick = 0, tAccum = 0;

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
  const hexC  = '#'+COL.part.toString(16).padStart(6,'0');
  const glyph = sign < 0 ? '−' : (sign > 0 ? '+' : '0');
  p.chargeSprite = makeTextSprite(glyph, hexC, SCENE_R*0.36);
  scene.add(p.chargeSprite);
  p.curSign = sign;
}

// ── build the particle ────────────────────────────────────────────────────────
function makeParticle() {
  const p = { chargeSprite:null, curSign:null, trail:null };

  p.mesh = new THREE.Mesh(
    new THREE.SphereGeometry(SCENE_R*0.07, 24, 24),
    new THREE.MeshStandardMaterial({ color:COL.part, emissive:COL.part,
                                     emissiveIntensity:0.45, roughness:0.3 })
  );
  scene.add(p.mesh);

  const mkArrow = (c, len) => {
    const a = new THREE.ArrowHelper(new THREE.Vector3(1,0,0), new THREE.Vector3(),
                                    len, c, len*0.28, len*0.16);
    a.visible = false; scene.add(a); return a;
  };
  p.velArrow   = mkArrow(COL.vel,   SCENE_R*0.9);
  p.vparArrow  = mkArrow(COL.vpar,  SCENE_R*0.7);
  p.vperpArrow = mkArrow(COL.vperp, SCENE_R*0.7);
  p.muArrow    = mkArrow(COL.mu,    SCENE_R*0.7);

  const mkLabel = (txt, hex) => {
    const s = makeTextSprite(txt, hex, SCENE_R*0.22); s.visible = false; scene.add(s); return s;
  };
  p.velLabel   = mkLabel('v',  '#ffd54f');
  p.vparLabel  = mkLabel('v∥', '#66bb6a');
  p.vperpLabel = mkLabel('v⊥', '#29b6f6');
  p.muLabel    = mkLabel('μ', '#ec407a');
  return p;
}

function hideAllVectors() {
  for (const a of [particle.velArrow, particle.vparArrow, particle.vperpArrow, particle.muArrow,
                   particle.velLabel, particle.vparLabel, particle.vperpLabel, particle.muLabel])
    a.visible = false;
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
  extraGroup = new THREE.Group();
  scene.add(fieldGroup, guideGroup, extraGroup);

  particle = makeParticle();
  clock = new THREE.Clock();

  window.addEventListener('resize', () => {
    const w2 = container.clientWidth, h2 = container.clientHeight;
    camera.aspect = w2/h2; camera.updateProjectionMatrix();
    renderer.setSize(w2,h2);
  });

  animate();
}

// ── geometry helpers ──────────────────────────────────────────────────────────
function bfac(xn, R) { return 1 + (R - 1) * xn * xn; }

function ringPoints(radius, xpos, segs = 64) {
  const pts = [];
  for (let i = 0; i <= segs; i++) {
    const a = (i / segs) * 2 * Math.PI;
    pts.push(new THREE.Vector3(xpos, radius*Math.cos(a), radius*Math.sin(a)));
  }
  return pts;
}

// a circle in the y-z plane (around the x-axis) with tangent arrowheads showing
// circulation sense (+1 → +alpha:  y→z,  -1 → reverse)
function makeCircArrows(group, xpos, radius, sense, color, opacity, nHeads = 4) {
  group.add(new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(ringPoints(radius, xpos)),
    new THREE.LineBasicMaterial({ color, transparent:true, opacity })));
  if (sense === 0) return;
  for (let k = 0; k < nHeads; k++) {
    const a   = (k / nHeads) * 2 * Math.PI;
    const pos = new THREE.Vector3(xpos, radius*Math.cos(a), radius*Math.sin(a));
    const tan = new THREE.Vector3(0, -Math.sin(a), Math.cos(a)).multiplyScalar(sense);
    const hl  = radius*0.5;
    const ar  = new THREE.ArrowHelper(tan, pos, hl, color, hl*0.6, hl*0.4);
    ar.line.material.transparent = true; ar.line.material.opacity = opacity;
    ar.cone.material.transparent = true; ar.cone.material.opacity = opacity;
    group.add(ar);
  }
}

// poloidal field loops wrapping a current ring of radius ringR (the wire lies in the
// y-z plane at x=0). Each little loop encircles the wire; by the right-hand rule the
// field threads −x̂ through the centre of the ring — the same direction as μ for a
// gyrating charge — so these loops "add up" to the magnetic dipole moment.
function makePoloidalLoops(group, ringR, color, opacity, nLoops = 8) {
  const rho  = ringR * 0.26;
  const xhat = new THREE.Vector3(1,0,0);
  const lm   = new THREE.LineBasicMaterial({ color, transparent:true, opacity });
  for (let k = 0; k < nLoops; k++) {
    const a    = (k / nLoops) * 2 * Math.PI;
    const rhat = new THREE.Vector3(0, Math.cos(a), Math.sin(a));   // outward radial
    const ctr  = rhat.clone().multiplyScalar(ringR);
    const segs = 44, pts = [];
    for (let i = 0; i <= segs; i++) {
      const b = (i/segs) * 2*Math.PI;                              // +β: inner side → −x̂
      pts.push(ctr.clone().addScaledVector(rhat, rho*Math.cos(b))
                          .addScaledVector(xhat, rho*Math.sin(b)));
    }
    group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), lm));
    for (const b of [Math.PI*0.5, Math.PI*1.5]) {                  // two arrowheads / loop
      const p = ctr.clone().addScaledVector(rhat, rho*Math.cos(b)).addScaledVector(xhat, rho*Math.sin(b));
      const t = rhat.clone().multiplyScalar(-Math.sin(b)).addScaledVector(xhat, Math.cos(b)).normalize();
      const hl = rho*0.5;
      const ar = new THREE.ArrowHelper(t, p, hl, color, hl*0.8, hl*0.55);
      ar.line.material.transparent = true; ar.line.material.opacity = opacity;
      ar.cone.material.transparent = true; ar.cone.material.opacity = opacity;
      group.add(ar);
    }
  }
}

// ════════════════════════════════════════════════════════════════════════════
//  MODE 1 — INDUCED MAGNETIC FIELD
// ════════════════════════════════════════════════════════════════════════════
function buildInduced(d) {
  fieldGroup.clear(); guideGroup.clear(); extraGroup.clear();
  extraGroup.position.set(0,0,0);
  if (particle.trail) { scene.remove(particle.trail); particle.trail.geometry.dispose(); particle.trail = null; }

  // central motion axis (static)
  const dashed = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-IND_L*1.2,0,0), new THREE.Vector3(IND_L*1.2,0,0)]),
    new THREE.LineDashedMaterial({ color:COL.axis, dashSize:0.4, gapSize:0.25 }));
  dashed.computeLineDistances();
  guideGroup.add(dashed);

  // The field of a single moving point charge travels WITH it and is strongest in the
  // transverse plane through the charge. Build a co-moving cluster of B-circles (in
  // extraGroup) centred on x=0; animateInduced slides it along with the charge.
  // Circulation sense set by charge sign (right-hand rule about v for +q).
  const sense  = d.sign;
  const radius = SCENE_R * 0.7;
  const rings  = [ {dx:-1.0, op:0.12, n:3, r:0.80},
                   {dx:-0.5, op:0.30, n:4, r:0.92},
                   {dx: 0.0, op:0.58, n:6, r:1.00},
                   {dx: 0.5, op:0.30, n:4, r:0.92},
                   {dx: 1.0, op:0.12, n:3, r:0.80} ];
  if (sense !== 0)
    for (const rg of rings)
      makeCircArrows(extraGroup, rg.dx*SCENE_R*0.6, radius*rg.r, sense, COL.field, rg.op, rg.n);

  if (showField && sense !== 0) {
    const bl = makeTextSprite('B', '#9fa8da', SCENE_R*0.28);
    bl.position.set(0, radius + SCENE_R*0.42, 0);
    extraGroup.add(bl);
  }
  extraGroup.visible = showField;
  setChargeSprite(particle, d.sign);
  resetCycle();
}

function animateInduced(d) {
  const moving = d.moving;
  const speedN = clamp((Math.abs(d.v) / V_REF_IND), 0.25, 3.0);
  const dur    = IND_SEC / speedN;
  const u      = moving ? clamp(cycleT / dur, 0, 1) : 0.5;
  const x      = -IND_L + 2*IND_L*u;             // travel −L → +L (sign of v is +x)
  const pos    = new THREE.Vector3(x, 0, 0);

  particle.mesh.position.copy(pos);
  particle.mesh.visible = true;
  particle.chargeSprite.position.copy(pos).add(new THREE.Vector3(0, SCENE_R*0.32, 0));
  particle.chargeSprite.visible = showField;

  // the induced-field cluster rides along with the charge
  extraGroup.position.x = moving ? x : 0;

  hideAllVectors();
  if (showVel && moving) {
    setArrow(particle.velArrow, particle.velLabel, pos, new THREE.Vector3(1,0,0), SCENE_R*0.9, true);
  }
  return moving ? dur : null;
}

// ════════════════════════════════════════════════════════════════════════════
//  MODE 2 — MAGNETIC MOMENT
// ════════════════════════════════════════════════════════════════════════════
function buildMoment(d) {
  fieldGroup.clear(); guideGroup.clear(); extraGroup.clear();
  extraGroup.position.set(0,0,0); extraGroup.visible = true;
  if (particle.trail) { scene.remove(particle.trail); particle.trail.geometry.dispose(); particle.trail = null; }

  // display radius (atan-compressed) and animation rate
  const rL = (d.r_L === null) ? 0 : d.r_L;
  const rDisp = (rL > 0)
    ? clamp(SCENE_R * 1.25 * (2/Math.PI) * Math.atan(rL / MOM_RREF), SCENE_R*0.35, SCENE_R*1.7)
    : SCENE_R*0.5;
  const visOmega = (d.omega_c)
    ? clamp(Math.sqrt(d.omega_c / MOM_WREF), 0.35, 2.6) * 1.6
    : 0;
  // gyration sense: +q in B(+x) rotates clockwise seen from +x → −alpha; reverse for −q
  const rotSign = (d.sign === 0) ? 0 : -d.sign;
  momView = { rDisp, visOmega, rotSign };

  // applied uniform B field, faint straight arrows along +x (the field the charge gyrates in)
  const H = SCENE_R*1.3, step = SCENE_R*0.85;
  for (let iy=-1; iy<=1; iy++) for (let iz=-1; iz<=1; iz++) {
    const a = new THREE.ArrowHelper(new THREE.Vector3(1,0,0),
              new THREE.Vector3(-H, iy*step, iz*step), 2*H, COL.field,
              SCENE_R*0.18, SCENE_R*0.09);
    a.line.material.transparent = true; a.line.material.opacity = (iy||iz)?0.13:0.22;
    a.cone.material.transparent = true; a.cone.material.opacity = (iy||iz)?0.13:0.22;
    fieldGroup.add(a);
  }

  // induced field OF the loop: poloidal circles wrapping the wire. They thread −x̂
  // through the ring centre and add up to the dipole moment μ.
  if (d.sign !== 0) makePoloidalLoops(fieldGroup, rDisp, COL.field, 0.5, 8);
  fieldGroup.visible = showField;

  // the gyration orbit / current loop in the y-z plane
  const orbit = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(ringPoints(rDisp, 0)),
    new THREE.LineBasicMaterial({ color:COL.part, transparent:true, opacity:0.32 }));
  extraGroup.add(orbit);

  // current-direction arrowheads (conventional current follows +charge motion)
  if (d.sign !== 0) makeCircArrows(extraGroup, 0, rDisp, d.sign * momView.rotSign, COL.curr, 0.9, 4);

  if (showField) {
    const il = makeTextSprite('I', '#ffa726', SCENE_R*0.22);
    il.position.set(0, rDisp + SCENE_R*0.42, 0);
    guideGroup.add(il);
    const bl = makeTextSprite('B', '#9fa8da', SCENE_R*0.26);
    bl.position.set(H*0.92, SCENE_R*0.2, 0);
    guideGroup.add(bl);
    if (d.sign !== 0) {
      const sl = makeTextSprite('ΣB → μ', '#ec407a', SCENE_R*0.22);
      sl.position.set(-SCENE_R*0.9, 0, 0);
      guideGroup.add(sl);
    }
  }
  setChargeSprite(particle, d.sign);
  resetCycle();
}

function animateMoment(d) {
  const mv = momView;
  const phase = mv.rotSign * (tAccum * mv.visOmega);
  const pos = new THREE.Vector3(0, mv.rDisp*Math.cos(phase), mv.rDisp*Math.sin(phase));

  particle.mesh.position.copy(pos);
  particle.mesh.visible = true;
  particle.chargeSprite.position.copy(pos)
    .add(new THREE.Vector3(SCENE_R*0.13, SCENE_R*0.16, SCENE_R*0.13));
  particle.chargeSprite.visible = showField;

  hideAllVectors();
  // velocity tangent
  const tan = new THREE.Vector3(0, -Math.sin(phase), Math.cos(phase)).multiplyScalar(mv.rotSign);
  if (showVel && d.sign !== 0 && d.v_perp > 0)
    setArrow(particle.velArrow, particle.velLabel, pos, tan, SCENE_R*0.85, true);
  // magnetic moment μ antiparallel to B (diamagnetic) → −x, drawn from the centre
  if (showMu && d.sign !== 0)
    setArrow(particle.muArrow, particle.muLabel, new THREE.Vector3(0,0,0),
             new THREE.Vector3(-1,0,0), SCENE_R*0.9, true);
  return null;   // free-running, no end pause
}

// ════════════════════════════════════════════════════════════════════════════
//  MODE 3 — MAGNETIC MIRROR
// ════════════════════════════════════════════════════════════════════════════
function buildMirrorField(d) {
  fieldGroup.clear(); guideGroup.clear(); extraGroup.clear();
  extraGroup.position.set(0,0,0); extraGroup.visible = true;
  const R = d.R, L = BOTTLE_L;
  const rFL = xn => R_FL_MAX / Math.sqrt(bfac(xn, R));

  const NLINES = 14, SEG = 80;
  const lm = new THREE.LineBasicMaterial({ color:COL.field, transparent:true, opacity:0.4 });
  for (let k = 0; k < NLINES; k++) {
    const a = (k / NLINES) * 2 * Math.PI, ca = Math.cos(a), sa = Math.sin(a);
    const pts = [];
    for (let i = 0; i <= SEG; i++) {
      const xn = -1 + 2*i/SEG, r = rFL(xn);
      pts.push(new THREE.Vector3(xn*L, r*ca, r*sa));
    }
    fieldGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), lm));
  }

  const rm = new THREE.LineBasicMaterial({ color:COL.field, transparent:true, opacity:0.22 });
  for (const xn of [-1,-0.66,-0.33,0,0.33,0.66,1])
    fieldGroup.add(new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(ringPoints(rFL(xn), xn*L)), rm));

  const dashed = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-L*1.15,0,0), new THREE.Vector3(L*1.15,0,0)]),
    new THREE.LineDashedMaterial({ color:COL.axis, dashSize:0.4, gapSize:0.25 }));
  dashed.computeLineDistances();
  guideGroup.add(dashed);
  for (const xn of [-0.55, 0.05, 0.65])
    guideGroup.add(new THREE.ArrowHelper(new THREE.Vector3(1,0,0),
      new THREE.Vector3(xn*L,0,0), SCENE_R*0.5, COL.axis, SCENE_R*0.16, SCENE_R*0.08));

  const throatMat = new THREE.LineBasicMaterial({ color:COL.throat, transparent:true, opacity:0.9 });
  for (const sx of [-1, 1])
    fieldGroup.add(new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(ringPoints(rFL(1)*1.02, sx*L)), throatMat));

  if (d.trapped && d.turn_frac > 0.01) {
    const tMat = new THREE.LineBasicMaterial({ color:COL.turn, transparent:true, opacity:0.85 });
    for (const sx of [-1, 1]) {
      const xn = sx*d.turn_frac;
      fieldGroup.add(new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(ringPoints(rFL(xn)*1.02, xn*L)), tMat));
    }
  }

  if (showField) {
    const bL = makeTextSprite('B', '#9fa8da', SCENE_R*0.3);
    bL.position.set(L*0.95, SCENE_R*0.25, 0); guideGroup.add(bL);
    const throat = makeTextSprite('B_max', '#ef5350', SCENE_R*0.24);
    throat.position.set(L, rFL(1) + SCENE_R*0.45, 0); guideGroup.add(throat);
    if (d.trapped && d.turn_frac > 0.01) {
      const mp = makeTextSprite('mirror', '#ffb300', SCENE_R*0.22);
      mp.position.set(d.turn_frac*L, rFL(d.turn_frac) + SCENE_R*0.4, 0); guideGroup.add(mp);
    }
  }
  fieldGroup.visible = showField;
}

function buildMirrorTrajectory(d) {
  if (particle.trail) { scene.remove(particle.trail); particle.trail.geometry.dispose(); particle.trail = null; }

  const L  = BOTTLE_L, R = d.R;
  const th = d.theta_deg * Math.PI/180;
  const s2 = Math.sin(th)*Math.sin(th);
  const chargeSign = d.sign;
  const pos = [], bfA = [], vparA = [], vperpA = [];

  let nGyro = BASE_GYRO;
  if (d.omega_c0 > 0)
    nGyro = Math.round(clamp(BASE_GYRO*Math.sqrt(d.omega_c0/OMEGA_REF), GYRO_MIN, GYRO_MAX));

  const baseR = (chargeSign === 0 || d.v_perp0 === 0)
    ? 0 : R_FL_MAX * clamp(0.10 + 0.60*Math.sin(th), 0.10, 0.72);
  const gyroFrac = xn => baseR / Math.sqrt(bfac(xn, R));

  if (d.at_rest) {
    for (let i = 0; i <= 1; i++) { pos.push(new THREE.Vector3(0,0,0)); bfA.push(1); vparA.push(0); vperpA.push(0); }
    path = { pos, bf:bfA, vpar:vparA, vperp:vperpA, periodic:false, dur:3.0 };
  } else if (d.trapped) {
    const Bf = i => bfac(d.turn_frac*Math.sin(2*Math.PI*i/NS), R);
    let Itot = 0;
    for (let i = 0; i < NS; i++) Itot += Bf(i) * (2*Math.PI/NS);
    let acc = 0;
    for (let i = 0; i <= NS; i++) {
      const psi = 2*Math.PI*i/NS, xn = d.turn_frac*Math.sin(psi), bf = bfac(xn, R);
      const phi = chargeSign * 2*Math.PI*nGyro * (acc/Itot), rG = gyroFrac(xn);
      pos.push(new THREE.Vector3(xn*L, rG*Math.cos(phi), rG*Math.sin(phi)));
      bfA.push(bf);
      vparA.push(Math.sqrt(Math.max(0,1 - s2*bf)) * Math.sign(Math.cos(psi)));
      vperpA.push(Math.sqrt(Math.max(0, s2*bf)));
      if (i < NS) acc += bf * (2*Math.PI/NS);
    }
    path = { pos, bf:bfA, vpar:vparA, vperp:vperpA, periodic:true, dur:TRAVEL_TRAP };
  } else {
    const XN_END = 1.18;
    let Itot = 0;
    for (let i = 0; i < NS; i++) Itot += bfac(XN_END*i/NS, R) * (1/NS);
    let acc = 0;
    for (let i = 0; i <= NS; i++) {
      const xn = XN_END*i/NS, bf = bfac(xn, R);
      const phi = chargeSign * 2*Math.PI*nGyro * (Itot > 0 ? acc/Itot : 0), rG = gyroFrac(xn);
      pos.push(new THREE.Vector3(xn*L, rG*Math.cos(phi), rG*Math.sin(phi)));
      bfA.push(bf);
      vparA.push(Math.sqrt(Math.max(0,1 - s2*bf)));
      vperpA.push(Math.sqrt(Math.max(0, s2*bf)));
      if (i < NS) acc += bf * (1/NS);
    }
    path = { pos, bf:bfA, vpar:vparA, vperp:vperpA, periodic:false, dur:TRAVEL_ESC };
  }

  particle.trail = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(pos),
    new THREE.LineBasicMaterial({ color:COL.part, transparent:true, opacity:0.22 }));
  scene.add(particle.trail);
  setChargeSprite(particle, d.sign);
  resetCycle();
}

function tangentAt(i) {
  const N = path.pos.length;
  let a, b;
  if (path.periodic) { a = (i-1+(N-1)) % (N-1); b = (i+1) % (N-1); }
  else { a = clamp(i-1,0,N-1); b = clamp(i+1,0,N-1); }
  const d = path.pos[b].clone().sub(path.pos[a]);
  return d.lengthSq() > 1e-12 ? d.normalize() : new THREE.Vector3(1,0,0);
}

function animateMirror(d) {
  const N = path.pos.length;
  const u = clamp(cycleT / Math.max(path.dur, 1e-9), 0, 1);
  const idx = clamp(Math.round(u*(N-1)), 0, N-1);
  const pos = path.pos[idx];
  const off = new THREE.Vector3(SCENE_R*0.13, SCENE_R*0.16, SCENE_R*0.13);

  particle.mesh.position.copy(pos);
  particle.mesh.visible = true;
  particle.chargeSprite.position.copy(pos).add(off);
  particle.chargeSprite.visible = showField;

  hideAllVectors();
  if (d.at_rest) { if ((liveTick++ % 4) === 0) updateLive(idx); return path.dur; }

  const tan    = tangentAt(idx);
  const vparF  = Math.abs(path.vpar[idx]);
  const vparS  = Math.sign(path.vpar[idx]) || 1;
  const vperpF = path.vperp[idx];
  const vlen   = SCENE_R*0.9;

  setArrow(particle.velArrow, particle.velLabel, pos, tan, vlen, showVel);

  const sComp = showComp && d.sign !== 0;
  const perp  = new THREE.Vector3(0, tan.y, tan.z);
  const perpD = perp.lengthSq() > 1e-9 ? perp.normalize() : new THREE.Vector3(0,1,0);
  setArrow(particle.vparArrow,  particle.vparLabel,  pos, new THREE.Vector3(vparS,0,0),
           vlen*Math.max(vparF,0.001),  sComp && vparF>0.02);
  setArrow(particle.vperpArrow, particle.vperpLabel, pos, perpD,
           vlen*Math.max(vperpF,0.001), sComp && vperpF>0.02);

  setArrow(particle.muArrow, particle.muLabel, pos, new THREE.Vector3(-1,0,0),
           SCENE_R*0.6, showMu && d.sign !== 0);

  if ((liveTick++ % 4) === 0) updateLive(idx);
  return path.dur;
}

// ── shared arrow setter ────────────────────────────────────────────────────────
function setArrow(arrow, label, pos, dir, len, show) {
  if (!show) { arrow.visible = false; label.visible = false; return; }
  arrow.position.copy(pos);
  arrow.setDirection(dir);
  arrow.setLength(len, len*0.3, len*0.17);
  arrow.visible = true;
  label.position.copy(pos).addScaledVector(dir, len + SCENE_R*0.13);
  label.visible = true;
}

// ════════════════════════════════════════════════════════════════════════════
//  ANIMATION LOOP
// ════════════════════════════════════════════════════════════════════════════
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  const dt = Math.min(clock.getDelta(), 0.05);
  tAccum += dt;

  let dur = null;
  if (curData) {
    if (curData.mode === 'induced')      dur = animateInduced(curData);
    else if (curData.mode === 'moment')  dur = animateMoment(curData);
    else if (curData.mode === 'mirror')  dur = animateMirror(curData);
  }

  renderer.render(scene, camera);

  // advance / loop (modes that report a finite duration; moment free-runs on tAccum)
  if (dur !== null) {
    if (cycleT >= dur) {
      cyclePauseT += dt;
      if (cyclePauseT >= END_PAUSE) resetCycle();
    } else {
      cycleT = Math.min(cycleT + dt, dur);
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
function fmtT(x) {
  if (x===null||x===undefined||!Number.isFinite(x)) return '∞';
  if (x===0) return '0 T';
  const a = Math.abs(x);
  return ((a>=1e3||a<1e-3) ? x.toExponential(3) : x.toPrecision(4)) + ' T';
}
function showError(msg){ $('error-msg').textContent=msg; $('error-msg').style.display='block'; }
function clearError(){ $('error-msg').style.display='none'; }

function writeOutputs(d) {
  if (d.mode === 'induced') {
    $('o-ind-q').textContent = d.sign>0 ? '+ (positive)' : (d.sign<0 ? '− (negative)' : '0 (neutral)');
    $('o-ind-c').textContent = d.circ;
  } else if (d.mode === 'moment') {
    $('o-mom-rL').textContent = (d.r_L===null)?'—':fmt(d.r_L);
    $('o-mom-wc').textContent = (d.omega_c===null)?'—':fmt(d.omega_c);
    $('o-mom-mu').textContent = fmt(d.mu);
    $('o-mom-Tc').textContent = (d.T_c===null)?'—':fmt(d.T_c);
  } else {
    $('o-mir-mu').textContent    = fmt(d.mu);
    $('o-mir-vperp').textContent = fmt(d.v_perp0);
    $('o-mir-vpar').textContent  = fmt(d.v_par0);
    $('o-mir-bstop').textContent = (d.B_stop===null) ? '∞' : fmt(d.B_stop);
    $('o-mir-bmax').textContent  = fmt(d.B_max);
    $('o-mir-loss').textContent  = fmt(d.loss_cone_deg);
    $('o-mir-status').textContent= d.status;
  }
}

function updateLive(idx) {
  if (!curData || !path || curData.mode !== 'mirror') return;
  const bf = path.bf[idx];
  $('live-B').textContent     = fmtT(curData.B0 * bf);
  $('live-vpar').textContent  = fmt(curData.v0 * Math.abs(path.vpar[idx])) + ' m/s';
  $('live-vperp').textContent = fmt(curData.v0 * path.vperp[idx]) + ' m/s';
}

function updateGeomReadout() {
  const R  = +$('R-r').value, B0 = +$('mir-B0').value;
  $('R-disp').textContent = R.toFixed(1);
  $('b-loss').textContent = (Math.asin(Math.min(1,Math.sqrt(1/R)))*180/Math.PI).toFixed(1)+'°';
  $('b-bmax').textContent = fmtT(R*B0);
}

// ── presets / input reading ─────────────────────────────────────────────────────
function applyPreset() {
  const pr = PRESETS[$('preset').value];
  if (!pr) return;
  $('inp-mass').value = pr.m;
  $('inp-qmag').value = Math.abs(pr.q);
  $('inp-sign').value = pr.q < 0 ? '-' : '+';
}

function chargeSigned() {
  const sign = $('inp-sign').value === '-' ? -1 : 1;
  return sign * Math.abs(+$('inp-qmag').value);
}

function readInputs() {
  if (mode === 'induced')
    return { mode:'induced', q_e: chargeSigned(), v: +$('ind-speed').value };
  if (mode === 'moment')
    return { mode:'moment', m_amu:+$('inp-mass').value, q_e: chargeSigned(),
             v_perp:+$('mom-vperp').value, B:+$('mom-B').value };
  return { mode:'mirror', m_amu:+$('inp-mass').value, q_e: chargeSigned(),
           v0:+$('mir-speed').value, theta_deg:+$('theta-r').value,
           B0:+$('mir-B0').value, R:+$('R-r').value };
}

async function api(payload) {
  const res = await fetch('/api/compute', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  return res.json();
}

// ── main update ────────────────────────────────────────────────────────────────
async function runUpdate() {
  clearError();
  if (mode === 'mirror') updateGeomReadout();
  try {
    const d = await api(readInputs());
    if (d.error) { showError(d.error); return; }
    curData = d;
    writeOutputs(d);
    if (mode === 'induced')     buildInduced(d);
    else if (mode === 'moment') buildMoment(d);
    else { buildMirrorField(d); buildMirrorTrajectory(d); }
    if (!firstRenderDone) { frameCamera(); firstRenderDone = true; }
  } catch(e) { showError('Server error: '+e.message); }
}

function frameCamera() {
  controls.target.set(0,0,0);
  if (mode === 'moment')
    camera.position.set(SCENE_R*3.4, SCENE_R*1.2, SCENE_R*3.2);
  else if (mode === 'induced')
    camera.position.set(SCENE_R*0.6, SCENE_R*1.5, SCENE_R*4.4);
  else
    camera.position.set(SCENE_R*0.1, SCENE_R*1.7, SCENE_R*4.6);
  controls.update();
}

// ════════════════════════════════════════════════════════════════════════════
//  MODE SWITCHING
// ════════════════════════════════════════════════════════════════════════════
function setMode(m) {
  mode = m;
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.mode === m));

  const isInd = m==='induced', isMom = m==='moment', isMir = m==='mirror';
  $('grp-induced').classList.toggle('hide', !isInd);
  $('grp-moment').classList.toggle('hide',  !isMom);
  $('grp-mirror').classList.toggle('hide',  !isMir);

  // particle block: induced needs only charge sign (no mass / magnitude / preset)
  $('row-mass').classList.toggle('hide', isInd);
  $('row-preset').classList.toggle('hide', isInd);
  $('inp-qmag').parentElement.parentElement.style.display = '';   // keep charge row

  // output rows
  document.querySelectorAll('.r-induced').forEach(el => el.classList.toggle('hide', !isInd));
  document.querySelectorAll('.r-moment').forEach(el => el.classList.toggle('hide',  !isMom));
  document.querySelectorAll('.r-mirror').forEach(el => el.classList.toggle('hide',  !isMir));

  // toggles relevant per mode
  document.querySelectorAll('.m-comp').forEach(el => el.classList.toggle('hide', !isMir));
  document.querySelectorAll('.m-mu').forEach(el => el.classList.toggle('hide', isInd));
  document.querySelectorAll('#legend .m-mirror').forEach(el => el.classList.toggle('hide', !isMir));

  // live box only meaningful for the mirror
  $('livebox').classList.toggle('hide', !isMir);

  $('title').textContent = isInd ? 'Induced B Field' : (isMom ? 'Magnetic Moment' : 'Magnetic Mirror');

  // clear scene leftovers then rebuild
  fieldGroup.clear(); guideGroup.clear(); extraGroup.clear();
  extraGroup.position.set(0,0,0); extraGroup.visible = true;
  if (particle.trail) { scene.remove(particle.trail); particle.trail.geometry.dispose(); particle.trail = null; }
  hideAllVectors();
  resetCycle(); tAccum = 0;

  frameCamera();
  runUpdate();
}

// ── event wiring ───────────────────────────────────────────────────────────────
let _deb = null;
const debounced = () => { clearTimeout(_deb); _deb = setTimeout(runUpdate,150); };

document.querySelectorAll('.tab').forEach(t =>
  t.addEventListener('click', () => setMode(t.dataset.mode)));

$('preset').addEventListener('change', () => { applyPreset(); debounced(); });
['inp-mass','inp-qmag','inp-sign'].forEach(id =>
  $(id).addEventListener('input', () => { $('preset').value='custom'; debounced(); }));

$('ind-speed').addEventListener('input', debounced);
$('mom-vperp').addEventListener('input', debounced);
$('mom-B').addEventListener('input', debounced);
$('mir-speed').addEventListener('input', debounced);
$('mir-B0').addEventListener('input', () => { updateGeomReadout(); debounced(); });
$('theta-r').addEventListener('input', () => { $('theta-disp').textContent=$('theta-r').value; debounced(); });
$('R-r').addEventListener('input', () => { updateGeomReadout(); debounced(); });

$('chk-labels').addEventListener('change', () => {
  showField = $('chk-labels').checked;
  if (curData) {
    if (mode==='induced') buildInduced(curData);
    else if (mode==='moment') buildMoment(curData);
    else buildMirrorField(curData);
  }
});
$('chk-vel').addEventListener('change',  () => { showVel  = $('chk-vel').checked; });
$('chk-comp').addEventListener('change', () => { showComp = $('chk-comp').checked; });
$('chk-mu').addEventListener('change',   () => { showMu   = $('chk-mu').checked; });
$('btn-run').addEventListener('click', runUpdate);

// ── boot ───────────────────────────────────────────────────────────────────────
initViz(document.getElementById('viewport'));
applyPreset();
updateGeomReadout();
setMode('induced');
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


HOST = "127.0.0.1"
# Candidate ports tried in order. Windows can forbid a port (WinError 10013) when it
# falls in an excluded/reserved range (Hyper-V, WSL, etc.); 0 lets the OS pick a free one.
PORTS = (8002, 8012, 8042, 8088, 8765, 9002, 0)


def _serve():
    last_err = None
    for port in PORTS:
        try:
            srv = _Server((HOST, port), Handler)
        except (OSError, PermissionError) as exc:
            last_err = exc
            continue
        actual = srv.server_address[1]
        url = f"http://{HOST}:{actual}"
        print(f"\n  Magnetism Applets -> {url}\n  Ctrl-C to quit.\n")
        webbrowser.open(url)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down.")
            srv.shutdown()
        return
    raise SystemExit(f"Could not bind any port {PORTS}: {last_err}")


if __name__ == "__main__":
    _serve()
