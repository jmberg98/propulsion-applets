#!/usr/bin/env python3
"""
gridded_ion.py — Gridded Ion Thruster 3D Viewer (Python prototype)
Single-file, stdlib-only. Run:  python gridded_ion.py

Serves an interactive WebGL (three.js) viewer of the SolidWorks assembly
gridded_ion_3D.STEP. The STEP file was tessellated offline into a compact
per-component mesh blob (gridded_ion_model.json) that lives alongside this
script; the server hands out both the page and that blob.

Features
  - Orbit / zoom / pan around the full thruster assembly.
  - "Cross-Section" button: switches to an orthographic axial section view
    (cut on the z = 0 plane) that matches gridded_ion_crosssection.png. The
    parallel projection shows the ion-optics grids edge-on and the discharge
    chamber as a flat sectioned wall; stencil-buffer caps fill the cut faces.
  - A movable cut plane (slider) to slice at different depths.
  - Component legend with show/hide toggles (housing, discharge chamber,
    grids, cathodes, magnet rings, injector, neutralizer).

This is Stage-1 prototype work per applet_style.txt: a local HTTP server with
the full HTML/JS embedded as a raw string. The model blob is served as a
sibling static file rather than embedded to keep this source readable.
"""

import os
import json
import webbrowser
from socketserver import ThreadingMixIn
from http.server import HTTPServer, BaseHTTPRequestHandler


class _Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True


HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_FILE = "gridded_ion_model.json"


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Gridded Ion Thruster — 3D Viewer</title>

<link rel="preconnect" href="https://fonts.googleapis.com" />
<link
  href="https://fonts.googleapis.com/css2?family=Barlow:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&display=swap"
  rel="stylesheet"
/>

<style>
  :root {
    /* Physics-quantity colors */
    --c-thrust : #FF4400;
    --c-ve     : #3DBFFF;
    --c-power  : #C060FF;
    --c-press  : #00DDB5;

    /* UI chrome */
    --c-accent      : #a0a0a0;
    --c-accent-bg   : rgba(160,160,160,0.07);
    --c-accent-glow : rgba(160,160,160,0.13);

    /* Text */
    --text-main      : #d6d6d6;
    --text-secondary : #aaaaaa;
    --text-muted     : #7a7a7a;
    --text-heading   : #f0f0f0;

    /* Borders */
    --border : #282828;

    /* Backgrounds */
    --bg-page    : #090909;
    --bg-panel-1 : #0e0e0e;
    --bg-panel-2 : #121212;
    --bg-panel-3 : #171717;
    --bg-panel-4 : #1d1d1d;
    --bg-input   : #191919;
    --bg-canvas  : #090909;
  }

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  html, body { height: 100%; }

  body {
    font-family: 'Barlow', 'Segoe UI', sans-serif;
    background : var(--bg-page);
    color      : var(--text-main);
    overflow   : hidden;
  }

  ::-webkit-scrollbar             { width:6px; height:6px; }
  ::-webkit-scrollbar-track       { background: var(--bg-panel-1); }
  ::-webkit-scrollbar-thumb       { background:#383838; border-radius:3px; }
  ::-webkit-scrollbar-thumb:hover { background:#d0d0d0; }

  /* ── App shell ───────────────────────────────────────────── */
  #app {
    display : flex;
    flex-direction: row;
    height  : 100vh;
    width   : 100vw;
  }

  #viewport {
    position : relative;
    flex     : 1 1 auto;
    min-width: 0;
    background: var(--bg-canvas);
  }
  #viewport canvas { display:block; }

  /* Title chip over the canvas */
  #title-chip {
    position : absolute;
    top      : 18px;
    left     : 20px;
    display  : flex;
    align-items: baseline;
    gap      : 12px;
    pointer-events: none;
    z-index  : 5;
  }
  #title-chip h1 {
    font-size  : 21px;
    font-weight: 700;
    color      : var(--text-heading);
    text-shadow: 0 1px 6px rgba(0,0,0,0.8);
  }
  .badge {
    display        : inline-block;
    font-size      : 12px;
    font-weight    : 700;
    letter-spacing : 1px;
    text-transform : uppercase;
    padding        : 2px 8px;
    border         : 1px solid var(--c-accent);
    border-radius  : 3px;
    color          : var(--c-accent);
    background     : var(--c-accent-bg);
    white-space    : nowrap;
  }

  /* Hint text bottom-left */
  #hint {
    position : absolute;
    bottom   : 14px;
    left     : 20px;
    font-size: 12px;
    color    : var(--text-muted);
    pointer-events: none;
    z-index  : 5;
    text-shadow: 0 1px 5px rgba(0,0,0,0.9);
  }

  /* Loading overlay */
  #loading {
    position : absolute; inset: 0;
    display  : flex; align-items:center; justify-content:center;
    flex-direction: column; gap: 14px;
    background: var(--bg-canvas);
    z-index  : 20;
    transition: opacity 0.4s ease, visibility 0.4s ease;
  }
  #loading.hidden { opacity:0; visibility:hidden; }
  .spinner {
    width:34px; height:34px; border-radius:50%;
    border:3px solid #222; border-top-color: var(--c-ve);
    animation: spin 0.9s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  #loading .lt { font-size:14px; color: var(--text-muted); letter-spacing:0.4px; }

  /* ── Panel ───────────────────────────────────────────────── */
  #panel {
    width     : 400px;
    min-width : 400px;
    height    : 100vh;
    overflow-y: auto;
    background: var(--bg-panel-1);
    border-left: 1px solid var(--border);
    padding   : 20px 20px 40px;
    display   : flex;
    flex-direction: column;
    gap       : 20px;
  }

  .sect-hdr {
    font-size      : 13px;
    font-weight    : 700;
    color          : var(--c-accent);
    letter-spacing : 1.2px;
    text-transform : uppercase;
    padding-bottom : 5px;
    border-bottom  : 1px solid var(--border);
    margin-bottom  : 12px;
  }

  .block { display:flex; flex-direction:column; }

  .p-note {
    font-size: 13px;
    line-height: 1.55;
    color: var(--text-secondary);
    margin-bottom: 12px;
  }

  /* Segmented view control */
  .seg {
    display: flex;
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
    background: var(--bg-panel-2);
  }
  .seg button {
    flex: 1 1 0;
    font-family: 'Barlow', sans-serif;
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 0.4px;
    padding: 11px 6px;
    background: transparent;
    color: var(--text-secondary);
    border: none;
    cursor: pointer;
    transition: background 0.15s ease, color 0.15s ease;
  }
  .seg button + button { border-left: 1px solid var(--border); }
  .seg button:hover { background: var(--bg-panel-3); color: var(--text-heading); }
  .seg button.active {
    background: var(--c-accent-glow);
    color: var(--text-heading);
    box-shadow: inset 0 -2px 0 var(--c-ve);
  }

  .btn-row { display:flex; gap:8px; margin-top:10px; }
  .btn {
    flex:1 1 0;
    font-family:'Barlow',sans-serif;
    font-size:13px; font-weight:600;
    padding:9px 8px;
    background: var(--bg-panel-2);
    color: var(--text-secondary);
    border:1px solid var(--border);
    border-radius:5px;
    cursor:pointer;
    transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  }
  .btn:hover { background: var(--bg-panel-3); color: var(--text-heading); border-color: var(--c-accent); }

  /* Slider group */
  .sl-group { display:flex; flex-direction:column; gap:6px; }
  .sl-group.disabled { opacity:0.4; pointer-events:none; }
  .sl-label {
    font-size:13px; color: var(--text-muted);
    text-transform:uppercase; letter-spacing:0.7px;
    display:flex; justify-content:space-between; align-items:baseline;
  }
  .sl-label .val { font-family:'Courier New',monospace; font-size:13px; color: var(--hi-blue, #3DBFFF); }
  input[type=range] {
    width:100%; accent-color: var(--c-ve);
    background: transparent; cursor:pointer;
  }

  /* Checkbox rows */
  .chk {
    display:flex; align-items:center; gap:9px;
    font-size:14px; color: var(--text-secondary);
    padding:5px 0; cursor:pointer; user-select:none;
  }
  .chk input { accent-color: var(--c-ve); width:15px; height:15px; cursor:pointer; }
  .chk:hover { color: var(--text-heading); }

  /* Legend */
  #legend { display:flex; flex-direction:column; gap:2px; }
  .leg-row {
    display:grid;
    grid-template-columns: 15px 14px 1fr;
    align-items:center;
    gap:9px;
    padding:5px 0;
    font-size:13.5px;
    color: var(--text-secondary);
    cursor:pointer; user-select:none;
  }
  .leg-row:hover { color: var(--text-heading); }
  .leg-row input { accent-color: var(--c-ve); width:15px; height:15px; cursor:pointer; }
  .leg-row.off { color: var(--text-muted); opacity:0.55; }
  .sw { width:14px; height:14px; border-radius:3px; border:1px solid rgba(255,255,255,0.15); }

  .footer-note {
    font-size:12px; color: var(--text-muted);
    line-height:1.5; margin-top:4px;
  }

  /* ── Cross-section annotation overlay (labels + magnetic field lines) ── */
  #annot {
    position: absolute; inset: 0;
    z-index: 4;
    pointer-events: none;
    display: none;                 /* shown only in section mode */
  }
  #annot svg {
    position: absolute; inset: 0;
    width: 100%; height: 100%;
    overflow: visible;
  }
  .mlabel {
    position: absolute;
    transform: translate(-50%, -50%);
    font: 600 12.5px 'Barlow', sans-serif;
    color: var(--text-heading);
    background: rgba(12,12,12,0.86);
    border: 1px solid #3a3a3a;
    border-radius: 5px;
    padding: 4px 9px;
    white-space: nowrap;
    box-shadow: 0 1px 7px rgba(0,0,0,0.65);
  }
  .leader     { stroke: #8b919b; stroke-width: 1.2; }
  .anchordot  { fill: #d3dae4; stroke: #0e0e0e; stroke-width: 1; }
  .fieldline  {
    fill: none;
    stroke: rgba(216,226,240,0.85);
    stroke-width: 1.6;
    stroke-dasharray: 6 5;
    stroke-linecap: round;
  }
</style>
</head>
<body>
<div id="app">
  <div id="viewport">
    <div id="title-chip">
      <h1>Gridded Ion Thruster</h1>
      <span class="badge">Electric Propulsion</span>
    </div>
    <div id="annot"></div>
    <div id="hint">Drag to orbit · scroll to zoom · right-drag to pan</div>
    <div id="loading">
      <div class="spinner"></div>
      <div class="lt">Loading 3D model…</div>
    </div>
  </div>

  <aside id="panel">
    <div class="block">
      <div class="sect-hdr">View</div>
      <p class="p-note">
        Explore the thruster in 3D, then switch to the labelled axial
        <b>cross-section</b> — a simplified schematic of the discharge
        chamber, magnet rings, magnetic field lines, and ion-optics grids.
      </p>
      <div class="seg" id="view-seg">
        <button data-view="solid" class="active">3D View</button>
        <button data-view="section">Cross-Section</button>
      </div>
      <div class="btn-row">
        <button class="btn" id="btn-reset">Reset Camera</button>
      </div>
    </div>

    <div class="block">
      <div class="sect-hdr">Section Plane</div>
      <div class="sl-group disabled" id="cut-group">
        <div class="sl-label">
          <span>Cut depth (z)</span><span class="val" id="cut-val">0 mm</span>
        </div>
        <input type="range" id="cut-slider" min="-120" max="120" value="0" step="1" />
      </div>
      <label class="chk" id="caps-chk-wrap" style="margin-top:8px;">
        <input type="checkbox" id="chk-caps" checked />
        Fill sectioned faces (caps)
      </label>
    </div>

    <div class="block">
      <div class="sect-hdr">Components</div>
      <div id="legend"></div>
    </div>

    <div class="block">
      <div class="sect-hdr">Display</div>
      <label class="chk"><input type="checkbox" id="chk-rotate" /> Auto-rotate</label>
      <label class="chk"><input type="checkbox" id="chk-wire" /> Wireframe</label>
      <p class="footer-note">
        Model: gridded_ion_3D.STEP (SolidWorks 2025) · units mm.<br/>
        Created by Jordan Bergmann — MIT Propulsion — 2026
      </p>
    </div>
  </aside>
</div>

<script type="importmap">
{ "imports": {
  "three":"https://unpkg.com/three@0.160.0/build/three.module.js",
  "three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"
}}
</script>

<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

/* ── Constants ─────────────────────────────────────────────── */
const FOV_SOLID      = 45;
const ANIM_SEC       = 0.9;
const SECTION_MARGIN = 1.2;    // padding around the XY silhouette in the ortho section

/* Material tuning per component role */
const ROLE_MAT = {
  structure  : { metalness:0.55, roughness:0.52 },
  anode      : { metalness:0.45, roughness:0.55 },
  cathode    : { metalness:0.85, roughness:0.32 },
  feed       : { metalness:0.85, roughness:0.34 },
  neutralizer: { metalness:0.85, roughness:0.32 },
  magnet     : { metalness:0.35, roughness:0.68 },
  'grid-pos' : { metalness:0.70, roughness:0.42 },
  'grid-neg' : { metalness:0.55, roughness:0.50 },
  other      : { metalness:0.5,  roughness:0.5  },
};

/* Sleek-gray exterior recolour (by component name). Cathodes and the
   neutralizer stay gold; magnet rings stay dark. */
const COLOR_OVERRIDE = {
  Outer_Shell_Housing     : '#c4c8ce',
  Anode_Discharge_Chamber : '#aab0ba',
  Propellant_Injector     : '#cdd1d8',   // reference draws the injector light gray
  Screen_Grid_Positive    : '#bcc1c8',
  Accel_Grid_Negative     : '#878d96',
};

/* Diagram-mode shading: matte, near-shadowless materials for the 2-D section. */
const DIAGRAM_MAT = { metalness: 0.0, roughness: 1.0, envMapIntensity: 0.22 };

/* Callout labels for the 2-D section.  `anchor` is a point in centered model
   space (X = thrust axis → screen right, Y → up, cut plane Z = 0); `chip` is
   the label position as a fraction of the viewport, laid out around the figure
   like the reference schematic. */
const CALLOUTS = [
  { text:'Propellant injector',         anchor:[-138,  22], chip:[0.055, 0.28] },
  { text:'Anode',                       anchor:[ -68,  54], chip:[0.235, 0.18] },
  { text:'Magnet ring',                 anchor:[  -2, 100], chip:[0.360, 0.085] },
  { text:'Hollow cathode (neutralizer)',anchor:[ 150, 120], chip:[0.640, 0.055] },
  { text:'Hollow cathode',              anchor:[-150,  -9], chip:[0.055, 0.72] },
  { text:'Magnetic field lines',        anchor:[ -30, -50], chip:[0.180, 0.90] },
  { text:'Positive / screen grid',      anchor:[ 111, -72], chip:[0.520, 0.93] },
  { text:'Negative / accelerator grid', anchor:[ 118, -96], chip:[0.800, 0.93] },
];

/* Magnetic field lines — control points in centered model space (cut plane
   Z = 0). Smoothed to dashed curves at build time. A cone "lens" around the
   rear cathode plus nested arcs bulging toward the rear, ring-cusp style. */
const FIELD_LINES = [
  [[-86,   4],[-72,  34],[-52,  60],[-30,  74],[-22,  80]],
  [[-86, -18],[-72, -42],[-52, -64],[-30, -78],[-22, -84]],
  [[ 26,  90],[  8,  46],[  2,   0],[  8, -46],[ 26, -90]],
  [[ 64,  90],[ 48,  46],[ 42,   0],[ 48, -46],[ 64, -90]],
  [[ 98,  90],[ 84,  46],[ 80,   0],[ 84, -46],[ 98, -90]],
];

/* ── Globals ───────────────────────────────────────────────── */
let scene, camera, renderer, controls;
let orthoCam;                  // orthographic camera for the axial section (parallel projection)
let clipPlane;                 // section plane (world z = cutOffset, keeps z<offset)
let cutOffset = 0;
let sectionMode = false;
const comps = [];              // { name,label,color,role, mesh, stencil, cap, visible }
let modelReady = false;
let capsEnabled = true;

/* camera framing distances / ortho silhouette half-extents (computed after model loads) */
let distSolid = 700, distSection = 1000;
let orthoHalfX = 200, orthoHalfY = 160;
const dirSolid = new THREE.Vector3(1.0, 0.52, 1.35).normalize();

/* camera tweens */
let tween  = null;             // perspective fly (3D view)
let oTween = null;             // ortho zoom-in (section entry)

/* section annotation overlay */
let annotSvg = null, fieldPolys = [], calloutEls = [], fieldLinesS = [];
let annotVisible = false;
const _proj = new THREE.Vector3();

const $ = id => document.getElementById(id);

/* ── Base64 typed-array helpers ────────────────────────────── */
function b64ToBytes(b64){
  const bin = atob(b64);
  const n = bin.length;
  const bytes = new Uint8Array(n);
  for (let i=0;i<n;i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}
const b64ToF32 = b64 => new Float32Array(b64ToBytes(b64).buffer);
const b64ToU32 = b64 => new Uint32Array(b64ToBytes(b64).buffer);

/* ── Stencil cap group (three.js clipping-stencil technique) ── */
function createPlaneStencilGroup(geometry, plane, renderOrder){
  const group = new THREE.Group();
  const base = new THREE.MeshBasicMaterial();
  base.depthWrite   = false;
  base.depthTest    = false;
  base.colorWrite   = false;
  base.stencilWrite = true;
  base.stencilFunc  = THREE.AlwaysStencilFunc;

  // back faces increment stencil
  const mBack = base.clone();
  mBack.side = THREE.BackSide;
  mBack.clippingPlanes = [plane];
  mBack.stencilFail = THREE.IncrementWrapStencilOp;
  mBack.stencilZFail = THREE.IncrementWrapStencilOp;
  mBack.stencilZPass = THREE.IncrementWrapStencilOp;
  const b = new THREE.Mesh(geometry, mBack);
  b.renderOrder = renderOrder;
  group.add(b);

  // front faces decrement stencil
  const mFront = base.clone();
  mFront.side = THREE.FrontSide;
  mFront.clippingPlanes = [plane];
  mFront.stencilFail = THREE.DecrementWrapStencilOp;
  mFront.stencilZFail = THREE.DecrementWrapStencilOp;
  mFront.stencilZPass = THREE.DecrementWrapStencilOp;
  const f = new THREE.Mesh(geometry, mFront);
  f.renderOrder = renderOrder;
  group.add(f);

  return group;
}

/* ── Build the scene from the model blob ───────────────────── */
function buildModel(data){
  const [cx, cy, cz] = data.center;

  // section plane: keep z < cutOffset ; normal (0,0,-1), constant = cutOffset
  clipPlane = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0);

  const capGeom = new THREE.PlaneGeometry(640, 520);   // covers the XY silhouette

  data.components.forEach((c, i) => {
    const pos = b64ToF32(c.pos);
    const nrm = b64ToF32(c.nrm);
    const idx = b64ToU32(c.idx);

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('normal',   new THREE.BufferAttribute(nrm, 3));
    geo.setIndex(new THREE.BufferAttribute(idx, 1));
    geo.translate(-cx, -cy, -cz);   // center the assembly at the origin

    const tune = ROLE_MAT[c.role] || ROLE_MAT.other;
    const hex  = COLOR_OVERRIDE[c.name] || c.color;
    const col  = new THREE.Color(hex);

    // Main visible mesh — DoubleSide so interior walls show in section
    const mat = new THREE.MeshStandardMaterial({
      color: col,
      metalness: tune.metalness,
      roughness: tune.roughness,
      side: THREE.DoubleSide,
      clippingPlanes: [],           // filled in when section mode turns on
      clipShadows: true,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.renderOrder = 0;
    scene.add(mesh);

    // Stencil group (writes stencil where the solid is cut)
    const stencil = createPlaneStencilGroup(geo, clipPlane, i + 1);
    stencil.visible = false;
    scene.add(stencil);

    // Cap plane — solid coloured face filling the cut, gated by stencil
    const capMat = new THREE.MeshStandardMaterial({
      color: col,
      metalness: tune.metalness,
      roughness: Math.min(0.7, tune.roughness + 0.08),
      side: THREE.DoubleSide,
      stencilWrite: true,
      stencilRef: 0,
      stencilFunc: THREE.NotEqualStencilFunc,
      stencilFail: THREE.ReplaceStencilOp,
      stencilZFail: THREE.ReplaceStencilOp,
      stencilZPass: THREE.ReplaceStencilOp,
    });
    const cap = new THREE.Mesh(capGeom, capMat);
    cap.renderOrder = i + 1.1;
    cap.visible = false;
    cap.onAfterRender = (r) => r.clearStencil();
    scene.add(cap);

    comps.push({ name:c.name, label:c.label, color:hex, role:c.role, tune,
                 mesh, stencil, cap, visible:true });
  });

  // Framing: perspective distance for the 3D view; silhouette half-extents for the section
  const sz = data.size;
  const rFull = 0.5 * Math.hypot(sz[0], sz[1], sz[2]);   // full 3D sphere
  distSolid   = fitDistance(rFull, FOV_SOLID) * 1.12;
  distSection = rFull * 3.0;                             // stand-off for the ortho section camera
  orthoHalfX  = 0.5 * sz[0] * SECTION_MARGIN;            // X is the thruster axis (screen horizontal)
  orthoHalfY  = 0.5 * sz[1] * SECTION_MARGIN;            // Y is screen vertical

  positionCapPlanes();
}

function fitDistance(radius, fovDeg){
  const aspect = viewAspect();
  const vFov = fovDeg * Math.PI / 180;
  const dV = radius / Math.sin(vFov / 2);
  const hFov = 2 * Math.atan(Math.tan(vFov / 2) * aspect);
  const dH = radius / Math.sin(hFov / 2);
  return Math.max(dV, dH);
}
function viewAspect(){
  const el = $('viewport');
  return el.clientWidth / el.clientHeight;
}

/* Keep cap planes on the cut plane (world z = cutOffset) */
function positionCapPlanes(){
  clipPlane.constant = cutOffset;                 // keeps z < cutOffset
  for (const c of comps) c.cap.position.set(0, 0, cutOffset);
}

/* ── Section mode on/off ───────────────────────────────────── */
function setSectionMode(on){
  sectionMode = on;
  for (const c of comps){
    c.mesh.material.clippingPlanes = on ? [clipPlane] : [];
    c.mesh.material.needsUpdate = true;
    c.stencil.visible = on && c.visible && capsEnabled;
    c.cap.visible     = on && c.visible && capsEnabled;
  }
  $('cut-group').classList.toggle('disabled', !on);
  $('caps-chk-wrap').style.opacity = on ? '1' : '0.4';
  $('caps-chk-wrap').style.pointerEvents = on ? 'auto' : 'none';

  // segmented control state
  document.querySelectorAll('#view-seg button').forEach(b => {
    b.classList.toggle('active', (b.dataset.view === 'section') === on);
  });

  setDiagramShading(on);
  showAnnotations(on);

  if (on){
    $('chk-rotate').checked = false;
    controls.autoRotate = false;
    tween = null;                       // cancel any in-flight perspective fly
    // 2-D schematic: pan + zoom only, no orbit (labels are laid out head-on)
    controls.enableRotate = false;
    controls.mouseButtons.LEFT = THREE.MOUSE.PAN;
    controls.touches.ONE = THREE.TOUCH.PAN;
    $('hint').textContent = 'Drag to pan · scroll to zoom';
    enterSection();
  } else {
    oTween = null;
    controls.object = camera;           // hand orbit back to the perspective camera
    controls.enableRotate = true;
    controls.mouseButtons.LEFT = THREE.MOUSE.ROTATE;
    controls.touches.ONE = THREE.TOUCH.ROTATE;
    $('hint').textContent = 'Drag to orbit · scroll to zoom · right-drag to pan';
    flyTo(solidCamPos(), new THREE.Vector3(0,0,0), FOV_SOLID);
  }
}

/* Flatten materials for the 2-D section: matte, near-shadowless, no metallic
   speculars — a clean schematic look. Restored to their PBR tuning in 3-D. */
function setDiagramShading(on){
  for (const c of comps){
    const m = c.mesh.material, cm = c.cap.material;
    if (on){
      m.metalness = DIAGRAM_MAT.metalness;  m.roughness = DIAGRAM_MAT.roughness;
      m.envMapIntensity = DIAGRAM_MAT.envMapIntensity;
      cm.metalness = DIAGRAM_MAT.metalness; cm.roughness = DIAGRAM_MAT.roughness;
      cm.envMapIntensity = DIAGRAM_MAT.envMapIntensity;
    } else {
      m.metalness = c.tune.metalness;  m.roughness = c.tune.roughness;  m.envMapIntensity = 1.0;
      cm.metalness = c.tune.metalness; cm.roughness = Math.min(0.7, c.tune.roughness + 0.08);
      cm.envMapIntensity = 1.0;
    }
    m.needsUpdate = true; cm.needsUpdate = true;
  }
}

/* Snap the ortho camera head-on (looking down -Z, the section normal) and gently
   zoom in. The parallel projection is what makes the flat ion-optics grids read
   as an edge-on dotted line and the discharge chamber as a flat sectioned wall —
   matching gridded_ion_crosssection.png. A perspective camera, even dead-on,
   splays the grid apertures open and rounds out the interior. */
function enterSection(){
  frameOrtho();
  orthoCam.position.set(0, 0, distSection);
  orthoCam.up.set(0, 1, 0);
  orthoCam.lookAt(0, 0, 0);
  orthoCam.zoom = 0.82;
  orthoCam.updateProjectionMatrix();
  controls.object = orthoCam;
  controls.target.set(0, 0, 0);
  controls.enabled = false;
  controls.update();
  oTween = { t: 0, dur: ANIM_SEC };
}

/* Size the ortho frustum so the whole XY silhouette (plus margin) fits the
   viewport at its current aspect, letterboxing the slack dimension. */
function frameOrtho(){
  const asp = viewAspect();
  let halfX = orthoHalfX, halfY = orthoHalfY;
  if (halfX / halfY < asp) halfX = halfY * asp;
  else                     halfY = halfX / asp;
  orthoCam.left = -halfX; orthoCam.right = halfX;
  orthoCam.top  =  halfY; orthoCam.bottom = -halfY;
  orthoCam.updateProjectionMatrix();
}

/* ── Section annotations (labels + magnetic field lines) ───────── */
const SVGNS = 'http://www.w3.org/2000/svg';

/* Catmull-Rom smoothing of a control polyline into a dense point list. */
function smoothCurve(pts, perSeg){
  const P = pts, out = [];
  for (let i = 0; i < P.length - 1; i++){
    const p0 = P[i-1] || P[i], p1 = P[i], p2 = P[i+1], p3 = P[i+2] || P[i+1];
    for (let s = 0; s < perSeg; s++){
      const t = s / perSeg, t2 = t*t, t3 = t2*t;
      const x = 0.5*(2*p1[0] + (-p0[0]+p2[0])*t + (2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*t2 + (-p0[0]+3*p1[0]-3*p2[0]+p3[0])*t3);
      const y = 0.5*(2*p1[1] + (-p0[1]+p2[1])*t + (2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*t2 + (-p0[1]+3*p1[1]-3*p2[1]+p3[1])*t3);
      out.push([x, y]);
    }
  }
  out.push(P[P.length-1]);
  return out;
}

function buildAnnotations(){
  const host = $('annot');
  host.innerHTML = '';
  fieldLinesS = FIELD_LINES.map(fl => smoothCurve(fl, 16));

  const svg = document.createElementNS(SVGNS, 'svg');
  host.appendChild(svg);
  annotSvg = svg;

  fieldPolys = fieldLinesS.map(() => {
    const pl = document.createElementNS(SVGNS, 'polyline');
    pl.setAttribute('class', 'fieldline');
    svg.appendChild(pl);
    return pl;
  });

  calloutEls = CALLOUTS.map(c => {
    const line = document.createElementNS(SVGNS, 'line');
    line.setAttribute('class', 'leader');
    svg.appendChild(line);
    const dot = document.createElementNS(SVGNS, 'circle');
    dot.setAttribute('class', 'anchordot');
    dot.setAttribute('r', '3');
    svg.appendChild(dot);
    const chip = document.createElement('div');
    chip.className = 'mlabel';
    chip.textContent = c.text;
    host.appendChild(chip);
    return { c, line, dot, chip };
  });
}

function showAnnotations(on){
  annotVisible = on;
  const host = $('annot');
  if (host) host.style.display = on ? 'block' : 'none';
}

/* Project world (cut-plane) points to screen pixels and lay out the overlay.
   Runs each frame in section mode so labels/field lines track pan & zoom. */
function updateAnnotations(){
  if (!annotVisible || !annotSvg) return;
  const vp = $('viewport'), w = vp.clientWidth, h = vp.clientHeight;
  annotSvg.setAttribute('viewBox', '0 0 ' + w + ' ' + h);

  const toScreen = (x, y) => {
    _proj.set(x, y, 0).project(orthoCam);
    return [ (_proj.x * 0.5 + 0.5) * w, (-_proj.y * 0.5 + 0.5) * h ];
  };

  for (let i = 0; i < fieldPolys.length; i++){
    let s = '';
    const src = fieldLinesS[i];
    for (let k = 0; k < src.length; k++){
      const p = toScreen(src[k][0], src[k][1]);
      s += p[0].toFixed(1) + ',' + p[1].toFixed(1) + ' ';
    }
    fieldPolys[i].setAttribute('points', s);
  }

  for (const e of calloutEls){
    const a  = toScreen(e.c.anchor[0], e.c.anchor[1]);
    const cx = e.c.chip[0] * w, cy = e.c.chip[1] * h;
    e.chip.style.left = cx + 'px';
    e.chip.style.top  = cy + 'px';
    e.line.setAttribute('x1', cx); e.line.setAttribute('y1', cy);
    e.line.setAttribute('x2', a[0]); e.line.setAttribute('y2', a[1]);
    e.dot.setAttribute('cx', a[0]);  e.dot.setAttribute('cy', a[1]);
  }
}

function solidCamPos(){ return dirSolid.clone().multiplyScalar(distSolid); }

/* ── Camera fly-to tween ───────────────────────────────────── */
function flyTo(toPos, toTarget, toFov){
  tween = {
    t: 0, dur: ANIM_SEC,
    fromPos: camera.position.clone(),
    toPos: toPos.clone(),
    fromTarget: controls.target.clone(),
    toTarget: toTarget.clone(),
    fromFov: camera.fov,
    toFov: toFov,
  };
  controls.enabled = false;
}
function smoothstep(x){ return x*x*(3 - 2*x); }

function updateTween(dt){
  if (oTween){
    oTween.t += dt / oTween.dur;
    const s = smoothstep(Math.min(oTween.t, 1));
    orthoCam.zoom = 0.82 + 0.18 * s;
    orthoCam.updateProjectionMatrix();
    if (oTween.t >= 1){ oTween = null; controls.enabled = true; }
  }
  if (!tween) return;
  tween.t += dt / tween.dur;
  const s = smoothstep(Math.min(tween.t, 1));
  camera.position.lerpVectors(tween.fromPos, tween.toPos, s);
  controls.target.lerpVectors(tween.fromTarget, tween.toTarget, s);
  camera.fov = tween.fromFov + (tween.toFov - tween.fromFov) * s;
  camera.updateProjectionMatrix();
  if (tween.t >= 1){
    tween = null;
    controls.enabled = true;
  }
}

/* ── Init ──────────────────────────────────────────────────── */
function init(){
  const vp = $('viewport');
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x090909);

  camera = new THREE.PerspectiveCamera(FOV_SOLID, viewAspect(), 0.5, 20000);
  camera.position.copy(dirSolid.clone().multiplyScalar(distSolid));

  orthoCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.5, 20000);
  orthoCam.position.set(0, 0, distSection);
  orthoCam.lookAt(0, 0, 0);

  renderer = new THREE.WebGLRenderer({ antialias:true, stencil:true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(vp.clientWidth, vp.clientHeight);
  renderer.localClippingEnabled = true;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  vp.appendChild(renderer.domElement);

  // Environment for believable metal reflections
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

  // Lights
  scene.add(new THREE.AmbientLight(0xffffff, 0.35));
  const key = new THREE.DirectionalLight(0xffffff, 1.6);
  key.position.set(1.2, 2.0, 2.4);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xbcd4ff, 0.55);
  fill.position.set(-2.0, 0.6, -1.4);
  scene.add(fill);
  const rim = new THREE.DirectionalLight(0xffffff, 0.5);
  rim.position.set(0.4, -1.5, -2.0);
  scene.add(rim);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.autoRotateSpeed = 1.2;

  window.addEventListener('resize', onResize);
  wireUI();
  animate();
}

function onResize(){
  const vp = $('viewport');
  camera.aspect = vp.clientWidth / vp.clientHeight;
  camera.updateProjectionMatrix();
  if (orthoCam) frameOrtho();
  renderer.setSize(vp.clientWidth, vp.clientHeight);
}

/* ── UI wiring ─────────────────────────────────────────────── */
function buildLegend(){
  const leg = $('legend');
  leg.innerHTML = '';
  comps.forEach((c, i) => {
    const row = document.createElement('label');
    row.className = 'leg-row';
    row.innerHTML =
      '<input type="checkbox" checked>' +
      '<span class="sw" style="background:' + c.color + '"></span>' +
      '<span>' + c.label + '</span>';
    const chk = row.querySelector('input');
    chk.addEventListener('change', () => {
      c.visible = chk.checked;
      c.mesh.visible = c.visible;
      c.stencil.visible = sectionMode && c.visible && capsEnabled;
      c.cap.visible     = sectionMode && c.visible && capsEnabled;
      row.classList.toggle('off', !c.visible);
    });
    leg.appendChild(row);
  });
}

function wireUI(){
  document.querySelectorAll('#view-seg button').forEach(b => {
    b.addEventListener('click', () => setSectionMode(b.dataset.view === 'section'));
  });

  $('btn-reset').addEventListener('click', () => {
    if (sectionMode) enterSection();
    else             flyTo(solidCamPos(), new THREE.Vector3(0,0,0), FOV_SOLID);
  });

  $('cut-slider').addEventListener('input', e => {
    cutOffset = +e.target.value;
    $('cut-val').textContent = cutOffset + ' mm';
    positionCapPlanes();
  });

  $('chk-caps').addEventListener('change', e => {
    capsEnabled = e.target.checked;
    for (const c of comps){
      c.stencil.visible = sectionMode && c.visible && capsEnabled;
      c.cap.visible     = sectionMode && c.visible && capsEnabled;
    }
  });

  $('chk-rotate').addEventListener('change', e => {
    controls.autoRotate = e.target.checked && !sectionMode;
    if (e.target.checked && sectionMode){ setSectionMode(false); }
  });

  $('chk-wire').addEventListener('change', e => {
    for (const c of comps) c.mesh.material.wireframe = e.target.checked;
  });
}

/* ── Render loop ───────────────────────────────────────────── */
let _last = null;
function animate(ts){
  requestAnimationFrame(animate);
  const now = (ts || 0) / 1000;
  const dt = _last === null ? 0 : Math.min(now - _last, 0.05);
  _last = now;

  updateTween(dt);
  controls.update();
  renderer.render(scene, sectionMode ? orthoCam : camera);
  if (sectionMode) updateAnnotations();
}

/* ── Boot ──────────────────────────────────────────────────── */
init();
fetch('gridded_ion_model.json')
  .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
  .then(data => {
    buildModel(data);
    buildLegend();
    buildAnnotations();
    // reframe now that distances are known
    camera.position.copy(solidCamPos());
    controls.target.set(0, 0, 0);
    modelReady = true;
    $('loading').classList.add('hidden');
  })
  .catch(err => {
    $('loading').innerHTML =
      '<div class="lt" style="color:#ff8e8e; max-width:320px; text-align:center;">' +
      'Could not load model:<br>' + err.message + '</div>';
  });
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
        elif self.path in ("/gridded_ion_model.json", "/" + MODEL_FILE):
            path = os.path.join(HERE, MODEL_FILE)
            try:
                with open(path, "rb") as f:
                    body = f.read()
                self._send(200, "application/json", body)
            except OSError as exc:
                self._send(404, "text/plain", str(exc).encode())
        else:
            self._send(404, "text/plain", b"Not found")


HOST = "127.0.0.1"
# Windows can forbid a reserved port (WinError 10013); 0 lets the OS pick a free one.
PORTS = (8003, 8013, 8043, 8089, 8766, 9003, 0)


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
        print(f"\n  Gridded Ion Thruster viewer -> {url}\n  Ctrl-C to quit.\n")
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
