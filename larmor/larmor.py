#!/usr/bin/env python3
"""
larmor_applet.py — Larmor Motion Applet
Single-file, stdlib-only. Run: python larmor_applet.py
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

def compute(m_amu, q_e, v, theta_deg, B):
    for name, val in (("m_amu", m_amu), ("q_e", q_e), ("v", v),
                      ("theta_deg", theta_deg), ("B", B)):
        if not math.isfinite(float(val)):
            raise ValueError(f"'{name}' must be a finite number.")
    if float(B) <= 0:
        raise ValueError("|B| must be positive.")
    if float(v) == 0:
        raise ValueError("|v| cannot be zero.")
    if float(m_amu) <= 0:
        raise ValueError("Mass must be positive.")

    m = float(m_amu) * AMU
    q = float(q_e) * E_C
    th = math.radians(float(theta_deg))
    v_par  = v * math.cos(th)
    v_perp = v * math.sin(th)
    absq   = abs(q)

    if absq == 0:
        return {"v_par": v_par, "v_perp": v_perp,
                "r_L": None, "omega_c": None, "mu": None,
                "T_c": None, "pitch": None, "sign": 0}

    omega_c = absq * B / m
    if omega_c == 0.0:
        return {"v_par": v_par, "v_perp": v_perp,
                "r_L": None, "omega_c": None, "mu": None,
                "T_c": None, "pitch": None, "sign": 0}

    r_L   = m * v_perp / (absq * B) if v_perp else 0.0
    mu    = m * v_perp**2 / (2.0 * B)
    T_c   = 2.0 * math.pi / omega_c
    pitch = v_par * T_c

    return {"v_par": v_par, "v_perp": v_perp,
            "r_L": r_L, "omega_c": omega_c, "mu": mu,
            "T_c": T_c, "pitch": pitch,
            "sign": 1 if q > 0 else -1}

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Larmor Motion Applet</title>
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
  width:288px;min-width:288px;
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
input[type="range"]{width:100%;accent-color:#42a5f5;margin-top:2px}
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
#btn-run{background:#1565c0;border:none;border-radius:5px;color:#fff;cursor:pointer;
         font-size:13px;font-weight:600;padding:9px;transition:background .15s;
         width:100%;letter-spacing:.04em;}
#btn-run:hover{background:#1976d2}
#btn-run:active{background:#0d47a1}
.chk{display:flex;align-items:center;gap:8px;font-size:11px;color:#90a4ae;cursor:pointer;
     user-select:none;background:#0d1117;border:1px solid #182330;border-radius:5px;padding:8px 10px;}
.chk input{accent-color:#ef5350;width:14px;height:14px}
#otable{width:100%;border-collapse:collapse;font-size:10px}
#otable th{font-size:9px;color:#546e7a;text-transform:uppercase;letter-spacing:.05em;
           padding:3px 4px;text-align:right;font-weight:700;}
#otable th:first-child{text-align:left}
#otable td{padding:3px 4px;font-family:'Cascadia Code','Fira Mono',monospace;
           text-align:right;color:#4fc3f7;}
#otable td:first-child{text-align:left;color:#607d8b;
                       font-family:'Segoe UI',sans-serif;font-size:10px;}
#otable tr+tr td{border-top:1px solid #141d27}
#error-msg{background:#4a0000;border:1px solid #c62828;border-radius:4px;
           color:#ef9a9a;font-size:11px;padding:7px 9px;display:none;}
#legend{margin-top:auto;background:#0d1117;border:1px solid #182330;
        border-radius:5px;padding:8px 10px;font-size:10px;line-height:2.0;}
#legend span.sw{display:inline-block;width:9px;height:9px;border-radius:50%;
             margin-right:6px;vertical-align:middle;}
#viewport{flex:1;overflow:hidden;position:relative}
#viewport canvas{display:block}
</style>
</head>
<body>

<div id="panel">
  <h1>Larmor Motion</h1>

  <!-- Ion / single particle -->
  <div class="pblock" id="block-A">
    <div class="phead"><span class="dot" style="background:#ff6e40"></span><span id="A-head">Ion</span></div>
    <div class="field">
      <label>Preset</label>
      <select id="A-preset">
        <option value="custom">Custom</option>
        <option value="xenon" selected>Xenon&#8314; (131.29 amu)</option>
        <option value="krypton">Krypton&#8314; (83.80 amu)</option>
        <option value="iodine">Iodine&#8314; (126.90 amu)</option>
        <option value="electron">Electron (e&#8315;)</option>
      </select>
    </div>
    <div class="field">
      <label>Mass <i>m</i> [amu]</label>
      <input type="number" id="A-mass" value="131.293" min="0.0000001" step="0.001">
    </div>
    <div class="field">
      <label>Charge <i>q</i> [e]</label>
      <div class="row2">
        <input type="number" id="A-qmag" value="1" min="0" step="1">
        <select id="A-sign">
          <option value="+">+</option>
          <option value="-">&#x2212;</option>
        </select>
      </div>
    </div>
  </div>

  <!-- Electron (two-particle mode) -->
  <div class="pblock" id="block-B">
    <div class="phead"><span class="dot" style="background:#4fc3f7"></span><span id="B-head">Electron</span></div>
    <div class="field">
      <label>Preset</label>
      <select id="B-preset">
        <option value="custom">Custom</option>
        <option value="xenon">Xenon&#8314; (131.29 amu)</option>
        <option value="krypton">Krypton&#8314; (83.80 amu)</option>
        <option value="iodine">Iodine&#8314; (126.90 amu)</option>
        <option value="electron" selected>Electron (e&#8315;)</option>
      </select>
    </div>
    <div class="field">
      <label>Mass <i>m</i> [amu]</label>
      <input type="number" id="B-mass" value="0.000548579909" min="0.0000001" step="0.001">
    </div>
    <div class="field">
      <label>Charge <i>q</i> [e]</label>
      <div class="row2">
        <input type="number" id="B-qmag" value="1" min="0" step="1">
        <select id="B-sign">
          <option value="+">+</option>
          <option value="-" selected>&#x2212;</option>
        </select>
      </div>
    </div>
  </div>

  <!-- Shared controls -->
  <div class="field">
    <label>|B| flux density [G] &nbsp;<i>(shared)</i></label>
    <input type="number" id="inp-BG" value="10000" min="1" step="100">
    <div class="readout">Equivalent: <b id="b-tesla">1.000 T</b></div>
  </div>

  <div class="field">
    <label>|v| speed [m/s] &nbsp;<i>(shared)</i></label>
    <input type="number" id="inp-speed" value="1000000" min="1" step="10000">
  </div>

  <div class="field">
    <label>Pitch angle &#952; = <b id="theta-disp">45</b>&#xB0; &nbsp;<i>(shared)</i></label>
    <input type="range" id="theta-r" min="0" max="90" value="45" step="1">
  </div>

  <!-- ── overlay toggles ── -->
  <label class="chk" for="chk-labels">
    <input type="checkbox" id="chk-labels" checked>
    Show charge / name labels
  </label>

  <label class="chk" for="chk-vel">
    <input type="checkbox" id="chk-vel" checked>
    Show velocity vector <b style="color:#ffd54f">V</b>
  </label>

  <label class="chk" for="chk-force">
    <input type="checkbox" id="chk-force">
    Show magnetic force <b style="color:#ef5350">F<sub>b</sub></b>
  </label>

  <button id="btn-run">&#9654;&#xFE0E;&nbsp; Run / Update</button>
  <div id="error-msg"></div>

  <div>
    <div class="sec">Outputs</div>
    <table id="otable">
      <tr>
        <th></th>
        <th id="th-A" style="color:#ff6e40">Ion</th>
        <th id="th-B" class="col-B" style="color:#4fc3f7">Electron</th>
      </tr>
      <tr><td>r<sub>L</sub> [m]</td>   <td id="A-rL">&#x2014;</td>  <td id="B-rL" class="col-B">&#x2014;</td></tr>
      <tr><td>&#x3C9;<sub>c</sub> [rad/s]</td><td id="A-wc">&#x2014;</td><td id="B-wc" class="col-B">&#x2014;</td></tr>
      <tr><td>&#x3BC; [J/T]</td>        <td id="A-mu">&#x2014;</td>  <td id="B-mu" class="col-B">&#x2014;</td></tr>
      <tr><td>v&#x2225; [m/s]</td>      <td id="A-vpar">&#x2014;</td><td id="B-vpar" class="col-B">&#x2014;</td></tr>
      <tr><td>v&#x22A5; [m/s]</td>      <td id="A-vperp">&#x2014;</td><td id="B-vperp" class="col-B">&#x2014;</td></tr>
      <tr><td>T<sub>c</sub> [s]</td>    <td id="A-Tc">&#x2014;</td>  <td id="B-Tc" class="col-B">&#x2014;</td></tr>
      <tr><td>pitch [m]</td>            <td id="A-pitch">&#x2014;</td><td id="B-pitch" class="col-B">&#x2014;</td></tr>
    </table>
  </div>

  <div id="legend">
    <div><span class="sw" style="background:#ff6e40"></span><b id="leg-A">Ion</b></div>
    <div id="leg-elec-row"><span class="sw" style="background:#4fc3f7"></span>Electron</div>
    <div><span class="sw" style="background:#ffd54f"></span>V velocity</div>
    <div><span class="sw" style="background:#ef5350"></span>F<sub>b</sub> magnetic force</div>
    <div><span class="sw" style="background:#37474f;border:1px solid #546e7a;border-radius:2px"></span>B field (+z)</div>
  </div>
</div>

<div id="viewport"></div>

<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

/* ───────────────────────────────────────────────────────────────────────────
   DEVELOPER SWITCH
   'two' → an ion (+ charge) and an electron (- charge)
   'one' → a single particle whose charge can be +, - or 0
   ─────────────────────────────────────────────────────────────────────────── */
const MODE = 'two';

const SCENE_R        = 5.0;
const SEG_PER_TURN   = 48;
const TRAVEL_SEC     = 7.0;
const END_PAUSE      = 0.6;
const GAUSS_TO_TESLA = 1e-4;

const RADIUS_REF_M = 1.0;

const TRAVEL_MULT = 3;
const AXIAL_BASE  = SCENE_R * 1.7;
const BASE_TURNS  = 3;
const MAX_TURNS   = 30;
const OMEGA_REF   = 7.0e5;
const FIELD_HALF  = SCENE_R * 2.8;

const clamp = (x,a,b) => Math.min(b, Math.max(a, x));

const PRESETS = {
  custom:   null,
  xenon:    { m: 131.293,        q: +1 },
  krypton:  { m: 83.798,         q: +1 },
  iodine:   { m: 126.90447,      q: +1 },
  electron: { m: 5.48579909e-4,  q: -1 },
};

const PCONF = [
  { key:'A', label:'Ion',      color:0xff6e40, emissive:0x3a1505, sphereScale:0.090 },
  { key:'B', label:'Electron', color:0x4fc3f7, emissive:0x082030, sphereScale:0.050 },
];

if (MODE === 'one') PCONF[0].label = 'Particle';

const ACTIVE = MODE === 'one' ? [PCONF[0]] : PCONF;

// ── overlay visibility flags ──────────────────────────────────────────────────
let showLabels = true;
let showVel    = true;
let showForces = false;

// ── generic text sprite ───────────────────────────────────────────────────────
function makeTextSprite(text, color, height = SCENE_R * 0.28) {
  const canvas = document.createElement('canvas');
  const ctx    = canvas.getContext('2d');
  const fs     = 72, px = 24, py = 16;

  ctx.font = `700 ${fs}px Segoe UI,Arial,sans-serif`;
  const tw = ctx.measureText(text).width;

  canvas.width  = Math.ceil(tw + px*2);
  canvas.height = Math.ceil(fs*1.25 + py*2);

  ctx.font = `700 ${fs}px Segoe UI,Arial,sans-serif`;
  ctx.fillStyle = 'rgba(11,14,20,0.72)';
  ctx.strokeStyle = 'rgba(207,216,220,0.25)';
  ctx.lineWidth = 4;

  const r = 18;
  const [x,y,w,h] = [2,2,canvas.width-4,canvas.height-4];

  ctx.beginPath();
  ctx.moveTo(x+r,y); ctx.lineTo(x+w-r,y);
  ctx.quadraticCurveTo(x+w,y,x+w,y+r);
  ctx.lineTo(x+w,y+h-r);
  ctx.quadraticCurveTo(x+w,y+h,x+w-r,y+h);
  ctx.lineTo(x+r,y+h);
  ctx.quadraticCurveTo(x,y+h,x,y+h-r);
  ctx.lineTo(x,y+r);
  ctx.quadraticCurveTo(x,y,x+r,y);
  ctx.closePath();
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

// ── B-field label: "B" with a hand-drawn vector arrow above it ───────────────
// Uses Canvas 2D paths so the arrow is guaranteed to render on every platform,
// unlike Unicode combining diacritics which vary by font/OS.
// Colour matches the 0x37474f B-field ArrowHelpers in the scene.
function makeBLabelSprite(height = SCENE_R * 0.38) {
  const B_COLOR = '#37474f'; // identical to the B-field ArrowHelper colour

  const canvas = document.createElement('canvas');
  const ctx    = canvas.getContext('2d');

  const fs      = 72;          // letter font size (px)
  const px      = 26, py = 14; // horizontal / vertical padding
  const arrowH  = 24;          // pixel height reserved for the arrow above B
  const gap     = 8;           // gap between bottom of arrow zone and top of letter

  // Arrowhead geometry (pixels at canvas resolution).
  const headW = 22, headH = 18;

  // Measure the "B" glyph width so we can size the canvas correctly.
  ctx.font = `700 ${fs}px Segoe UI,Arial,sans-serif`;
  const tw = ctx.measureText('B').width;

  const cw = Math.ceil(tw + px * 2);
  const ch = Math.ceil(fs * 1.2 + arrowH + gap + py * 2);

  canvas.width  = cw;
  canvas.height = ch;

  // ── rounded-rect background ────────────────────────────────────────────────
  ctx.fillStyle   = 'rgba(11,14,20,0.72)';
  ctx.strokeStyle = 'rgba(207,216,220,0.18)';
  ctx.lineWidth   = 3;

  const br = 14;
  const [bx, by, bw, bh] = [2, 2, cw - 4, ch - 4];

  ctx.beginPath();
  ctx.moveTo(bx+br, by);        ctx.lineTo(bx+bw-br, by);
  ctx.quadraticCurveTo(bx+bw, by,    bx+bw, by+br);
  ctx.lineTo(bx+bw, by+bh-br);
  ctx.quadraticCurveTo(bx+bw, by+bh, bx+bw-br, by+bh);
  ctx.lineTo(bx+br, by+bh);
  ctx.quadraticCurveTo(bx, by+bh,    bx, by+bh-br);
  ctx.lineTo(bx, by+br);
  ctx.quadraticCurveTo(bx, by,       bx+br, by);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  // ── vector arrow above the letter ─────────────────────────────────────────
  const midX      = cw / 2;
  const arrowY    = py + arrowH / 2;           // vertical centre of arrow zone
  const shaftL    = midX - tw * 0.38;          // shaft start x
  const shaftR    = midX + tw * 0.38;          // tip x (rightmost point)
  const shaftEnd  = shaftR - headW * 0.6;      // shaft ends before the head

  // Shaft
  ctx.strokeStyle = B_COLOR;
  ctx.lineWidth   = 6;
  ctx.lineCap     = 'round';
  ctx.beginPath();
  ctx.moveTo(shaftL, arrowY);
  ctx.lineTo(shaftEnd, arrowY);
  ctx.stroke();

  // Filled triangular arrowhead pointing right
  ctx.fillStyle = B_COLOR;
  ctx.beginPath();
  ctx.moveTo(shaftR,           arrowY);
  ctx.lineTo(shaftR - headW,   arrowY - headH / 2);
  ctx.lineTo(shaftR - headW,   arrowY + headH / 2);
  ctx.closePath();
  ctx.fill();

  // ── "B" letter ─────────────────────────────────────────────────────────────
  ctx.font         = `700 ${fs}px Segoe UI,Arial,sans-serif`;
  ctx.fillStyle    = B_COLOR;
  ctx.textAlign    = 'center';
  ctx.textBaseline = 'top';
  ctx.fillText('B', midX, py + arrowH + gap);

  // ── build sprite ───────────────────────────────────────────────────────────
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;

  const sp = new THREE.Sprite(new THREE.SpriteMaterial({
    map: tex, transparent: true, depthTest: false, depthWrite: false
  }));

  sp.scale.set(height * (cw / ch), height, 1);
  sp.renderOrder = 999;
  return sp;
}

// ── scene globals ─────────────────────────────────────────────────────────────
let renderer, scene, camera, controls, clock;
let fieldGroup, guideGroup;
let parts = [];
let firstRenderDone = false;

let cycleT = 0;
let cyclePauseT = 0;

function resetCycle() {
  cycleT = 0;
  cyclePauseT = 0;
}

// ── charge-sign sprite over an orb ────────────────────────────────────────────
function setChargeSprite(p, sign) {
  if (p.chargeSprite && p.curSign === sign) return;

  if (p.chargeSprite) {
    scene.remove(p.chargeSprite);
    if (p.chargeSprite.material.map) p.chargeSprite.material.map.dispose();
    p.chargeSprite.material.dispose();
  }

  const hexC = '#'+p.conf.color.toString(16).padStart(6,'0');
  const glyph = sign < 0 ? '\u2212' : (sign > 0 ? '+' : '0');

  p.chargeSprite = makeTextSprite(glyph, hexC, SCENE_R*0.40);
  scene.add(p.chargeSprite);
  p.curSign = sign;
}

// ── build one particle object ─────────────────────────────────────────────────
function makeParticle(conf) {
  const p = { conf, cur:null, data:null, helixLine:null, tubeMesh:null,
              chargeSprite:null, curSign:null };

  p.mesh = new THREE.Mesh(
    new THREE.SphereGeometry(SCENE_R*conf.sphereScale, 24, 24),
    new THREE.MeshStandardMaterial({
      color:conf.color, emissive:conf.emissive, roughness:0.35
    })
  );
  scene.add(p.mesh);

  setChargeSprite(p, conf.key === 'B' ? -1 : 1);

  p.velArrow = new THREE.ArrowHelper(
    new THREE.Vector3(1,0,0), new THREE.Vector3(),
    SCENE_R*0.85, 0xffd54f, SCENE_R*0.22, SCENE_R*0.1
  );
  scene.add(p.velArrow);

  p.velLabel = makeTextSprite('V', '#ffd54f', SCENE_R*0.27);
  scene.add(p.velLabel);

  p.forceArrow = new THREE.ArrowHelper(
    new THREE.Vector3(1,0,0), new THREE.Vector3(),
    SCENE_R*0.6, 0xef5350, SCENE_R*0.18, SCENE_R*0.09
  );
  p.forceArrow.visible = false;
  scene.add(p.forceArrow);

  p.forceLabel = makeTextSprite('F_b', '#ef5350', SCENE_R*0.27);
  p.forceLabel.visible = false;
  scene.add(p.forceLabel);

  return p;
}

// ── init Three.js ─────────────────────────────────────────────────────────────
function initViz(container) {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b0e14);

  const w = container.clientWidth;
  const h = container.clientHeight;

  renderer = new THREE.WebGLRenderer({ antialias:true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(w,h);
  container.appendChild(renderer.domElement);

  camera = new THREE.PerspectiveCamera(50, w/h, 0.01, 5000);
  camera.position.set(SCENE_R*2.4, SCENE_R*1.7, SCENE_R*2.8);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.07;

  scene.add(new THREE.AmbientLight(0xffffff, 0.55));
  const dl = new THREE.DirectionalLight(0xffffff, 0.85);
  dl.position.set(1,2,3);
  scene.add(dl);

  fieldGroup = new THREE.Group();
  guideGroup = new THREE.Group();
  scene.add(fieldGroup);
  scene.add(guideGroup);

  parts = ACTIVE.map(makeParticle);
  clock = new THREE.Clock();

  window.addEventListener('resize', () => {
    const w2 = container.clientWidth;
    const h2 = container.clientHeight;
    camera.aspect = w2/h2;
    camera.updateProjectionMatrix();
    renderer.setSize(w2,h2);
  });

  animate();
}

// ── field lines ───────────────────────────────────────────────────────────────
function buildFieldLines() {
  fieldGroup.clear();
  guideGroup.clear();

  const zHalf = FIELD_HALF;
  const N = 3;
  const step = SCENE_R*0.9;

  const lm = new THREE.LineBasicMaterial({
    color:0x1a2a35, transparent:true, opacity:0.9
  });

  for (let i=-N; i<=N; i++) {
    for (let j=-N; j<=N; j++) {
      if (Math.abs(i)+Math.abs(j) > N+1) continue;

      const x = i*step;
      const y = j*step;

      fieldGroup.add(new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(x,y,-zHalf),
          new THREE.Vector3(x,y, zHalf)
        ]),
        lm
      ));

      fieldGroup.add(new THREE.ArrowHelper(
        new THREE.Vector3(0,0,1),
        new THREE.Vector3(x,y,zHalf*0.5),
        zHalf*0.28, 0x37474f, zHalf*0.09, SCENE_R*0.05
      ));
    }
  }

  const dashed = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0,0,-zHalf),
      new THREE.Vector3(0,0, zHalf)
    ]),
    new THREE.LineDashedMaterial({ color:0x546e7a, dashSize:0.4, gapSize:0.25 })
  );
  dashed.computeLineDistances();
  guideGroup.add(dashed);

  // ── B-field label with canvas-drawn vector arrow ───────────────────────────
  // Placed at the far edge of the field grid, well away from the particle paths
  // (which run near x=0, y=0).  Colour matches the 0x37474f ArrowHelpers above.
  const bLabel = makeBLabelSprite(SCENE_R * 0.38);
  bLabel.position.set(SCENE_R * 2.4, SCENE_R * 0.4, zHalf * 0.85);
  guideGroup.add(bLabel);
}

// ── camera frame ──────────────────────────────────────────────────────────────
function frameCamera() {
  const box = new THREE.Box3();
  let any = false;

  for (const p of parts) {
    if (p.helixLine) { box.expandByObject(p.helixLine); any = true; }
  }

  if (!any) return;

  const sphere = new THREE.Sphere();
  box.getBoundingSphere(sphere);
  controls.target.copy(sphere.center);

  const fovRad = camera.fov * Math.PI / 180;
  const dist   = sphere.radius / Math.sin(fovRad/2) * 1.3;

  camera.position.copy(
    sphere.center.clone().addScaledVector(
      new THREE.Vector3(1.1,0.7,1.3).normalize(), dist
    )
  );

  controls.update();
}

// ── dispose old trajectory ────────────────────────────────────────────────────
function disposeTraj(p) {
  if (p.helixLine) {
    scene.remove(p.helixLine);
    p.helixLine.geometry.dispose();
    p.helixLine = null;
  }
  if (p.tubeMesh) {
    scene.remove(p.tubeMesh);
    p.tubeMesh.geometry.dispose();
    p.tubeMesh = null;
  }
}

// ── Larmor radius → visual radius ────────────────────────────────────────────
function displayRadiusFromLarmor(rL) {
  if (rL === null || rL === undefined || !Number.isFinite(rL) || rL <= 0) return 0;
  return SCENE_R * 1.35 * (2 / Math.PI) * Math.atan(rL / RADIUS_REF_M);
}

function computeDisplayRadii(datas) {
  const raw = d => displayRadiusFromLarmor(d.r_L);

  if (MODE === 'one') {
    return datas.map(d => { const r = raw(d); return r > 0 ? Math.max(r, SCENE_R*0.05) : 0; });
  }

  const ion = datas[0], el = datas[1];
  let ionR = raw(ion);
  if (ionR > 0) ionR = Math.max(ionR, SCENE_R*0.06);

  let elR = raw(el);
  if (elR > 0) {
    const upper = ionR > 0 ? ionR*0.75 : SCENE_R*0.2;
    elR = clamp(elR, SCENE_R*0.03, upper);
  }

  return [ionR, elR];
}

// ── helix helpers ─────────────────────────────────────────────────────────────
function helixPoint(rS, sign, turns, z0, commonZ, s) {
  s = clamp(s, 0, 1);
  const phase = sign * 2*Math.PI * turns * s;
  return new THREE.Vector3(rS*Math.cos(phase), rS*Math.sin(phase), z0+commonZ*s);
}

function commonAxialSpan() {
  const theta = +document.getElementById('theta-r').value;
  return AXIAL_BASE * TRAVEL_MULT * Math.cos(theta * Math.PI / 180);
}

function turnsFor(d) {
  if (!d || d.omega_c === null || d.omega_c === undefined || !Number.isFinite(d.omega_c))
    return BASE_TURNS;
  return clamp(BASE_TURNS * Math.sqrt(d.omega_c / OMEGA_REF), BASE_TURNS, MAX_TURNS);
}

// ── build trajectory ──────────────────────────────────────────────────────────
function updateTrajectory(p, data, commonZ, turns, rDisplay) {
  const { r_L, sign } = data;
  const col = p.conf.color;
  const z0 = -commonZ/2, z1 = commonZ/2;

  disposeTraj(p);

  if (r_L === null) {
    const start = new THREE.Vector3(0,0,z0);
    const end   = new THREE.Vector3(0,0,z1);
    const diff  = end.clone().sub(start);
    const len   = diff.length();
    const dir   = len > 1e-12 ? diff.clone().normalize() : new THREE.Vector3(0,0,1);
    const pts   = Array.from({length:33}, (_,i) => start.clone().lerp(end,i/32));

    p.helixLine = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color:col, transparent:true, opacity:0.18 })
    );
    scene.add(p.helixLine);

    const tubeEnd = len > 1e-12 ? end : new THREE.Vector3(0,0,z0+SCENE_R*0.01);
    p.tubeMesh = new THREE.Mesh(
      new THREE.TubeGeometry(new THREE.LineCurve3(start,tubeEnd), 2, SCENE_R*0.007, 8, false),
      new THREE.MeshStandardMaterial({ color:col, transparent:true, opacity:0.58, roughness:0.45, metalness:0.15 })
    );
    scene.add(p.tubeMesh);
    p.cur = { straight:true, start, end, dir, duration:TRAVEL_SEC };
    return;
  }

  const steps = Math.max(8, Math.ceil(turns * SEG_PER_TURN));
  const pts = rDisplay === 0
    ? [new THREE.Vector3(0,0,z0), new THREE.Vector3(0,0,z1)]
    : Array.from({length:steps+1}, (_,i) => helixPoint(rDisplay, sign, turns, z0, commonZ, i/steps));

  p.helixLine = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({ color:col, transparent:true, opacity:0.18 })
  );
  scene.add(p.helixLine);

  const tubeR = Math.max(rDisplay*0.018, SCENE_R*0.007);
  let tubeCurve, tubeSeg;

  if (rDisplay === 0) {
    const tubeEnd = Math.abs(commonZ) > 1e-12 ? new THREE.Vector3(0,0,z1) : new THREE.Vector3(0,0,z0+SCENE_R*0.01);
    tubeCurve = new THREE.LineCurve3(new THREE.Vector3(0,0,z0), tubeEnd);
    tubeSeg = 2;
  } else {
    tubeCurve = new THREE.CatmullRomCurve3(pts, false);
    tubeSeg = steps;
  }

  p.tubeMesh = new THREE.Mesh(
    new THREE.TubeGeometry(tubeCurve, tubeSeg, tubeR, 8, false),
    new THREE.MeshStandardMaterial({ color:col, transparent:true, opacity:0.58, roughness:0.45, metalness:0.15 })
  );
  scene.add(p.tubeMesh);
  p.cur = { straight:false, rS:rDisplay, sign, turns, z0, commonZ, duration:TRAVEL_SEC };
}

// ── position / tangent at parameter s ────────────────────────────────────────
function positionAt(cur, s) {
  if (cur.straight) return cur.start.clone().lerp(cur.end, clamp(s,0,1));
  return helixPoint(cur.rS, cur.sign, cur.turns, cur.z0, cur.commonZ, s);
}

function tangentAt(cur, s) {
  const eps = 0.001;
  const d = positionAt(cur, clamp(s+eps,0,1)).sub(positionAt(cur, clamp(s-eps,0,1)));
  const L = d.length();
  return L < 1e-12 ? new THREE.Vector3(0,0,1) : d.normalize();
}

// ── animation loop ────────────────────────────────────────────────────────────
function animate() {
  requestAnimationFrame(animate);
  controls.update();

  const dt  = Math.min(clock.getDelta(), 0.05);
  const off = new THREE.Vector3(SCENE_R*0.16, SCENE_R*0.16, SCENE_R*0.16);

  for (const p of parts) {
    if (!p.cur) continue;

    const s   = Math.min(cycleT / Math.max(p.cur.duration||1, 1e-9), 1.0);
    const pos = positionAt(p.cur, s);

    p.mesh.position.copy(pos);

    // charge / name label
    p.chargeSprite.position.copy(pos).add(off);
    p.chargeSprite.visible = showLabels;

    // velocity arrow + V label
    const velDir = p.cur.straight ? p.cur.dir : tangentAt(p.cur, s);
    p.velArrow.setDirection(velDir);
    p.velArrow.position.copy(pos);
    p.velArrow.visible = showVel;
    p.velLabel.position.copy(pos).addScaledVector(velDir, SCENE_R*0.95);
    p.velLabel.visible = showVel;

    // magnetic force arrow + F_b label
    if (p.cur.straight) {
      p.forceArrow.visible = false;
      p.forceLabel.visible = false;
    } else {
      const radial    = new THREE.Vector3(pos.x, pos.y, 0);
      const radialLen = radial.length();

      if (showForces && radialLen > SCENE_R*0.02) {
        const fd = radial.multiplyScalar(-1).normalize();
        p.forceArrow.setDirection(fd);
        p.forceArrow.position.copy(pos);
        p.forceArrow.visible = true;
        p.forceLabel.position.copy(pos).addScaledVector(fd, SCENE_R*0.72);
        p.forceLabel.visible = true;
      } else {
        p.forceArrow.visible = false;
        p.forceLabel.visible = false;
      }
    }
  }

  renderer.render(scene, camera);

  const active = parts.filter(p => p.cur);
  if (active.length) {
    const maxDur = Math.max(...active.map(p => p.cur.duration||0));
    if (cycleT >= maxDur) {
      cyclePauseT += dt;
      if (cyclePauseT >= END_PAUSE) resetCycle();
    } else {
      cycleT = Math.min(cycleT + dt, maxDur);
      cyclePauseT = 0;
    }
  }
}

// ── output table ──────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

function fmt(x) {
  if (x===null||x===undefined||isNaN(x)) return '\u2014';
  if (x===0) return '0';
  const a = Math.abs(x);
  return (a>=1e4||a<1e-2) ? x.toExponential(3) : x.toPrecision(4);
}

function fmtTesla(x) {
  if (!Number.isFinite(x)) return '\u2014 T';
  if (x===0) return '0 T';
  const a = Math.abs(x);
  return ((a>=1e3||a<1e-3) ? x.toExponential(3) : x.toPrecision(4)) + ' T';
}

function updateBReadout() {
  $('b-tesla').textContent = fmtTesla(+$('inp-BG').value * GAUSS_TO_TESLA);
}

function writeReadouts(key, d) {
  const f = (x,u) => x===null||x===undefined ? '\u2014' : fmt(x)+' '+u;
  $(key+'-rL').textContent    = f(d.r_L,     'm');
  $(key+'-wc').textContent    = f(d.omega_c, 'rad/s');
  $(key+'-mu').textContent    = f(d.mu,      'J/T');
  $(key+'-vpar').textContent  = f(d.v_par,   'm/s');
  $(key+'-vperp').textContent = f(d.v_perp,  'm/s');
  $(key+'-Tc').textContent    = f(d.T_c,     's');
  $(key+'-pitch').textContent = f(d.pitch,   'm');
}

function showError(msg) {
  $('error-msg').textContent = msg;
  $('error-msg').style.display = 'block';
}

function clearError() { $('error-msg').style.display = 'none'; }

// ── preset fill ───────────────────────────────────────────────────────────────
function applyPreset(key) {
  const pr = PRESETS[$(key+'-preset').value];
  if (!pr) return;
  $(key+'-mass').value = pr.m;
  $(key+'-qmag').value = Math.abs(pr.q);
  $(key+'-sign').value = pr.q < 0 ? '-' : '+';
  if (MODE==='two' && key==='A') $('A-sign').value = '+';
}

// ── read inputs ───────────────────────────────────────────────────────────────
function readParticle(key, B_T) {
  const sign = $(key+'-sign').value==='-' ? -1 : 1;
  return {
    m_amu: +$(key+'-mass').value,
    q_e: sign * Math.abs(+$(key+'-qmag').value),
    v: +$('inp-speed').value,
    theta_deg: +$('theta-r').value,
    B: B_T,
  };
}

// ── main update ───────────────────────────────────────────────────────────────
async function runUpdate() {
  clearError();
  updateBReadout();

  const B_T = +$('inp-BG').value * GAUSS_TO_TESLA;
  const datas = [];

  for (const p of parts) {
    try {
      const res  = await fetch('/api/compute', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(readParticle(p.conf.key, B_T)),
      });
      const data = await res.json();
      if (data.error) { showError(p.conf.label+': '+data.error); return; }
      datas.push(data);
    } catch(e) { showError('Server error: '+e.message); return; }
  }

  parts.forEach((p,i) => {
    p.data = datas[i];
    writeReadouts(p.conf.key, datas[i]);
    setChargeSprite(p, datas[i].sign);
  });

  const sharedZ = commonAxialSpan();
  const dispR   = computeDisplayRadii(datas);
  const isFirst = !firstRenderDone;

  resetCycle();

  parts.forEach((p,i) => {
    updateTrajectory(p, datas[i], sharedZ, turnsFor(datas[i]), dispR[i]);
  });

  buildFieldLines();
  firstRenderDone = true;
  if (isFirst) frameCamera();
}

// ── mode setup ────────────────────────────────────────────────────────────────
function setupMode() {
  const single = MODE==='one';
  const aLabel = single ? 'Particle' : 'Ion';
  $('A-head').textContent = aLabel;
  $('th-A').textContent   = aLabel;
  $('leg-A').textContent  = aLabel;

  if (single) {
    $('block-B').style.display = 'none';
    document.querySelectorAll('.col-B').forEach(el => el.style.display='none');
    $('leg-elec-row').style.display = 'none';
    $('A-sign').disabled = false;
  } else {
    $('A-sign').value = '+';
    $('A-sign').disabled = true;
    [...$('A-preset').options].forEach(o => { if (o.value==='electron') o.disabled=true; });
    if ($('A-preset').value==='electron') $('A-preset').value='xenon';

    $('B-preset').value = 'electron';
    applyPreset('B');
    ['B-preset','B-mass','B-qmag','B-sign'].forEach(id => { $(id).disabled=true; });
  }
}

// ── event wiring ──────────────────────────────────────────────────────────────
let _deb = null;
const debounced = () => { clearTimeout(_deb); _deb = setTimeout(runUpdate,150); };

ACTIVE.forEach(c => {
  const k = c.key;
  $(k+'-preset').addEventListener('change', () => { applyPreset(k); debounced(); });
  $(k+'-mass').addEventListener('input',  () => { $(k+'-preset').value='custom'; debounced(); });
  $(k+'-qmag').addEventListener('input',  () => { $(k+'-preset').value='custom'; debounced(); });
  $(k+'-sign').addEventListener('change', () => { $(k+'-preset').value='custom'; debounced(); });
});

$('theta-r').addEventListener('input', () => { $('theta-disp').textContent=$('theta-r').value; debounced(); });
$('inp-speed').addEventListener('input', debounced);
$('inp-BG').addEventListener('input', () => { updateBReadout(); debounced(); });

$('chk-labels').addEventListener('change', () => { showLabels = $('chk-labels').checked; });
$('chk-vel').addEventListener('change',    () => { showVel    = $('chk-vel').checked; });
$('chk-force').addEventListener('change',  () => { showForces = $('chk-force').checked; });

$('btn-run').addEventListener('click', runUpdate);

// ── boot ──────────────────────────────────────────────────────────────────────
initViz(document.getElementById('viewport'));
setupMode();
applyPreset('A');
updateBReadout();
runUpdate();
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
            r = compute(**{k: float(p[k]) for k in ("m_amu","q_e","v","theta_deg","B")})
            self._send(200, "application/json", json.dumps(r).encode())
        except (ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
            self._send(400, "application/json", json.dumps({"error":str(exc)}).encode())

HOST, PORT = "127.0.0.1", 8000

if __name__ == "__main__":
    srv = _Server((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"\n  Larmor Motion Applet → {url}\n  Ctrl-C to quit.\n")
    webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        srv.shutdown()