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
  - "Cross-Section" button: the camera swings square to the cut plane, then the
    view eases into an orthographic axial section (cut on z = 0). The parallel
    projection shows the ion-optics grids edge-on and the discharge chamber as a
    flat sectioned wall; stencil-buffer caps fill the cut faces, and a labelled
    overlay draws the ring-cusp magnetic field lines and part callouts.
  - A movable cut plane (slider) to slice at different depths.
  - A static component legend (every part shown by default).

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
    width     : 300px;
    min-width : 300px;
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

  /* Checkbox rows */
  .chk {
    display:flex; align-items:center; gap:9px;
    font-size:14px; color: var(--text-secondary);
    padding:5px 0; cursor:pointer; user-select:none;
  }
  .chk input { accent-color: var(--c-ve); width:15px; height:15px; cursor:pointer; }
  .chk:hover { color: var(--text-heading); }

  .footer-note {
    font-size:12px; color: var(--text-muted);
    line-height:1.5; margin-top:4px;
  }

  /* ── Cross-section annotation overlay (labels + magnetic field lines) ── */
  #annot {
    position: absolute; inset: 0;
    z-index: 4;
    pointer-events: none;
    opacity: 0;                    /* faded in only in section mode */
    transition: opacity 0.55s ease;
  }
  #annot.show { opacity: 1; }
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
    stroke: rgba(245,249,255,0.95);
    stroke-width: 1.9;
    stroke-dasharray: 7 5;
    stroke-linecap: round;
    /* dark halo so the light field lines read over the light-gray section */
    filter: drop-shadow(0 0 1.7px rgba(6,8,14,0.92));
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

/* ── Constants ─────────────────────────────────────────────── */
const FOV_SOLID       = 45;
const FOV_ORTHO_MATCH = 6;     // near-parallel FOV the head-on view flattens to before the swap to
                               // the true orthographic camera — small enough that the grid apertures
                               // read straight, so the flatten and the swap are both imperceptible
const ANIM_SEC       = 0.9;
const SECTION_MARGIN = 1.2;    // padding around the XY silhouette in the ortho section

/* Material tuning per component role. Low metalness + high roughness for a
   matte, un-shiny CAD look (no environment reflections) in the spirit of the
   other applets — the 2-D section flattens these further via DIAGRAM_MAT. */
const ROLE_MAT = {
  structure  : { metalness:0.0,  roughness:0.72 },
  anode      : { metalness:0.0,  roughness:0.78 },
  cathode    : { metalness:0.25, roughness:0.50 },
  feed       : { metalness:0.20, roughness:0.55 },
  neutralizer: { metalness:0.25, roughness:0.50 },
  magnet     : { metalness:0.05, roughness:0.85 },
  'grid-pos' : { metalness:0.20, roughness:0.55 },
  'grid-neg' : { metalness:0.20, roughness:0.60 },
  other      : { metalness:0.10, roughness:0.70 },
};

/* Matte recolour (by component name) to match the schematic. The inside of the
   ionization chamber is whitest; the outer structure — the shell between/around
   the magnet rings, the propellant injector, and the neutralizer's attaching
   piece (all part of the housing) — shares ONE lighter lavender-gray. The
   ion-optics grids are the darkest so they read clearly in section; the magnet
   rings sit between. The hollow cathodes / neutralizer are a yellower gold. */
const STRUCTURE_GRAY = '#d5d8e4';           // unified outer-structure tone
const COLOR_OVERRIDE = {
  Anode_Discharge_Chamber    : '#f4f6fb',   // inside of the ionization chamber — whitest
  Outer_Shell_Housing        : STRUCTURE_GRAY,
  Propellant_Injector        : STRUCTURE_GRAY,  // same as the shell / neutralizer attaching piece
  Screen_Grid_Positive       : '#4c515a',   // grids: dark, clearly visible against the white body
  Accel_Grid_Negative        : '#2f333a',
  Magnet_Ring_Cathode        : '#616670',
  Magnet_Ring_Mid            : '#616670',
  Magnet_Ring_Front          : '#616670',
  Hollow_Cathode             : '#d8b62e',   // yellower, less gold
  Neutralizer_Hollow_Cathode : '#d8b62e',
};

/* Diagram-mode shading: matte, near-shadowless materials for the 2-D section. */
const DIAGRAM_MAT = { metalness: 0.0, roughness: 1.0 };

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
  { text:'Magnetic field lines',        anchor:[ -30, -76], chip:[0.180, 0.90] },
  { text:'Positive / screen grid',      anchor:[ 111, -72], chip:[0.520, 0.93] },
  { text:'Negative / accelerator grid', anchor:[ 118, -96], chip:[0.800, 0.93] },
];

/* Magnetic field lines — control points in centered section space (cut plane
   Z = 0; X = thrust axis with the grids at +X, Y up, chamber axis at Y ≈ −8).
   Ring-cusp topology matching the reference schematic: the line rises from the
   rear cathode ring along the anode cone, then SCALLOPS — cusping out to the wall
   at each magnet ring (mid ring x ≈ −2, front ring x ≈ +98) and bowing back in
   toward the axis in the gaps between them. Wall is at |Y| ≈ 92 (top) / 108
   (bottom); the lower line mirrors the upper about the chamber axis (Y = −8). */
const FIELD_LINES = [
  // upper line: cone → cusp at mid ring → inward bow → cusp at front ring
  [[-90, 20],[-54, 34],[-14, 78],[-2, 88],[34, 46],[62, 44],[88, 78],[98, 88],[104, 74]],
  // lower line: mirror of the upper about the chamber axis (Y = −8)
  [[-90,-36],[-54,-50],[-14,-94],[-2,-104],[34,-62],[62,-60],[88,-94],[98,-104],[104,-90]],
];

/* ── Globals ───────────────────────────────────────────────── */
let scene, camera, renderer, controls;
let orthoCam;                  // orthographic camera for the axial section (parallel projection)
let clipPlane;                 // section plane (world z = cutOffset, keeps z<offset)
let cutOffset = 0;
let sectionMode = false;       // target state: the cross-section is selected
let orthoActive = false;       // the ortho section camera has taken over (post camera-swing)
const comps = [];              // { name,label,color,role, mesh, stencil, cap, visible }
let modelReady = false;

/* camera framing distances / ortho silhouette half-extents (computed after model loads) */
let distSolid = 700, distSection = 1000;
let orthoHalfX = 200, orthoHalfY = 160;
const dirSolid = new THREE.Vector3(1.0, 0.52, 1.35).normalize();

/* camera tweens */
let tween  = null;             // perspective fly (3D view)
let oTween = null;             // ortho zoom-in (section entry) — unused since the flatten pass
let fTween = null;             // in-place FOV → parallel flatten; grids straighten before the ortho swap
let frameHalf = 200;           // target ortho half-height the section frames to (set on entry)

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
    c.stencil.visible = on && c.visible;   // caps always fill the cut in section mode
    c.cap.visible     = on && c.visible;
  }
  // segmented control state
  document.querySelectorAll('#view-seg button').forEach(b => {
    b.classList.toggle('active', (b.dataset.view === 'section') === on);
  });

  setDiagramShading(on);

  if (on){
    // Swing the perspective camera square to the cut plane first; the ortho
    // section (and its labelled overlay) only take over once we're head-on.
    orthoActive = false;
    showAnnotations(false);
    tween = null; oTween = null; fTween = null;
    controls.enabled = false;
    controls.object = camera;
    $('hint').textContent = 'Rotating to cross-section…';
    beginSectionEntry();
  } else {
    const wasOrtho = orthoActive;       // false if still mid-swing into the section
    orthoActive = false;
    oTween = null; fTween = null;
    showAnnotations(false);
    controls.object = camera;           // hand orbit back to the perspective camera
    controls.enableRotate = true;
    controls.mouseButtons.LEFT = THREE.MOUSE.ROTATE;
    controls.touches.ONE = THREE.TOUCH.ROTATE;
    controls.target.set(0, 0, 0);
    $('hint').textContent = 'Drag to orbit · scroll to zoom · right-drag to pan';
    if (wasOrtho){
      // Mirror of the entry: take over from the ortho camera head-on at the same
      // near-parallel FOV (seamless), un-flatten the projection in place so the
      // grids re-splay smoothly, then orbit back out to the 3-D view.
      frameHalf = orthoCam.top;
      camera.up.set(0, 1, 0);
      camera.fov = FOV_ORTHO_MATCH;
      camera.position.set(0, 0, frameHalf / Math.tan(FOV_ORTHO_MATCH * Math.PI / 360));
      camera.lookAt(0, 0, 0);
      camera.updateProjectionMatrix();
      controls.enabled = false;
      fTween = { t:0, dur: ANIM_SEC * 0.6, fromFov: FOV_ORTHO_MATCH, toFov: FOV_SOLID,
                 onDone: () => flyTo(solidCamPos(), new THREE.Vector3(0,0,0), FOV_SOLID) };
    } else {
      flyTo(solidCamPos(), new THREE.Vector3(0,0,0), FOV_SOLID);
    }
  }
}

/* Flatten materials for the 2-D section: matte, near-shadowless — a clean
   schematic look. Restored to their (already matte) 3-D tuning otherwise. */
function setDiagramShading(on){
  for (const c of comps){
    const m = c.mesh.material, cm = c.cap.material;
    if (on){
      m.metalness = DIAGRAM_MAT.metalness;  m.roughness = DIAGRAM_MAT.roughness;
      cm.metalness = DIAGRAM_MAT.metalness; cm.roughness = DIAGRAM_MAT.roughness;
    } else {
      m.metalness = c.tune.metalness;  m.roughness = c.tune.roughness;
      cm.metalness = c.tune.metalness; cm.roughness = Math.min(0.85, c.tune.roughness + 0.08);
    }
    m.needsUpdate = true; cm.needsUpdate = true;
  }
}

/* Entry, phase 1 — swing the perspective camera round to a head-on view of the
   cut plane (looking down −Z), landing at the distance that frames the silhouette
   at FOV_SOLID (so there is no later zoom). Clipping + caps are already live, so
   the section forms and the near half falls away as it turns. beginFlatten() then
   takes over, still head-on. */
function beginSectionEntry(){
  frameOrtho();                                   // size the ortho frustum for the current aspect
  frameHalf = orthoCam.top;                        // half-height the section frames to
  fTween = null;
  const D1 = frameHalf / Math.tan(FOV_SOLID * Math.PI / 360);
  flyTo(new THREE.Vector3(0, 0, D1), new THREE.Vector3(0, 0, 0), FOV_SOLID, beginFlatten);
}

/* Entry, phase 2 — head-on already, so narrow the FOV toward parallel *in place*.
   The distance tracks the FOV (frameHalf / tan(fov/2)) so the silhouette stays
   framed the whole time: the projection flattens continuously — the grid apertures
   un-splay smoothly instead of snapping from curved to straight — and by the end
   the perspective is near-parallel, so settleOrtho()'s swap to the true ortho
   camera (zoom = 1) is imperceptible. */
function beginFlatten(){
  controls.enabled = false;
  fTween = { t:0, dur: ANIM_SEC * 0.7, fromFov: FOV_SOLID, toFov: FOV_ORTHO_MATCH,
             onDone: settleOrtho };
}

/* Swap to the orthographic projection — parallel rays are what make the flat
   ion-optics grids read edge-on and the chamber a flat sectioned wall. The
   preceding flatten left the perspective near-parallel and framing the silhouette,
   so ortho takes over at zoom = 1 with matching framing and projection — seamless. */
function settleOrtho(){
  fTween = null;
  frameOrtho();
  orthoCam.position.set(0, 0, distSection);
  orthoCam.up.set(0, 1, 0);
  orthoCam.lookAt(0, 0, 0);
  orthoCam.zoom = 1.0;
  orthoCam.updateProjectionMatrix();

  controls.object = orthoCam;
  controls.target.set(0, 0, 0);
  controls.enableRotate = false;               // head-on schematic: pan + zoom only
  controls.mouseButtons.LEFT = THREE.MOUSE.PAN;
  controls.touches.ONE = THREE.TOUCH.PAN;
  controls.enabled = true;
  controls.update();

  orthoActive = true;
  oTween = null;
  showAnnotations(true);
  $('hint').textContent = 'Drag to pan · scroll to zoom';
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
  if (host) host.classList.toggle('show', on);   // CSS opacity transition fades it in/out
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

  const PAD = 24;   // keep chips this far off the viewport edges (breathing room)
  for (const e of calloutEls){
    const a  = toScreen(e.c.anchor[0], e.c.anchor[1]);
    const cw = e.chip.offsetWidth, ch = e.chip.offsetHeight;
    const cx = Math.min(Math.max(e.c.chip[0] * w, PAD + cw / 2), w - PAD - cw / 2);
    const cy = Math.min(Math.max(e.c.chip[1] * h, PAD + ch / 2), h - PAD - ch / 2);
    e.chip.style.left = cx + 'px';
    e.chip.style.top  = cy + 'px';
    e.line.setAttribute('x1', cx); e.line.setAttribute('y1', cy);
    e.line.setAttribute('x2', a[0]); e.line.setAttribute('y2', a[1]);
    e.dot.setAttribute('cx', a[0]);  e.dot.setAttribute('cy', a[1]);
  }
}

function solidCamPos(){ return dirSolid.clone().multiplyScalar(distSolid); }

/* ── Camera fly-to tween ───────────────────────────────────── */
function flyTo(toPos, toTarget, toFov, onDone){
  tween = {
    t: 0, dur: ANIM_SEC,
    fromPos: camera.position.clone(),
    toPos: toPos.clone(),
    fromTarget: controls.target.clone(),
    toTarget: toTarget.clone(),
    fromFov: camera.fov,
    toFov: toFov,
    onDone: onDone || null,
  };
  controls.enabled = false;
}
function smoothstep(x){ return x*x*(3 - 2*x); }

function updateTween(dt){
  if (fTween){
    // Head-on flatten: narrow the FOV while distance tracks it (frameHalf / tan),
    // so the silhouette stays framed and only the perspective flattens.
    fTween.t += dt / fTween.dur;
    const s = smoothstep(Math.min(fTween.t, 1));
    const fov = fTween.fromFov + (fTween.toFov - fTween.fromFov) * s;
    camera.fov = fov;
    camera.position.set(0, 0, frameHalf / Math.tan(fov * Math.PI / 360));
    controls.target.set(0, 0, 0);
    camera.updateProjectionMatrix();
    if (fTween.t >= 1){
      const done = fTween.onDone;
      fTween = null;
      if (done) done();
    }
    return;
  }
  if (oTween){
    oTween.t += dt / oTween.dur;
    const s = smoothstep(Math.min(oTween.t, 1));
    orthoCam.zoom = oTween.from + (oTween.to - oTween.from) * s;
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
    const done = tween.onDone;
    tween = null;
    if (done) done();               // e.g. hand off to the ortho section
    else controls.enabled = true;
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
  vp.appendChild(renderer.domElement);

  // Soft, even, matte lighting — a clean CAD look with no environment
  // reflections and no filmic tone-map, matching the flatter house style.
  scene.add(new THREE.AmbientLight(0xffffff, 0.52));
  scene.add(new THREE.HemisphereLight(0xdfe6f2, 0x2a2e35, 0.32));
  const key = new THREE.DirectionalLight(0xffffff, 0.80);
  key.position.set(1.4, 1.9, 2.2);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xcdddff, 0.30);
  fill.position.set(-2.0, 0.5, -1.2);
  scene.add(fill);
  const rim = new THREE.DirectionalLight(0xffffff, 0.20);
  rim.position.set(0.2, -1.6, -1.8);
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
function wireUI(){
  document.querySelectorAll('#view-seg button').forEach(b => {
    b.addEventListener('click', () => setSectionMode(b.dataset.view === 'section'));
  });

  $('btn-reset').addEventListener('click', () => {
    if (sectionMode){
      if (orthoActive) settleOrtho();        // re-centre the section (no re-swing)
      else             beginSectionEntry();
    } else {
      flyTo(solidCamPos(), new THREE.Vector3(0,0,0), FOV_SOLID);
    }
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
  renderer.render(scene, orthoActive ? orthoCam : camera);
  if (orthoActive) updateAnnotations();
}

/* ── Boot ──────────────────────────────────────────────────── */
init();
fetch('gridded_ion_model.json')
  .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
  .then(data => {
    buildModel(data);
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
