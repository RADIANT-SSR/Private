# Changelog

All notable changes to RADIANT are recorded here, per CLAUDE.md Rule 29.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Newest entries
at the top of `[Unreleased]`; on release, `[Unreleased]` rolls into a dated
version heading. Categories: **Added** / **Changed** / **Deprecated** /
**Removed** / **Fixed**. Entries that change computed numbers (physics models,
parameter defaults, golden baselines) are prefixed **Results-affecting:** and
state the direction and rough magnitude of the change.

What gets an entry (Rule 29): changes to computed results, public API surface
(methods, parameters, metrics, error classes, config fields), and capability
additions or removals. What does not: refactors, doc-only, test-only, and
internal changes with no observable effect.

This changelog begins 2026-07-07. Earlier history lives in `git log`,
`docs/tracking/gaps.md`, and `docs/tracking/Cleanup_Backlog.md` and is not
retroactively reconstructed.

## [Unreleased]

### Added
- **GUI geometry schematic — ground vectors for elevated targets (owner feedback 2026-07-14,
  view-only).** When the target is above the ground (`geometry.target_altitude_m > 0`) the
  Schematic tab now additionally draws a **SENSOR→GROUND** vector (blue, dashed) and a
  **SUN→GROUND** vector (amber, dashed), both landing at the target's **ground projection**
  (nadir footprint, directly below the body on the ground plane). The VECTORS legend gains
  matching rows, shown only when the vectors are present. A ground target (altitude 0) has
  target == ground, so the two vectors are degenerate and absent — unchanged behaviour there.
  Colours come from the allowlisted physics palette (sensor = blue, sun = amber). Golden
  untouched (the GUI is a view over the scripting API).
- **GUI geometry Schematic tab — editable + nominal shape dims (owner feedback 2026-07-14,
  view-only).** Three changes to the Geometry stage's Schematic tab (golden untouched — the
  GUI is a view over the scripting API): (1) **Geometry is now settable from the Schematic
  tab.** Its side panel gains a **Geometry inputs** accordion page hosting the reusable
  Phase-5 `GeometryModeForm`, wired through the same edit → one `sensor.set` → debounced
  re-evaluate → schematic re-render path as the Inputs tab, so the user can edit geometry and
  watch the schematic + arcs move. Both geometry forms (Inputs + Schematic) read the one live
  sensor and re-sync on the next clean evaluation. New public GUI surface:
  `GeometryAnglePanel.geometry_form` property; `StagePane.refresh_geometry_forms`. (2)
  **Shapes load with nominal dimensions (CU-125).** Selecting a target shape whose required
  dimensions are still the `0.0` "not set" sentinel now seeds them to nominal non-zero values
  (`geometry_angle_panel.NOMINAL_SHAPE_DIMENSIONS`) — one `sensor.set` each, only where unset,
  never overwriting a user value — so the re-evaluate succeeds instead of tripping the
  `radiant.source` shape factory. The schema keeps the `0.0` Rule-12 default; the nominal map
  is a GUI-side UX default only.
- **GUI geometry schematic — Pass 2 (annotations + shape editing; ADR-0007, view-only).**
  The 2D orthographic schematic gains the annotations and shape-editing the mockup/owner
  specify. (1) **Angle arcs + degree labels (CU-128):** revealable arcs for off-nadir η,
  sun-zenith θ_s, relative-azimuth Δφ (ground), and phase α_t, each drawn with the ported
  projection math but labelled with the angle **value from `stage_outputs["geometry"]`**
  (bound verbatim into `ViewerState`) shown in **degrees** (§6.3); the phase arc is
  symbol-only (no stage-output phase angle). The side-panel angle toggles now reveal/hide
  the arcs and repaint. (2) **Altitude leader labels (CU-129):** `h_s` / `h_t` pills in
  km/m, the not-to-scale magnitude annotation (§6.1). (3) **Full shape library + ALL
  dimension inputs (CU-131 + owner request):** the schematic draws distinct
  sphere/box/cylinder/cone/flat-plate wireframes (aspect ratio from the shape's own dims,
  never metric magnitude), and the side panel exposes every relevant dimension input for
  the selected shape (radius / length / width / height / base-radius), showing only the
  subset the shape uses, each one `sensor.set` per edit. (4) **RPY triad (CU-130):** the
  on-target body-axes gizmo (roll +X′ pink / pitch +Y′ green / yaw +Z′ purple) from
  `source.target.shape_{yaw,pitch,roll}_rad`, with the body wireframe rotated by the same
  ZYX Euler. New public GUI surface: `GeometryAnglePanel.dimensionRequested` signal +
  `set_dimension_bounds`/`set_dimensions`/`dimension_spin`; `SchematicView.set_revealed_angles`;
  new modules `radiant.gui.viewer.angle_catalog` / `radiant.gui.viewer.angle_truth`. A
  **binding angle-truth consistency test** asserts the viewer's local angle recomputation
  agrees with `stage_outputs["geometry"]` within `ANGLE_CONSISTENCY_ABS_TOL_RAD = 1e-9` rad
  (measured residual ~1e-16). No computed results change (the stage remains the single
  source of angle truth); golden untouched.

### Removed
- **GUI geometry Schematic tab — redundant derived-angles table removed (owner feedback
  2026-07-14, view-only).** The Schematic tab's side panel no longer carries the derived
  "Geometry — derived angles & ranges" `GeometryReadout` (it duplicated the Inputs tab; the
  key derived values surface on the schematic itself as arc degree labels + altitude leader
  labels). The angle-arc reveal toggles remain; the Inputs-tab readout is unchanged. Removed
  public GUI surface: `GeometryAnglePanel.readout` property + `populate_readout` method.
- **GUI lifted VTK/PyVista scene library removed (CU-132, ADR-0007 Rule 27).** The
  superseded `radiant.gui.viewer.scene` render library (~3.9 kLoC across `builder`,
  `arcs/`, `frames/`, `glyphs/`, `ground/`, `labels/`, `target/`, `vectors/`) is deleted now
  that the 2D `QPainter` schematic fully replaces it; only the allowlisted glyph-colour
  module `radiant.gui.viewer.scene.palette` survives. `radiant.gui.viewer` no longer imports
  `pyvista`/`pyvistaqt`/`vtk` (the `gui`-extra pins are retained pending a dependency-drop
  audit — CU-134).

### Changed
- **GUI geometry Schematic tab — Target shape & orientation fields restyled to match the
  Geometry inputs (owner feedback 2026-07-14, view-only).** The **Target shape & orientation**
  accordion page's controls previously rendered with default-Qt chrome (a plain combo, and
  `QDoubleSpinBox`es with native up/down arrows for the dimension and yaw/pitch/roll values),
  which looked nothing like the styled **Geometry inputs** fields. They are now built from the
  **same** building blocks as the `GeometryModeForm`: `geoModeFamily` cards, a
  `geoModeSelector`-styled shape combo, and the shared `FieldRow` (label + value button) —
  factored into a new `radiant.gui.widgets.field_row` module (`FieldRow`, `ElidingLabel`) that
  both surfaces import, so they cannot visually diverge again. Editing a dimension or RPY value
  now opens the shared `ParameterEditorDialog` (value + unit + validate-on-a-clone reject path,
  one `sensor.set` on commit) instead of a bare spin box, matching the Inputs-tab fields.
  Changed public GUI surface: `GeometryAnglePanel` replaces its `dimensionRequested(str,float)`
  / `orientationRequested(str,float)` signals + `dimension_spin` / `rpy_spin` accessors with a
  single `editRequested(str)` signal + `dimension_row` / `rpy_row` (returning `FieldRow`), and
  drops `set_orientation_bounds` / `set_dimension_bounds` (the dialog now enforces schema
  bounds). Golden untouched (the GUI is a view over the scripting API).
- **GUI geometry Schematic tab — angle-arc selector moved to a plot overlay (owner feedback
  2026-07-14, view-only).** The angle-arc reveal toggles (θ_s sun zenith, Δφ relative
  azimuth, α_t phase angle, η off nadir) moved **out** of the right-column accordion's
  "Angles" page and **onto the schematic plot** as a compact **bottom-left overlay**
  (`AngleToggleOverlay`, new module `radiant.gui.viewer.angle_overlay`), mirroring the
  top-left VECTORS legend. It is a real child `QWidget` on the `SchematicView` canvas,
  repositioned bottom-left on resize, and stays interactive — each checkbox still reveals its
  arc via `GeometryViewer.set_angle_revealed` (reveal path unchanged). The right-column
  accordion now holds only the **Geometry inputs** and **Target shape & orientation** pages.
  Removed public GUI surface: `GeometryAnglePanel.angleToggled` signal + `angle_checkbox`
  accessor (both now on `SchematicView.angle_overlay`). Golden untouched (the GUI is a view
  over the scripting API).
- **GUI geometry viewer reimplemented as a 2D orthographic schematic — view-only
  (ADR-0007 superseded 2026-07-14, Pass 1).** The Geometry stage's viewer is no longer a
  PyVista/VTK render but a crisp, antialiased **2D orthographic line-schematic** drawn with
  `QPainter`, porting the `geometry_viewer` mockup's `geometry.js` projection (new modules
  `radiant.gui.viewer.projection` + `radiant.gui.viewer.schematic_view`). The Geometry
  center tab is renamed **"3D View" → "Schematic"**. Pass 1 draws the ground grid, X/Y/Z
  axes, the four labelled vectors (sun→target, sensor→target, sun→ground, zenith),
  sun/sensor glyphs, a wireframe target (sphere/box/point), ground drop-lines, and the
  VECTORS legend, with orthographic yaw/pitch by mouse drag. The `GeometryViewer` public
  surface (`show_result`, `set_angle_revealed`/`set_triad_visible` as Pass-2 no-op-safe
  stubs, `close_viewer`, `set_theme`) and the `ViewerState` adapter are preserved. The
  three-backend "3D viewer unavailable" degradation ladder is removed — a pure-Qt canvas
  has no VTK/OpenGL dependency and renders/tests faithfully headless. No computed results
  change (the stage remains the single source of angle truth). Deferred to Pass 2: angle
  arcs, altitude leader labels, RPY triad, shape library + dimensions, the angle-truth
  test, and removal of the now-unwired lifted VTK scene library (CU-128–CU-133).

### Fixed
- **GUI geometry Schematic tab — inputs no longer clipped horizontally (owner bug
  2026-07-14, view-only).** The right-column "Geometry inputs" form was wider than its
  accordion column, so the value fields (e.g. `8000 m`, `1.5708 rad`) were cut off behind a
  horizontal scrollbar. The mode-selector combos and field-value editors now size to the
  available column width (expanding, minimum-contents sizing) instead of forcing their
  content width, the long form title wraps, and the raw dot-path field labels elide (full
  name on hover) — so the form fits its column and scrolls only vertically when tall, never
  clipping horizontally. Golden untouched.
- **GUI geometry schematic — centred + framed, no longer bottom-anchored (view-only).**
  The 2D orthographic schematic rendered anchored to the *bottom* of its panel with the
  canvas above it empty (owner screenshot 2026-07-14). Two compounding causes fixed:
  (1) the schematic canvas ballooned taller than its tab viewport — the Geometry
  "Schematic" tab shares a `QTabWidget` stack with the tall "Inputs" tab, whose full-height
  derived-angles readout inflated the shared minimum height; each non-canvas sub-view is now
  wrapped in its own `QScrollArea` so the canvas fills the viewport (with a sensible
  `Expanding` policy + 360×360 minimum + concrete `sizeHint`) instead of growing unbounded;
  (2) the orthographic fit anchored the scene origin low (`cy = 0.72·height`) with a
  width-limited scale, so on a too-tall canvas the scene clustered near the bottom — the
  camera now scales the projected scene bounding box to the *live* paint rect with a
  symmetric margin and centres it on both axes, recomputed every paint so the scene stays
  centred and framed on resize (short / tall / wide). No computed results change; golden
  untouched.

### Added
- **GUI 3D geometry viewer — interactions: angle annotations, shape library, RPY triad
  (GUI plan Phase 7 Part B, ADR-0007).** The Geometry "3D View" becomes a split of the
  viewport and a new accordion side panel (`GeometryAnglePanel`). (1) **Click-to-reveal
  angle annotations:** per-angle toggles reveal an arc (off-nadir η, sun-zenith θ_s,
  phase-angle α_t) with the numeric value pinned from `stage_outputs["geometry"]` verbatim
  (never recomputed; the phase angle is symbol-only as it has no stage-output truth), split
  target-frame vs ground-frame to match the Phase-5 readout — which the panel **shares**,
  not duplicates. (2) **Target shape library:** a shape combo populated from the
  `source.target.shape` schema `enum_values`; selecting a shape performs one `sensor.set`
  and re-renders. (3) **RPY triad:** an on-target body-axes gizmo (pink=Roll / green=Pitch /
  purple=Yaw) rendered from `source.target.shape_{yaw,pitch,roll}_rad`; editing those tilts
  the triad and the orientation-dependent geometry. A **binding consistency test** asserts
  the viewer's local angle recomputation (ported `geometry.js` math, used only for
  camera/picking) agrees with the stage outputs within 1e-9 rad — the stage is the single
  source of angle truth. In-scene VTK picking and platform-attitude are deferred
  (CU-124/CU-122). View-only — no computed results change.
- **GUI 3D geometry viewer — static bound scene (GUI plan Phase 7 Part A, ADR-0007).** The
  Geometry stage center becomes a two-tab composite — **Inputs** (the mode forms + angle
  readout) and **3D View** — the latter embedding a new `GeometryViewer`
  (`radiant.gui.viewer`). It renders a not-to-scale PyVista schematic of the sun / sensor /
  target geometry (ground reference, target/regime glyph, the four vectors, sun/sensor
  glyphs, deconflicted leader labels) bound to `stage_outputs["geometry"]` + the final
  optics regime after each evaluate, via the new `ViewerState` adapter. The Qt-free scene
  library is lifted from `dev_tools/geometry_gui_v2` into `radiant.gui.viewer.scene`
  (imports no physics stage; gui → api + core kept). Viewport background and label/leader
  chrome follow the design-system `Theme`; the physics-domain glyph palette
  (sun = amber, sensor = blue, normal = green, target = teal) lives in one allowlisted
  module. Three render backends (live `QtInteractor` / static offscreen image / actionable
  degradation panel) keep the app alive where OpenGL/VTK is unavailable. `StageComposition`
  and `StageSubView` gained a `geometry_viewer` field. Angle-arc annotations, the shape
  library, and the RPY triad are deferred to Part B. View-only — no computed results change.
- **GUI Geometry screen — stage-0 input-mode forms + frame-grouped derived-angle readout
  (GUI plan Phase 5).** The Geometry stage's contextual center gains a `GeometryModeForm`
  (new `radiant.gui.widgets.geometry_mode_form`, over a Qt-free `radiant.gui.geometry_modes`
  manifest): a mode selector per family (viewing V0–V4 / solar S1–S3+night / kinematics
  direct-or-circular) with only the active mode's fields editable, all fields schema-driven,
  each edit one `sensor.set` through the shared Parameter Editor (validate-on-clone reject,
  display-unit aware). The `GeometryReadout` now groups its values by reference frame
  (target-frame vs ground/platform frame vs resolution), each with unit and symbol. An
  over-/under-specified geometry (the stage's `GeometrySpecificationError`) highlights the
  offending mode selector and navigates to the Geometry screen. `StageComposition` gained a
  `geometry_form` field. View-only — no computed results change.
- **GUI per-stage center tabbed sub-view hook (provision only, deferred content).** A stage's
  center composite can now be presented as multiple named tabs: `StageComposition` (in
  `radiant.gui.stage_views`) gained an optional `subviews` field of the new `StageSubView`,
  and `StagePane` renders a `QTabWidget` when two or more are declared, falling back to the
  current single pane otherwise. **No v1 stage declares any sub-view** — every stage renders
  exactly as before; this is the seam a later per-stage phase fills. View-only — no computed
  results change.
- **`radiant.api.stage_output_units.stage_output_unit(stage, key)` — canonical display unit
  for a scalar stage output.** Stage outputs are computed values with no per-field unit
  metadata (Gap 87); this new public accessor (and its `STAGE_OUTPUT_UNITS` table) supplies
  the canonical unit string a renderer needs to honour the R-UNITS rule. View-only — no
  computed results change.

### Fixed
- **GUI Geometry derived-angles readout had a short scrollbar that did not span the table
  (owner report 2026-07-14).** On the Geometry "Inputs" tab the derived-angles readout sat
  in its own inner scroll area *inside* the stage pane's outer scroll; the tall input form
  above it crushed the readout to a ~100 px sliver, so its inner scrollbar covered only that
  sliver instead of the full table. `GeometryReadout` gains a `scrollable` flag (default
  `True`, keeping the inner scroll for the compact 3D-view accordion side panel); the Inputs
  tab now uses `scrollable=False` so the table sizes to its full content and the pane's outer
  scroll owns scrolling — one full-height scrollbar spans the whole form + derived table. The
  stage pane omits its trailing stretch when a filling section (the readout or the 3D-view
  split) is present so that section absorbs the slack. View-only — no computed results change.
- **GUI 3D geometry viewer did not visually update on re-render (owner report 2026-07-14).**
  Parameter edits, re-evaluations, and annotation/triad toggles reached the viewer, but the
  embedded viewport showed the stale scene. On the live pyvistaqt `QtInteractor` (macOS /
  real display) a `clear()` → rebuild → `render()` sequence does not reliably repaint the GL
  widget — the VTK `render()` alone can be a no-visual-op after a scene rebuild. `_render_live`
  now follows the VTK `render()` with an explicit Qt `update()` of the interactor widget, and
  the static-image backend now calls `update()` after `setPixmap`, so both backends repaint on
  every re-render. The user's current camera is preserved (PyVista's `camera_set` flag survives
  `clear()`, so the default-camera call is a no-op after the first render — the view is never
  snapped back). View-only — no computed results change.
- **GUI Evaluate button relocated to the right-rail footer (owner feedback 2026-07-13).**
  The accent Evaluate (F5) button sat in a thin run bar in the center of the window, which
  read as out-of-place. It now lives as a persistent footer pinned at the bottom-right of
  the right rail (the persistence area), below the Messages panel, so it never scrolls away.
  The center run bar is removed. F5 and Run ▸ Evaluate still drive the same evaluation.
  View-only — no computed results change.
- **Twin-axis plot y-labels clipped at the figure edges in the narrow embedded pane (owner
  feedback 2026-07-13).** The Atmosphere plot's rotated y-axis labels were spelled-out and
  long — `"Transmittance τ_atm (dimensionless)"` and `"Path radiance L_path (W/m²/sr/µm)"` —
  and overflowed the figure edges at GUI embedded width even under constrained_layout.
  `plot_atmosphere_spectral` now labels the axes with the symbol + unit form only
  (`"τ_atm (dimensionless)"`, `"L_path (W/m²/sr/µm)"`); the unit is always retained (R-UNITS).
  All other builders already used short symbol + unit labels. View-only — no computed
  results change.
- **MTF Budget overlay legend blanketed the curves in the narrow embedded pane (CU-117).**
  `plot_mtf_terms` drew one legend entry per term — ~16 for an 8-contributor × x/y overlay —
  inside the axes, covering much of the curve area at GUI embedded width. Each contributor's
  `_x`/`_y` are now merged into a single legend entry when they coincide (~16 → ~8 labels;
  differing x/y keep both), and the legend is placed below the axes in a compact multi-column
  block so it never overlaps the curves. All contributor curves are still plotted. View-only —
  no computed results change.
- **GUI stage Outputs readout showed dimensional values as bare numbers (R-UNITS
  violation).** The per-stage Outputs readout inferred a value's unit from the output key's
  trailing suffix, so keys without a canonical suffix (`optics.A_collect`, `optics.Omega_pixel`)
  rendered unit-free and a mid-key token (`readout.signal_e_final`, `spectral_integration.e_rate_per_s`)
  was mislabelled or dropped. Units now come from the single authoritative framework table
  (`radiant.api.stage_output_units`): `A_collect` → `m²`, `Omega_pixel` → `sr`,
  `e_rate_per_s` → `e-/s`, etc. Booleans/strings and genuine dimensionless numerics stay
  unit-free. View-only — no computed results change.

- **GUI contextual per-stage center + global Inspector (contextual-layout retrofit
  Step B, arch doc §4.4 / §4.6 / §4.7).** Selecting a stage in the signal-chain strip now
  makes the center show **only that stage's contextual composite** — its outputs readout
  (scalar `stage_outputs` values with units, or the performance metric surface), its
  plot(s) drawn from the public `result.plot.*` accessors, and its relocated detail content
  (the MTF per-term table + overlay on Optics, the noise-budget table + bars + click-explain
  on Detector, the geometry angle readout on Geometry). This replaces the single shared
  canvas. Every Outputs / Metrics row carries a **pin affordance** that adds the value to
  the right-rail Pinned panel — a stage-output pin re-reads `stage_outputs` on each run; a
  metric pin reads the metric surface (CU-115 Step-B clause delivered). A new global
  **Inspector** tool (Tools → Inspector / the menu-bar `◈ Inspector` button, `Ctrl+I`) opens
  the full `inspect_result(result)` variable dump as a collapsible tree; it is disabled
  until the first evaluation.
- **GUI contextual-layout right rail — Pinned / Edit Config (YAML) / Messages
  (contextual-layout retrofit Step A, arch doc §4.5).** A persistent right-side dock now
  carries three sections: a **Pinned** panel of metric cards (default set = SNR · NEDT ·
  NIIRS · GSD · MTF@Nyquist, each value + unit sourced from `ChainResult.metric_records()`,
  with unpin and a `+ Pin…` picker over the metric surface; session-scoped); an **Edit
  Config (YAML)** button that opens a roomy modal editor preloaded with the current config
  and re-parses the edited text through `Sensor.load` on Apply (invalid YAML shows the
  actionable error and leaves the live config untouched — validated on a throwaway sensor);
  and a **Messages** panel listing chain warnings and errors (the widened warning strip),
  each clickable to its full-text dialog. The full-well saturation banner stays in the
  center column (high-signal, non-dismissible).
- **GUI detail tabs — Spectral, MTF, Noise Budget, Variables, YAML (GUI plan
  Phase 4 Task B).** The bottom detail dock's five tabs are now live, each its own
  widget class and each populated on every successful evaluation from a public API
  surface (no plotting or physics in GUI code): **Spectral** (a themed selector over
  `result.plot.spectral_source()` / `spectral_atmosphere()` / `spectral_inband()`,
  showing the accessor's actionable message when a frame is absent for the regime);
  **MTF** (per-contributor MTF@Nyquist table discovered from the result's
  `mtf_budget.per_term_at_nyquist`, x/y columns, dimensionless → bare numbers, plus the
  `result.plot.mtf()` overlay); **Noise Budget** (per-term σ table in e- RMS from
  `result.noise_terms`, `result.plot.noise_budget()` bars, and a click-a-term describe
  panel from the `NoiseTerm` metadata); **Variables** (`radiant.api.inspect.inspect_result`
  re-rendered as a collapsible tree); and **YAML** (read-only provenance-coloured current
  config via `Sensor.save`, with an Export… button — the tab's only file I/O). Units on
  every numeric cell (R-UNITS); all styling from theme tokens. Visual/UX capability only;
  results-neutral.
- **Spectral-radiance figure accessors on `result.plot.*` (Gap 86).** The
  `ResultPlotNamespace` gains three accessors — `spectral_source()` (target +
  optional background at-aperture radiance vs λ [W/m²/sr/µm]),
  `spectral_atmosphere()` (τ_atm(λ) [dimensionless] and L_path(λ) [W/m²/sr/µm]
  on twin unit-labelled axes), and `spectral_inband()` (band-filtered
  post-optics radiance vs λ [W/m²/sr/µm]) — plus two supporting module
  functions in `radiant.api.plot` (`plot_spectral_multi`,
  `plot_atmosphere_spectral`). Each accessor plots only real stored frames /
  stage outputs (no recomputation) and raises an actionable `ApiValidationError`
  when the required frame is absent. This carries the arch-doc §4.4 Source /
  Atmosphere / Spectral-Integration default views and unblocks the GUI Phase 4B
  Spectral detail tab. Public-surface addition; results-neutral.
- **GUI stage-strip navigation, per-stage default visualizations, and live health
  dots (GUI plan Phase 4 Task A).** The 9-stage signal-chain strip is now clickable:
  a click scrolls the parameter panel to that stage's namespace group and swaps the
  central canvas to the stage's default visualization (arch doc §4.4) — the derived
  geometry angle/range **readout** (values with units + symbols) for Geometry, an
  MTF overlay (`result.plot.mtf()`) for Optics/Platform/Performance, a noise-budget
  bar chart (`result.plot.noise_budget()`) for Detector/Readout, and a themed
  "visualization not yet available (Gap 86)" panel for Source/Atmosphere/Spectral
  Integration whose spectral-radiance figure the `result.plot` surface does not yet
  carry (no faked figure — ground rule §4.1). Every figure is one call on the public
  `result.plot.*` surface (no plotting in GUI code). The per-stage **health dots**
  now update live: gray/stale before a run and on any parameter edit, green after a
  clean run, yellow on a run with chain warnings (whole-run, not per-stage), red on a
  failed evaluation. Selecting a stage highlights its chip. Visual/UX capability
  only; results-neutral.
- **GUI display units — rows and the Parameter Editor show the user's unit (GUI
  plan Phase 3 checkpoint punch-list round 2, owner feedback 2026-07-13).** A
  parameter row now displays its value in the unit the user chose (an altitude set
  as 500 km reads `500 km`, not `500000 m`), not always the schema canonical/input
  unit. Committing a Parameter-Editor edit with an explicit unit adopts that unit as
  the row's display unit; the editor opens on it (Current line, value field, unit
  combo, and bounds), and inline Value-column edits interpret the typed number in it
  and write it back with the same unit (type `550` into a km row → `550000 m`
  canonical, row shows `550 km`). All canonical↔display conversion routes through the
  public `radiant.api.units` seam (no ad-hoc GUI maths); a unit that is not soundly
  convertible (offset/one-way) falls back to the canonical unit. The unit suffix is
  always part of the string. Session-scoped (QSettings persistence lands in Phase 9).
  Visual/UX capability only; results-neutral.
- **GUI in-window chain-warning strip (GUI plan Phase 3 checkpoint punch-list round
  2, owner feedback 2026-07-13).** Chain `UserWarning`s (saturation clip, NIIRS
  extrapolation, …) — which previously printed only to the terminal — are now
  captured by the evaluation worker and shown in a themed **warn-token** strip
  between the KPI badges and the canvas, reading `⚠ N warnings` with the first
  message inline and, clicked, opening a dialog listing all messages verbatim. The
  strip clears on a warning-free evaluation. Captured warnings are also re-logged, so
  nothing is swallowed (Rule 17). Visual/UX capability only; results-neutral.
- **`radiant.api.units.inverse_convert` re-export.** The public units seam now
  re-exports `inverse_convert` (canonical → display-unit) alongside `convert` and
  `_CONVERSIONS`, the sanctioned surface for output-side conversion (used by the GUI
  display-unit feature). Additive-offset and one-way units remain unregistered, so it
  is sound (invertible) for every registered conversion.
- **GUI Parameter Editor dialog (GUI plan Phase 3 checkpoint punch-list).** The
  parameter panel gains a full-detail editor box that opens on a parameter
  (double-click its Parameter or Source column, or right-click → **Edit…**) and
  shows the complete dot-path the narrow tree truncates, the schema description,
  the current value with unit + provenance, the bounds, and the derived/read-only
  state. It edits the value with a per-dtype control and, for a dimensional
  parameter, a **unit selector** populated from the units the conversion registry
  can convert to the canonical unit (public `radiant.api.units` seam, never a
  hardcode); it previews the resulting canonical value (enter `8` `km` → `= 8000 m`)
  and commits one `sensor.set(dotpath, value, unit=…)`, validated on a clone so a
  rejected value never touches the live sensor and its actionable error renders in
  the dialog. Derived parameters open read-only. The Value column keeps its
  existing fast in-place editor (two complementary edit paths). Visual/UX capability
  only; results-neutral.
- **GUI evaluate loop, live metric badges, and saturation banner (GUI plan
  Phase 3 — Milestone A / D2).** `radiant gui` now runs the full chain: opening
  or editing a config evaluates `sensor.evaluate()` on a background worker thread
  (the Qt thread never runs the chain), driven by Run → Evaluate (F5) or the
  accent Run button, and auto-re-evaluated after a 200 ms debounce on any
  parameter edit (full chain — no incremental engine, CU-079). The five KPI
  badges (SNR · NEDT · NIIRS · GSD · MTF@Nyquist) fill from the `ChainResult`
  metric surface with each value's unit sourced from the result metadata
  (`metric_records()`), a result-typed metric failure shows its `failure_reason`
  (never a blank), and the central matplotlib canvas renders the existing
  `result.plot.*` figure (default: the MTF overlay). A failed evaluation keeps
  the previous result on screen, flagged stale ("last evaluation failed"), and
  shows the actionable error (`RadiantError` → what/why/action; otherwise a
  traceback dialog). A **non-dismissible saturation banner** appears whenever
  `result.well_status().is_saturated`, showing the fill fraction and the
  accumulated-vs-capacity electrons with units, and clears on the next
  unsaturated result. Visual/UX capability only; the GUI is results-neutral (no
  computed-result or public-API change).
- **`ChainResult.well_status()` — full-well saturation on the result surface
  (CU-101).** The readout stage's well-capacity clip decision is now a
  first-class accessor returning a `WellStatus` record (exported as
  `radiant.api.WellStatus`): `.status` (`"ok"`/`"clipped"`, equal to
  `stage_outputs["readout"]["well_status"]`), `.is_saturated`, `.fill_fraction`
  (dimensionless), `.total_well_e` [e-], and `.full_well_capacity_e` [e-]. The
  readout stage additionally publishes `well_fill_fraction`, `total_well_e`, and
  `full_well_capacity_e` to `stage_outputs["readout"]` (serialization-safe, so
  the surface survives `save()`/`load()`). Lets the GUI saturation banner — and
  scripting users — read a metric instead of digging into `stage_outputs`; the
  underlying silent-clip trap (Gap 65) is now surfaced. Public-surface addition
  only; no computed-result change.
- **Schema-driven parameter tree in the GUI (GUI plan Phase 2, Task A —
  read-only half).** The parameter dock now populates a Parameter / Value /
  Source tree generated entirely from `Sensor.parameter_defs()` (never a
  transcribed list), grouped by dot-path namespace in chain order (geometry
  first). Each row shows the resolved value with its schema unit suffix; derived
  parameters carry a ⚡ marker; the Source column shows provenance (config /
  default / derived / user-set) read from the resolved set. A live filter box
  narrows rows by substring across dot-paths. Launched on a config the tree is
  populated; launched bare it shows a "no configuration loaded" state. Visual/UX
  capability only; no computed-result or public-API change.
  **Task B (editing):** non-derived rows are now editable in place — a
  schema-typed editor (combo for enums with schema-sourced choices, checkbox for
  bools, spin box for ints, line edit for floats/strings), each commit one
  `sensor.set`; rejected values (bounds / enum / consistency-group) render their
  actionable what/why/action inline and in a modal and never stick; right-click
  gives Copy dot-path, Explain (`sensor.explain`), and Reset to Default
  (`sensor.reset`).
- **`radiant gui` entry point and the `radiant.gui` package (GUI plan Phase 1,
  Task A).** A new PySide6 desktop-GUI shell — `launch_gui(sensor=None)` and the
  `radiant gui [CONFIG.yaml]` CLI subcommand — behind a new optional dependency
  group, `pip install "radiant[gui]"`. The GUI is a view over the scripting API
  (no physics, no computed-result changes); this phase ships only the window
  shell (menus, empty stage strip, dock panels, status bar). Without the `gui`
  extra installed, `radiant gui` raises an actionable error naming the remedy and
  the rest of RADIANT is unaffected. Not results-affecting.
- **GUI design-system theme (GUI plan Phase 1, Task B).** The shell now boots with
  the ratified design-system look (arch doc §8): a **light** QSS theme is applied at
  startup (the v1 launch default) with a **dark** alternate deriving from the same
  token set. `radiant.gui.themes` is the single owner of every colour, font, and
  spacing value; a mechanical test blocks any hardcoded colour/font literal elsewhere
  in the GUI. Visual change only — no computed results, no public API change beyond
  the internal `themes` helpers.

### Fixed
- **Embedded matplotlib plots no longer clip titles / axis labels / legends
  (owner feedback 2026-07-13).** Every `radiant.api.plot` builder (and thus every
  `ResultPlotNamespace` / `result.plot.*` figure) now uses matplotlib constrained
  layout instead of a one-shot `tight_layout()`, so titles, axis labels, and legends
  keep a reserved margin and re-fit on resize — fixing the cut-off "Source spectral
  radiance" title, the "MTF Budget" title overlapped by its legend, and edge-crowded
  axis labels in the GUI (and improving `savefig` output for script users too). The
  dense MTF-terms legend now sits inside the axes so it never reaches the title band at
  any canvas width. In the GUI, the MTF per-term table's first column shows its full
  "Contributor" header (was truncated to "trib…") and every column sizes to its
  contents; the MTF/noise panels' embedded canvases keep a minimum height so a short
  window scrolls rather than collapsing the figure. Visual only — no computed results
  changed.
- **GUI Parameter-Editor unit dropdown no longer clips (GUI plan Phase 3
  checkpoint punch-list round 2, owner feedback 2026-07-13).** The unit selector's
  popup previously truncated unit names to ~2 characters ("cr", "kı"); the combo now
  sizes to its contents and its popup view is sized to the widest unit label, so every
  unit reads in full. Visual only.

### Changed
- **Results-affecting: Earth radius unified to 6371.0 km mean (CU-097).**
  RADIANT previously used two Earth radii: the atmospheric slant-path /
  airmass geometry ran on the WGS-84 equatorial radius (6378.137 km) while
  slant range, incidence, ground range, and orbital kinematics used the
  6371.0 km mean radius. Both now use the single canonical
  `constants.R_EARTH_M = 6.371e6 m` (IUGG / US Standard 1976 mean). Nadir
  results are unchanged; off-nadir atmospheric path lengths and airmass
  shift at the sub-percent level (−0.11 % radius, e.g. the 60° reference
  slant path drops 195601 → 195566 m, ~0.018 %), in the
  correct-consistency direction (one triangle, one Earth). No golden
  baseline changed (all 14 sit at the nadir default).

### Removed
- **GUI bottom detail-tabs dock (contextual-layout retrofit Step B, arch doc §4.7).**
  The bottom `DetailTabs` dock and its five tab widgets are removed; their content is
  **relocated**, not discarded: the MTF and Noise Budget tabs became the embeddable
  `MtfPanel` / `NoiseBudgetPanel` (Optics / Detector center views), the Spectral tab's
  three figures became per-stage plot sections (Source / Atmosphere / Spectral
  Integration), the Variable Explorer tab became the global `InspectorDialog` tool, and
  the read-only YAML tab was superseded by the Step-A right-rail Edit Config (YAML) modal.
  The `View → Show/Hide Detail Panel` action is removed with the dock it toggled.
- **GUI global metric-badge row and floating warning strip (contextual-layout
  retrofit Step A).** The `KpiBadgeRow`, `MetricBadge`, and `WarningStrip` widget
  classes are retired: the metrics relocated to the right-rail Pinned cards and the
  warnings to the Messages panel (nothing user-facing is lost — badges → pinnable
  cards, strip → Messages). The accent Evaluate button that lived in the badge row
  moved to the central canvas run bar.
- `radiant.core` no longer exports `ObserverGeometry`, `TargetGeometry`,
  `SceneGeometry` (CU-094, ADR-0006 Phase 4). The flat-Earth scene
  dataclasses had zero consumers outside their own tests and were
  superseded by GeometryStage + `core.viewing_triangle`. The module's
  live functions (`slant_range_spherical_m`, `incidence_angle_rad`,
  Euler helpers) are unchanged.

### Deprecated
- `platform.h_sensor` → folded into `geometry.sensor_altitude_m` (CU-090,
  ADR-0006 Phase 3). One sensor altitude, one owner; the old name keeps
  working via `deprecated_aliases` (warn-and-redirect) for one release
  cycle. The no_atmosphere 'space' Earth-limb check now reads the
  canonical name (its error message names `geometry.sensor_altitude_m`).

### Added
- **Range-consistency enforcement (CU-093).** `geometry.target_range_m`
  set together with an explicit viewing angle now must agree with the
  angle-implied slant range within 1% or GeometryStage raises an
  actionable `GeometrySpecificationError`. A user range combined with
  *defaulted* viewing angles (mode V0) keeps the historical behavior —
  range drives regime/detection, nadir drives spatial metrics — but the
  previously silent disagreement now emits a `UserWarning` naming both
  distances.

### Fixed
- Lab/bench configurations with `geometry.sensor_altitude_m = 0` (sensor
  and target collocated) no longer trip the GeometryStage viewing
  triangle: the degenerate case publishes `None` slant/ground/incidence
  and the chain proceeds on the V0 range/regime path. (Regression
  introduced by the Phase-1 stage landing earlier today; caught in the
  CU-090 call-site audit — lab scenario scripts are not in the test
  suite.) Uplooking (`sensor below target`) still raises, per the
  owner-ratified v1 policy.

### Changed
- **Geometry input modes now steer the whole chain (ADR-0006 Phase 2).**
  SourceStage adopts the GeometryStage-published scene LOS (so the off-nadir /
  ground-range / elevation / site+time / night modes reach the atmospheric
  assembly and shape view directions); PlatformStage consumes the published
  slant range for velocity smear; PerformanceStage consumes the published
  slant range, incidence angle, ground range, and ground speed (GSD, ground
  metrics, diffraction ground projection, access rate — `circular_orbit`
  now yields `access_rate_m2_s` with no manual speed entry).
- **Results-affecting (off-nadir configurations only):** GSD, ground range,
  diffraction ground projection, and velocity smear now derive from the
  canonical target-side zenith θ_o via one spherical triangle
  (`core.viewing_triangle`, R_E = 6378.137 km), where they previously
  re-derived from `geometry.path_zenith_rad` *misread as the sensor-side
  off-nadir angle* on a 6371 km Earth (CU-096; CU-097). At nadir — every
  shipped golden baseline — values are unchanged (verified byte-identical).
  At off-nadir the new values are the physically consistent ones; e.g. at
  h = 500 km, θ_o = 45°: slant range 683.1 km (was 737.3 km when 45° was
  treated as the sensor-side η) — metrics that scale with slant range shrink
  by ~7 % there, more at steeper angles.

### Added
- `performance.gsd.compute_gsd_from_geometry` — GSD from already-derived
  (slant range, incidence angle); the legacy `compute_gsd(altitude, angle)`
  remains for direct callers (CU-096 tracks retiring it).

### Added
- **GeometryStage — geometry is stage 0 of the chain (ADR-0006).** The signal
  chain is now `geometry → source → … → performance` (9 stages;
  `ChainResult.history` and provenance `active_models` gain a leading
  `"geometry"` entry). The new stage owns the `geometry.*` namespace, resolves
  the scene-geometry input mode, and publishes every derived quantity once via
  `stage_outputs["geometry"]` (`los_geometry`, `theta_o_rad`, `eta_rad`,
  `slant_range_m`, `ground_range_m`, `incidence_angle_rad`, solar geometry,
  ground speed, and the mode labels). Zero numerical drift: existing
  configurations resolve exactly as before (all goldens byte-identical);
  downstream stages still read the canonical parameters until the Phase-2
  re-plumb (`docs/plans/Geometry_Stage_Plan.md`).
- **New geometry input modes** (published by the stage; chain-steering lands
  with Phase 2): `geometry.sensor_off_nadir_rad` (off-nadir η — wires the
  CU-005-reserved `theta_o_from_eta` converter), `geometry.ground_range_m`
  (surface-arc entry), `geometry.elevation_angle_rad` (grazing-angle entry),
  `geometry.solar_elevation_rad`, site+time solar inputs
  (`geometry.site_latitude_rad`, `geometry.day_of_year`,
  `geometry.local_solar_time_h`, `geometry.ltan_h` — wires the previously
  consumer-less `core.solar_geometry`), and `geometry.circular_orbit`
  (derives ground-track speed and orbital period from altitude via
  `core.orbit`). Over-specified or mutually inconsistent entries raise the
  new actionable `radiant.geometry.GeometrySpecificationError`.
- `core.viewing_triangle` — θ_o-referenced spherical viewing-triangle
  solutions (`eta_from_theta_o`, `slant_range_from_theta_o_m`,
  `ground_range_from_theta_o_m`, `theta_o_from_ground_range_m`).

### Deprecated
- `source.target.range_m` → renamed `geometry.target_range_m` (ADR-0006).
  The old name keeps working via `deprecated_aliases` (set/get redirect with
  a `DeprecationWarning`) for one release cycle.

### Changed
- Uplooking configurations (`geometry.sensor_altitude_m` at or below
  `geometry.target_altitude_m`) are now rejected by GeometryStage at the head
  of the chain with an actionable error, instead of surfacing later as the
  atmosphere Earth-limb check. Same v1 policy (uplooking rejection,
  owner-ratified 2026-07-11); earlier, clearer error site.

### Added
- MODTRAN downwelling zeroing now warns (Gap 81, partial): a
  MODTRAN-backed atmospheric state emits a `UserWarning` that the
  downwelling sky emission (`atm_emission_down` / `E_sky_thermal`) and
  scattered-solar sky radiance are set to zero (the standard IEMSCT=2
  tape7 carries no downwelling column) — switching `atmosphere.model`
  from `simple` to `modtran` no longer *silently* drops the thermal-band
  background terms. The full fix (ingest a separate downwelling run via
  `atmosphere.modtran.tape7_down_path`) is deferred on MODTRAN access.

### Fixed
- **Results-affecting (`simple` atmosphere, wavelengths > 5 µm only):**
  the aerosol Ångström power law is now clamped at the MWIR–LWIR boundary
  (5 µm) instead of extrapolating toward zero into the LWIR, where real
  aerosol extinction is absorption-dominated and roughly flat (CU-088).
  Beyond 5 µm the extinction is frozen at its 5 µm value (raising LWIR
  aerosol extinction vs the old extrapolation), and `SimpleAtmosphere`
  warns once per run when the clamp engages. MWIR (≤ 5 µm) and the golden
  baseline are unchanged; the clamp only affects LWIR `simple`-model runs.

### Changed
- **Results-affecting (only when `dark_activation_energy_eV > 0` and the
  reference was left at its default):** `detector.dark_reference_temperature_K`
  default changed 300 K → 77 K to match the `detector_temperature_K` default
  (CU-081), so the default config is self-consistent. With the default
  `dark_activation_energy_eV = 0` the dark rate is temperature-inert, so
  `dark_e` is unchanged for the default config and the golden baseline.

### Added
- Enum validation on `readout.tdi_mode` (`analog`/`digital`) and
  `detector.noise_regime` (`imaging`/`detection`) (CU-076): a typo now
  raises at resolve instead of silently selecting the wrong model
  (analog scaling / dropped spatial noise).
- Dark-current temperature-inertness warning (CU-081): when
  `detector_temperature_K` differs from the reference and
  `dark_activation_energy_eV = 0`, `DetectorStage` warns that the
  temperature setting has no effect on dark noise (a GUI temperature
  slider that silently does nothing).
- Validation hardening (CU-085): `Tolerance` now validates its
  distribution and required spread parameters at construction (a
  parameter-less gaussian previously sampled zero spread silently); the
  consistency-group over-specification check no longer skips when the
  first parameter lacks a derivation rule; velocity smear warns instead
  of silently returning 0 when altitude/integration time is missing; the
  IPC y-axis MTF uses the y pitch (was x — wrong for rectangular pixels);
  the CLI provenance version reads `radiant.__version__` (was hardcoded
  "0.1.0"); the `pixel_pitch_y_um` "defaults to x pitch" description
  (false — it is required) is corrected.
- SCNR and in-chain point-source detection range (Gap 77): new `scnr`
  metric (signal-to-clutter-plus-noise — target contrast over the
  clutter-inclusive total noise √(σ_temporal² + σ_spatial²), the detection
  figure of merit, unlike `snr`/`contrast_snr` which respect
  `noise_regime`); new `detection_range_m` metric, computed in the
  point-source regime by bisecting the Beer-Lambert solver to the range
  where SNR falls to the new `performance.detection_snr_threshold`
  parameter (default 5.0). New modules `radiant.performance.scnr` and a
  `radiant.performance._schema`. The detection range uses a constant
  atmospheric extinction (exact in vacuum; first-order for atmospheric
  paths) — the geometry-aware slant-path refinement is deferred (Gap 77
  narrowed). The wider acquisition-metric family (Pd/ROC, Johnson DRI,
  NEΔL/NEΔρ, D*/NEP/NEI) stays library-only pending GUI-phase surfacing
  (Gap 78).
- Orbit-derived ground velocity + duplicate collapse (Gap 75):
  `Sensor.set_ground_velocity_from_orbit()` derives
  `platform.ground_velocity_m_s` from `geometry.sensor_altitude_m` via the
  circular-orbit sub-satellite ground-track speed (`radiant.core.orbit`,
  previously wired to nothing). `platform.ground_velocity_m_s` and
  `geometry.ground_speed_m_s` — the same physical quantity, previously two
  independent fields that could silently disagree — are now a collapsed
  identity consistency group: setting either derives the other, and
  setting both to disagreeing values raises an over-specification error.
  (The analogous altitude duplicate `sensor_altitude_m` vs
  `platform.h_sensor` is deferred — CU-090.)
- Pushbroom/TDI scan-timing feasibility guard (Gap 74, minimum slice):
  when `platform.ground_velocity_m_s` is set, `PerformanceStage` computes
  the per-line dwell `t_dwell = GSD_along / v_ground`, stores it as the new
  `max_integration_time_s` metric, and warns when
  `spectral_integration.integration_time_s` exceeds it (the along-track
  image smears more than one ground sample per integration — an unphysical
  TDI timing whose SNR would otherwise look authoritative). New module
  `radiant.performance.scan_feasibility`. Parameter-gated: inert without a
  ground velocity, so existing results are unchanged.

### Fixed
- `ChainResult.signal_at(DN)` (and DN propagation generally) no longer
  raises when the well fully saturates (`signal_e_final = 0`) — a state
  now reachable when a bright point-source background pedestal fills the
  well (Gap 73). The `post_readout→dn` transfer factor falls back to the
  linear `1/gain` conversion, so a saturated pixel reports 0 DN instead
  of a missing-transfer-factor error. New readout output `gain_e_per_dn`.
- **Results-affecting (IPC coupling > 0 only):** the PSF-path IPC kernel is
  now resampled to the PSF sample grid (CU-083). The raw 3×3 kernel was
  convolved onto the sub-µm PSF grid, placing its α couplings one *sample*
  (not one pixel pitch) away — so the PSF-path IPC blur was orders of
  magnitude too small and diverged from the analytic MTF-product term.
  Now `ipc_kernel_pitch_spaced` places the couplings at ±pitch, so RER,
  FWHM, EE, and MTF-at-Nyquist reflect the correct IPC degradation
  (e.g. MTF at Nyquist × (1−4α)) and the dual-path consistency check
  passes. At `ipc_coupling = 0` (default, golden baseline) no kernel is
  built — golden unchanged. New `detector` stage output `ipc_kernel_psf`;
  the raw 3×3 `ipc_kernel` output is retained for provenance.
- **Results-affecting (fill_factor < 1 only):** `detector.fill_factor` now
  couples consistently across all three affected paths (CU-074). It is the
  areal photosensitive fraction, so a square photosite has linear width
  `pitch·√FF`: this width now drives BOTH the PSF-path pixel-aperture
  kernel and the MTF-product pixel sinc (previously the sinc used the full
  pitch, diverging the two Rule-4 paths and warning on every FF<1 run), and
  the collecting area `pitch²·FF` scales the radiometric signal (previously
  the full-pitch area was used, overcounting signal). Nearfield and stray
  electrons also scale by FF. Direction at FF<1: signal ↓ by factor FF,
  pixel MTF ↑ (narrower photosite). At FF=1 (the default and the golden
  baseline) every change is an exact no-op — golden unchanged.
- **Results-affecting (point-source regime only):** point targets now sit
  on a full-pixel background pedestal (Gap 73). Previously the
  point-source branch hardcoded `background_e = 0`, so a compact target
  against a bright background (daytime sky, sunlit cloud) had zero
  background shot noise and zero well fill from the sky — optimistic
  SNR/detection-range, and a discontinuous noise budget across the
  sub-pixel→point-source boundary. Now `background_e` is the full-pixel
  pedestal (same formula as the extended/sub-pixel background reference)
  when an at-aperture background frame exists; it feeds background shot
  noise and the readout well-fill (regime-gated — the pedestal is
  additional well charge only in point-source, where signal_e is
  target-only). Target signal and `contrast_e = signal_e` are unchanged;
  extended/sub-pixel results and the golden baseline are unchanged.
  Direction: point-source SNR against non-dark backgrounds decreases;
  magnitude scales with background radiance.

### Added
- Progress and cancellation hooks (Gap 72): `progress(done, total)` and
  `cancel() -> bool` keyword arguments on `Sensor.sweep`/`sweep_2d`/
  `monte_carlo`/`sensitivity` (and the underlying API functions) and
  `BatchRunner.run`. Cancellation raises the new
  `radiant.api.OperationCancelledError` (a `RadiantError` carrying
  operation/done/total). `solve_for` is excluded (unpredictable
  iteration count).
- `UnknownParameterError` (CU-073): typo'd parameter names in
  `set`/`get`/`reset`/`set_tolerance`/`parameter_def` now raise a
  `RadiantError` subclass (co-inheriting `KeyError` for back-compat)
  with the did-you-mean suggestion — the documented `except
  RadiantError` boundary now catches the most common user mistake.

### Fixed
- Parallel sweep crash (CU-072): `n_workers > 1` no longer dies with an
  unhandled `PicklingError` when the run function or its returned
  `ChainResult` cannot pickle (the common case — results carry
  `MappingProxyType` fields). Pickling failures are now caught at both
  submit time and result time and the sweep falls back to sequential
  with a logged warning, as originally documented.

### Added
- Non-scalar input reachability (Gap 68): `Sensor.set_stage_output(group,
  key, value)` and `Sensor.evaluate(extra_stage_outputs=...)` forward
  pre-chain injections to every evaluation, including all trade studies
  (sweep/sweep_2d/monte_carlo/sensitivity/solve_for). Optics
  transmission modes `spectral_file`/`telescope_plus_filters`/
  `key_elements` and stray-light `spectral_file` now actually consume
  their `optics_config` injections (previously these schema-selectable
  modes raised unconditionally); injected curves are resampled onto the
  chain grid with a loud out-of-coverage error.

### Changed
- `optics.transmission_input_mode`, `optics.wfe_mode`, and
  `optics.stray.input_mode` now validate against explicit enum values
  (Gap 68). The always-raising modes `opd_map` (no pupil-phase
  representation in v1) and `pst_file` (needs a scene radiance
  distribution v1 lacks) are no longer offered — setting them now fails
  at `params.set`/resolve with the allowed list instead of deep in the
  optics stage.

### Added
- Metric metadata contract (Gap 71): every computed metric now carries a
  non-empty unit, description, and kind via the reconciled metric
  registry; new `ChainResult.metric_records()` returns unit-labelled
  `MetricRecord` tuples, and `radiant.performance.metric_info(name)`
  exposes single-metric metadata. `MetricSpec` gains
  `unit`/`description`/`kind`/`requires_mtf_terms` fields.

### Removed
- Metric registry phantoms (CU-078): the never-computed registry
  entries `nedt`, `nedl`, `nedr`, `csnr`, `ee`, `edge_slope`,
  `detection_range`, `saturation_margin`, `dynamic_range` are gone;
  the catalog now registers exactly the 32 keys the performance stage
  computes (real keys: `nedt_K`, `ee_1x1`/`ee_3x3`,
  `well_margin_dB`/`adc_margin_dB`, `dynamic_range_dB`, …).
  NEΔL/NEΔρ/edge-slope/detection-range specs return with the commits
  that compute them (Gaps 77/78). Reconciliation is CI-enforced.

### Added
- Persistence (Gap 67): `Sensor.save(path)` / `Sensor.load(path)` —
  YAML round trip of explicit inputs, tolerance distributions, and
  `wavelength_points` via a new `_radiant` config metadata block
  (`RADIANT_Config_Format.md` §1.7); reloading reproduces the original
  resolution and provenance exactly. `ChainResult.save(path)` /
  `ChainResult.load(path)` — single-file zip archive (JSON manifest +
  npz arrays) holding the full ChainState with dtype-preserving,
  full-fidelity reload and the provenance record frozen at save time.
  Supporting public surface: `ParameterSet.inputs()`,
  `radiant.io.config.read_radiant_meta()`, `save_config(scope=)`,
  `radiant.io.serialization` (`ResultArchiveError`,
  `UnserializedValue`).
- Public schema-introspection API (Gap 70): `ParameterSet.parameter_defs()`,
  `parameter_def(name)`, `consistency_groups()`, `tolerances()`,
  `is_resolved`, and `copy()`, plus `Sensor.parameter_defs()` /
  `Sensor.parameter_def(dotpath)` passthroughs. GUIs/CLIs/sweep tooling
  can now enumerate the full parameter schema (dtype, units, bounds,
  enums, defaults, descriptions, tags) without touching private state;
  all framework consumers migrated off the `_defs`/`_groups`/`_inputs`/
  `_tolerances`/`_resolved_flag` privates. Side effect: sweep- and
  sensitivity-cloned ParameterSets now carry loaded-file provenance
  records (previously dropped by the private clone path).

### Fixed
- **CU-065 (deck-side):** `render_tape5` now converts RADIANT's
  lower-endpoint path zenith to MODTRAN's Card 3 ANGLE-at-H1
  convention: downlooking decks render `180° − zenith` (a nadir
  space sensor renders ANGLE = 180, previously 0), uplooking decks
  are unchanged. Matches `modtran_run_matrix.csv`'s hand-worked
  `modtran_angle_at_h1_deg` column for every ITYPE=2 row; the
  rendered decks in `modtran/decks/` (regenerable) are what a real
  MODTRAN run will consume. No computed chain result changes (no
  binary has ever run), but downlooking tape5 decks — and therefore
  their SHA-256 cache keys — differ from pre-fix renders. CU-065's
  remaining residue: confirm the convention against the MODTRAN
  manual on access.

### Added
- `atmosphere.modtran.tape7_sun_path` (CU-011, file flavor): optional
  sun-leg tape7 for the Option C two-leg split. When set (requires
  `tape7_path`), `tau_sun` comes from the sun-leg file's transmittance
  instead of aliasing the up-leg value, the single-τ collapse
  `UserWarning` is not emitted, and the assembly's direct-solar term
  consumes the split. Unset, behavior is unchanged (alias + warning).
  The binary-invocation two-run flavor and real-MODTRAN physics parity
  remain deferred under CU-011.
- `atmosphere.modtran.tape7_path`: first-class MODTRAN tape7 file import.
  Setting it (with `atmosphere.model="modtran"`) builds the atmospheric
  state directly from a tape7 file produced elsewhere — parsed before
  chain execution (Rule 6), no MODTRAN binary, cache, or fallback
  involved. Replaces the manual side-door (Tape7Reader → temp CSVs →
  `atmosphere.model="tabulated"`) that every consumer hand-rolled;
  outputs are identical to that side-door (integration-tested to exact
  equality). Unset, the binary/cache/fallback behavior is unchanged.
  Like tabulated files, an imported tape7 is geometry-agnostic, and
  airborne targets (`h_tgt > 0`) are rejected. See
  `RADIANT_Atmosphere.md` §5.1.

### Changed
- **CU-066:** `Tape7Reader` now locates MODTRAN tape7 columns by their
  header label (left-to-right order of appearance), not a fixed token
  index. The prior positional mapping would have silently swapped
  `path_scattered_radiance` and `ground_reflected_radiance` with the
  wrong columns (THRML SCT / SURF EMIS instead of SOL SCAT / GRND
  RFLT) on real MODTRAN output, and could ingest numeric card-echo
  lines as spectral data. No shipped result is affected — no
  MODTRAN-derived value has ever been computed by RADIANT. Tape7
  files with no recognisable header now emit a `UserWarning` and use
  the old positional mapping as a documented fallback.
- **Results-affecting (NEDT, small):** exact band-integrated NEDT dS/dT
  (Gap 43). `SpectralIntegrationStage` now computes
  `dS/dT = ∫ (signal integrand)·(∂B/∂T)/B dλ` — the exact Planck
  log-derivative over the band — and `PerformanceStage` uses it (σ/(dS/dT))
  in place of the single-λ (band-center) Planck-factor approximation. The
  two agree **exactly** in the narrow-band limit; over a wide band NEDT
  shifts by the Planck band curvature: ~+0.3% / −0.2% for LWIR cells,
  ~+4.5% for a 3.5–5 µm MWIR band. No golden baseline asserted NEDT; the
  two pinned Option-C LWIR anchors were repinned with provenance. The
  single-λ form remains the fallback when no target temperature is set.

### Added
- `ParameterDef.required_unless` (Gap 66): a required parameter may now
  name an alternative that supersedes it — when the alternative is
  explicitly set, the requirement is waived and the parameter is left
  unresolved (never phantom-populated). First use: `detector.qe_value`
  is required unless `detector.qe_table_path` is set, so a spectral QE
  CSV now works WITHOUT also setting a meaningless scalar QE — the
  schema always documented the table as superseding the scalar, but the
  resolver rejected the config ("Required parameter 'detector.qe_value'
  is not set"); scenarios 1.1 and 1.2 both hit this and worked around
  it by band-averaging. The required-parameter error message now also
  names the superseding alternative when one exists.
- Saturation warnings (Gap 65, Rule 17): `ReadoutStage` now emits a
  `UserWarning` whenever the well-capacity or ADC saturation check clips
  the signal, naming the exceeded ceiling, the clipped value, and the
  remedies (integration time / gain / ADC bits / FWC). Previously both
  clips were silent outside `stage_outputs["readout"]["well_status"]` /
  `["adc_status"]`, which cost three scenarios (6.1, 6.2, 8.2) real
  debugging time on bit-identical "no effect" results. No computed
  values change — warning only.
- MODTRAN deck-builder fields, opt-in (CU-063/064/069): `ModtranConfig.visibility_km`
  (`float | None`, default `None` = IHAZE default) threads to Card 2 VIS;
  `ModtranConfig.itype` (`int`, default `2`) and `ModtranConfig.iemsct`
  (`int`, default `2`) thread to Card 1, adding ITYPE=3 (slant path to
  space) and IEMSCT=3 (solar/lunar irradiance mode). All defaults
  reproduce the pre-change tape5 deck byte-for-byte.
- Veiling-glare spatial halo, opt-in (Gap 60 partial): new parameters
  `optics.stray.veiling_glare_mtf` (int 0/1, default 0) and
  `optics.stray.halo_sigma_um` (default 50 µm). When enabled with
  `veiling_glare_fraction > 0`, the stray fraction is re-imaged as a
  Gaussian halo entering BOTH spatial paths (Rule 4): kernel
  `(1−vgf)·δ + vgf·G(σ)` on the `EffectivePSF` and the exact Fourier
  pair `(1−vgf) + vgf·exp(−2π²σ²f²)` on the MTF product
  (`mtf_stray_x/y`) — the low-frequency contrast-modulation loss the
  CU-062 radiometric pedestal cannot express. Default-off: existing
  results are bit-identical; enabling it is results-affecting for
  veiling-glare configs (MTF/RER/NIIRS drop toward the (1−vgf) floor).
  The 2-D PST/vendor-PSF import (`pst_file`) stays deferred
  (single-pixel scope decision).
- ROC / detection-probability model (scenario 6.4):
  `radiant.performance.roc` — `roc_curve` (P_d vs P_fa from a detection
  index / contrast SNR), `detection_probability` (`Q(Q⁻¹(P_fa)−SNR)`), and
  `roc_auc` (`Φ(SNR/√2)`) for the equal-variance Gaussian model. New error
  class `RocError`. No chain change.
- Multi-frame persistence sequence (scenario 2.4):
  `radiant.detector.persistence_sequence` — `persistence_residual_e` /
  `persistence_residual_sequence_e` (residual ghost signal
  `prior·f·exp(−(n−1)Δt/τ)` over a frame sequence) and `frames_to_clear`
  (frames until the residual drops below one LSB). Extends the existing
  single-frame `persistence_noise` term to the temporal domain. New error
  class `PersistenceSequenceError`. No chain change.
- Temperature retrieval + emissivity/temperature Jacobian (scenario 6.5):
  `radiant.performance.temperature_retrieval` — `retrieve_temperature_K`
  (invert a measured band radiance for surface T given an assumed ε, via
  Brent), `band_planck_radiance`, and the Jacobians `emissivity_jacobian`
  (∂L/∂ε = B̄(T)) and `temperature_jacobian` (∂L/∂T = ε·∫dB/dT). New error
  class `TemperatureRetrievalError`. Analysis model — no chain change.

### Added
- `geometry.solar_illumination` day/night toggle (Gap 59): `night` removes
  the solar terms for reflective/mixed (T2/T3) targets (`theta_s = None` —
  no direct-solar reflection, no single-scatter solar sky) while thermal
  self-emission and reflected thermal downwelling remain. Previously the
  `solar_zenith_rad` schema default (0.5 rad) gave every T2/T3 scene a
  phantom daytime sun and night was inexpressible. The `day` default
  preserves every existing configuration bit-for-bit.
- Spectral GroundBackground ε_g(λ) (CU-008): two new parameters give the
  sub-pixel/point-source background a spectral emissivity surface —
  `source.background.material` (a named `radiant.data.SpectralLibrary`
  entry: vegetation_green, snow, soil_dry, asphalt, … ; default `grey`
  keeps the exact scalar back-compat path) and
  `source.background.emissivity_path` (measured two-column CSV; wins over
  material). Resolution happens in the API layer pre-chain (Rule 6) and is
  injected via `stage_outputs["source_config"]["background_emissivity"]`.
  The Stage-2 "grey placeholder" `UserWarning` is removed — grey is now an
  explicit choice, and all existing sub-pixel configs are numerically
  unchanged. Unknown material names are rejected with the legal
  vocabulary.
- `source.lab_test_mode` parameter (Gap 40): positive `dark`/`lit`
  assertion for the ground_test/lab_test sub-cases. `dark` declares a
  no-external-illumination configuration (the D-lab dark-cal sub-mode) and
  is validated — a user-set `source.target.reflectance` contradicts it and
  is rejected with an actionable error; `lit` is a recorded assertion;
  the empty-string default is unasserted and preserves every existing
  config byte-for-byte.
- Stage-scoped error classes (CU-043, Rule 15): every stage package now
  exposes a `<Stage>ValidationError(RadiantError, ValueError)` — plus
  `CoreStateError`, `AtmosphereStateError`, and
  `SpectralIntegrationStateError` co-inheriting `RuntimeError` — in its
  `errors.py` (`CoreValidationError`/`CoreStateError` live in
  `core/exceptions.py`). All 428 bare `raise ValueError`/`RuntimeError`
  sites across core, the eight physics stages, and `api/` were migrated to
  these classes, so `except RadiantError` now catches every framework
  rejection. **No behavioral change for existing code**: the classes
  co-inherit their historical built-in type (the sanctioned Rule 15
  back-compat carve-out), so `except ValueError` /
  `pytest.raises(ValueError)` call sites keep working unchanged. A
  regression guard (`tests/test_exceptions.py::TestNoBareBuiltinRaises`)
  forbids new bare built-in raises.

### Changed
- **Results-affecting (PSF-path spatial metrics; small):** the
  pixel-aperture rect kernel is now sampled by exact area overlap
  (anti-aliased edges) instead of a binary inside/outside mask (CU-003
  option a). The binary mask quantised the rect width to the PSF sample
  grid, over- or under-blurring by up to half a sample; MTF-at-Nyquist,
  RER, and EE shift by a few percent in configurations where the grid did
  not divide the pitch (Option-C anchors: Cell 28 MTF@Ny +5.6%, Cell 58
  +7.9% — repinned with provenance). FFT-vs-analytic-sinc agreement
  improves ~13× (4.5e-2 → 3.6e-3 at Nyquist, worst config); the worst
  full-chain dual-path residual drops from ~5.8e-2 to ~1e-2. Radiometric
  goldens (signal/noise/SNR) are unaffected.
- Dual-path consistency default tolerance tightened 5e-2 → 2e-2 (CU-045):
  ~2× margin over the worst measured full-chain residual after CU-003.
  The check remains warn-only by design — it is a diagnostic invariant,
  and raising would abort runs whose physics is otherwise valid.
- **Results-affecting (non-default atmosphere profiles; large in
  water-sensitive bands):** the `atmosphere.standard_atmosphere` preset now
  carries its standard water column (Gap 57). When
  `precipitable_water_cm` is left at its schema default, the simple-model
  loader substitutes the profile's McClatchey/MODTRAN column
  (tropical 4.11 cm, midlat_summer 2.92, midlat_winter 0.85,
  subarctic_summer 2.08, subarctic_winter 0.42; us_standard stays 1.4) —
  previously "tropical" silently ran US-standard humidity. An explicitly
  set `precipitable_water_cm` always wins (provenance-based). Configs
  using a non-default profile without explicit PWV shift: the
  `mwir_leo_minimal` golden (midlat_summer) drops 52% in signal / 31% in
  SNR (more water → less MWIR transmission; regenerated via
  `update_golden.py` with the §5.3 protocol), and the Cell-28 LWIR anchor
  repins NEDT +0.9% / L@8µm −34%. Default-everything (us_standard)
  configs are bit-identical.

### Fixed
- **Results-affecting (defocused configs; moderate):** defocus is now
  unified as pupil Zernike Z4 on BOTH spatial paths (CU-058, Rule 4). The
  PSF path previously applied a Gaussian kernel (σ = |δ|/(4·f/#·√3)) while
  the MTF product path folded Z4 into the pupil — and, when scalar-RMS WFE
  was combined with defocus, discarded the RMS screen entirely, so any such
  config structurally failed the dual-path consistency check (scenario 7.3:
  max_err 0.169 vs tol 0.05). Now `_add_defocus_to_wfe` preserves the
  scalar-RMS screen (screen + Z4 in one pupil phase), the fold happens once
  before both paths, and the former Gaussian defocus kernel — plus the
  `optics.defocus` module (`defocus_kernel_2d`, `defocus_sigma_m`) and the
  `defocus_sigma_m` stage output — are removed. PSF-path spatial metrics for
  defocused systems change (Gaussian → true Z4 defocus OTF, ~few % at
  moderate defocus); configs with `defocus_um = 0` (all goldens) are
  unchanged. Also fixes a latent reference-wavelength bug: the folded Z4 is
  now rescaled to the WFE's reference wavelength, so the defocus OPD is
  correct when `reference_wavelength_um` differs from band center. All three
  pupil-phase dispatch sites now share one builder
  (`pupil_phase.make_pupil_phase_for_wfe`).
- Saturated `contrast_snr` is now flagged, not reported silently (CU-061).
  When the pixel saturates the readout caps the signal (and its shot noise)
  at full well but the contrast ΔS is not re-derived from the clipped
  signals, so `contrast_snr = ΔS/σ` was inflated and unreliable.
  `compute_contrast_snr` now detects the clip (`signal_e_final < signal_e`),
  emits a `UserWarning`, and sets `failure_reason` on the `contrast_snr_result`
  (so `.ok` is False). The metric value is unchanged for unsaturated runs
  (no golden impact); only the flag/warning are new.
- **Results-affecting (stray light / noise; large where used):** veiling-glare
  stray light (`optics.stray.input_mode = veiling_glare`) was effectively
  inert (CU-062). `OpticsStage` scaled the in-FOV image-plane irradiance by
  the pixel IFOV solid angle `Ω_pixel = pitch²/focal²` instead of the f-cone
  solid angle `Ω_cone = A_collect/focal²`, under-counting stray by
  `A_collect/A_pixel ≈ (D/pitch)²·π/4` (~10⁷–10⁸) so any `veiling_glare_fraction`
  produced ~zero stray. Now `stray_e = vgf × signal_e` for a uniform extended
  scene. Only affects runs using `veiling_glare` mode with a non-zero fraction
  (default 0.0 → no change; goldens unaffected); such runs gain the correct
  stray-light shot-noise penalty (lower SNR/NIIRS). `absolute_irradiance` and
  `spectral_file` modes were already correct.

### Changed
- Lab/ground-test scenarios reachable from the config surface (Gap 42):
  `source.no_atmosphere_subcase` ∈ {`ground_test`, `lab_test`} now builds a
  grey-body chamber/test-range background `L_bg(λ) = ε_bg·B(λ, T_bg)` from
  `source.background.temperature`/`.emissivity` (which Decision #15 makes
  valid for the no-atmosphere sub-cases) instead of raising and requiring a
  manual `UserSpectralBackground` injection. Warns if the chamber
  temperature is left at the schema default (Rule 17). A measured `L_bg(λ)`
  can still be injected directly. **Behaviour change:** these sub-cases
  previously raised `ParameterBoundsError` at inference; they now run. No
  golden change (no golden used these sub-cases).

### Added
- Spectral target emissivity input (Gap 47): new parameter
  `source.target.emissivity_path` — a 2-column `(wavelength_um, emissivity)`
  CSV. When set, the source inferrer builds the thermal descriptor with a
  spectral ε(λ) (`L_t(λ) = ε(λ)·B(λ, source.target.temperature)`) instead of
  a grey scalar, reusing the existing `SpectralData` emissivity that
  `T1Thermal`/`T3Mixed` already accept. Mutually exclusive with the scalar
  `source.target.emissivity` and every reflective / radiance /
  brightness-temperature surface (raises `ParameterBoundsError`). Opt-in;
  goldens unchanged. Retires the S8 `user_radiance_path` workaround for
  spectral-emissivity thermal targets (scenario 4.3).
- Minimum resolvable temperature / contrast (Gap 53):
  `radiant.performance.minimum_resolvable` —
  `minimum_resolvable_temperature_K` (MRT = k·NETD/MTF_sys(f)) and
  `minimum_resolvable_contrast` (MRC = k·NEΔρ/MTF_sys(f)), the
  contrast-limited resolution metrics (k = 2.25 observer SNR default). New
  metric `mrt_at_nyquist_K` (additive; requires NEDT + MTF). New error
  class `MinimumResolvableError`. Companion to the sampling-limited Johnson
  model; consumed by scenario 3.5.
- Extended target-vs-background contrast (ADR-0005, Gap 52): new
  parameters `source.contrast_reference.temperature` and
  `source.contrast_reference.emissivity` make `contrast_snr` a true
  two-pixel spatial differential in the extended regime — `ΔS = S_target −
  S_reference`, combined noise `√(N_t² + N_ref²)` — which nulls at the
  radiance crossover. The reference is metric-only: it never enters the
  noise budget, so absolute SNR (and Decision #13's pinned anchors) are
  unchanged. Opt-in (`temperature = 0` disables it, the default), so no
  golden result moves. Supersedes the two-pixel-differencing workaround in
  scenarios 4.3/4.4. New error class n/a; explicitly distinct from the
  deprecated `source.background.*` (Decision #15).
- D*/NEP/NETD noise-spec converters (scenarios 6.1, 4.5 prerequisite):
  `performance/detectivity.py` (`nep_from_dstar`/`dstar_from_nep`,
  `D* = √(A·Δf)/NEP`), `performance/nep_electrons.py`
  (`nep_from_noise_electrons`/`noise_electrons_from_nep`,
  `NEP = σ_e·hc/(η·λ·t_int)`, plus `integrating_bandwidth_hz`), and
  `performance/nep_netd.py` (`netd_from_nep`/`nep_from_netd`,
  `NETD = NEP/(dP/dT)`). Standard radiometric definitions relating
  datasheet detector figures of merit to the chain's electron-domain
  noise. New error classes `DetectivityError`, `NepElectronsError`,
  `NepNetdError`. No chain change.
- QE temperature dependence (Gap 48): new parameters
  `detector.qe_temperature_coeff_per_K` and `detector.qe_temperature_ref_K`
  apply a linear QE(T) factor `1 + coeff·(T_det − T_ref)` to the scalar
  `qe_value` or the `qe_table_path` curve, folded in at the API layer.
  **Results-affecting only when `coeff ≠ 0`** (lower/higher QE shifts SNR
  and NEDT); the default `coeff = 0` is byte-identical (goldens intact).
  QE is clamped to [0, 1] with a `UserWarning` if the factor pushes it out
  of range (Rule 17).
- Spectral QE from a file (Gap 44): `detector.qe_table_path` — a
  schema-only parameter until now — is wired. When set, `RadiantSession`
  loads the wavelength-vs-QE CSV (`io.qe_csv`, Rule 6: file I/O in the api
  layer) onto the wavelength grid and applies it spectrally, superseding
  the scalar `detector.qe_value`; QE past the measured cutoff is zero.
  Absent a path, the scalar `qe_value` behaviour is unchanged (goldens
  intact).
- Arbitrary / measured pupil-mask injection (Gap 54): inject
  `optics_config["pupil_mask_override"]` (a `(pupil_npix, pupil_npix)`
  amplitude array) via `extra_stage_outputs` to supersede the parametric
  circular/obscuration/spider pupil — for segmented or non-circular
  apertures. Threaded through `make_pupil_amplitude` into both the PSF and
  MTF paths (Rule 4). No default-behavior change (absent ⇒ parametric
  mask; 504 optics + 10 golden tests unchanged).
- Detector figures of merit (Gap 45): `performance/dark_crossover_rate.py`
  (`dark_shot_crossover_rate_e_per_s` = σ_read²/t_int),
  `performance/blip_rate.py` (`blip_rate_e_per_s` = signal_e/t_int), and
  `performance/noise_equivalent_irradiance.py`
  (`noise_equivalent_irradiance_ph_s_cm2`). Standalone helpers for the
  detector cooler-budget/sensitivity trade; new error classes. No chain
  change.
- Radiometric-calibration analysis (Gap 46):
  `radiant.api.calibration_analysis` — `analyze_calibration` → a
  `CalibrationReport` (gain/offset fit, temperature & radiance
  responsivity, linearity residuals % full-scale, N-frame temperature
  uncertainty), plus the underlying `gain_offset_fit`,
  `linearity_residuals_pct_fs`, etc. New error `CalibrationAnalysisError`.
  Pure sweep-array analysis; no chain change.
- Repeat-ground-track & revisit model (Gap 51):
  `radiant.core.repeat_ground_track` — `nodal_regression_rate_deg_per_day`
  (J2 secular Ω̇), `sun_synchronous_inclination_deg`,
  `equatorial_ground_track_spacing_m`, and a first-order
  `revisit_interval_days`. New Earth constant `J2_earth`; new error class
  `RepeatGroundTrackError`. Standalone analysis model — no chain change.
- Diffraction-limited-resolution metrics (Gap 49):
  `diffraction_limit_angular_urad` (Rayleigh `1.22 λ_c / D`) and
  `diffraction_limit_ground_m` (projected to the slant range, companion to
  GSD) in the new `performance/diffraction_limit.py`. Analysis outputs
  only — no existing result changes.
- Sampling-regime flag (Gap 50): `sampling_regime_code` metric
  (0 detector-limited / 1 near-critical / 2 diffraction-limited, from
  `q_center`) in the new `performance/sampling_regime.py`. New error
  classes `DiffractionLimitError`, `SamplingRegimeError`. Additive
  metrics; goldens unchanged.
- Spider-vane / secondary-support struts (scenario 1.5 prerequisite):
  new optics parameters `optics.n_spiders`, `optics.spider_width_m`,
  `optics.spider_angle_deg` implement RADIANT_Optics.md §3.3 (previously
  aspirational). Struts enter the pupil amplitude mask
  (`make_pupil_amplitude` via the new `SpiderVaneSpec`), so they degrade
  **both** spatial paths (PSF and MTF) per Rule 4, and subtract from the
  radiometric clear area (`CircularAperture.clear_area_m2`).
  **Results-affecting only when `n_spiders > 0` and `spider_width_m > 0`**
  — lowers SNR (less collecting area), EE_box, and RER (diffraction
  spikes); the `strehl` metric is unaffected (vanes are common-mode in
  the WFE reference). Default (no struts) reproduces all existing results
  byte-for-byte (496 optics + 10 golden tests unchanged).
- Johnson-criteria DRI calculator (scenario 4.2 prerequisite):
  `radiant.performance.johnson_criteria` — `johnson_range_m`,
  `resolved_cycles`, and the standard `JOHNSON_N50` cycle table
  (detection/orientation/recognition/identification). Computes the range
  at which a discrimination task's N50 cycles are resolved across a
  target's critical dimension (`R = D / (2·IFOV·N50)`). Sampling-limited
  form (no MRT/MRC coupling). New error class `JohnsonCriteriaError`.
- Orbit-kinematics calculator (scenario 3.1 prerequisite):
  `radiant.core.orbit` — `orbital_velocity_m_s`, `orbital_period_s`, and
  `ground_track_speed_m_s` for a circular LEO altitude (two-body,
  spherical Earth, non-rotating ground track). Feeds the
  `ground_speed_m_s` input that `performance.access_rate` could not
  itself compute. New Earth gravitational-parameter constant
  `mu_earth_m3_s2` in `core.constants`; new error class `OrbitError`.
- Solar-geometry calculator (scenario 1.2 prerequisite):
  `radiant.core.solar_geometry` — `solar_zenith_angle_rad(latitude_deg,
  day_of_year, local_solar_time_hr)`, `solar_declination_deg`
  (Spencer's series), and `local_solar_time_from_ltan` for
  sun-synchronous orbits. Converts date/latitude/LTAN into the solar
  zenith angle for `geometry.solar_zenith_rad`. New error class
  `SolarGeometryError`.
- ASTER spectral-library import (scenario 1.3 prerequisite):
  `radiant.io.aster_library.load_aster_spectrum` parses JPL/NASA ASTER
  library text files (metadata header + wavelength/reflectance columns,
  descending order handled) into an `AsterSpectrum` with `emissivity()`
  (ε = 1 − ρ, opaque scene material) and `band_averaged_emissivity()`.
  New error class `AsterLibraryError`. No extrapolation outside the
  measured range.
- Batch matrix execution (scenario 4.1 prerequisite):
  `radiant.api.batch.BatchRunner` — the `BatchRunner` named in the
  architecture's api layout — runs one evaluation per cell of a labeled
  cartesian grid (targets × atmospheres × sensors), with per-cell
  parameter overrides and Rule 17 failure capture (a failed cell is a
  recorded `error` row, never silently dropped). Returns a `BatchResult`
  with a `pivot()` helper. New error class `BatchRunnerError`.
- Target-library import (scenario 4.1 prerequisite):
  `radiant.io.target_library.load_target_library` reads a mission target
  list workbook into validated `TargetEntry` objects with derived
  `projected_area_m2`; lazy openpyxl (actionable error naming the
  `[scenarios]` extra). New error class `TargetLibraryError`.
- Vendor detector-datasheet importers (scenario 2.1 prerequisites):
  `radiant.io.qe_csv.load_qe_csv` reads wavelength-vs-QE vendor CSVs
  (nm/µm × percent/fraction, header-token or explicit unit resolution)
  into a canonical-units `QeCurve` with grid evaluation and band
  averaging; `radiant.io.dark_current_csv.load_dark_current_csv` reads
  `T_K, Jdark_A_cm2` curves into a `DarkCurrentCurve` with
  Arrhenius-faithful interpolation (ln J linear in 1/T),
  `dark_rate_e_per_s(T, pixel_pitch_m=)` conversion (J·A_pixel/q), and
  the inverse `temperature_at_rate`. New error classes `QeCsvParseError`
  and `DarkCurrentCsvParseError` (both `RadiantError`). Neither loader
  extrapolates outside the measured range by default.

### Fixed
- Scatter (Gap 31) and defocus (Gap 29) kernel sizing crashed with
  `ValueError: npix must be a positive odd integer, got 256` whenever
  the 6σ kernel span exceeded the PSF grid — the odd-forcing happened
  before the cap to the (even) grid size. The cap now clamps to the
  largest odd size within the grid. Fine-spacing configurations (VNIR
  band, small pixels) with `optics.surface_roughness_nm` or large
  `optics.defocus_um` now run; no numeric change for configurations
  that previously ran. Found by the scenario 7.3 refresh.

### Deprecated
- `optics.cold_stop_efficiency` renamed to `optics.nearfield_fraction`
  (Gap 12) — the old name inverted the vendor convention ("100%
  efficient cold stop" = complete blocking, but η=1 here means *no*
  cold stop). Same semantics, no numeric change:
  `nearfield_fraction = 1 − vendor_cold_stop_efficiency`. The old name
  still works via a new parameter-alias mechanism
  (`ParameterDef.deprecated_aliases`) with a `DeprecationWarning`, and
  will be removed in a future release.

### Fixed
- **Results-affecting (labels/exports only):** the MTF product-path
  frequency grid `ChainState.spatial_freq_cycles_per_mrad` (and
  `MTFBudgetResult.freq_cycles_per_mrad`) stored values 1e6× true
  cycles/mrad (conversion used `× f·1e3` instead of `× f·1e-3`). All
  internal consumers round-tripped with the same inverse factor, so
  MTF curves, metrics, and golden results are unchanged — but the grid
  values themselves and the cycles/mrad axis of `result.plot.mtf()`
  now read correctly (e.g. 33.3 cy/mrad at Nyquist for an 18 µm pixel
  at f = 1.2 m, previously 3.33e7). Found during Gap 27.

### Added
- `scenarios` optional-dependency group (`pip install -e ".[scenarios]"`):
  openpyxl + matplotlib, required by the scenario run scripts (CU-057).
- Zemax Zernike importer (Gap 26): `radiant.io.zemax_zernike.
  load_zemax_zernike` parses "Zernike Standard Coefficients" text
  exports (Noll-indexed waves, UTF-8/UTF-16 tolerant) into the existing
  Zernike WFE pipeline via `ZemaxZernikeResult.to_wavefront_error()`.
- Measurement import + comparison (Gap 30):
  `radiant.io.measurement.load_measured_curve` (CSV → `MeasuredCurve`)
  and `radiant.api.compare.compare_mtf` (unit-aware measured-vs-predicted
  MTF residuals, overlap-only interpolation). Excel import out of scope
  (CSV export required).
- Surface-roughness scatter (Gap 31): new `optics.surface_roughness_nm`
  and `optics.scatter_halo_sigma_um` parameters drive a TIS model
  (`optics/scatter.py`): TIS = 1 − exp(−(4πσ/λ)²), scattered fraction
  into a Gaussian halo. **Results-affecting only when roughness is set
  nonzero** — lowers MTF/RER at all frequencies via both spatial paths
  (Rule 4 Fourier pair); default 0 preserves all results.
- MTF budget reporting (Gap 19): `MTFBudgetResult.table()` and
  `plot_mtf_budget` / `ResultPlotNamespace.mtf_budget()` — human-facing
  views over the existing per-contributor MTF-at-Nyquist decomposition.
- `Sensor.solve_for(param, target, bounds=, metric=)` (Gap 10): inverse
  solver — Brent root-finding for the parameter value that hits a target
  metric, replacing sweep-and-interpolate. New `api/solve.py` module,
  `SolveResult` exported from `radiant.api`.
- `ErrorBudget` / `BudgetContributor` (Gaps 23+28): generic RSS error
  budget with allocation tracking, headroom queries, budget table, and
  dict round-trip — one model for jitter (µrad) and WFE (waves)
  budgets. Exported from `radiant.api`.
- Unit-aware parameter input (Gap 6): `ParameterSet.set(name, value,
  unit=...)` and `Sensor.set(dotpath, value, unit=...)` convert from the
  caller's native unit (cm, ms, %, min, …) at the set boundary. Bounds
  validated after conversion; original value+unit recorded in
  provenance. Omitting `unit=` keeps historical input-unit behavior —
  no result changes.
- `convert_spatial_frequency()` (Gap 27): cy/m ↔ cy/mm ↔ cy/mrad ↔
  cy/pixel conversion utility in the new
  `performance/frequency_units.py` module.
- PSF weighting spectrum override (Gap 17): `RadiantSession.run` gains an
  `extra_stage_outputs` injection argument;
  `optics_config["psf_weighting_spectrum"]` (SpectralData) decouples
  polychromatic PSF weighting from the scene spectrum. Radiometry is
  unaffected; weighting provenance recorded in
  `stage_outputs["optics"]["psf_weighting_source"]`. No default-behavior
  change.
- Electronics MTF (Gap 32): new `readout.electronics_sigma_um` parameter
  (default 0.0 = ideal electronics, no result change) models readout
  amplifier bandwidth as a Gaussian blur along the readout (x) axis.
  **Results-affecting only when set nonzero** — enters both the
  EffectivePSF and the MTF product per Rule 4, lowering x-axis MTF,
  RER, and NIIRS. New `readout/electronics_mtf.py` module and
  `mtf_electronics_x/_y` product terms.
- `giqe5_sensitivity()` (Gap 20): analytic d(NIIRS)/d(GSD, RER, SNR, H, G)
  partials and exact per-+1% deltas in the new
  `performance/giqe_sensitivity.py` module. Analysis utility only — no
  chain output changes.
- GIQE-5 calibration-range flagging (Gap 22): NIIRS results outside the
  published fit ranges (GSD 3–80 cm, RER 0.2–0.95, SNR 2–130) now carry
  `GIQEResult.extrapolated=True`, a `UserWarning`, and a new
  `niirs_extrapolated` metric (0.0/1.0). The NIIRS value itself is
  unchanged — flagging only. The prior ad-hoc low-end checks (SNR < 5,
  RER < 0.2) are replaced by the spec-based ranges, both ends.
- `optics.scalar_emissivity` parameter (default 0.0): declared effective
  emissivity of the lumped train in scalar transmission mode, enabling
  warm-optics nearfield emission from the simplest input mode (Gap 37).
  **Results-affecting only when set nonzero** — it adds nearfield background
  and shot noise (lower SNR, higher NEDT) for warm-optics MWIR/LWIR
  configurations; the default preserves all existing results (`ε = 0`,
  nearfield dark). `OpticalElement` gains a `declared_emissivity` field,
  legal only on `kind=LUMPED` pseudo-elements; `KirchhoffViolationError`
  on physical surfaces or when `ε + τ + R > 1`.
