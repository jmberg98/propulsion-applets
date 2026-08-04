# Geometry Lessons — from the Gridded-Ion applet, for the Hall-Effect build

Compiled 2026-07-24 from the full `gridded_ion/` record: 60+ commits, `build_thruster.py`,
`gridded_ion_devlog.html` (30 chapters, Jul 1–9), and the project memory files.

**Purpose.** Every geometry *creation* and *modification* request made against the gridded-ion
engine, what actually happened, and what it cost. The last three sections turn that into a
pre-flight checklist for the Hall-effect thruster (HET) applet so the same weeks aren't spent
twice.

**Headline number:** of the ~35 distinct geometry requests cataloged below, **fewer than a third
were actually geometry problems.** The rest were render/compositing artifacts that *looked* like
broken geometry — and several days were lost to fixing solids that were never broken.

---

## 0. The ten rules (read this if you read nothing else)

1. **Own the whole chain in-repo from day one.** params → solid → mesh → JSON → HTML. The
   gridded-ion CAD generator and the STEP→JSON tessellator were both authored outside the repo
   and lost. That single omission caused a ~4-hour wall, a hard reset, three reverted
   redesigns, and ~2 weeks of applet-side hacks standing in for geometry edits.
2. **Never hand-edit a B-rep STEP.** It was tried, it corrupted the file on the first pass (a
   regex replacement ate the trailing `;` terminator), and even the "provably safe" axial scale
   couldn't do what was actually asked.
3. **Never patch geometry at load time in JS.** Every runtime vertex push (`reach`, grid fatten,
   bore widening, radial grid stretch) became an invisible second source of truth that later
   contradicted the CAD, the STEP, and the physics constants.
4. **Assume the report is a render artifact until a raycast says otherwise.** Ray-cast the actual
   mesh before touching a solid. "The body intersects the tube" was reported for ~2 weeks and was
   never once a real intersection.
5. **The cut plane must slice watertight, closed, consistently-wound solids.** Clip-plane +
   stencil caps produce garbage on thin open shells. Model every visible part as a closed solid,
   full stop.
6. **Every visible surface must be reachable by a single, uniform draw path.** The recurring
   color/darkness/banding bugs were all *layer-count* or *stale-GL-state* mismatches, not color
   values.
7. **Draw order and depth are geometry.** `renderOrder`, `depthTest`, `depthWrite`, `capless`,
   stencil membership: define these per-role *once* and make symmetric parts symmetric. The
   longest bug in the project was one tube having them and its twin not.
8. **The physics must read its collision surfaces from the loaded mesh**, never from
   hand-transcribed constants. Hardcoded grid planes drifted ~5.7 units inside the drawn slabs;
   3933 sprites were penetrating metal.
9. **An open bore renders as the color behind it.** A clean tunnel through a grey wall reads as
   grey — i.e. as *not drilled*. Depth cues must be authored deliberately; they don't fall out of
   correct geometry.
10. **Confirm the intent before executing a literal instruction.** "Extend the tube" turned out to
    mean *retract* it. "Axially in/out" meant *radially*. A/B two renders instead of guessing.

---

## 1. The pipeline that finally worked

Reached ~3 weeks in. **Start the HET here.**

```
build_thruster.py   parameters + solids (build123d / OpenCASCADE)  →  .STEP
       ↓ imports constants & helpers
build_model.py      rebuilds the same solids, emits the applet's exact component
mesher.py           list (name/label/role/color) IN ORDER  →  model.json
       ↓ node script swaps the content of <script id="model-data">
applet.html         self-contained single file
```

**Environment (the parts that bit):**
- Dedicated venv at a **short root path**: `C:\Users\jmatt\.cadenv`, **Python 3.11**.
  System Python 3.14 has no OpenCASCADE wheels. The first install failed because deep scratchpad
  paths blow past Windows `MAX_PATH` mid-dependency-tree.
- Run: `/c/Users/jmatt/.cadenv/Scripts/python.exe build_thruster.py out.STEP`
- fontTools emits a harmless `'name' table stringOffset` warning — `grep -v stringOffset`.

**`mesher.py` — the non-obvious part.** OCC's `BRepMesh` triangulation carries **no normals**, and
`.tessellate()` doesn't give usable ones. Compute them per-face via `BRepGProp_Face.Normal` at each
UV node — this yields smooth normals within a face and crisp creases between faces. Skipping this
gives faceted, muddy shading that no material tweak will fix.

**Axis mapping.** The CAD is authored on one axis and the viewer expects another. Gridded-ion uses
`(vx,vy,vz) = (cz,cy,cx)` applied to positions **and** normals (a reflection — fine under
`DoubleSide` materials). Decide this once, apply it in the tessellator, and never rotate at runtime.

**Freeze `center` / `size` / `bounds`.** Hardcoded plume orifices, callout anchors, and field-line
control points all key off them. Recomputing on a regen silently moves every label. Keep the frozen
values in the JSON and let geometry change underneath them.

**Mesh budget.** Perforated grids tessellated to ~65k triangles each and pushed the single HTML from
1.1 MB → 7 MB. The later rebuild got the same visual result at ~16.7k verts and a 1.8 MB JSON.
Tessellation tolerance is a knob — set it deliberately.

---

## 2. Catalog of geometry requests

### Phase 0 — original CAD authoring (separate session, CadQuery)

| # | Request | Outcome |
|---|---|---|
| 1 | "Generate a 3D CAD model of the diagram for WebGL visualization… must be openable and editable in Onshape/SolidWorks" | CadQuery parametric build → STEP + GLB + `.py`. **The `.py` generator was never committed.** |
| 2 | Remove the ion cone; add a shell; make the neutralizer part of the thruster; add the missing magnet ring around the hollow cathode | Shell authored to follow the form (conical back, cylindrical mid, front rim ring); neutralizer fused via a pylon; cathode ring added. 10 named bodies. |
| 3 | Make the neutralizer angle much shallower, and its bracket, to match the reference render | Pylon → low-profile bracket; 60° → 15° below the thrust axis. |

> **Cost of #1's omission:** the STEP acquired a SolidWorks header on a round-trip, so weeks later
> the file *looked* SolidWorks-native. A full scan of all 637 git objects was needed to establish
> that no generator had ever existed in the repo.

### Phase 1 — viewer on a baked mesh (Jul 1–3)

| # | Request | Outcome |
|---|---|---|
| 4 | Make a WebGL 3D graphic of the STEP, with a button that moves the camera to a cross-section matching the reference PNG | STEP tessellated **offline** → `gridded_ion_model.json`. **The tessellator was also not committed.** From here the viewer is a baked-mesh viewer with no path back to the solid. |
| 5 | Make the cross-section an orthographic labeled schematic | Perspective splayed the grid apertures open even dead-on; ortho camera fixed it. Callouts + dashed field lines added. |
| 6 | Recolour: grids darker, chamber interior lightest, outer structure unified | Straightforward. |
| 7 | Uniform body, cylindrical bore/grid depth, ring-cusp field lines | Cut faces (caps) rendered unlit/emissive so all body cross-sections are ONE grey; receding meshes lit by a camera-axis key light. **Grids "fattened along the axis and pulled apart" — implemented as a JS vertex hack at load.** This hack survived into later sessions and had to be hunted down and removed. |

### Phase 2 — the wall, the hard reset, three reverts (Jul 4)

| # | Request | Outcome |
|---|---|---|
| 8 | "Make the shell not hollow… filled with the same color metal. Grids thicker, same thickness, more space between." | Discovered: baked mesh, no tessellator. **User: "I've spent about 4 hours struggling with the results… The verification process simply doesn't work. It doesn't ever match expectations."** Root cause named: the section is a clip-plane + stencil-cap slice, which only yields clean filled caps from watertight closed solids — `Outer_Shell_Housing` was **a thin open shell** (which is *why* it read as hollow), and the assembly isn't axisymmetric. Proposal: rebuild the section as an authored parametric schematic. Built. → **"Nevermind, revert it."** |
| 9 | Same asks, re-scoped: "Only change the STEP file and update the cross-section file" | No CAD kernel present. A new numpy-authored GLB + a fresh headless three.js section render were produced instead. → **"revert changes."** |
| 10 | Same asks again: attempt everything in the STEP directly | Parsed the B-rep, proved both grids are **100 % X-axial** (148 cylinders, 296 circles, 2 planes, 0 non-axial), so an X-only scale is mathematically safe for thickness/gap. First pass **corrupted the file** — the replacement records dropped the trailing `;`. Restored from backup, redone, validated (0 distorted surfaces). **Gap-fill was still impossible** (needs new solid material) and the PNG couldn't be re-rendered. Net: two of five asks delivered, file put at risk. |
| 11 | "Are you able to modify a step file?" → "Would you be able to make a new file instead?" → "Claude made the file." | Full git-object scan proved no generator existed. Decision: author a fresh parametric model. Kernel hunt → build123d on Py 3.11; first venv install died on `MAX_PATH` → relocated to `C:\Users\jmatt\.cadenv`. |
| 12 | **The decisive spec:** "Each grid a bit thicker, more gap between them. There must be no gap between the outermost shell and the ionization chamber — filled by making the outermost shell larger. Same color as the outermost wall." | `build_thruster.py` written. Screen 2 → 3.5, accel 3 → 5, gap 4 → 8, housing filled inward so its inner wall meets the chamber (`R_CHAMBER_OUT`), housing grey `#9096a0`. → `gridded_ion_3D_v2.STEP`. **The request that had failed three times in a row succeeded on the first try once the model was parametric.** |

> **This phase is the whole lesson.** Three reverted deliverables and a corrupted STEP, all
> attempting to do parametrically-shaped edits without a parametric model.

### Phase 3 — real cross-section from the real model (Jul 5)

| # | Request | Outcome |
|---|---|---|
| 13 | Use v2 STEP as the 3D model and the reference PNG as the cross-section; keep colors consistent | Delivered — the section became a faded-in PNG overlay. |
| 14 | **"The cross-section should be the actual cross-section of the 3D view, not the png I uploaded. Keep the labels and magnetic field lines."** | PNG approach reverted wholesale. Re-tessellated with a −90° Y rotation so v2's `+Z` thrust axis maps to the viewer's `+X` convention — chosen specifically so `center`/`size` matched the original and **the clip plane, stencil caps, ortho framing, callouts and field lines needed no code changes.** Field-line cusps re-tuned to v2's real ring stations (centered X ≈ −46.5 / +33.5 / +118.5, chamber axis Y ≈ −11.5). |
| 15 | Shorter label leaders; rename to "Neutralizer Cathode" / "Bombardment Cathode"; move the anode / neutralizer / magnet-ring anchor nodes | `MAX_LEADER` 240 → 150 plus per-anchor moves. Pure annotation. |
| 16 | Embed the magnet rings **in the thruster wall**, not the plasma cavity | Rings moved to `r = R_CHAMBER_OUT+2 … R_HOUSE−10`, i.e. buried in wall material, so in section they read as dark boxes embedded in the wall rather than rings protruding into the chamber. |

### Phase 4 — clean parametric edits (Jul 6–9)

| # | Request | Outcome |
|---|---|---|
| 17 | Neutralizer keeper enclosure — a box wrapping the cathode with a bored front plate so you can't see inside | Added as part of `housing` (not a new component): outer box minus a cavity flush to the Ø18 cathode, minus an r8 front-plate bore. |
| 18 | Fill the neutralizer cathode (solid, not hollow) | **Done in `build_thruster.py` + re-tessellate, replacing an earlier applet-side "patch-fill".** The good precedent — a geometry ask solved in geometry. |
| 19 | Back-wall magnet ring buried in a thickened rear plate, closing an extra ring cusp | Rear plate thickened (`Z_REAR_BACK = Z_REAR_INNER − 20`). Ring radius iterated **by eye across three rounds**: 102..116 → 34..48 (encircle the feed-throughs) → 44..58 (hold it off the injector, clear radial gap). |
| 20 | Enlarge the grid apertures | Screen 6.0 → 7.5, accel 3.0 → 4.5; STEP regenerated. One-line parameter change. |
| 21 | Draw each magnet ring split N/S, add corner cusp arcs | Section **overlay**, not CAD — correct call: magnetisation is annotation, not solid geometry. |

> Phases 4 and 6 are the two halves of the project: parameter edits took minutes; render-compositing
> issues took days.

### Phase 5 — the feed-through saga (Jul 8 → Jul 20) — the single longest-running issue

Reported over and over as *"the thruster body intersects / cuts through / caps the bombardment
cathode and propellant injector."* Ray-casting the meshes (Möller–Trumbore, axial rays at the tube
surface radius, 16 angles) proved the rear-plate bores were **fully clear** — cathode bore r14
around an r10 tube, injector r7 around r5, no body triangle within 1 mm. **It was never a geometric
intersection.** The reports were, in sequence:

| Sub-issue | Actual cause | Fix |
|---|---|---|
| Tube looks "capped at the chamber" | `Anode_Discharge_Chamber` still depth-writes in the ghost/cut view, occluding the tube's in-chamber length | `drawFeedOverBody`: `material.depthTest = false` whenever the body is cut or ghosted; keep depth ON in the solid 3-D view |
| A band cuts across one tube at the wall; its bore is disced shut | **Asymmetry.** The injector was `capless:true` + `renderOrder 45`; the cathode was **neither**, so the cut-face caps painted across it | Make the twins symmetric in all three places (rec `capless`, mesh `renderOrder`, the `setGridsTransparent` else-branch) |
| Gold rim artifact around the injector cut | A `capless` part that still writes stencil leaves the buffer dirty; a later gold cap paints the leftover region | Drop the stencil write together with the cap |
| Bright white band flashes across the body mid-morph | Cut-face caps were full-bright emissive, and cut-face area balloons like √p as the plane grazes the outer shell | Retime the sweep decelerating (`cutOffset = modelHalfZ·q²`) **and** ramp cap style from lit body color → unlit emissive. (Dead end: fading cap *opacity* — the buried magnets then show through) |
| That band "cuts through" the cathode mid-morph | `drawFeedOverBody` didn't cover the morph | Gate on `cutOpen = cutOffset < modelHalfZ − 0.5`. **Required companion fix:** initialise `cutOffset = modelHalfZ` so the fresh 3-D view doesn't x-ray the tubes |
| Bore "bits"/blobs across the openings | The **back-wall magnet ring's** cap + back half bleeding across the bores — it sits at the same axial station | Diagnosed; a fix was built and then **reverted at the user's request** — the bits were kept |
| "The hole doesn't go all the way through" (recurring) | Not reproducible on a real GPU in any mode. Initially a **stale-cache** red herring (a 7 MB single HTML caches hard) | Later established as a *look preference*, not a bug |
| The literal fix made it worse | "Extend it" was honoured — reach 14→45 / 26→55 mm | **The real ask was the opposite: retract.** Final `reach = Hollow_Cathode ? -20 : 0` |
| Bore still doesn't read as drilled | **An open bore renders as the chamber grey behind it — the same grey as the wall. Zero contrast.** | A dark bore-liner was built to create contrast → rejected ("reads as black void slots"). Preference settled on a clean snug tube, no shadow |
| "Get rid of the bores" — rear wall should read solid | The clearance bores showed as recessed slots flanking each tube | **`borePlugs`: stencil-only cylinders that feed each bore column into the *shell's own* cut-face cap.** Two earlier attempts failed and are the lesson: (a) a solid wall-colored cylinder — clipping discards `z>cut` so it never caps the cut *face*; (b) a separate stencil+cap per plug — worked, but the cap object **overhung the rear face** ("hanging out the back") |
| Tubes discolour after toggling transparent | Two causes. (1) The injector's role `feed` picked up a ghost **emissive floor** that the later override never cleared → self-lit near-white. (2) Both tubes are `DoubleSide` **and** depth-test-off, so their front/back walls don't occlude each other; toggling leaves **stale GL blend state** and the rod reads ~13 % darker | (1) clear `emissive` in the feed override; (2) `m.needsUpdate = true` to force a material refresh. Material dumps were byte-identical — proving it was render state, not a property |

Only at the very end did the fix land **in the geometry**: `a9d679e` bored the injector and cathode
fully through the rear face and dropped the coincident interface disc, with `build_thruster.py`
updated to match; `d84f101` merged the rear back-plate into the shell mesh (one piece, no inter-mesh
seam) and dropped the chamber's redundant back-wall discs.

### Phase 6 — transparent-view compositing (Jul 15–23)

| # | Request | Cause & fix |
|---|---|---|
| 27 | Cathodes read as a grey shell around a gold bore in transparent view | Thin tube walls go dim edge-on when translucent → keep cathodes opaque |
| 28 | Body color mismatch — edges/caps darker than the body; grid/housing corner notch | Ghost rendered as **stacked translucent layers**, so single-layer edges read darker. Fixed with a per-component **depth pre-pass proxy** so every pixel is exactly one layer. Grids stretched radially to close the notch. → **This whole commit was reverted** (`a7f100a`) and re-approached later |
| 29 | A dark "slit" band bleeding through the shell at each magnet ring | The ring's **curved half-torus** showing in the cut → hide it, show only the flat cap square, darkened for contrast |
| 29b | Screen grid buried in the shell rim / visible gap | Pin the grid's upstream face flush to the chamber front wall (`x = 135.5`) — further either way breaks one view or the other |
| 30 | Bore-fill and anode outlines **flicker while panning** | Every cut-face cap sat exactly at `z = cutOffset`, coincident with the clipped mesh **edges** → depth tie, flickers only while the camera moves. `polygonOffset` was the wrong tool (view-angle dependent). **Fix: `CAP_LIFT = 0.6`** — lift every cap a *constant* amount toward the camera. Invisible in ortho, cap isn't clipped, depth-test-off tubes still draw over |
| 31 | The inter-grid gap reads as a distinctly darker grey block | **Ghost layer-count mismatch, not color.** Down the chamber a ray crosses 2 translucent surfaces (chamber bore + shell inner wall); the gap has only 1 (the housing front-ring bore). Fix: carry the chamber wall across the gap as a **ghost-only sleeve** at `1−(1−a)²` opacity — algebraically identical to the two coats, no second silhouette. **Axis taken from the grid-disc bbox centre**, because the assembly is centered on its full bbox and the neutralizer pulls that ~11.5 mm off the thrust axis |
| 32 | Magnet spans invisible in the transparent section | The pale shell in front **veils** a near-black span down to ~3/255. Fix: draw the magnet mesh in the transparent pass with `depthTest=false, renderOrder=40` so it paints over the veil |
| 32b | The dark outer frame can't be lightened | `Outer_Shell_Housing` is **veiled-pinned** to ~78/255 by overlapping ghost layers — unchanged even at `STRUCTURE_GRAY = white`. Un-veiling it lightens it but flattens the frame and chamber into one block. Documented as a known limit |

> **Structural insight from this phase:** in the flat section, the visible surfaces are the **caps**,
> not the ghost mesh. So `ghostOpacity`/`ghostEmis` have *zero* effect on the section's appearance —
> hours were spent turning color knobs that were wired to nothing.

### Phase 7 — collision geometry (Jul 23)

| # | Request | Cause & fix |
|---|---|---|
| 33 | "Particles pass through / bounce wrongly off the grids" | Four separate faults. (a) Rebounds were sent straight back along −k with sideways velocity discarded → generalised specular `reflectOffWall` + `bounceOffGrid` roughness. (b) The inter-grid gap had **no upstream boundary**, so atoms walked back through the screen grid's metal; recombining ions were left standing *inside* the grid (154 chamber neutrals downstream of the grid plane → 0); ions entering the wide screen hole (±9) rode that y through the accel bore (±4.5) — measured 8.7 mm off-centre, straight through webbing → beamlet now eases onto the channel centreline. (c) Particles were depth-tested against the hardware and swallowed by the far side of an aperture → same depth-test-off treatment as the feed tubes. **(d) The core geometry bug: each grid is *drawn* as a slab but the sim bounced off a single hardcoded *plane inside it*** (137 vs a slab drawn 135.5–140.4; 156 vs 153–162) — sprites were ~5.7 units buried before turning. Replaced with `SCREEN_SLAB` / `ACCEL_SLAB` **filled from the real meshes at load**, testing the sprite's *edge* against the real face. **Sprites penetrating grid metal: 3933 → 2.** |
| 33b | Flicker introduced by that fix | Bore-confinement was applied to *any* particle sharing a grid's x-range — the neutralizer jet at y = 128 got yanked 59 mm onto the outermost channel. Fix: **latch the bore at the gate that admitted the particle.** Draw-time teleports 59.5 → 5.6 mm |

Honest side effects were reported rather than hidden: neutrals dwell longer in the gap (6.2 → 13.6)
and propellant utilisation drifted 82.1 % → 77.6 %, just below the documented 80–85 % target.

---

## 3. Failure taxonomy

Sorted by how much time each class consumed.

### A. Missing pipeline (largest single cost)
No committed generator, no committed tessellator. Symptoms: geometry asks become JS hacks; JS hacks
become a second source of truth; the CAD, the STEP, the JSON, and the applet all drift apart.
**Prevention:** commit `build_*.py` and `mesher.py` **before** the first model is used anywhere.

### B. Render artifact misdiagnosed as broken geometry (second largest)
Every "the body intersects X", "the hole is capped", "there's a ring/band/blob/slit". Each had a
compositing cause. **Prevention:** raycast first — it takes minutes and settles the question.

### C. Layer-count and veiling mismatches
Translucent bodies composite by *how many surfaces a ray crosses*. Any span with a different count
is a different color, and no color/opacity knob will equalise them. Cures: depth pre-pass proxy
(force single layer), or a compensating ghost sleeve at `1−(1−a)ⁿ`.

### D. Depth ties at the cut plane
Caps coincident with clipped mesh edges → flicker **only while the camera moves** (settled frames are
always clean, so static headless screenshots can't catch it). Cure: a **constant** cap lift, never
`polygonOffset`.

### E. Draw-state asymmetry between twin parts
Two tubes, two grids, N magnet rings — if they don't share `capless` / `renderOrder` / stencil
membership / role, one of them will look wrong in exactly one view. Cure: derive these from **role**,
never per-name.

### F. Stale GL state
`DoubleSide` + `depthTest:false` parts blend against themselves after a material toggle. Material
dumps are byte-identical; only `needsUpdate = true` fixes it.

### G. Physics constants transcribed from geometry
Hardcoded plane positions, radii, bore centres. They go stale on the first regen.
Cure: read from `mesh.geometry.boundingBox` at load.

### H. Coincident / redundant faces
Stacked back-plate discs read as spurious thin discs in transparent view; coincident chamber walls
made an extra silhouette. Cure: merge parts that are conceptually one piece **in the CAD**, and
delete interface discs.

### I. Ambiguous instructions taken literally
"Extend" meant retract. "Axially in/out" meant radially. Cure: A/B two renders before committing.

### J. Stale cache
A 7 MB single HTML caches hard. `page.setCacheEnabled(false)` headlessly; `?v=N` for the user;
OneDrive can also serve a not-yet-flushed copy right after an edit — always `grep -c` the served copy.

---

## 4. Pre-flight checklist for the Hall-effect applet

**Before authoring any geometry**

- [ ] Create `hall_thruster/build_thruster.py`, `build_model.py`, `mesher.py` and commit them
      *empty-but-runnable* first. Copy the gridded-ion ones as the starting point.
- [ ] Reuse `C:\Users\jmatt\.cadenv` (Py 3.11 + build123d). Don't rebuild the venv; don't use 3.14.
- [ ] Fix the axis convention **once**, in the tessellator, and write it in a comment at the top of
      all three files.
- [ ] Decide the component list (name / label / role / color) **up front** and have `build_model.py`
      emit exactly that list in exactly that order. Roles drive every render decision downstream.
- [ ] Set the tessellation tolerance deliberately. Target ≲2 MB JSON.

**While authoring**

- [ ] Every visible part is a **closed watertight solid**. No thin open shells anywhere.
- [ ] No coincident faces between parts. If two things are conceptually one piece, `+` them into one
      solid in the CAD (the rear-plate/shell merge lesson).
- [ ] Give each conceptual pair/group **identical** render treatment via its role.
- [ ] Freeze `center`/`size`/`bounds` in the JSON as soon as any label or overlay references them.

**Before declaring a geometry bug**

- [ ] Raycast the mesh along the suspect axis at several radii.
- [ ] Turn particles off and zoom the ortho camera tight (f ≈ 0.3–0.6).
- [ ] Dump each component's `renderOrder` / `depthTest` / `cap.visible` and compare twins.
- [ ] Color the suspect part bright green — the animate loop overwrites `mesh.visible` every frame,
      so hiding it from an injected script won't stick, but color will.
- [ ] Check it isn't a **pan-only** flicker (settled frames clean → depth tie).
- [ ] Confirm the user isn't on a cached copy.

**Never**

- [ ] ...hand-edit a STEP.
- [ ] ...push vertices at load time.
- [ ] ...hardcode a collision plane.
- [ ] ...try to fix a layer-count problem with a color.

---

## 5. Hall-effect specifics — where these traps will bite differently

An HET is **annular**, which changes the geometry problem in three concrete ways.

**5.1 The axial cut now crosses *four* walls, not two.**
A `z = 0` section of an annular channel cuts the outer channel wall, the outer plasma gap, the inner
plasma gap, and the inner wall/centre stem — on *both* sides of the axis. Expect the Phase-6
layer-count bug immediately and by design: the channel interior, the two wall thicknesses, the
magnetic screens, and the coil pockets will each have a different ghost layer count. **Plan the
depth pre-pass proxy from day one** rather than retrofitting it.

**5.2 The centre stem is the new feed-through.**
The inner magnetic core / inner coil / inner pole runs down the middle of the annulus and passes
through the back plate — exactly the topology that produced the two-week feed-through saga. Apply
the resolved recipe *pre-emptively*: give the stem the same `capless` + high `renderOrder` +
depth-test-off-when-cut treatment as its neighbors, symmetric across every part that crosses the
back plate, and use stencil-only `borePlugs` for any clearance bore you want to read as solid wall.

**5.3 The magnetic circuit is mostly buried metal.**
Inner and outer coils, front and rear pole pieces, magnetic screens, and the back-plate return path
are all embedded in structure — i.e. all of them are Phase-6 "veiled" parts that will render
invisible in the transparent section without an explicit over-veil draw
(`depthTest=false, renderOrder≈40`). Decide up front which of these are **solids** and which are
**overlay annotation**. Gridded-ion got this right once: N/S magnetisation was drawn as a schematic
overlay, never modelled.

**5.4 Component list to settle before modeling**

| Part | Solid or overlay | Notes |
|---|---|---|
| Discharge channel (BN/BNSiO₂ annulus) | solid | Two coaxial walls + a base — model as one closed solid, not three |
| Anode / gas distributor ring | solid | At the channel base; it is also the propellant manifold |
| Inner coil + inner pole/core | solid | The centre-stem trap — see 5.2 |
| Outer coils (typically 4) + outer pole | solid | Not axisymmetric → the `z=0` cut may miss or clip them; check before tuning the section |
| Magnetic screens / back plate | solid | Merge into one piece where conceptually continuous |
| Cathode (external, on a bracket) | solid | Pulls the assembly bbox off the thrust axis — **the gridded-ion neutralizer did exactly this, by ~11.5 mm.** Take section-sleeve and overlay axes from a *component* bbox, never the assembly bbox |
| Radial **B** field lines | **overlay** | The defining HET feature; annotation, never geometry |
| Axial **E** field / acceleration zone | **overlay** | |
| Hall current (azimuthal e⁻ drift) | **overlay** | Genuinely 3-D and azimuthal — the one place a flat section under-serves the physics; plan a 3-D or perspective inset |
| Plume / beam | **overlay** | Additive, `depthWrite:false` |

**5.5 Physics collision surfaces to read from the mesh, not transcribe**
Channel inner radius, channel outer radius, channel exit plane, anode plane, cathode orifice. All
five must be filled from `mesh.geometry.boundingBox` at load, exactly as `SCREEN_SLAB`/`ACCEL_SLAB`
are. The annulus adds a wrinkle gridded-ion never had: particles need **two** radial walls with a
forbidden zone between the axis and the inner wall — that region must be an explicit boundary or
electrons will pool on the centreline.

**5.6 What is genuinely easier than gridded-ion**
No perforated grids. That single fact removes the 65k-triangle-per-part mesh explosion, the
aperture-alignment collision problem, the bore-latching flicker, and the hole-pattern tessellation
cost. The HET model should tessellate an order of magnitude lighter.

---

## 6. Diagnostics playbook

**Headless screenshots** — `puppeteer-core` driving installed Chrome via `executablePath`.
`page.goto(url, {waitUntil:'domcontentloaded'})` — *not* `networkidle2` (persistent font/CDN sockets
never settle). Wait on a global you expose at the end of the main module script. The one-shot
`--virtual-time-budget --screenshot` path **hangs** on these viewers because the rAF particle loop
never lets virtual time drain.

**Interior geometry** — faster than WebGL: slice the JSON meshes by a plane in matplotlib
(triangle–plane intersect → `LineCollection`). A true 2-D cutaway, no browser. This is also the
right way to judge CAD interiors: matplotlib's `Poly3DCollection` **cannot** depth-sort hollow
solids, so iso views lie — use 2-D sections.

**Physics/kinematics** — screenshots are weak for stochastic motion. Inject a harness inside the
**module scope** (right before the final `</script>`, where `PARTS`/`updateParticles`/etc. are
lexically visible), expose `window.__runTest(scenario)`, run a **synchronous** step loop so the app's
own rAF can't interleave, and `console.log('TEST_RESULT '+JSON.stringify(...))`. Average over the
last ~4 s — small-count ratios have high run-to-run variance.

**Pan flicker** — real GPU (`headless:false`) plus actual camera motion. Color two suspect parts
differently and right-drag; settled frames are always clean.

**Reproducibility** — `page.setCacheEnabled(false)`; `grep -c "<new string>"` the served copy before
rendering (OneDrive can hand back a not-yet-flushed file); `curl … | grep -c` to confirm the server
sees it too. Remove any `window.__DBG` hook from the source before finishing.

**CSS gotcha that will recur** — a base rule like `#viewport canvas { display:block }` (specificity
101) beats a bare `#my-canvas { display:none }`. Any new 2-D overlay canvas must out-specify it
(`#viewport #my-canvas`) or it is stuck visible in every mode, painting over everything. Symptom: the
backing store has pixels but nothing composites, and `elementFromPoint` returns the wrong canvas.

---

## 7. Working agreements

- **"Axially in/out" means radially.** Confirm the axis before moving anything.
- Directional asks about depth/protrusion are **look preferences**, not bug reports. A/B two renders.
- Geometry asks get solved **in the geometry**. If a render patch is the right call, say so
  explicitly and record why — the `build_thruster.py` comment block is the model for this.
- Report side effects of a correct fix (utilisation drifting 82 → 78 %) rather than absorbing them.
- Reverts are cheap and were used freely (`a7f100a`, the SVG schematic, the numpy GLB, the bore
  liners, the bore-bits fix). Building the alternative to *look at* is fine; assuming it will be
  kept is not.
- When a fix is reverted **on purpose**, record it so it isn't "re-fixed" later — the magnet-ring
  bore bits were deliberately kept.

---

## Source index

- `gridded_ion/build_thruster.py` — parametric source; its comment blocks record several fix rationales
- `gridded_ion/gridded_ion_devlog.html` — 30 narrative chapters, Jul 1–9 (ch. 10–14 are the CAD arc)
- Git log for `gridded_ion/` — 60+ commits, Jul 1–24; commit bodies carry the detailed diagnoses
- Memory: `gridded-ion-cad-rebuild`, `gridded-ion-feedthrough-not-intersecting` (the long one),
  `gridded-ion-transparent-section-veiling`, `gridded-ion-overlay-canvas-specificity`,
  `verify-webgl-applet-headless`, `verify-applet-physics-numerically`
