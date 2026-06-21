
#!/usr/bin/env python3
"""
larmor_applet.py — Larmor Motion Applet
Single-file, stdlib-only.  Run:  python larmor_applet.py
"""

import json
import math
import webbrowser
from socketserver import ThreadingMixIn
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── threading server (Python 3.7-compatible) ───────────────────────────────────
class _Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True

# ── physical constants ─────────────────────────────────────────────────────────
AMU = 1.66053906660e-27   # kg / amu
E_C = 1.602176634e-19     # C  / elementary charge

# ── physics engine ─────────────────────────────────────────────────────────────
def compute(m_amu, q_e, v, theta_deg, B):
    if B     == 0: raise ValueError("|B| cannot be zero.")
    if v     == 0: raise ValueError("|v| cannot be zero.")
    if m_amu <= 0: raise ValueError("Mass must be positive.")

    m  = float(m_amu) * AMU
    q  = float(q_e)   * E_C          # signed [C]
    th = math.radians(float(theta_deg))

    v_par  = v * math.cos(th)         # ∥ to B  [m/s]
    v_perp = v * math.sin(th)         # ⊥ to B  [m/s]
    absq   = abs(q)

    omega_c = absq * B / m                                # [rad/s]
    r_L     = m * v_perp / (absq * B) if v_perp else 0.0 # [m]
    mu      = m * v_perp**2 / (2.0 * B)                  # [J/T]
    T_c     = 2.0 * math.pi / omega_c                    # [s]
    pitch   = v_par * T_c                                 # d [m] per gyration

    return {
        "v_par":   v_par,   "v_perp":  v_perp,
        "r_L":     r_L,     "omega_c": omega_c,
        "mu":      mu,      "T_c":     T_c,
        "pitch":   pitch,
        "sign":    1 if q >= 0 else -1,   # +1 → CW when viewing oncoming particle
    }

# ── embedded page ──────────────────────────────────────────────────────────────
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

/* ── panel ── */
#panel{
  width:272px;min-width:272px;
  display:flex;flex-direction:column;gap:14px;
  background:#111720;border-right:1px solid #1e2a35;
  padding:16px 14px 14px;overflow-y:auto;
}
h1{
  font-size:13px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  color:#90caf9;padding-bottom:8px;border-bottom:1px solid #1e2a35;
}
.sec{
  font-size:9px;letter-spacing:.1em;text-transform:uppercase;
  color:#546e7a;margin-bottom:6px;
}
.field{display:flex;flex-direction:column;gap:3px}
.field label{font-size:11px;color:#90a4ae}

input[type="number"],select{
  background:#0d1117;border:1px solid #263238;border-radius:4px;
  color:#eceff1;padding:5px 8px;font-size:12px;
  outline:none;width:100%;transition:border-color .15s;
}
input[type="number"]:focus,select:focus{border-color:#42a5f5}

.row2{display:flex;gap:6px}
.row2 input{flex:1}
.row2 select{width:52px;flex:none}

input[type="range"]{width:100%;accent-color:#42a5f5;margin-top:2px}

#btn-run{
  background:#1565c0;border:none;border-radius:5px;
  color:#fff;cursor:pointer;font-size:13px;font-weight:600;
  padding:9px;transition:background .15s;width:100%;letter-spacing:.04em;
}
#btn-run:hover{background:#1976d2}
#btn-run:active{background:#0d47a1}

/* outputs */
.out-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}
.card{
  background:#0d1117;border:1px solid #1e2a35;
  border-radius:5px;padding:7px 9px;
}
.card.wide{grid-column:1/-1}
.card .lbl{
  font-size:9px;color:#546e7a;text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:3px;
}
.card .val{
  font-size:13px;
  font-family:'Cascadia Code','Fira Mono',monospace;
  color:#4fc3f7;
}
.sec-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.scard{
  background:#0d1117;border:1px solid #182330;
  border-radius:4px;padding:5px 8px;
}
.scard .lbl{
  font-size:9px;color:#37474f;text-transform:uppercase;
  letter-spacing:.04em;margin-bottom:2px;
}
.scard .val{font-size:11px;font-family:monospace;color:#607d8b}

#error-msg{
  background:#4a0000;border:1px solid #c62828;border-radius:4px;
  color:#ef9a9a;font-size:11px;padding:7px 9px;display:none;
}

#legend{
  margin-top:auto;background:#0d1117;border:1px solid #182330;
  border-radius:5px;padding:8px 10px;font-size:10px;line-height:2.1;
}
#legend span{
  display:inline-block;width:9px;height:9px;border-radius:50%;
  margin-right:6px;vertical-align:middle;
}

/* viewport */
#viewport{flex:1;overflow:hidden;position:relative}
#viewport canvas{display:block}
</style>
</head>
<body>

<!-- ── left panel ── -->
<div id="panel">
  <h1>Larmor Motion</h1>

  <div>
    <div class="sec">Inputs</div>
    <div style="display:flex;flex-direction:column;gap:10px">

      <div class="field">
        <label>Mass <i>m</i> [amu]</label>
        <input type="number" id="inp-mass" value="1" min="0.001" step="0.001">
      </div>

      <div class="field">
        <label>Charge <i>q</i> [e]</label>
        <div class="row2">
          <input type="number" id="inp-qmag" value="1" min="0" step="1">
          <select id="sel-sign">
            <option value="+">+</option>
            <option value="-">&#x2212;</option>
          </select>
        </div>
      </div>

      <div class="field">
        <label>Speed |v| [m/s]</label>
        <input type="number" id="inp-speed" value="1000000" min="1" step="10000">
      </div>

      <div class="field">
        <label>Pitch angle &#952; = <b id="tdisp">45</b>&#xB0;</label>
        <input type="range"  id="inp-theta-r" min="0" max="90" value="45" step="1">
        <input type="number" id="inp-theta"   min="0" max="90" value="45" step="1"
               style="margin-top:4px">
      </div>

      <div class="field">
        <label>Flux density |B| [T]</label>
        <input type="number" id="inp-B" value="1.0" min="0.0001" step="0.1">
      </div>

    </div>
  </div>

  <button id="btn-run">&#9654;&#xFE0E;&nbsp; Run / Update</button>
  <div id="error-msg"></div>

  <!-- primary outputs -->
  <div>
    <div class="sec">Outputs</div>
    <div class="out-grid">
      <div class="card wide">
        <div class="lbl">Larmor Radius r<sub>L</sub></div>
        <div class="val" id="out-rL">&#x2014;</div>
      </div>
      <div class="card">
        <div class="lbl">&#x3C9;<sub>c</sub> [rad/s]</div>
        <div class="val" id="out-wc">&#x2014;</div>
      </div>
      <div class="card">
        <div class="lbl">&#x3BC; [J/T]</div>
        <div class="val" id="out-mu">&#x2014;</div>
      </div>
    </div>
  </div>

  <!-- secondary outputs -->
  <div>
    <div class="sec">Derived</div>
    <div class="sec-grid">
      <div class="scard">
        <div class="lbl">v&#x2225; [m/s]</div>
        <div class="val" id="out-vpar">&#x2014;</div>
      </div>
      <div class="scard">
        <div class="lbl">v&#x22A5; [m/s]</div>
        <div class="val" id="out-vperp">&#x2014;</div>
      </div>
      <div class="scard">
        <div class="lbl">T<sub>c</sub> [s]</div>
        <div class="val" id="out-Tc">&#x2014;</div>
      </div>
      <div class="scard">
        <div class="lbl">Pitch d [m]</div>
        <div class="val" id="out-pitch">&#x2014;</div>
      </div>
    </div>
  </div>

  <div id="legend">
    <span style="background:#4fc3f7"></span>Particle<br>
    <span style="background:#ffd54f"></span>Velocity v<br>
    <span style="background:#263238;border:1px solid #37474f"></span>B-field (+z)
  </div>
</div>

<!-- ── WebGL viewport ── -->
<div id="viewport"></div>

<!-- ── Three.js module ── -->
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ─────────────────────────────────────────────────────────────────────────────
//  Visualization constants
// ─────────────────────────────────────────────────────────────────────────────
const SCENE_R      = 5.0;   // on-screen Larmor radius (scene units)
const TURNS        = 4;     // number of gyrations to render
const SEG_PER_TURN = 128;   // curve segments per gyration
const SEC_PER_TURN = 2.0;   // wall-clock seconds per gyration (animation speed)

let renderer, scene, camera, controls, clock;
let helixLine, tubeMesh, particleMesh, velArrow, fieldGroup, guideGroup;
let cur = null;   // current animated parameters

// ─────────────────────────────────────────────────────────────────────────────
//  Scene initialisation
// ─────────────────────────────────────────────────────────────────────────────
function initViz(container) {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b0e14);

  const w = container.clientWidth, h = container.clientHeight;

  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(w, h);
  container.appendChild(renderer.domElement);

  camera = new THREE.PerspectiveCamera(50, w / h, 0.01, 5000);
  camera.position.set(SCENE_R * 2.4, SCENE_R * 1.7, SCENE_R * 2.8);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.07;

  scene.add(new THREE.AmbientLight(0xffffff, 0.55));
  const dl = new THREE.DirectionalLight(0xffffff, 0.85);
  dl.position.set(1, 2, 3);
  scene.add(dl);

  // particle sphere
  particleMesh = new THREE.Mesh(
    new THREE.SphereGeometry(SCENE_R * 0.075, 24, 24),
    new THREE.MeshStandardMaterial({
      color: 0x4fc3f7, emissive: 0x082030, roughness: 0.35
    })
  );
  scene.add(particleMesh);

  // velocity arrow (re-aimed every frame)
  velArrow = new THREE.ArrowHelper(
    new THREE.Vector3(1, 0, 0), new THREE.Vector3(),
    SCENE_R * 0.85, 0xffd54f, SCENE_R * 0.22, SCENE_R * 0.1
  );
  scene.add(velArrow);

  fieldGroup = new THREE.Group(); scene.add(fieldGroup);
  guideGroup = new THREE.Group(); scene.add(guideGroup);

  clock = new THREE.Clock();

  window.addEventListener('resize', () => {
    const w2 = container.clientWidth, h2 = container.clientHeight;
    camera.aspect = w2 / h2;
    camera.updateProjectionMatrix();
    renderer.setSize(w2, h2);
  });

  animate();
}

// ─────────────────────────────────────────────────────────────────────────────
//  B-field lines (grid of parallel lines along +z with arrowheads)
// ─────────────────────────────────────────────────────────────────────────────
function buildFieldLines(zHalf) {
  fieldGroup.clear();
  guideGroup.clear();

  const N = 3, step = SCENE_R * 0.9;
  const lineMat = new THREE.LineBasicMaterial({
    color: 0x1a2a35, transparent: true, opacity: 0.9
  });

  for (let i = -N; i <= N; i++) {
    for (let j = -N; j <= N; j++) {
      if (Math.abs(i) + Math.abs(j) > N + 1) continue;
      const x = i * step, y = j * step;

      const g = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(x, y, -zHalf),
        new THREE.Vector3(x, y,  zHalf),
      ]);
      fieldGroup.add(new THREE.Line(g, lineMat));

      fieldGroup.add(new THREE.ArrowHelper(
        new THREE.Vector3(0, 0, 1),
        new THREE.Vector3(x, y, zHalf * 0.5),
        zHalf * 0.28, 0x37474f,
        zHalf * 0.09, SCENE_R * 0.05
      ));
    }
  }

  // dashed guide line along gyro-centre axis (x=0, y=0)
  const geoG = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, 0, -zHalf), new THREE.Vector3(0, 0, zHalf)
  ]);
  const dashed = new THREE.Line(geoG,
    new THREE.LineDashedMaterial({ color: 0x546e7a, dashSize: 0.4, gapSize: 0.25 }));
  dashed.computeLineDistances();
  guideGroup.add(dashed);
}

// ─────────────────────────────────────────────────────────────────────────────
//  Build/rebuild helix from physics data
//
//  Parametrisation (B along +z):
//    x(φ) = r_S · sin(sign · 2π · φ)
//    y(φ) = r_S · cos(sign · 2π · φ)   ← starting at +y at φ=0
//    z(φ) = p_S · φ + zOff
//  where φ = gyrations completed.
//
//  For sign = +1 (positive charge): at φ=0 we are at +y, and φ increases
//  → x increases → clockwise rotation viewed from +z (oncoming). ✓
// ─────────────────────────────────────────────────────────────────────────────
function updateTrajectory(data) {
  const { r_L, pitch, sign } = data;

  //  Scale: pin gyroradius to SCENE_R units.
  //  The ratio pS/rS = pitch/r_L = 2π·cot(θ) is preserved,
  //  so the on-screen pitch angle matches the real one.
  let rS, pS, turns = TURNS;

  if (r_L > 0) {
    const s = SCENE_R / r_L;
    rS = SCENE_R;
    pS = pitch * s;                 // = SCENE_R · 2π · cot(θ)
  } else {
    // θ = 0: no gyration — straight streak along B
    rS = 0.0;
    pS = SCENE_R * 2.0;
  }

  // prevent runaway scene extent for very small θ
  const maxAxial = SCENE_R * 16;
  if (Math.abs(pS) * turns > maxAxial) {
    turns = Math.max(1, Math.floor(maxAxial / (Math.abs(pS) + 1e-30)));
  }

  const totalZ = pS * turns;
  const zOff   = -totalZ / 2.0;    // centre the helix at world origin

  //  Sample helix points
  const steps = turns * SEG_PER_TURN;
  const pts   = [];
  for (let i = 0; i <= steps; i++) {
    const phi   = i / SEG_PER_TURN;                      // gyrations
    const phase = sign * 2.0 * Math.PI * phi;
    pts.push(new THREE.Vector3(
      rS * Math.sin(phase),
      rS * Math.cos(phase),
      pS * phi + zOff
    ));
  }

  //  Dispose stale geometry
  if (helixLine) { scene.remove(helixLine); helixLine.geometry.dispose(); }
  if (tubeMesh)  { scene.remove(tubeMesh);  tubeMesh.geometry.dispose();  }

  //  Ghost trail (translucent line)
  helixLine = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({ color: 0x29b6f6, transparent: true, opacity: 0.18 })
  );
  scene.add(helixLine);

  //  Solid tube  (minimum radius so θ=0 still renders a thin rod)
  const tubeR = Math.max(rS * 0.018, SCENE_R * 0.007);
  const curve = new THREE.CatmullRomCurve3(pts);
  tubeMesh = new THREE.Mesh(
    new THREE.TubeGeometry(curve, steps, tubeR, 8, false),
    new THREE.MeshStandardMaterial({
      color: 0x29b6f6, transparent: true, opacity: 0.58,
      roughness: 0.45, metalness: 0.15,
    })
  );
  scene.add(tubeMesh);

  //  B-field lines spanning the full helix
  buildFieldLines(Math.max(SCENE_R * 1.6, Math.abs(totalZ) / 2 + SCENE_R * 0.9));

  //  Save animated state
  cur = { rS, pS, sign, turns, zOff };

  //  Re-frame camera to bounding sphere of helix
  const box    = new THREE.Box3().setFromObject(helixLine);
  const sphere = new THREE.Sphere();
  box.getBoundingSphere(sphere);
  controls.target.copy(sphere.center);
  const fovRad = camera.fov * Math.PI / 180;
  const dist   = sphere.radius / Math.sin(fovRad / 2) * 1.3;
  camera.position.copy(
    sphere.center.clone().addScaledVector(
      new THREE.Vector3(1.1, 0.7, 1.3).normalize(), dist
    )
  );
  controls.update();
}

// ─────────────────────────────────────────────────────────────────────────────
//  Animation loop
// ─────────────────────────────────────────────────────────────────────────────
function animate() {
  requestAnimationFrame(animate);
  controls.update();

  if (cur) {
    const loopTime = SEC_PER_TURN * cur.turns;
    const t        = clock.getElapsedTime() % loopTime;
    const phi      = (t / loopTime) * cur.turns;         // gyrations completed
    const phase    = cur.sign * 2.0 * Math.PI * phi;

    //  Position on helix
    const pos = new THREE.Vector3(
      cur.rS * Math.sin(phase),
      cur.rS * Math.cos(phase),
      cur.pS * phi + cur.zOff
    );
    particleMesh.position.copy(pos);

    //  Velocity direction = d(pos)/d(phi) normalised
    //    dx/dφ =  rS · cos(phase) · sign · 2π
    //    dy/dφ = -rS · sin(phase) · sign · 2π
    //    dz/dφ =  pS
    const tx = cur.rS * Math.cos(phase) * cur.sign * 2 * Math.PI;
    const ty = -cur.rS * Math.sin(phase) * cur.sign * 2 * Math.PI;
    const tz = cur.pS;
    const tl = Math.sqrt(tx * tx + ty * ty + tz * tz);
    if (tl > 1e-12) {
      velArrow.setDirection(new THREE.Vector3(tx / tl, ty / tl, tz / tl));
    }
    velArrow.position.copy(pos);
  }

  renderer.render(scene, camera);
}

// ─────────────────────────────────────────────────────────────────────────────
//  Form wiring
// ─────────────────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

//  Theta: keep slider and number box in sync
$('inp-theta-r').addEventListener('input', () => {
  const v = $('inp-theta-r').value;
  $('inp-theta').value    = v;
  $('tdisp').textContent  = v;
});
$('inp-theta').addEventListener('input', () => {
  const v = $('inp-theta').value;
  $('inp-theta-r').value  = v;
  $('tdisp').textContent  = v;
});

//  Number formatting
function fmt(x) {
  if (x === null || x === undefined || isNaN(x)) return '\u2014';
  if (x === 0) return '0';
  const a = Math.abs(x);
  if (a >= 1e4 || a < 1e-2) return x.toExponential(3);
  return x.toPrecision(4);
}

function writeReadouts(d) {
  $('out-rL').textContent    = fmt(d.r_L)     + ' m';
  $('out-wc').textContent    = fmt(d.omega_c) + ' rad/s';
  $('out-mu').textContent    = fmt(d.mu)      + ' J/T';
  $('out-vpar').textContent  = fmt(d.v_par)   + ' m/s';
  $('out-vperp').textContent = fmt(d.v_perp)  + ' m/s';
  $('out-Tc').textContent    = fmt(d.T_c)     + ' s';
  $('out-pitch').textContent = fmt(d.pitch)   + ' m';
}

function showError(msg) {
  $('error-msg').textContent   = msg;
  $('error-msg').style.display = 'block';
}
function clearError() { $('error-msg').style.display = 'none'; }

async function runUpdate() {
  clearError();
  const sign = $('sel-sign').value === '-' ? -1 : 1;
  const body = {
    m_amu:     +$('inp-mass').value,
    q_e:       sign * Math.abs(+$('inp-qmag').value),
    v:         +$('inp-speed').value,
    theta_deg: +$('inp-theta').value,
    B:         +$('inp-B').value,
  };
  try {
    const res  = await fetch('/api/compute', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(body),
    });
    const data = await res.json();
    if (data.error) { showError(data.error); return; }
    writeReadouts(data);
    updateTrajectory(data);
  } catch (e) {
    showError('Server error: ' + e.message);
  }
}

//  Live update (150 ms debounce)
let _debounce = null;
function debounced() {
  clearTimeout(_debounce);
  _debounce = setTimeout(runUpdate, 150);
}

['inp-mass','inp-qmag','inp-speed','inp-theta','inp-theta-r','inp-B','sel-sign']
  .forEach(id => $(id).addEventListener('input', debounced));
$('btn-run').addEventListener('click', runUpdate);

//  Boot
initViz(document.getElementById('viewport'));
runUpdate();   // compute & render defaults immediately
</script>
</body>
</html>
"""

# ── HTTP handler ───────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass   # silence per-request noise

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type",   ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control",  "no-cache")
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
        n   = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        try:
            p = json.loads(raw)
            r = compute(**{k: float(p[k])
                           for k in ("m_amu", "q_e", "v", "theta_deg", "B")})
            self._send(200, "application/json", json.dumps(r).encode())
        except (ValueError, KeyError, TypeError) as exc:
            self._send(400, "application/json",
                       json.dumps({"error": str(exc)}).encode())

# ── entry point ────────────────────────────────────────────────────────────────
HOST, PORT = "127.0.0.1", 8000

if __name__ == "__main__":
    srv = _Server((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"\n  Larmor Motion Applet  →  {url}")
    print("  Ctrl-C to quit.\n")
    webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        srv.shutdown()