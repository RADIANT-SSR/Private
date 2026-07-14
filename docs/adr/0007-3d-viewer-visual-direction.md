# ADR-0007: Geometry Viewer — Visual Direction and Scene-Library Lift

**Date:** 2026-07-13 (updated 2026-07-14)
**Status:** Accepted — **2D orthographic Qt schematic** (owner-ratified 2026-07-14). The
original recommendation below (Direction B: flat/line-art **PyVista** render, §Decision 1)
is **SUPERSEDED**: the PyVista/VTK raster could not match the mockup's crisp SVG line-art,
so the viewer is reimplemented as a pure-Qt 2D orthographic schematic that ports the
`dev_tools/gui_mockups/geometry_viewer` mockup. See **§Supersession (2026-07-14)** below.

## Supersession (2026-07-14) — 2D orthographic Qt schematic

The owner ratified, 2026-07-14, replacing the PyVista/VTK viewer with a **2D orthographic
Qt schematic** drawn with `QPainter` over a Python port of the mockup's `geometry.js`
projection. Rationale: the VTK raster (even flat-shaded on the light theme, §Decision 1)
reads as a soft raster, not the crisp antialiased hairline line-art the mockup specifies;
a Qt 2D canvas reproduces the mockup faithfully, adds **no** new dependency, and — being
pure Qt — has **no** VTK/OpenGL requirement, so it renders and tests identically headless
(`QWidget.grab()`) with no segfault-prone live interactor. The three-backend degradation
ladder (live / offscreen-image / unavailable, §Decision, §6.6) collapses to a single
always-available canvas with a minimal guard: **the "3D viewer unavailable" fragility is
gone.**

- **Pass 1 (shipped 2026-07-14):** the renderer core — the *look*. New modules
  `radiant.gui.viewer.projection` (the ported `geometry.js` orthographic projection +
  direction math) and `radiant.gui.viewer.schematic_view` (the `SchematicView` QPainter
  canvas); `GeometryViewer` (`viewer_widget.py`) reimplemented over the canvas with its
  StageCenter-facing surface preserved (`show_result`, `set_angle_revealed` /
  `set_triad_visible` as Pass-2 no-op-safe stubs, `close_viewer`, `set_theme`). The
  Geometry center tab is renamed **"3D View" → "Schematic"**. Draws: light background,
  ground grid, X/Y ground axes + zenith Z axis (arrowheads + labels), the four labelled
  vectors (sun→target amber solid, sensor→target blue solid, sun→ground amber dashed,
  zenith grey), sun/sensor glyphs, a wireframe target (sphere great-circles / box / point
  reticle), ground-projection dashed drop-lines, and the VECTORS legend overlay.
  Orthographic yaw/pitch by mouse drag. The `ViewerState` adapter (`viewer_state.py`) is
  **reused unchanged** across the pivot.
- **Pass 2 (deferred, tracked CUs):** the θ_v/φ_v/θ_s angle arcs (CU-128), the h_s /
  altitude leader labels (CU-129), the RPY body triad (CU-130), the full shape library +
  dimension inputs (CU-131), the angle-truth consistency test ported onto the 2D math
  (CU-133), and **removal of the now-unwired lifted VTK scene library**
  (`radiant.gui.viewer.scene`, `pyvistaqt`/`pyvista` no longer rendered) (CU-132).
- **PyVista-specific CUs re-audited:** CU-122 (broken `geometry_gui_v2` shell / no
  attitude source), CU-124 (in-scene VTK point-picking + `highlight.py`), and CU-127
  (live-interactor repaint regression) are **superseded by the 2D pivot** — the live VTK
  interactor they gate no longer exists in the production path; they are dispositioned in
  the Cleanup Backlog (2026-07-14).

Everything from §Decision 1 onward is the **original 2026-07-13 PyVista recommendation**,
retained for the decision history; it no longer describes the shipped viewer.

## Context

GUI Development Plan Phase 6 (`docs/plans/GUI_Development_Plan.md` §6) settles what
remains before the production 3D geometry viewer (Phase 7) can be built. The engine
decision is already made — **D5** (ratified 2026-07-12): PyVista embedded via
`pyvistaqt.QtInteractor`, lifting the `dev_tools/geometry_gui_v2` scene library. VTK
offscreen rendering is confirmed working in this environment (pyvista 0.47.3, vtk
9.6.1). Three questions remain, and this ADR answers them:

1. **Visual direction.** `dev_tools/geometry_gui_v2` renders a lit/PBR scene; the newer
   `dev_tools/gui_mockups/geometry_viewer` mockup specifies an intentionally schematic
   CAD-line-art look and explicitly says *"keep the schematic aesthetic — line-art, no
   realistic shading, intentional non-to-scale. Resist the urge to apply PBR materials"*
   (`radiant_geometry_handoff.md` §5). The same engine produces either.
2. **Lift assessment.** Which scene-library files lift verbatim, which must rebind from
   the deleted `core/geometry.py` dataclasses (CU-094) to the new `GeometryStage`
   outputs (ADR-0006), and which stay behind.
3. **Theme integration.** Whether the viewer can follow the Phase 1 design-system tokens
   (`src/radiant/gui/themes/tokens.py`) so the 3D panel matches the rest of the app.

This ADR is a **recommendation**. The owner ratifies the visual direction before Phase 7.
Phase 7 proceeds on the recommended direction as **provisional** — the whole look is
driven from `scene/style.py`, so a later reversal is a token/constant swap, not a
rewrite.

## Decision

### 1. Visual direction — RECOMMENDED: flat / line-art on the light theme (pending owner ratification)

Both directions were rendered offscreen from the default scenario. Side-by-side compare
page: `docs/adr/assets/0007-3d-viewer/` (renders below; generator
`render_geometry_viewer_directions.py`, invoked with
`QT_QPA_PLATFORM=offscreen PYTHONPATH=<repo-root>`).

| Direction | Render | What it is |
|-----------|--------|-----------|
| **(A) Lit / PBR — as-is** | `geometry_viewer_lit_pbr.png` (real `geometry_gui_v2.scene.build_scene`) | Dark viewport `#1F242B`, PBR-shaded teal target, softly-lit sun/satellite glyphs, full leader labels + angle arcs. |
| **(A′) Lit / PBR — matched minimal** | `geometry_viewer_lit_matched.png` | Same representative geometry as (B), lit/PBR on dark, isolating the *look* from the *labeling*. |
| **(B) Flat / line-art — RECOMMENDED** | `geometry_viewer_flat_lineart.png` | Light background from token `bg = #ebeef2`, flat shading, edges on, no PBR — a restyle of the same scene. |

**Recommendation: Direction B (flat / line-art on the light theme), with a documented
option to blend** — schematic vectors/arcs over *softly*-lit (low-metallic, high-
roughness, ambient-forward) target shapes if pure-flat shapes read as too "cut-out" once
the full shape library and labels are in. Reasoning:

- **It matches the authoritative mockup.** The `geometry_viewer` handoff is the *newer*
  design intent and is explicit: line-art, no realistic shading, resist PBR. The
  geometry_gui_v2 PBR look predates that directive.
- **It matches the app.** The production GUI launches on the **light** theme
  (`tokens.LIGHT`, Phase 0 checkpoint amendment 1). A dark PBR viewport embedded in a
  light flat app reads as "a different app in a window" — the exact failure Phase 6 task 3
  guards against. Direction B's background *is* the app background token.
- **Readability of the schematic content.** The panel's job is to make angles, vectors,
  and arcs legible (θ_o, η, θ_s, α_t, the four vectors, the ground point) — not to render
  a photoreal satellite. Flat shading + crisp edges + neutral background maximize vector/
  arc contrast; PBR speculars and a dark ground grid compete with them.

This is **recommended, pending owner ratification.** If the owner prefers the lit look,
Phase 7 flips `FACETED_SMOOTH_SHADING`/PBR constants and the viewport background in
`style.py` — no structural change.

### 2. Scene-library lift — the Phase 7 work list

The `dev_tools/geometry_gui_v2/scene/` package is **49 `.py` files**. The C7 contract
(no Qt imports under `scene/`) still holds — verified: no `PySide6`/`PyQt` import appears
anywhere under `scene/`, and `tests/test_scene_imports_without_qt.py` pins it. The lift
of `scene/` → `src/radiant/gui/scene/` is therefore mechanical for the Qt dimension.

**However, the "no-UI-dependency" contract is narrower than "no Qt".** 37 of the 49
files import `from dev_tools.geometry_gui_v2.app.state import SceneState` — the frozen
slider-input dataclass that lives under `app/`. `SceneState` itself is pure (no Qt, no
dependency on the deleted dataclasses), so the *coupling* is to a data shape, not to the
Qt shell. Two mechanical changes apply to Phase 7:

- **Path rewrite (all 49 files, verbatim):** `dev_tools.geometry_gui_v2.scene` →
  `radiant.gui.scene`. Find/replace; no semantics change.
- **Input rebind (the 37 `SceneState` consumers):** introduce a production
  `ViewerState` built from `stage_outputs["geometry"]` + the relevant params, with the
  **same field names** as `SceneState` so the per-module edits are near-zero. See the
  rebind mapping below.

**Per-file classification:**

| Files | Count | Disposition |
|-------|-------|-------------|
| `_layout.py`, `camera_views.py`, `highlight.py`, `style.py`, `arcs/_arc.py`, `vectors/_tube.py`, `labels/layout.py`, `labels/leader_label.py`, `labels/typography.py`, `widgets/view_cube.py`, `widgets/world_axes_gnomon.py`, `widgets/__init__.py` | ~12 | **LIFT VERBATIM** — geometry-agnostic (layout solvers, camera poses, style constants, tube/arc/leader primitives, corner widgets). Only the intra-package import path is rewritten. `style.py` additionally gains a token-binding layer (see §3) and, under Direction B, the flat/line-art constant swap. |
| `builder.py`, `_directions.py`, `_display_distance.py`, `_lighting.py`, `framing.py`, `point_source_marker.py`, `extended_pixel_cell.py`, and the `arcs/`, `frames/`, `glyphs/`, `ground/`, `target/`, `vectors/`, `labels/_anchors.py` modules that read `SceneState` | ~37 | **LIFT + REBIND** — replace `SceneState` field reads with `ViewerState`/`stage_outputs` reads per the mapping. `target/_pose.py` also imports `radiant.core.geometry.euler_to_rotation_matrix` (still present — **not** deleted; only the dataclasses were), so that import survives. |
| `app/main.py`, `app/panels/`, `app/dialogs/`, `app/theme.py`, `app/window_persistence.py`, `app/status_bar_text.py`, `app/interaction_state.py` | — | **STAY BEHIND** — prototype shell; the production GUI has its own main window, docks, dialogs, and persistence. |
| `app/state.py` (`SceneState`) | 1 | **REBIND → new `ViewerState`** owned by the production GUI, populated from `stage_outputs["geometry"]` + params. Keep the field names to minimize churn in the 37 consumers. |
| `app/view_model.py` | 1 | **LEAVE / SUPERSEDED** — currently **broken** (imports the deleted `ObserverGeometry`/`TargetGeometry`/`SceneGeometry`; see Findings). Its geometry-derivation role is now owned by `GeometryStage`; its shape/projected-area helpers rebind to the source shape params. The production viewer reads `stage_outputs`, not a re-derivation. |

**Rebind mapping — `SceneState` field → production source (ADR-0006):**

| `SceneState` field | Production source |
|--------------------|-------------------|
| `observer_altitude_m` | `stage_outputs["geometry"]["h_sensor_m"]` |
| `observer_look_angle_rad` | `stage_outputs["geometry"]["eta_rad"]` (sensor off-nadir η) |
| `target_altitude_m` | `stage_outputs["geometry"]["h_target_m"]` |
| `solar_zenith_rad` | `stage_outputs["geometry"]["theta_s_rad"]` |
| `relative_azimuth_rad` | `stage_outputs["geometry"]["delta_phi_rad"]` |
| `regime_override` | `stage_outputs["optics"]["regime"]` (final regime, Rule 10) |
| `target_shape`, `target_radius_m`, `target_length/width/height/base_radius_m`, `target_fill_fraction` | source shape params (`source.target.*`) via `ParameterSet` — **not** a geometry output |
| `focal_length_m` | `optics.focal_length_m` param |
| `pixel_pitch_m` | `detector.pixel_pitch_m` param |
| `background_kind` | source background param |
| `observer_{yaw,pitch,roll}_rad`, `target_{yaw,pitch,roll}_rad` | **No stage emits platform/target attitude** — ADR-0006 §4 deferred attitude "until a consumer exists." The viewer *is* that consumer (RPY triad, `target/_pose.py`, `frames/body_axes.py`). **Gap for Phase 7** — see Findings / CU-122. |

New geometric truths the viewer should now annotate via leader labels (available from
`GeometryStage`, absent from the flat-Earth prototype): `theta_o_rad` (target-referenced
off-nadir, ADR-0006), `slant_range_m`, `ground_range_m`, `incidence_angle_rad`. Per Phase
7 task 2, the stage is the single source of angle truth; the ported `geometry.js`/scene
math is used only for camera/projection/picking, and a consistency test asserts viewer-
local recomputation agrees with stage outputs.

### 3. Theme integration — the viewer follows `tokens.py`

Confirmed feasible. PyVista exposes every color the scene sets, so `style.py` binds to
the design tokens instead of hardcoding hex:

- **Viewport background** ← `Theme.bg` (`plotter.set_background(theme.bg)`); light default
  `#ebeef2`. Replaces the prototype's hardcoded `VIEWPORT_BACKGROUND_COLOR = #1F242B`.
- **Accent / active-edit re-stroke** ← `Theme.accent` (`#b8431a` light) instead of the
  prototype `ACCENT_COLOR = #FF6B35`.
- **Label text / leader lines / neutral frames** ← `Theme.ink`, `Theme.muted`,
  `Theme.line` for `vtkTextActor` color and leader/gnomon strokes.
- **Physics color roles kept from the mockup** (sun = amber, sensor = blue/cyan, surface
  normal = green, phase/azimuth = accent) stay as semantic constants — they encode
  meaning, not chrome — but sit beside the token bindings in `style.py`.

Because the token set has a `LIGHT` and `DARK` instance sharing field names, the Phase 9
View-menu theme toggle re-applies the viewer background/label colors the same way it
re-applies the QSS: one `Theme` in, viewer restyles. **Implication:** the Phase-1
discipline test forbids color literals outside `themes/`; the lifted `style.py` must take
its chrome colors from a passed-in `Theme` rather than defining hex constants, or live
under an allowlisted boundary. Flag for Phase 7.

### 4. Not-to-scale rule (restated, owner-endorsed)

The viewer is a **schematic, intentionally not-to-scale**. Altitudes and ranges are
annotated via **leader labels**; geometry is **never rescaled or translated** to fake
proportionality. Vectors render at fixed display lengths with break-marks, not at true
metric length (a 600 km slant range and a 1 m target cannot share a linear scale). This
matches `radiant_geometry_handoff.md` §1 and the owner-endorsed convention, and is a
Phase 7 acceptance criterion.

## Rationale

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **B. Flat / line-art on light theme (recommended)** | Matches the newer authoritative mockup and the app's flat/light aesthetic; maximizes vector/arc/label readability; viewport background *is* the app token | Softly-modeled 3D shapes lose some depth cue; pure-flat shapes can read as cut-out at some camera angles (mitigated by the blend option) |
| A. Lit / PBR as-is (geometry_gui_v2) | Zero restyle work; depth/shape reads well; already built and golden-tested | Contradicts the mockup's explicit "resist PBR"; dark viewport clashes with the light app; speculars compete with schematic vectors |
| Blend — schematic vectors/arcs over softly-lit shapes | Keeps shape depth cue while foregrounding schematic content; a valid owner choice | Two rendering styles to tune; slightly more `style.py` surface |

Direction B is a `style.py` constant set, not an architecture. Recommending it now
unblocks Phase 7; ratifying A or the blend later is a token swap.

## Consequences

- **Positive:** Phase 7 has a concrete per-file work list (~12 verbatim, ~37 lift+rebind,
  the app shell stays behind), a field-level rebind mapping to `GeometryStage` outputs, a
  confirmed theme-integration path, and a ratified-pending visual direction. The C7
  contract is confirmed intact, so the lift is mechanical for Qt.
- **Negative:** The rebind is non-trivial (37 files touch `SceneState`); the production
  GUI must introduce a `ViewerState` adapter and the theme-color discipline forces
  `style.py` chrome colors through a passed-in `Theme`. Platform/target **attitude has no
  stage owner** (ADR-0006 §4 deferral), so the viewer's RPY triad needs either a new
  attitude source or a viewer-local attitude input in Phase 7 (CU-122).
- **Neutral:** No production code changes in this phase (Category A). Golden screenshots
  in `geometry_gui_v2/tests/golden_phase*/` are the prototype's, not the production
  viewer's; Phase 7 pins its own.

## Findings (filed as CUs / gaps per Rule 21)

- **`dev_tools/geometry_gui_v2` is currently broken against the deleted dataclasses.**
  `app/view_model.py` (and `tests/test_integration_boundary.py`) still
  `from radiant.core.geometry import ObserverGeometry, SceneGeometry, TargetGeometry` —
  all three deleted 2026-07-12 by CU-094 (ADR-0006 Phase 4). Verified: importing
  `dev_tools.geometry_gui_v2.app.view_model` raises `ImportError`, so the full prototype
  app shell will not launch. **The `scene/` library itself imports cleanly** (`build_scene`
  imports and renders — this ADR's renders prove it), so the Phase 7 lift target is
  intact; only the prototype's own app shell is dead. Filed as **CU-122**.
- **Platform/target attitude has no stage owner** (RPY triad input) — ADR-0006 §4
  deferred it "until a consumer exists"; the viewer is that consumer. Recorded in CU-122's
  scope as the Phase 7 rebind gap.

## References

- ADR-0006 (`0006-geometry-stage.md`) — GeometryStage, θ_o conventions, dataclass deletion
- `docs/plans/GUI_Development_Plan.md` §2 (D5), §6 (Phase 6), §7 (Phase 7)
- `dev_tools/gui_mockups/geometry_viewer/radiant_geometry_handoff.md` §§1, 5, 7
- `dev_tools/geometry_gui_v2/ARCHITECTURE.md` (C1–C8 contracts, C7)
- `src/radiant/gui/themes/tokens.py`; `docs/architecture/RADIANT_GUI_Architecture.md` §8
- Renders + compare page + generator: `docs/adr/assets/0007-3d-viewer/`
