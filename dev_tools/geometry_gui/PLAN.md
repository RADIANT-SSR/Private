# RADIANT Geometry GUI — Master Plan

**Owner:** Jason Forsyth
**Status:** Draft v1, 2026-04-26
**Scope:** developer-only diagnostic tool; not the production GUI

---

## 1. Goal

A standalone interactive 3D viewer that lets a developer drag sliders for every geometric
parameter RADIANT consumes — observer altitude/look-angle/attitude, target altitude/shape/size/orientation,
sun zenith/azimuth, regime selector, sensor focal length & pixel pitch — and watch the
scene update in real time. The viewer must:

1. Render observer, Earth, target, target body axes, sun direction, and a background marker
   in a rotatable 3D scene (not necessarily to scale).
2. Compute and display the **projected target area used by the radiometry** by calling
   `TargetShape.projected_area(view_direction)` directly, so the displayed value is the value.
3. Toggle between **extended** and **sub-pixel** target regimes, plus an `auto` mode that
   shows which Rule-10 branch fired.
4. For sub-pixel: shape selector with size/orientation controls per shape
   (Sphere, Cylinder, FlatPlate, Box, Cone — matching `radiant.source.shapes`).
5. Show derived geometry (slant range, ground range, GSD, IFOV, angular extent, fill fraction)
   with units on every value.

## 2. Non-goals

- Not a production GUI. Not part of `radiant.api` or `radiant.cli`.
- No radiance / SNR / NEDT computation. Geometry only — but the projected-area handoff
  to radiometry is the one numeric link we surface.
- No scenario YAML loading in v1. Sliders only.
- No persistence (save/load) in v1.

## 3. Hard constraints

| # | Rule | Enforcement |
|---|------|-------------|
| C1 | Zero edits to `/src/`. | CI check: `git diff --name-only | grep -q '^src/' && exit 1` in Phase 7. |
| C2 | All code lives under `dev_tools/geometry_gui/app/`. Tests under `dev_tools/geometry_gui/tests/`. | Convention; reviewed at end of each phase. |
| C3 | Projected area shown on screen comes from `TargetShape.projected_area(...)` — no re-derivation. | Phase 5 acceptance test. |
| C4 | Units on every numeric label (Jason's hard rule). | Snapshot test of the readout panel in Phase 5. |
| C5 | Rule 19 (one computation, one module) applies to GUI code. | Reviewer check each phase. |
| C6 | No private `/src` symbols (anything starting with `_`). Re-implement small math (regime classifier) in the view-model layer if needed. | Grep check in Phase 1 acceptance. |

## 4. Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Dash browser front-end (plotly figure + dcc.Slider widgets) │
└─────────────────────────┬────────────────────────────────────┘
                          │ user inputs
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  app/state.py   — SceneState dataclass (frozen)              │
│                   one field per slider value                 │
└─────────────────────────┬────────────────────────────────────┘
                          │ build()
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  app/view_model.py  — pure functions that take SceneState   │
│   - build_observer_geometry()                                │
│   - build_target_shape()                                     │
│   - compute_view_direction()                                 │
│   - classify_regime()                                        │
│   - projected_area()  ← calls shape.projected_area(...)      │
│  Imports ONLY from radiant.core.* and radiant.source.shapes  │
└─────────────────────────┬────────────────────────────────────┘
                          │ derived values
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  app/scene_builder.py — turns view-model into plotly meshes  │
│   - earth_mesh()       (one file)                            │
│   - observer_marker()  (one file)                            │
│   - target_mesh()      (one file per shape, dispatched)      │
│   - sun_arrow()                                              │
│   - body_axes()                                              │
│   Output: list[plotly.graph_objects.Trace]                  │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│  app/main.py — Dash app: layout, callbacks, run_server()     │
└──────────────────────────────────────────────────────────────┘
```

Data flow is one-way (state → view-model → scene). No mutation. No callbacks that mutate state.

## 5. Tech stack — committed choice

**Plotly Dash + plotly.graph_objects.Mesh3d / Scatter3d.**

| Why | |
|-----|---|
| Browser-based: no native window deps, runs over SSH with port-forward, easy to share. | |
| `dcc.Slider` widgets are first-class; layout is pure Python. | |
| 3D rotation/zoom/pan come free with `plotly.graph_objects.Figure`. | |
| Pip-installable: `pip install dash plotly numpy`. No VTK, no Qt. | |
| Plotly `Mesh3d` handles arbitrary triangle meshes — sufficient for sphere, cylinder, plate, box, cone. | |

Alternatives considered and rejected: PyVista+Qt (heavy VTK dep), matplotlib mpl_toolkits (poor 3D quality),
ipywidgets in Jupyter (not standalone enough for a developer tool).

## 6. Slider inventory (exhaustive — matches the prompts)

### Observer
| Slider | Range | Units | RADIANT param / class field |
|---|---|---|---|
| altitude | 100 – 36 000 | km | `ObserverGeometry.altitude_m` |
| look_angle | 0 – 60 | deg | `ObserverGeometry.look_angle_rad` |
| yaw / pitch / roll | -30 – 30 | deg | `ObserverGeometry.yaw_rad/pitch_rad/roll_rad` |

### Target
| Slider | Range | Units | Field |
|---|---|---|---|
| altitude (above sea level) | 0 – 5 | km | `TargetGeometry.altitude_m` |
| shape (dropdown) | enum | — | `source.target.shape` |
| shape sizes (radius / length / width / height / base_radius) | 0.01 – 100 | m | `source.target.shape_*_m` |
| yaw / pitch / roll | -180 – 180 | deg | `source.target.shape_yaw_rad` etc. |
| fill_fraction | 0.001 – 1.0 | — | `source.target.fill_fraction` |

### Sun
| Slider | Range | Units | Field |
|---|---|---|---|
| solar_zenith (`theta_s`) | 0 – 180 | deg | `LineOfSightGeometry.theta_s` |
| relative_azimuth (`delta_phi`) | -180 – 180 | deg | `LineOfSightGeometry.delta_phi` |

### Sensor (drives IFOV / GSD / regime)
| Slider | Range | Units | Field |
|---|---|---|---|
| focal_length | 0.1 – 10 | m | `optics.focal_length_m` |
| pixel_pitch | 1 – 50 | µm | `detector.pixel_pitch_m` |

### Mode toggles
- Regime override: `auto` / `extended` / `sub_pixel` / `point_source` (radio)
- Background type: `none` / `cold_space` / `ground` / `at_aperture` (radio — visual only in v1)

## 7. Readout panel (one text block, units on every line)

```
Slant range         : 824.6 km
Ground range        : 412.3 km
GSD                 : 5.20 m
IFOV                : 5.20 µrad   (1.07 arcsec)
Angular extent      : 12.1 µrad
Fill fraction       : 1.000 (computed)
Pixel area on ground: 27.04 m²
Projected area A_t  : 12.57 m²    ← from shape.projected_area(view_dir)
Regime (auto)       : SUB_PIXEL    [reason: 0.25*ifov < ang_ext < 2*ifov]
Solar zenith θ_s    : 35.0°
Relative azimuth Δφ : 12.0°
```

## 8. Caveats / known gaps (do not patch in this tool)

| # | Gap | Workaround |
|---|---|---|
| G1 | `theta_s` / `delta_phi` are not in the legacy parameter schema yet (Stage-2 placeholder per `_inferrer.py`). | GUI carries its own sun sliders and constructs `LineOfSightGeometry` directly in the view-model. |
| G2 | `_classify_regime` is private. | View-model re-implements the four-line decision (Rule 10) — math, not API. Documented in `view_model.py` docstring. |
| G3 | `shape_factory.build_shape(params)` requires a `ParameterSet` with a registered schema. | View-model bypasses this and instantiates shape classes directly (`Sphere(...)`, `FlatPlate(...)`, …). |
| G4 | Background descriptors require `SpectralData` to be meaningful. | v1 shows background only as a colored marker (cold-space / ground / off). No spectral content. |
| G5 | `view_direction` for `projected_area` is a body-frame unit vector target→observer. | View-model computes this in scene frame from observer & target geometry, then converts using the shape's own orientation via `radiant.source.shapes._helpers.view_to_body` (note: `_helpers` is private — re-implement the 4-line ZYX-transpose locally instead). |

## 9. Phase plan (each phase = one prompt file)

| Phase | File | Output | Acceptance |
|---|---|---|---|
| 0 | `phase_0_scaffold.md` | `app/__init__.py`, `app/main.py` stub, `tests/__init__.py`, `requirements.txt`, smoke test that imports `radiant.core.geometry`. | `python -m dev_tools.geometry_gui.app.main` opens an empty Dash page. |
| 1 | `phase_1_view_model.md` | `app/state.py`, `app/view_model.py` (pure functions, no plotly). | Unit tests cover regime classifier truth table + projected-area parity vs. direct shape call. |
| 2 | `phase_2_scene_builder.md` | `app/scene_builder/` with one file per primitive (Rule 19). | Static screenshot test: render fixed `SceneState` → PNG matches golden. |
| 3 | `phase_3_controls.md` | Slider panel + Dash callbacks wiring state → figure. | Manual: every slider visibly moves something. |
| 4 | `phase_4_regime_and_shape.md` | Shape dropdown swaps target mesh; regime override radio; readout shows which Rule-10 branch fired. | Test: each shape dropdown choice produces a valid `TargetShape` instance and a non-empty mesh. |
| 5 | `phase_5_projected_area.md` | Projected-area readout calls `shape.projected_area(view_dir)` and renders the projected silhouette as a translucent disk for visual confirmation. | Test: GUI's reported A_t equals `shape.projected_area(view_dir)` to machine precision across 50 random states. |
| 6 | `phase_6_sun_and_background.md` | Sun arrow, background marker (cold-space / ground / at-aperture), terminator hint on Earth sphere. | Manual: sun zenith=0 puts arrow over target; zenith=90° puts it on horizon. |
| 7 | `phase_7_polish.md` | README run instructions, screenshot, CI check that no `/src` files were modified across the whole tool's history. | `git log --all -- 'src/**' | wc -l` unchanged from baseline. |

## 10. Out-of-scope follow-ons (file as separate ideas, not in this plan)

- Loading a real scenario YAML and snapping all sliders to its values.
- Showing the PSF, MTF product, or pupil — those are dual-path optical state, not geometry.
- Multi-target / constellation views.
- Saving a session to disk.

---

## 11. Phase 8–10 — Target-centric redesign (added 2026-04-26)

### Motivation
Phases 0–7 produced a scene-accurate view: Earth fills the figure, target is a tiny
dot at altitude, observer is far above. This is geometrically faithful but
**diagnostically useless** — at true scale (550 km observer + 1 m target +
6378 km Earth), the target occupies <1% of the visible area and the observation /
sun vectors are barely distinguishable. A developer cannot read off α_t,
θ_sun,B, or the off-nadir angle by inspection.

The 2D reference diagram Jason supplied (satellite at 550 km, target at 50 km,
Sun, background point B, with α_t / θ_sun,B / n_B labeled) is the target idiom.
We want a **3D version of that diagram**: target as the visual anchor (~30–50%
of view), observer/sun as labeled glyphs at illustrative (not metric) distances
along their **true angular directions**, ground rendered as a curved cap (not a
full sphere), and every relevant angle drawn as an arc with a units-bearing
text label.

This is a **redesign of the rendering layer**, not the physics. View-model,
state, and the C3 invariant are untouched.

### New hard constraint
| # | Rule | Enforcement |
|---|------|-------------|
| C7 | Distances in the rendered scene are **illustrative**, not metric. Angles remain physical and exact. The readout panel must say so explicitly. | Phase 8 acceptance: a `Distances illustrative; angles physical` row in the readout. |

### Architecture delta

`app/scene_builder/` gains the modules below. Each is its own file (Rule 19 / C5).
Existing `earth_mesh.py` is replaced by `ground_patch.py`. `target_mesh.py`,
`observer_marker.py`, `sun_arrow.py`, `background_marker.py`, `body_axes.py`
remain — but with rescaled display sizes.

| New module | Job |
|---|---|
| `ground_patch.py` | Curved Earth cap below the target, sized to fit the camera frustum. Replaces `earth_mesh.py` at the call site. |
| `boresight_ray.py` | Purple ray observer→target with a small `o` label. |
| `nadir_reference.py` | Faint dashed line from observer straight down (local nadir). |
| `off_nadir_arc.py` | Arc between boresight and nadir at observer, labeled with the off-nadir angle in degrees. |
| `sun_ray_target.py` | Solid orange ray target→sun, labeled `s_t`. |
| `sun_ray_background.py` | Dashed orange ray background-point→sun, labeled `s_B`. |
| `phase_angle_arc.py` | Arc at target between `−o` and `s_t`, labeled `α_t = …°`. |
| `solar_zenith_arc.py` | Arc at background point B between `n_B` and `s_B`, labeled `θ_sun,B = …°`. |
| `surface_normal_arrow.py` | Short arrow at B along `n_B`. |
| `observer_glyph.py` | Replaces the bare scatter point — small box-and-label "Satellite, h_obs km". |
| `sun_glyph.py` | Sun marker at the end of `s_t`, sized to be visible. |
| `background_point.py` | Marker at B (the boresight–ground intersection) so the `n_B` arrow and `θ_sun,B` arc have an anchor. |

### Display-coordinate convention (frozen)
| Quantity | Value | Why |
|---|---|---|
| `TARGET_DISPLAY_RADIUS` | bumped from `0.04` to `1.0` | target becomes the anchor object. |
| `OBSERVER_DISPLAY_DISTANCE` | `4.0` | far enough to read the off-nadir arc, close enough to see the satellite glyph. |
| `SUN_DISPLAY_DISTANCE` | `6.0` | beyond observer; sun glyph must not overlap the satellite. |
| `BACKGROUND_DISPLAY_DISTANCE_BELOW_TARGET` | `1.5` | B sits along the boresight, on the ground patch. |
| `GROUND_PATCH_HALF_EXTENT` | `2.5` | curved cap, just-visible curvature. |
| `ARC_DISPLAY_RADIUS` | `0.4` | every angle arc uses one consistent radius for visual unity. |

True observer altitude, target altitude, and the actual physical distances are
**recorded in glyph labels** ("Satellite, 550 km alt" etc.) — they are no longer
encoded by position in the scene. This is the C7 trade.

### Phase plan

| Phase | File | Output | Acceptance |
|---|---|---|---|
| 8 | `phase_8_target_centric_layout.md` | `ground_patch.py`, rescaled `target_mesh.py`, `observer_glyph.py`, `sun_glyph.py`, `background_point.py`. `build_scene.py` rewritten to compose them at the new display constants. Old `earth_mesh.py` deleted (C1: never touched `/src`, only its own `dev_tools/` files). Readout panel grows the `Distances illustrative; angles physical` row. | Manual: target fills ≥30% of viewport; observer + sun + ground all simultaneously visible. Existing C3 invariant test (`test_projected_area_invariant.py`) still passes — the redesign does not touch the view-model. Phase-2 goldens regenerated. |
| 9 | `phase_9_geometry_annotations.md` | `boresight_ray.py`, `nadir_reference.py`, `off_nadir_arc.py`, `sun_ray_target.py`, `sun_ray_background.py`, `surface_normal_arrow.py`, `phase_angle_arc.py`, `solar_zenith_arc.py`. Each emits its own arc/ray traces and a Scatter3d text label with units. | Tests per module: arc swept angle equals the labeled angle to machine precision; label string contains the unit token (`°`); 50-seed parametric test for α_t and θ_sun,B against direct dot-product computation. |
| 10 | `phase_10_angle_groups_and_projections.md` | (0) scrollwheel zoom; (a) **multi-select** angle-group checklist (six independent toggles incl. world-axes triad and projections); (b) az/el decomposition modules; (c) sun zenith/azimuth arc modules; (d) angle-projection traces. Gallery + README updated. | Per-group toggle test (each toggle independently adds/removes exactly its declared traces). Empty selection yields zero arc/ray/triad traces. Az/el sum-to-pointing test: reconstructed boresight from az + el equals the original boresight to 1e-12. Projection-plane test: each projected arc lies in its declared plane to machine precision. World-axes triad test: three orthogonal unit-length lines along ±X/±Y/±Z. Visual review of new gallery. Full test suite green. C1 gate still green. |

### Phase 10 detail (pivot from earlier "polish + gallery" draft)

**(0) Scrollwheel zoom.** `dcc.Graph(config={...})` updated to enable
`scrollZoom: True` and `doubleClick: "reset"` so the developer can dolly into
the target with the mouse wheel and return to the default framing with a
double-click. No state, no callback — pure client-side plotly behavior. Done
in this PR alongside the rest of Phase 10.



User feedback after Phase 9: scene is busy (28 traces), the 3D angles need
clearer mental projection onto reference planes, the master Cartesian frame
should be plottable on demand, and groups must be **independently togglable**
(not mutually exclusive). Phase 10 splits into the pieces below.

**(a) Angle-group multi-select.** New `dcc.Checklist` (not RadioItems) in the
controls panel — each toggle is independent, any combination is legal, the
empty selection is legal and yields the bare geometry. Six toggles:

| Toggle key | Members | Anchor | Default |
|---|---|---|---|
| `world_axes` | Master Cartesian X / Y / Z triad with tick labels | scene origin | off |
| `observer` | off-nadir θ_look arc, azimuth arc, elevation arc, nadir reference line | observer | on |
| `target` | phase-angle arc α_t, view-direction ray `−o`, sun ray `s_t` | target | on |
| `background` | n_B normal arrow, sun ray `s_B`, solar-zenith arc θ_sun,B | background point B | on |
| `sun` | sun-zenith arc θ_s (from +Z at target), sun-azimuth arc Δφ (from +X on XY) | target / scene origin | off |
| `projections` | dashed companion arcs on reference planes (off-nadir XZ, α_t tangent, θ_sun,B ground) | per-arc | off |

Grouping rationale: one toggle per **anchor location** plus one global helper
(world axes) and one global modifier (projections). Mixing anchors in one
group is what made the old "all" view feel busy, so the eye now has a stable
expectation: turn on `target` ⇒ angles measured *at* the target.
`projections` is its own peer toggle (not a sub-flag of each group) because
the developer may want a projection without its parent arc and vice-versa.

Wired by extending the existing single Dash callback with one new Input
(`angle-groups`, `Checklist.value`) and routing the resulting `frozenset[str]`
through `build_scene(state, *, angle_groups=...)`. No new state field — the
checklist is a pure rendering filter, so `SceneState` is untouched (preserves
the "no new state" line below).

**(b) Az/el decomposition.** Two new Rule-19 modules. Both consume the
existing `boresight_unit_display(state)`; no view-model additions. Tests
verify az + el reconstructs the boresight to machine precision.

| New module | Job |
|---|---|
| `azimuth_arc.py` | Project boresight onto the local horizontal plane (XY at target). Arc from +X (along-track reference) to that projection. Label `az = …°`. |
| `elevation_arc.py` | Arc from horizontal projection up to the boresight itself. Label `el = …°`. (Complement of off-nadir for the canonical observer-in-XZ case; distinct when the observer is rolled out of XZ.) |

**(c) Sun-direction decomposition.** Two new Rule-19 modules consuming the
existing `sun_unit_vector_scene(state)` output:

| New module | Job |
|---|---|
| `sun_zenith_arc.py` | Arc at the target between +Z and the sun direction. Label `θ_s = …°`. |
| `sun_azimuth_arc.py` | Arc at the scene origin on the XY plane between +X and the XY-projection of the sun direction. Label `Δφ = …°`. |

**(d) World-axes triad.** New Rule-19 module `world_axes_triad.py` emits three
unit-length scatter lines from the scene origin along +X, +Y, +Z with single
text labels at each tip. Off by default. Provides a master-frame reference
without competing with the body-frame target axes (which sit at the target,
not the origin).

**(e) Angle projections.** For each 3D arc that lives in a non-axis-aligned
plane, draw a faint dashed companion arc projected onto the nearest reference
plane. One module per projection (Rule 19):

| New module | Projection plane |
|---|---|
| `off_nadir_projection.py` | XZ plane at observer (already in-plane for canonical observer; module no-ops then) |
| `phase_angle_projection.py` | tangent plane at target normal to the local zenith |
| `solar_zenith_projection.py` | tangent plane at B normal to n_B (i.e., the ground plane there) |

Projections render as low-opacity dashed arcs in the same color as the parent
arc, so the eye can read "this 3D arc shadows that 2D arc on this plane".
Gated by the `projections` toggle, independent of their parent group.

### What does NOT change in Phases 8–10
- `app/state.py` — no new state fields. The angle-group selector is a pure
  rendering filter, not a state property.
- `app/view_model.py` — no new physics. `α_t` and `θ_sun,B` are computed from
  the existing `compute_view_direction_scene` and `sun_unit_vector_scene`
  outputs (one-line each, both purely derived). Az/el are derived from
  `boresight_unit_display` in the scene-builder layer.
- C1 (no /src writes), C3 (projected-area invariant), C4 (units on outputs),
  C5 (Rule 19), C6 (no private symbols) — all still hold.
- The existing test suite — every Phase 0–9 test must still pass after Phase 10.

---

## 12. Phase 11 — Visual polish + readout integration (added 2026-04-26)

### Motivation
Phase 10 made the scene fully togglable, but with the default groups on
the rendering still reads as "rough":
  * arcs at one shared radius pile up at the same anchor;
  * labels include `= …°` which collides at the target/B and
    duplicates information already in the readout panel;
  * arc colors are nine unrelated picks rather than a coherent palette;
  * the camera is hard-coded so off-axis configurations push elements
    out of frame;
  * the new az/el/θ_s/Δφ values are not surfaced numerically anywhere.

User feedback (2026-04-26): "looking closer but still rough" → polish track.

### Phase 11 acceptance overview

| Phase | File | Output | Acceptance |
|---|---|---|---|
| 11 | `phase_11_visual_polish.md` | (a) per-group concentric arc radii; (b) symbol-only labels with real Unicode subscripts; (c) anchor-keyed color palette; (d) camera auto-frame from base-scene bbox; (e) readout rows for az/el/θ_s/Δφ; (f) empty-selection caption; (g) verify checklist persistence under slider drags; (h) Phase-10 CU sweep. | Per-radius test (each group's arcs sit at its declared radius). Label-content test (no numeric value in any arc label; subscript chars match the canonical mapping). Color-palette test (one palette constant per anchor, every arc reads from it). Auto-frame test (camera eye scales with base-scene bbox; default camera unchanged for a default state). Readout test: each new row carries a unit token. Empty-selection caption visible when `angle-groups == []`. CU log gains entries for the duplicate-name issue + any others surfaced. |

### Phase 11 detail

**(a) Per-group concentric arc radii.** Replace the single
`ARC_DISPLAY_RADIUS` with a per-group lookup so arcs nest concentrically
at each anchor and do not visually overlap:

| Group | Arc radius |
|---|---|
| observer (off-nadir, az, el) | 0.40 |
| target (α_t) | 0.60 |
| sun (θ_s, Δφ) | 0.80 |
| background (θ_sun,B) | 0.45 (single arc; smaller cap) |

Each arc module reads its radius from a new `_arc_radii.py` constant
table; `arc_points()` already accepts a `radius` argument. No new math.

**(b) Symbol-only labels with Unicode subscripts.** Drop `= …°` from every
arc text label. Numeric values stay in the trace `name` (legend / hover
text) so the readout is still inspectable, but the on-figure text is
just the symbol. Use Unicode subscript characters where the block
supports the letters (`₀–₉`, `ₐ ₑ ₕ ᵢ ⱼ ₖ ₗ ₘ ₙ ₒ ₚ ᵣ ₛ ₜ ᵤ ᵥ ₓ`); fall
back to a plain underscore form when the subscript glyph does not exist:

| Arc | On-figure label | Trace name (still has the value) |
|---|---|---|
| off-nadir | `θ_off` | `off-nadir = …°` |
| azimuth | `az` | `az = …°` |
| elevation | `el` | `el = …°` |
| phase angle | `αₜ` | `alpha_t = …°` |
| solar zenith at B | `θ_sun,B` (no Unicode glyph for capital B) | `theta_sun_B = …°` |
| sun zenith at target | `θₛ` | `theta_s = …°` |
| sun azimuth | `Δφ` | `delta_phi = …°` |
| world axes | `X`, `Y`, `Z` | unchanged |

Each Unicode mapping is pinned by a canonical-mapping test so a future
edit cannot silently break the rendering.

**(c) Anchor-keyed color palette.** A new `_arc_palette.py` constant
table assigns colors by anchor location, not by arbitrary per-module
choice. Every arc module reads its color from this table:

| Anchor | Hex | Used by |
|---|---|---|
| observer-blue | `#1f4ea8` | nadir reference, off-nadir, az, el |
| target-red | `#a83030` | α_t, view-direction ray |
| background-brown | `#7a3a1a` | n_B, s_B, θ_sun,B |
| sun-amber | `#c08020` | θ_s, Δφ |
| world-axes | per-axis red/green/blue (separate; visually distinct) | world axes triad |
| projections | parent's color, alpha 0.5 | every projection module |

Existing arc-module colors are removed; tests verify each arc reads
the table value, not a literal.

**(d) Camera auto-frame.** Replace the fixed `camera.eye=(1.8, 1.8, 1.4)`
with a small helper that computes the camera-eye distance from the
union bounding box of the always-on base-scene traces. Output: same
`camera` dict (Plotly schema preserved). For the default state the
helper must match today's framing within ε — verified by a fixed-state
test so user-visible defaults do not drift.

**(e) Readout rows for new angles.** `view_model.derived_readout` and
the readout-panel formatter gain rows for **az**, **el**, **θ_s**, **Δφ**
in degrees. C4 hard rule: every numeric row carries a unit token.
Test: each new key is present; each rendered string ends in `deg` (or
`°` consistently with the existing format).

**(f) Empty-selection caption.** When `angle-groups == []`, the
controls panel renders a small `(no annotations selected)` caption
beneath the checklist so the developer knows the empty scene is
deliberate. Implementation is one `html.Div` whose children flip via
the existing single Dash callback (which already sees the
`angle-groups` value).

**(g) Checklist persistence verification.** `dcc.Graph(uirevision="locked")`
preserves the camera; we need to verify that the **checklist value**
persists across slider drags as well. Test: simulate a sequence of
callback invocations with a non-default checklist value and assert the
checklist is read back correctly each call. If Dash already preserves
the user's selection (it should, since the callback receives the live
value as Input), the test exists as a regression guard. If not, we
introduce a `dcc.Store` to memoize.

**(h) Phase-10 CU sweep.** Per Rules 21/22, walk the Phase-10 diff for
latent issues that did not block landing but should be tracked. Known
candidates so far:
  * **Duplicate trace name** — `off-nadir = X°` is emitted twice (once
    per off-nadir arc trace, line + label). The label trace can keep
    `showlegend=False` and a distinct internal name. Same pattern in
    other arc modules.
  * **Ambiguous `θ_s` vs `θ_sun,B`** — same physics in flat-ground; the
    readout panel may want a one-line note explaining when they differ
    (oblique surfaces / ground-tilt extension).

Each becomes a CU entry in `docs/Cleanup_Backlog.md` before the
Phase-11 PR merges.

### What does NOT change in Phase 11
- `app/state.py` — still no new state fields.
- Physics — no view-model math changes; (e) only re-shapes derived
  outputs already computed.
- C1 (no /src writes), C3 (projected-area invariant), C4 (units),
  C5 (Rule 19), C6 (no private symbols) — all still hold.
- Phase 0–10 test suite — every existing test must still pass.

---

## 13. Phase 12 — Lift angle annotations clear of the shape geometry (added 2026-04-26)

### Motivation
Phase 11 made arcs symbol-only with per-group radii, but the radii are
still measured *from the physical vertex* (target center, B, observer
chip, sun chip). When the target shape is large or oriented obliquely,
the target-anchored arcs (α_t at the target, plus α_t's projection)
clip through the mesh — the user can't read the angle and can't see
the geometry underneath. The same risk lurks for any future scenario
that grows the observer/sun chip beyond its current display radius.

User feedback (2026-04-26): "I think all angle definitions and
orientations should be shown outside of the shape geometry."

### Phase 12 acceptance overview

| Phase | File | Output | Acceptance |
|---|---|---|---|
| 12 | `phase_12_anchor_offsets.md` | (a) per-anchor outward-offset table in `_arc_radii.py` (or a sibling `_arc_offsets.py`); (b) every arc module shifts its anchor along the outward radial direction by the offset before invoking `arc_points()`; (c) projection arcs stay at the parent's offset (so projection + parent remain visually coupled); (d) on-figure label placement re-derived from the offset anchor so labels float outside the mesh too; (e) leader line (thin, parent's color, alpha 0.5) from the *physical* vertex to the offset arc's geometric center, so the viewer can still see what each arc is measuring; (f) per-arc test asserting the arc anchor is offset from the physical vertex by exactly the table value along the outward direction; (g) golden re-spin for `scene_*.json` / `scene_*.png`. | Per-anchor offset table is the single source of truth (no module-local literals). Every existing arc test continues to pass after substituting the offset anchor (the swept angle and the directional unit vectors are unchanged). At the default state, the bounding box of every arc trace lies *outside* the target mesh's bounding box for the largest test shape (cone). The leader line is present and connects vertex → arc center within numerical tolerance. |

### Phase 12 detail

**(a) Per-anchor outward-offset table.** New constant table keyed by
the same anchor names the palette uses (`observer`, `target`,
`background`, `sun`). The offset is the *additional* clearance applied
to the anchor before the arc is drawn — it does not replace the arc
radius, which still controls the arc's own size:

| Anchor | Outward offset | Outward direction |
|---|---|---|
| observer | 0.0 (chip is small + already in clear space) | n/a |
| target | 1.6 × max(target shape half-extent) + 0.1 | unit vector along (vertex − target_center) — for arcs anchored at the target center this is the *bisector* of the arc's two direction vectors |
| background | 0.0 (B sits on the ground patch; arcs already point upward) | n/a |
| sun | 0.0 (sun chip is far from the rest of the scene) | n/a |

Only the target anchor needs a non-zero offset today. The table form
exists so the four other anchors can be tuned without code changes if
a future scenario grows them.

**Outward direction for the target anchor.** When the arc is centered
at the target center (α_t and the off-nadir-style arcs would fall
into this bucket if any were target-centered — currently α_t is the
only one), the natural "outward" direction is the bisector of the
arc's two unit-direction vectors `(u1 + u2) / |u1 + u2|`. The arc is
offset *from the target center* along that bisector by the table
value. Result: the arc floats outside the mesh on the side the angle
is opening into, which is exactly where the eye expects to find it.

**(b) Apply the offset before `arc_points()`.** Each arc module today
calls `arc_points(anchor, u1, u2, radius=arc_radius_for(...))`. The
new flow:

```python
shifted = anchor + offset_for("target") * bisector(u1, u2)
xs, ys, zs, swept = arc_points(shifted, u1, u2, radius=arc_radius_for(...))
```

`arc_points()` itself does not change — it still draws an arc of the
given radius around whatever anchor it's handed. The offset is purely
a caller-side decision, which keeps the helper trivial and Rule-19
clean.

**(c) Projection arcs follow their parent.** Each projection module
(`off_nadir_projection.py`, `phase_angle_projection.py`,
`solar_zenith_projection.py`) already shares the parent arc's anchor
and color. After Phase 12 the projection module reads the *same*
shifted anchor, so the dotted projection sits next to its parent arc
rather than next to the physical vertex. This preserves the visual
coupling that Phase 11 introduced.

**(d) Label placement.** The label-text trace today places the label
at `anchor + radius * bisector + small_offset_along_bisector`. After
Phase 12 the same formula uses the *shifted* anchor. No new math.

**(e) Leader line.** Thin (`width=1`) line from the physical vertex
to the shifted anchor's geometric center, in the parent's palette
color at alpha 0.5 (same alpha used by Phase-11 projections). This
is the diagnostic affordance that tells the viewer "this arc, way
over here, is measuring an angle at *that* vertex over there."
Implemented as one new helper `arc_leader_line_traces(vertex,
shifted_anchor, color)` returning a single Scatter3d, called by
each arc module that uses a non-zero offset. Skipped entirely when
the offset is zero (no leader needed).

**(f) Tests.** New test file `test_phase12_anchor_offsets.py`:
  * **offset-table-is-source-of-truth** — every arc module's anchor
    after offset application equals `physical_vertex + offset *
    bisector` to machine precision.
  * **arc-outside-target-mesh** — for the default state with the
    cone target (largest mesh), the bounding box of every
    target-anchored arc trace has no overlap with the cone mesh's
    bounding box.
  * **leader-line-endpoints** — each arc with non-zero offset emits
    one leader-line Scatter3d whose endpoints are the physical
    vertex and the arc's geometric center.
  * **no-offset-no-leader** — observer/background/sun arcs (offset
    = 0) emit zero leader-line traces.
  * **swept-angle-unchanged** — the swept angle returned by every
    arc helper is identical (machine precision) before and after
    the offset shift, since `arc_points()` only sees a translated
    anchor.

**(g) Golden re-spin.** `scene_{sphere,cylinder,flat_plate,box,
cone}.{json,png}` regenerated via the existing
`tests/dev_render_goldens.py` after the offset code lands.

### CU candidates surfaced by Phase 12 (file at PR-merge time per R21/R22)

  * If the cone-shape half-extent computation requires a new helper
    on `state.py`, that helper itself becomes a Rule-19 candidate
    (one computation per file). Either land it in a sibling module
    or note it as a CU.
  * The bisector formula degenerates when `u1` and `u2` are
    anti-parallel (180° arc). All arcs we currently render are
    strictly < 180°, but a future fully-back-illuminated phase angle
    (`α_t = 180°`) would trip this. File a CU describing the
    degeneracy and either guard at the helper or document the
    constraint.

### What does NOT change in Phase 12
- `app/state.py` — no new state fields. Target half-extent is computed
  on demand from existing size sliders.
- Physics — no view-model math changes. The arc helpers, the angle
  decompositions, and the readout panel all see identical inputs.
- The arc *radii* (Phase-11 `_arc_radii.py`) — unchanged. Phase 12
  only translates the anchor; the arc itself is the same size.
- C1 (no /src writes), C3 (projected-area invariant), C4 (units),
  C5 (Rule 19), C6 (no private symbols) — all still hold.
- Phase 0–11 test suite — every existing test must still pass after
  the offset substitution (sweeps and decomposition values unchanged).

---

## 14. Phase 13 — Label-management system: leader lines, slot layout, no overlaps (added 2026-04-26)

### Motivation
Phase 12 lifted the *arcs* off the target mesh, but labels are still
emitted as `Scatter3d(mode="text")` traces anchored at a 3D point in
the arc. Plotly renders 3D text with no pixel-level layout: when two
labels share roughly the same world-space position (and the target is
the densest cluster — α_t at target, θ_sun,B at B which is near-target,
n_B, s_B, az, el plus the body-axis tip labels), they all get
projected to nearly the same screen pixel and stack into an unreadable
glyph soup. Every Phase-12 screenshot shows this — `α_t = 70.0°`
glyph-collides with neighbors and the body-axis labels.

User feedback (2026-04-26):

> every screenshot has the same defect: at the target location, the
> labels α_t, θ_sun,B, n_B, s_B, az, el, and the body axes all stack
> on top of each other and become unreadable… Fix this with a proper
> label-management system before doing anything else, because no
> other improvement will be visible until labels stop overlapping.

User requirements (verbatim):
1. **Leader lines.** Labels render in screen-space at a fixed pixel
   offset from their anchor, connected by a thin 1px line. Labels
   never overlap the geometry.
2. **Force-directed OR angular distribution** (~80px screen-space
   circle around the target) so labels fan out instead of stacking.
3. **Collapsible label clusters.** Default: show only the angle group
   the user is currently editing; others render as faded numeric chips
   that expand on hover.
4. **Subtle white halo / text-stroke** (2px, 80% opacity background).
5. **Hard invariant:** never render two labels at the same
   screen-space pixel — verified in tests.

### Phase 13 acceptance overview

| Phase | File | Output | Acceptance |
|---|---|---|---|
| 13 | `phase_13_label_layout.md` | (a) per-label-key slot table in new `_label_layout.py` mapping `label_key → (xshift_px, yshift_px, slot_index)`; (b) every arc module ships a `<arc>_label_annotation(...)` constructor returning a single `plotly.graph_objs.layout.scene.Annotation`-compatible dict (or `None` when its arc is suppressed) and *no longer* emits a `Scatter3d(mode="text")` label trace; (c) new orchestrator `build_annotations.py` that reads a `SceneState` plus the same active angle-group filter `build_scene` already takes, calls each module's `<arc>_label_annotation()`, and returns `list[dict]`; (d) `main.py` figure construction passes the result into `fig.update_layout(scene=dict(annotations=…))`; (e) every annotation uses the slot-table `xshift`/`yshift` (~80 px circle around the target) for fan-out, `bgcolor='rgba(255,255,255,0.8)'` + `bordercolor` matching the parent arc + `borderpad=2` for the white halo, and `showarrow=True` with `arrowwidth=1` for the leader line; (f) `test_phase13_label_layout.py` hard-asserts the pixel-distinctness invariant (no two slots resolve to the same `(xshift, yshift)` pair within a 12-px tolerance circle) plus per-arc construction tests; (g) golden re-spin for `scene_*.json` / `scene_*.png`. | The slot table is the single source of truth for label fan-out. Every arc module that previously emitted a label-text Scatter3d now emits exactly one annotation entry instead and zero text traces. The pixel-distinctness invariant test passes for every active-angle-group combination the GUI exposes. Visually: at the default state, no two labels share the same screen rectangle in any of the five golden screenshots. |

### Phase 13 detail

**(a) Per-label-key slot table.** New module
`app/scene_builder/_label_layout.py` (Rule 19 — own file). Single
source of truth, keyed by *label* identifier (one slot per visible
arc/axis label, not per anchor — anchors host multiple labels):

```python
LABEL_SLOT_RADIUS_PX: Final[float] = 80.0  # screen-space circle radius

# (slot_index, friendly_name) — slot_index ∈ [0, N) is converted to
# (xshift_px, yshift_px) by `slot_offset(slot_index, N)` below using
# evenly-spaced angles around an 80 px circle. Order is fixed so a
# label's slot is deterministic across renders.
LABEL_SLOTS: Final[tuple[str, ...]] = (
    "off_nadir",       # θ_look at observer
    "azimuth",         # az at observer
    "elevation",       # el at observer
    "phase_angle",     # α_t at target
    "sun_zenith_at_t", # θ_s at target
    "sun_azimuth",     # Δφ at target
    "solar_zenith_b",  # θ_sun,B at background point B
    "surface_normal",  # n_B label at B
    "body_axis_x",     # body-axis tip labels (x_b, y_b, z_b)
    "body_axis_y",
    "body_axis_z",
    "world_axis_x",    # world-axis triad tip labels
    "world_axis_y",
    "world_axis_z",
)

def slot_offset(label_key: str) -> tuple[float, float]:
    """Return (xshift_px, yshift_px) for `label_key` on the 80 px circle."""
```

The mapping function distributes the N slots evenly around the 80 px
circle, but with a stable seeded ordering so two labels that *could*
share the same anchor (e.g., α_t and θ_s,t both anchored at target)
land on opposite sides of the circle. Slot indices are reserved at
table-definition time, not computed dynamically — that is what makes
the pixel-distinctness invariant testable as a pure unit assertion.

**(b) Per-arc-module annotation builders.** Each arc module currently
returns a list of `Scatter3d` traces, one of which is a `mode="text"`
label. After Phase 13:

  * `<arc>_traces(...)` returns *only* the geometry traces (the arc,
    the leader line from Phase 12) — the text-mode Scatter3d is
    removed entirely.
  * New sibling function in the same file:
    `<arc>_label_annotation(...) -> dict | None`
    returns a plotly scene-annotation dict ready to drop into
    `layout.scene.annotations`, or `None` when the arc is suppressed
    (e.g., zero swept angle, antiparallel inputs).

The annotation dict shape:

```python
{
    "x": <world-x of label anchor>,
    "y": <world-y>,
    "z": <world-z>,
    "text": "α_t = 70.0°",            # same string the trace used to carry
    "showarrow": True,
    "arrowhead": 0,                   # plain line, not arrowhead
    "arrowwidth": 1,
    "arrowcolor": <arc palette color>,
    "ax": <xshift_px from slot_offset>,
    "ay": <yshift_px from slot_offset>,
    "xanchor": "left",                # or "right" depending on slot quadrant
    "yanchor": "middle",
    "bgcolor": "rgba(255,255,255,0.8)",
    "bordercolor": <arc palette color>,
    "borderpad": 2,
    "borderwidth": 1,
    "font": {"size": 12, "color": <arc palette color>},
    "captureevents": False,
}
```

`xanchor` is selected by the slot-offset quadrant (right-side slots →
`"left"`, left-side slots → `"right"`) so the leader line points
*toward* the anchor and the label text reads outward. This is
deterministic from the slot index.

**(c) `build_annotations.py` orchestrator.** New module that mirrors
`build_scene.py`'s structure: takes `SceneState` + the same
`angle_groups` set, walks the same group-conditional branches, and
calls each `<arc>_label_annotation()`. Returns `list[dict]` (empty
when no group is active). This preserves Rule 19 — composition lives
in its own file rather than swelling `build_scene.py`.

```python
def build_annotations(
    state: SceneState,
    *,
    angle_groups: frozenset[str] | None = None,
    # … (same precomputed inputs build_scene currently takes) …
) -> list[dict]:
    ...
```

The orchestrator drops `None` returns and also drops body-/world-axis
annotations when the corresponding group is hidden. The "currently
editing" cluster (user requirement #3) is encoded by callers passing a
narrower `angle_groups` set — no separate "active group" parameter.

**(d) Figure wiring in `main.py`.** Today the figure layout is built
once with `traces` only. Phase 13 changes the build to:

```python
traces = build_scene(state, angle_groups=groups, …)
annotations = build_annotations(state, angle_groups=groups, …)
fig = go.Figure(data=traces)
fig.update_layout(scene=dict(annotations=annotations, …existing scene options…))
```

`build_scene`'s signature and return type are unchanged — labels are
simply *removed* from its traces. This keeps every existing
`build_scene` callsite valid.

**(e) Faded-chip "hover-expand" mode (user requirement #3).**
Deferred to a future phase. The current Phase-10 angle-group checklist
already gives the user the same control granularity as the
"currently editing → others faded" mode the user described, and it
ships immediately without a hover-state interaction model. The slot
table is the precondition for any future faded-chip mode, so Phase 13
unblocks it without implementing it.

**(f) Pixel-distinctness invariant test (user requirement #5).**
`test_phase13_label_layout.py` asserts as a *pure* unit test (no
plotly figure construction needed):

  * **slot-uniqueness** — for every pair of distinct keys
    `(k_i, k_j)` in `LABEL_SLOTS`, the Euclidean distance
    `‖slot_offset(k_i) − slot_offset(k_j)‖₂` is ≥ 12 px (the chosen
    text bounding-box exclusion radius).
  * **slot-on-circle** — every `slot_offset(k)` has Euclidean magnitude
    `LABEL_SLOT_RADIUS_PX` to within 1e-9.
  * **per-arc-annotation-shape** — for the default `SceneState` and
    each arc module, calling the module's `<arc>_label_annotation()`
    returns a dict with exactly the keys listed in (b), the leader
    `arrowcolor` matches the palette, and `(ax, ay)` matches the slot
    table for that arc's label key.
  * **annotation-emission-vs-group-filter** — calling
    `build_annotations(state, angle_groups=frozenset())` returns `[]`;
    each single-group `frozenset({grp})` returns the count of
    annotations expected for that group; the union over all groups
    has no duplicate label-key entries.
  * **no-text-trace-leakage** — `build_scene(state)` no longer
    returns any `Scatter3d` whose `mode` contains `"text"` for the
    arc/axis labels (target marker label, observer/sun/B chip labels
    that are *anchor* identifiers, not arc labels, may remain — the
    test enumerates the arc-label trace-name patterns explicitly).
  * **annotation-list-shape** — `build_annotations(...)` returns a
    list of plain `dict`s (mypy-friendly, JSON-serializable) so
    `fig.to_json()` round-trip is preserved.

**(g) Golden re-spin.** `scene_{sphere,cylinder,flat_plate,box,
cone}.{json,png}` regenerated via the existing
`tests/dev_render_goldens.py` after Phase 13 lands. The .json
deltas will show: arc text traces removed; `layout.scene.annotations`
populated.

### CU candidates surfaced by Phase 13 (file at PR-merge time per R21/R22)

  * Body-axis and world-axis tip labels are currently emitted as
    `mode="text"` Scatter3d traces from inside `body_axes.py` and
    `world_axes_triad.py`. Phase 13 has the option to migrate those
    to annotations too (so they participate in the slot table) or to
    leave them as 3D text. Recommendation: migrate, since they are
    the worst offenders in the user's "stack on top of each other"
    complaint. Either way, file a CU if any arc/axis label is left
    on the trace path after Phase 13.
  * Plotly's `xshift`/`yshift` annotation parameters are evaluated
    in screen pixels at *render time* — viewport-resize re-applies
    them but does not rotate them. Aggressive camera spin can place
    a label on top of unrelated geometry. Phase 13 accepts this
    fragility (Phase 12 leader lines mitigate it). File a CU for a
    follow-up that reapplies slot rotation when the user drags the
    camera past 45° azimuth quadrants.
  * The "currently-editing → faded chips" interaction model
    (requirement #3) is deferred. File a CU describing the
    hover-expand interaction so it is not lost.

### What does NOT change in Phase 13
- `app/state.py` — no new state fields.
- Physics / angle math — angle decompositions, swept values, and the
  readout panel see identical inputs and produce identical numbers.
- `_arc_radii.py`, `_arc_offsets.py`, `_arc_palette.py`,
  `_arc_labels.py` — Phase-11 + Phase-12 invariants stand. Phase 13
  is purely a label-rendering layer.
- `build_scene` signature and return type — only the *content* of
  the trace list shrinks (label text traces removed). All 16
  existing callsites continue to compile.
- C1 (no /src writes), C3 (projected-area invariant), C4 (units),
  C5 (Rule 19), C6 (no private symbols) — all still hold.
- Phase 0–12 test suite — every existing test must still pass.
  Tests that previously asserted on label-text trace presence are
  rewritten to assert on annotation entries instead.
